from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, make_dataclass
from typing import TYPE_CHECKING, Any
import numpy as np

import random
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
    param_specs = []
    for inp in inputs:
        if inp.get("parameter") is None:
            continue
        f = _field_spec(inp["parameter"])
        fields.append(f)
        param_names.append(f[0])
        (kind, data), = inp["parameter"].items()
        param_specs.append((kind, data))

    validator = _build_validator(inputs)

    def to_spec(self, _tid=type_id, _names=param_names) -> dict:
        return {'type': _tid, "params": {n: getattr(self, n) for n in _names}}

    namespace = {"to_spec": to_spec, "__doc__": info.get("description", "")}
    if validator is not None:
        namespace["__post_init__"] = validator

    cls = make_dataclass(type_id, fields, namespace=namespace)

    def _random(cls=cls, specs=param_specs):
        kwargs = {}
        for kind, data in specs:
            name = data["field_name"]
            if kind == "Toggle":
                kwargs[name] = random.choice([True, False])
            elif kind == "Range":
                default = float(data["default"])
                vmin = float(data["min"])
                vmax = float(data["max"])
                sigma = (vmax - vmin) / 6.0
                val = np.random.normal(loc=default, scale=sigma)
                kwargs[name] = float(np.clip(val, vmin, vmax))
            elif kind == "Float":
                default = float(data["default"])
                mu = np.log(default) if default > 0.0 else 0.0
                kwargs[name] = float(np.random.lognormal(mean=mu, sigma=0.3))
            elif kind == "Int":
                default = int(data["default"])
                vmin = data.get("min")
                vmax = data.get("max")
                if vmin is not None and vmax is not None:
                    sigma = (float(vmax) - float(vmin)) / 6.0
                    val = int(round(np.random.normal(loc=default, scale=sigma)))
                    kwargs[name] = int(np.clip(val, int(vmin), int(vmax)))
                else:
                    kwargs[name] = max(1, int(round(np.random.normal(
                        loc=default, scale=max(1.0, abs(default) * 0.3)
                    ))))
            elif kind == "List":
                kwargs[name] = []
        return cls(**kwargs)

    cls.random = staticmethod(_random)
    return cls


@dataclass
class ADSRSpec:
    # Each tuple: (duration, peak, control_time, control_peak) for Bezier curve
    attack:  tuple = (0.01, 1.0, 0.01, 0.0)
    decay:   tuple = (0.1,  0.8, 0.1,  1.0)
    sustain: float = 0.8
    release: tuple = (0.2,  0.0, 0.0,  0.0)

    def to_spec(self) -> dict[str, Any]:
        return {
            "attack":  list(self.attack),
            "decay":   list(self.decay),
            "sustain": self.sustain,
            "release": list(self.release),
        }

    @staticmethod
    def random() -> ADSRSpec:
        """Returns a random ADSR spec in believable ranges"""

        # Sustain is uniform over [0;1]
        sustain = np.random.uniform(0, 1)

        # Attack segment
        attack_duration = np.random.lognormal(mean=-1.2, sigma=0.5)
        attack_duration = max(0.001, min(attack_duration, 2.0))
        attack_peak = np.random.uniform(0.8, 1.0)  # Attack usually reaches near max
        # Control points for attack (time between 0 and duration, amplitude between 0 and peak)
        attack_c1_time = np.random.uniform(0, attack_duration)
        attack_c1_amp = np.random.uniform(0, attack_peak)
        # Keep in mind that a second point could be useful
        # attack_c2_time = np.random.uniform(attack_c1_time, attack_duration)
        # attack_c2_amp = np.random.uniform(attack_peak, 1.0

        # Decay segment
        decay_duration = np.random.lognormal(mean=-1.0, sigma=0.4)
        decay_duration = max(0.001, min(decay_duration, 3.0))
        decay_peak = sustain  # Decay ends at sustain level
        # Control points for decay
        decay_c1_time = np.random.uniform(0, decay_duration)
        decay_c1_amp = np.random.uniform(attack_peak, sustain)
        # decay_c2_time = np.random.uniform(decay_c1_time, decay_duration)
        # decay_c2_amp = np.random.uniform(sustain, attack_peak)

        # Release segment
        release_duration = np.random.lognormal(mean=-1.1, sigma=0.45)
        release_duration = max(0.001, min(release_duration, 4.0))
        release_peak = 0.0  # Release ends at 0
        # Control points for release
        release_c1_time = np.random.uniform(0, release_duration)
        release_c1_amp = np.random.uniform(sustain, 0)
        # release_c2_time = np.random.uniform(release_c1_time, release_duration)
        # release_c2_amp = np.random.uniform(0, sustain)

        return ADSRSpec(
            attack=(attack_duration, attack_peak, attack_c1_time, attack_c1_amp),
            decay=(decay_duration, decay_peak, decay_c1_time, decay_c1_amp),
            sustain=sustain,
            release=(release_duration, release_peak, release_c1_time, release_c1_amp)
        )

