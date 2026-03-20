from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, make_dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

from .rustic_py import available_filters, available_sources

# Helpers
def _field_spec(params: dict[str, dict]) -> tuple[str, type, Any]:
    """Convert one ParameterDict into make_dataclass 3 field tuple"""
    (kind, data), = params.items()
    name = data["field_name"]
    if kind == "Toggle":
        return (name, bool, field(default=bool(data["default"])))
    elif kind == "Range":
        return (name, float, field(default=float(data["default"])))
    elif kind == "Float":
        return (name, float, field(default=float(data["default"])))
    elif kind == "Int":
        return (name, int, field(default=int(data["default"])))
    elif kind == "List":
        return (name, list, field(default_factory=list))
    else:
        raise ValueError(f"Unknown parameter kind: {kind!r}")


def _build_validator(inputs: list[dict]) -> Callable[..., None] | None:
    """Returns a __post_init__ to validate ranges/int bounds"""
    checks = []
    for inp in inputs:
        p = inp.get("parameter")
        if p is None:
            continue
        (kind, data), = p.items()
        if kind == "Range":
            checks.append((data["field_name"], float(data["min"]), float(data["max"])))
        elif kind == "Int":
            vmin = data.get("min")
            vmax = data.get("max")
            if vmin is not None or vmax is not None:
                checks.append((data["field_name"], vmin, vmax))

    if not checks:
        return None

    def __post_init__(self, _checks=checks):
        for name, vmin, vmax in _checks:
            val = getattr(self, name)
            if vmin is not None and val < vmin:
                raise ValueError(f"{name}={val!r} must be >= {vmin}")

            if vmax is not None and val > vmax:
                raise ValueError(f"{name}={val!r} must be <= {vmax}")

    return __post_init__

def _make_filter_class(info: dict[str, Any]) -> type:
    """Generates a dataclass from a FilterInfo dict"""
    type_id = info["type_id"]
    inputs = info["inputs"]
    
    fields = []
    param_names = []
    for inp in inputs:
        if inp.get("parameter") is None:
            continue
        f = _field_spec(inp["parameter"])
        fields.append(f)
        param_names.append(f[0])

    validator = _build_validator(inputs)
    
    def to_spec(self, _tid=type_id, _names=param_names) -> dict:
        return {'type': _tid, "params": {n: getattr(self, n) for n in _names}}

    namespace = {"to_spec": to_spec, "__doc__": info.get("description", "")}
    if validator is not None:
        namespace["__post_init__"] = validator

    return make_dataclass(type_id, fields, namespace=namespace)


@dataclass
class SourceSpec:
    waveform: str = "sine"
    frequency_relation: str = "identity"
    attack: float = 0.01
    decay: float = 0.01
    sustain: float = 0.08
    release: float = 0.03

    def __post_init__(self):
        valid = [s["type_id"] for s in available_sources()]
        if self.waveform not in valid:
            raise ValueError(f"waveform must be one of {valid!r}, got {self.waveform!r}")
        if not (0.0 <= self.sustain <= 1.0):
            raise ValueError(f"sustain={self.sustain!r} must be in [0.0, 1.0]")
        for name, val in [("attack", self.attack), ("decay", self.decay), ("release", self.release)]:
            if val < 0.001:
                raise ValueError(f"{name}={val!r} must be >= 0.001")

    def to_spec(self) -> dict[str, Any]:
        return {
            "waveform": self.waveform,
            "frequency_relation": self.frequency_relation,
            "attack": self.attack,
            "decay": self.decay,
            "sustain": self.sustain,
            "release": self.release,
        }


@dataclass
class GraphSpec:
    note: int
    note_on: float
    note_off: float
    duration: float
    source: SourceSpec
    filters: list = field(default_factory=list)
    sample_rate: float = 44100.0
    block_size: int = 512

    def __post_init__(self):
        if not (0 <= self.note <= 127):
            raise ValueError(f"note must be 0–127, got {self.note!r}")
        if self.note_on < 0:
            raise ValueError(f"note_on must be >= 0")
        if self.note_off < self.note_on:
            raise ValueError(f"note_off={self.note_off!r} must be >= note_on={self.note_on!r}")
        if self.duration < self.note_off:
            raise ValueError(f"duration={self.duration!r} must be >= note_off={self.note_off!r}")

    def to_spec(self) -> dict[str, Any]:
        return {
            "note": self.note,
            "note_on": self.note_on,
            "note_off": self.note_off,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "block_size": self.block_size,
            "source": self.source.to_spec(),
            "filters": [f.to_spec() for f in self.filters],
        }

    def render(self) -> np.ndarray:
        from .rustic_py import render as _render
        return _render(self.to_spec())


filter_classes: dict[str, type] = {}

for _info in available_filters():
    _cls = _make_filter_class(_info)
    filter_classes[_info["type_id"]] = _cls
    globals()[_cls.__name__] = _cls
