"""Behaviour of the generated spec classes and their random samplers.

Run after building the extension: `maturin develop && pytest tests`.
"""
from __future__ import annotations

import math
import random
from collections import Counter

import numpy as np
import pytest

import treble_py
from treble_py import GraphSpec, SourceSpec, available_filters, filter_classes


@pytest.fixture(autouse=True)
def _seed():
    random.seed(1234)
    np.random.seed(1234)


def _params(info: dict) -> list[tuple[dict, str, str | None]]:
    out = []
    for inp in info["inputs"]:
        if inp.get("parameter") is not None:
            (_, data), = inp["parameter"].items()
            out.append((data, inp["access"], inp["scale"]))
    return out


def test_metadata_exposes_access_and_scale():
    for info in available_filters():
        for inp in info["inputs"]:
            assert inp["access"] in ("user", "engine")
            assert inp["scale"] in (None, "linear", "logarithmic")


def test_engine_owned_parameters_are_not_fields():
    seen_engine = 0
    for info in available_filters():
        fields = filter_classes[info["type_id"]].__dataclass_fields__
        for data, access, _ in _params(info):
            if access == "engine":
                seen_engine += 1
                assert data["field_name"] not in fields
            else:
                assert data["field_name"] in fields
    assert seen_engine == 9  # sample_rate on the nine rate-dependent filters


def test_engine_owned_parameters_are_rejected_as_kwargs():
    with pytest.raises(TypeError):
        treble_py.LowPassFilter(cutoff_frequency=1000.0, sample_rate=8000.0)
    assert "sample_rate" not in treble_py.LowPassFilter().to_spec()["params"]


def test_random_filters_stay_in_declared_ranges():
    for info in available_filters():
        cls = filter_classes[info["type_id"]]
        for _ in range(200):
            inst = cls.random()
            for data, access, _ in _params(info):
                if access == "engine":
                    continue
                lo, hi = data.get("min"), data.get("max")
                val = getattr(inst, data["field_name"])
                if lo is not None:
                    assert val >= lo, (info["type_id"], data["field_name"], val)
                if hi is not None:
                    assert val <= hi, (info["type_id"], data["field_name"], val)


def test_logarithmic_parameters_are_centred_on_their_default_in_log_space():
    cutoffs = [treble_py.LowPassFilter.random().cutoff_frequency for _ in range(4000)]
    assert 700 < float(np.median(cutoffs)) < 1400  # default 1000 Hz
    sizes = [treble_py.MovingAverage.random().size for _ in range(4000)]
    assert np.median(sizes) == 3
    assert np.percentile(sizes, 95) < 100


def test_gain_prior_is_a_gentle_lognormal_around_unity():
    gains = np.array([treble_py.GainFilter.random().factor for _ in range(4000)])
    assert (gains > 0).all()
    assert 0.9 < float(np.median(gains)) < 1.1
    assert float(np.std(np.log(gains))) == pytest.approx(0.3, abs=0.03)


def test_random_sources_cover_all_frequency_relations():
    from treble_py._classes import RELATION_WEIGHTS

    n = 6000
    kinds = Counter()
    for _ in range(n):
        rel = SourceSpec.random().frequency_relation
        kinds["identity" if rel == "identity" else next(iter(rel))] += 1
    assert set(kinds) == set(RELATION_WEIGHTS)
    for kind, weight in RELATION_WEIGHTS.items():
        assert kinds[kind] / n == pytest.approx(weight, abs=0.025), kind


@pytest.mark.parametrize("rel", [
    "identity", "ratio:2", "harmonic:3", "semitones:-7", "offset:12.5", "constant:440",
    {"ratio": 1.5}, {"harmonic": 2}, {"semitones": 7}, {"offset": -3.0}, {"constant": 220.0},
])
def test_valid_frequency_relations_are_accepted(rel):
    spec = SourceSpec(frequency_relation=rel)
    assert spec.to_spec()["frequency_relation"] == rel


@pytest.mark.parametrize("rel", [
    "fifth", "ratio:", "ratio:abc", {"ratio": 2.0, "offset": 1.0}, {"detune": 1.0},
    {"ratio": float("nan")}, {"harmonic": True}, 3,
])
def test_invalid_frequency_relations_are_rejected(rel):
    with pytest.raises(ValueError):
        SourceSpec(frequency_relation=rel)


def _render_one_source(rel) -> np.ndarray:
    spec = GraphSpec(
        note=57, note_on=0.0, note_off=0.5, duration=0.5,
        sources=[treble_py.MultiSourceSpec(sources=[SourceSpec(frequency_relation=rel)])],
        connections=[{"SourceSink": {"source": 0, "sink": 0}}],
    )
    return spec.render()[:, 0]


def _dominant_hz(audio: np.ndarray, sr: float = 44100.0) -> float:
    seg = audio[2048:2048 + 16384] * np.hanning(16384)
    spectrum = np.abs(np.fft.rfft(seg))
    return float(np.argmax(spectrum) * sr / 16384)


def test_string_and_dict_relations_render_identically():
    for s, d in [("ratio:2", {"ratio": 2.0}), ("constant:440", {"constant": 440.0})]:
        np.testing.assert_array_equal(_render_one_source(s), _render_one_source(d))
    assert _dominant_hz(_render_one_source({"constant": 440.0})) == pytest.approx(440.0, abs=5.0)


def test_random_graph_specs_render_finite_audio():
    for complexity in (0.0, 0.25, 0.5, 1.0):
        spec = GraphSpec.random(complexity)
        audio = spec.render()
        assert audio.ndim == 2 and audio.shape[1] == 2
        assert audio.shape[0] == math.ceil(spec.duration * spec.sample_rate)
        assert all("sample_rate" not in f.to_spec()["params"] for f in spec.filters)