@dataclass
class SourceSpec:
    waveform: str = "sine"
    frequency_relation: str = "identity"
    envelope: ADSRSpec = field(default_factory=ADSRSpec)

    def __post_init__(self):
        valid = [s["type_id"] for s in available_sources()]
        if self.waveform not in valid:
            raise ValueError(f"waveform must be one of {valid!r}, got {self.waveform!r}")

    def to_spec(self) -> dict[str, Any]:
        return {
            "waveform": self.waveform,
            "frequency_relation": self.frequency_relation,
            "envelope": self.envelope.to_spec(),
        }

    @staticmethod
    def random(waveform_weights: dict[str, float] | None = None) -> SourceSpec:
        """Returns a random SourceSpec.

        Args:
            waveform_weights: mutable dict mapping waveform type_id → weight. Chosen waveforms
                have their weight multiplied by 0.25 in-place, so repeated calls naturally
                diversify across waveform types within the same spec. 'blank' is always excluded.
        """
        candidates = [s['type_id'] for s in available_sources() if s['type_id'] != 'blank']
        weights = [waveform_weights.get(wf, 1.0) for wf in candidates] if waveform_weights is not None else None
        waveform = random.choices(candidates, weights=weights, k=1)[0]
        if waveform_weights is not None:
            waveform_weights[waveform] = waveform_weights.get(waveform, 1.0) * 0.25

        return SourceSpec(
            waveform=waveform,
            envelope=ADSRSpec.random(),
            frequency_relation="identity",
        )


@dataclass
class MultiSourceSpec:
    sources: list
    base_frequency: float = 440.0
    mix_mode: str = "Average"  # "Sum" | "Average" | "Max" | "Min"
    glob_ampl: ADSRSpec = field(default_factory=ADSRSpec)

    def __post_init__(self):
        valid = {"Sum", "Average", "Max"}
        if self.mix_mode not in valid:
            raise ValueError(f"mix_mode must be one of {valid!r}, got {self.mix_mode!r}")

    def to_spec(self) -> dict[str, Any]:
        return {
            "sources": [s.to_spec() for s in self.sources],
            "base_frequency": self.base_frequency,
            "mix_mode": self.mix_mode,
            "glob_ampl": self.glob_ampl.to_spec(),
        }

    @staticmethod
    def random(
        n_sources: int | None = None,
        waveform_weights: dict[str, float] | None = None,
    ) -> MultiSourceSpec:
        if n_sources is None:
            n_sources = max(1, min(int(np.random.zipf(a=2)), 20))
        sources = [SourceSpec.random(waveform_weights=waveform_weights) for _ in range(n_sources)]
        mix_mode = random.choice(["Sum", "Average", "Max"])
        glob_ampl = ADSRSpec.random()

        return MultiSourceSpec(
            sources=sources,
            mix_mode=mix_mode,
            glob_ampl=glob_ampl,
        )


_CONN_TYPE_ORDER: dict[str, int] = {
    "SourceSink": 0, "SourceFilter": 1, "FilterFilter": 2, "FilterSink": 3
}


def _filter_sort_key(f: Any) -> tuple:
    spec = f.to_spec()
    type_id: str = spec["type"]
    params = spec.get("params", {})
    primary = float(list(params.values())[0]) if params else 0.0
    return (type_id, primary)


def _conn_sort_key(conn: dict) -> tuple:
    conn_type = next(iter(conn))
    data = conn[conn_type]
    order = _CONN_TYPE_ORDER.get(conn_type, 99)
    exit_idx = data.get("source", data.get("filter_out", data.get("filter", 0)))
    entry_idx = data.get("sink", data.get("filter", data.get("filter_in", 0)))
    return (order, exit_idx, entry_idx)


def _renumber_connections(connections: list, old_to_new: dict[int, int]) -> list:
    result = []
    for conn in connections:
        if "SourceSink" in conn:
            result.append(conn)
        elif "SourceFilter" in conn:
            d = conn["SourceFilter"]
            result.append({"SourceFilter": {"source": d["source"], "filter": old_to_new[d["filter"]]}})
        elif "FilterFilter" in conn:
            d = conn["FilterFilter"]
            result.append({"FilterFilter": {
                "filter_out": old_to_new[d["filter_out"]],
                "filter_in":  old_to_new[d["filter_in"]],
            }})
        elif "FilterSink" in conn:
            d = conn["FilterSink"]
            result.append({"FilterSink": {"filter": old_to_new[d["filter"]], "sink": d["sink"]}})
    return sorted(result, key=_conn_sort_key)


def _build_dag_connections(n_sources: int, n_filters: int, complexity: float) -> list:
    """Build a random DAG connection list for a synthesis graph.

    Guarantees no cycles: filter fi only receives edges from nodes with index < fi,
    so the filter processing order is always a valid topological sort.
    At low complexity (< 0.3) this degenerates to a strict linear chain.
    """
    if n_filters == 0:
        return [{"SourceSink": {"source": i, "sink": 0}} for i in range(n_sources)]

    connections = []
    filter_has_outgoing = [False] * n_filters
    source_connected: set[int] = set()

    max_extra_parents = max(0, round(2 * complexity))  # 0 at low, 2 at high

    for fi in range(n_filters):
        if complexity < 0.3 and n_filters > 1:
            # Strict linear chain
            if fi == 0:
                parents = [('s', si) for si in range(n_sources)]
            else:
                parents = [('f', fi - 1)]
        else:
            candidates = [('s', si) for si in range(n_sources)] + \
                         [('f', fj) for fj in range(fi)]
            n_parents = 1 + int(np.random.binomial(max_extra_parents, 0.5 + 0.3 * complexity))
            n_parents = min(n_parents, len(candidates))
            parents = random.sample(candidates, n_parents)

        for p_type, p_idx in parents:
            if p_type == 's':
                connections.append({"SourceFilter": {"source": p_idx, "filter": fi}})
                source_connected.add(p_idx)
            else:
                connections.append({"FilterFilter": {"filter_out": p_idx, "filter_in": fi}})
                filter_has_outgoing[p_idx] = True

    # Terminal filters (no outgoing edge) → sink
    for fi in range(n_filters):
        if not filter_has_outgoing[fi]:
            connections.append({"FilterSink": {"filter": fi, "sink": 0}})

    # Sources not feeding any filter → sink directly
    for si in range(n_sources):
        if si not in source_connected:
            connections.append({"SourceSink": {"source": si, "sink": 0}})

    return connections


@dataclass
class GraphSpec:
    note: int
    note_on: float
    note_off: float
    duration: float
    sources: list[MultiSourceSpec]
    filters: list = field(default_factory=list)
    connections: list = field(default_factory=list)
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
            "sources": [source.to_spec() for source in self.sources],
            "filters": [f.to_spec() for f in self.filters],
            "connections": self.connections,
        }

    def render(self) -> np.ndarray:
        from .rustic_py import render as _render
        return _render(self.to_spec())

    def canonical(self) -> GraphSpec:
        """Return a copy of this GraphSpec in canonical form.

        Canonical ordering eliminates sequence ambiguity so that cross-entropy
        training on token sequences converges to a single ordering per
        perceptual equivalence class rather than averaging over valid permutations.

        Rules applied in order:
          1. Sources within each MultiSourceSpec: sorted by (waveform, -sustain).
          2. MultiSourceSpec blocks: sorted by (-n_sources, dominant_wf, -glob_ampl.sustain).
          3. Filters: topological sort (signal path order); ties broken by type_id then
             primary parameter value. Filter indices in connections are renumbered.
          4. Connections: sorted by type (SourceSink < SourceFilter < FilterFilter <
             FilterSink), then exit index, then entry index.
        """
        # 1. Sort sources within each MultiSourceSpec
        def _source_key(s: SourceSpec) -> tuple:
            return (s.waveform, -s.envelope.sustain)

        canonical_multis = []
        for ms in self.sources:
            canonical_multis.append(MultiSourceSpec(
                sources=sorted(ms.sources, key=_source_key),
                base_frequency=ms.base_frequency,
                mix_mode=ms.mix_mode,
                glob_ampl=ms.glob_ampl,
            ))

        # 2. Sort MultiSourceSpec blocks
        def _ms_key(ms: MultiSourceSpec) -> tuple:
            wf_counts: dict[str, int] = {}
            for s in ms.sources:
                wf_counts[s.waveform] = wf_counts.get(s.waveform, 0) + 1
            dominant = min(wf_counts, key=lambda w: (-wf_counts[w], w))
            return (-len(ms.sources), dominant, -ms.glob_ampl.sustain)

        canonical_multis = sorted(canonical_multis, key=_ms_key)

        # 3. Topological sort of filters (Kahn's algorithm)
        n = len(self.filters)
        if n == 0:
            canonical_filters = []
            old_to_new: dict[int, int] = {}
        else:
            # Build predecessor and successor sets from FilterFilter connections
            preds: dict[int, set[int]] = {i: set() for i in range(n)}
            succs: dict[int, set[int]] = {i: set() for i in range(n)}
            for conn in self.connections:
                if "FilterFilter" in conn:
                    fo = conn["FilterFilter"]["filter_out"]
                    fi = conn["FilterFilter"]["filter_in"]
                    preds[fi].add(fo)
                    succs[fo].add(fi)

            in_degree = {i: len(preds[i]) for i in range(n)}
            ready = sorted(
                [i for i in range(n) if in_degree[i] == 0],
                key=lambda i: _filter_sort_key(self.filters[i]),
            )
            topo: list[int] = []
            while ready:
                node = ready.pop(0)
                topo.append(node)
                newly_ready = []
                for succ in succs[node]:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        newly_ready.append(succ)
                newly_ready.sort(key=lambda i: _filter_sort_key(self.filters[i]))
                ready = sorted(ready + newly_ready, key=lambda i: _filter_sort_key(self.filters[i]))

            old_to_new = {old: new for new, old in enumerate(topo)}
            canonical_filters = [self.filters[old] for old in topo]

        # 4. Renumber and sort connections
        if old_to_new:
            canonical_connections = _renumber_connections(self.connections, old_to_new)
        else:
            canonical_connections = sorted(self.connections, key=_conn_sort_key)

        return GraphSpec(
            note=self.note,
            note_on=self.note_on,
            note_off=self.note_off,
            duration=self.duration,
            sources=canonical_multis,
            filters=canonical_filters,
            connections=canonical_connections,
            sample_rate=self.sample_rate,
            block_size=self.block_size,
        )

    @staticmethod
    def random(complexity: float = 0.5) -> GraphSpec:
        """Generate a random but believable GraphSpec.

        Args:
            complexity: Float in [0.0, 1.0].
                0.0 → 1 source, 0–2 filters, linear chain.
                1.0 → up to 10 sources, 10–20 filters, branching DAG.
        """
        complexity = float(np.clip(complexity, 0.0, 1.0))

        # MIDI note: truncated normal around C4 (60), clamped to piano range [21, 108]
        note = int(np.clip(round(np.random.normal(loc=60, scale=12)), 21, 108))

        note_on = float(np.clip(np.random.lognormal(mean=0.0, sigma=0.5), 0.1, 8.0))
        note_duration = float(np.clip(np.random.lognormal(mean=0.0, sigma=0.5), 0.1, 8.0))
        note_off = note_on + note_duration

        max_graph_sources = max(1, int(1 + 4 * complexity))
        graph_zipf_a = max(1.5, 4.0 - 2.5 * complexity)
        n_graph_sources = int(np.clip(np.random.zipf(a=graph_zipf_a), 1, max_graph_sources))
        
        sources = []
        waveform_weights: dict[str, float] = {}
        # Source count: Zipf with a shaped by complexity (lower a → heavier tail)
        for _ in range(n_graph_sources):
            max_sources = max(2, int(2 + 8 * complexity))
            zipf_a = max(1.1, 3.0 - 2.0 * complexity)
            n_sources = int(np.clip(np.random.zipf(a=zipf_a), 1, max_sources))
            sources.append(MultiSourceSpec.random(n_sources=n_sources, waveform_weights=waveform_weights))

        # Duration includes the release tail from the global envelope
        release_tail = max([source.glob_ampl.release[0] for source in sources])
        duration = note_off + max(0.1, release_tail)

        # Filter count: 0–2 at low complexity, 10–20 at high complexity
        filter_mean = complexity * 15.0
        n_filters = max(0, int(round(np.random.normal(
            loc=filter_mean, scale=1.5 + complexity * 2.0
        ))))
        n_filters = min(n_filters, 25)

        filters = []
        if n_filters > 0 and filter_classes:
            chosen_types = random.choices(list(filter_classes.values()), k=n_filters)
            filters = [cls.random() for cls in chosen_types]

        connections = _build_dag_connections(n_graph_sources, len(filters), complexity)

        return GraphSpec(
            note=note,
            note_on=note_on,
            note_off=note_off,
            duration=duration,
            sources=sources,
            filters=filters,
            connections=connections,
            sample_rate=44100.0,
            block_size=512,
        )

filter_classes: dict[str, type] = {}

for _info in available_filters():
    _cls = _make_filter_class(_info)
    filter_classes[_info["type_id"]] = _cls
    globals()[_cls.__name__] = _cls
