"""The archetype sampler behind `GraphSpec.random()`."""
from __future__ import annotations

import numpy as np
import pytest

import treble_py
from treble_py import ARCHETYPES, GraphSpec


def _envelopes(spec: GraphSpec):
    for block in spec.sources:
        yield block.glob_ampl
        for voice in block.sources:
            yield voice.envelope


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_archetype_patches_render_sound(archetype):
    rng = np.random.default_rng(42)
    for complexity in (0.0, 0.5, 1.0):
        for _ in range(15):
            spec = GraphSpec.random(complexity, archetype=archetype, rng=rng)
            audio = spec.render()
            assert np.isfinite(audio).all()
            peak = float(np.abs(audio).max())
            assert 1e-3 < peak < 4.0, (archetype, peak)
            assert all("sample_rate" not in f.to_spec()["params"] for f in spec.filters)


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_envelopes_complete_inside_the_note_and_the_render(archetype):
    rng = np.random.default_rng(7)
    for _ in range(40):
        spec = GraphSpec.random(rng.uniform(), archetype=archetype, rng=rng)
        held = spec.note_off - spec.note_on
        assert 0.0 <= spec.note_on <= 0.1
        for env in _envelopes(spec):
            assert env.attack[0] + env.decay[0] <= held + 1e-9
            assert spec.note_off + env.release[0] <= spec.duration


def test_note_ranges_and_cutoffs_follow_the_archetype():
    rng = np.random.default_rng(3)
    for _ in range(60):
        bass = GraphSpec.random(0.5, archetype="bass", rng=rng)
        assert 28 <= bass.note <= 52
        lowpass = [f for f in bass.filters if type(f).__name__ == "LowPassFilter"]
        assert len(lowpass) == 1
        f0 = 440.0 * 2.0 ** ((bass.note - 69) / 12.0)
        assert 2.0 * f0 * 0.999 <= lowpass[0].cutoff_frequency <= 12.0 * f0 * 1.001


def test_complexity_adds_voices_and_stages():
    rng = np.random.default_rng(11)
    def mean_size(c):
        specs = [GraphSpec.random(c, archetype="pad", rng=rng) for _ in range(80)]
        voices = np.mean([sum(len(b.sources) for b in s.sources) for s in specs])
        stages = np.mean([len(s.filters) for s in specs])
        return voices, stages
    v0, s0 = mean_size(0.0)
    v1, s1 = mean_size(1.0)
    assert v1 > v0 and s1 > s0


def test_unrequested_archetypes_follow_their_weights():
    rng = np.random.default_rng(5)
    seen = {GraphSpec.random(rng=rng).note for _ in range(200)}
    assert len(seen) > 30  # many archetypes, many registers


def test_same_seed_same_patch():
    a = GraphSpec.random(0.7, rng=np.random.default_rng(99))
    b = GraphSpec.random(0.7, rng=np.random.default_rng(99))
    assert a.to_spec() == b.to_spec()


def test_global_numpy_seed_applies_without_rng():
    np.random.seed(123)
    a = GraphSpec.random(0.5).to_spec()
    np.random.seed(123)
    b = GraphSpec.random(0.5).to_spec()
    assert a == b


def test_unknown_archetype_is_rejected():
    with pytest.raises(ValueError):
        GraphSpec.random(archetype="kazoo")


def test_random_uniform_keeps_the_previous_sampler():
    np.random.seed(0)
    spec = GraphSpec.random_uniform(1.0)
    assert spec.render().shape[1] == 2


def test_budgeted_adsr_fits_the_note():
    rng = np.random.default_rng(1)
    for _ in range(500):
        env = treble_py.ADSRSpec.random(note_len=0.6, tail=0.5, rng=rng)
        assert env.attack[0] + env.decay[0] <= 0.6 * 0.8 + 1e-9
        assert env.release[0] <= 0.5


def test_canonical_renumbers_source_blocks():
    """Two blocks wired to different chains must keep their wiring when reordered."""
    S = treble_py.SourceSpec
    M = treble_py.MultiSourceSpec
    one = M(sources=[S(waveform="sine")])
    three = M(sources=[S(waveform="saw"), S(waveform="saw"), S(waveform="saw")])
    spec = GraphSpec(
        note=60, note_on=0.0, note_off=0.4, duration=0.6,
        sources=[one, three],  # canonical order puts the 3-voice block first
        filters=[treble_py.LowPassFilter(cutoff_frequency=200.0), treble_py.HighPassFilter(cutoff_frequency=4000.0)],
        connections=[
            {"SourceFilter": {"source": 0, "filter": 0}},
            {"SourceFilter": {"source": 1, "filter": 1}},
            {"FilterSink": {"filter": 0, "sink": 0}},
            {"FilterSink": {"filter": 1, "sink": 0}},
        ],
    )
    canon = spec.canonical()
    assert len(canon.sources[0].sources) == 3
    np.testing.assert_allclose(canon.render(), spec.render(), atol=1e-6)


def test_parallel_outputs_are_mixed_at_the_sink():
    S, M = treble_py.SourceSpec, treble_py.MultiSourceSpec
    def render(*to_sink):
        conns = [{"SourceFilter": {"source": i, "filter": i}} for i in (0, 1)]
        conns += [{"FilterSink": {"filter": f, "sink": 0}} for f in to_sink]
        return GraphSpec(
            note=60, note_on=0.0, note_off=0.4, duration=0.6,
            sources=[M(sources=[S(waveform="sine")]), M(sources=[S(waveform="saw")])],
            filters=[treble_py.GainFilter(factor=1.0), treble_py.GainFilter(factor=1.0)],
            connections=conns,
        ).render()
    a, b = render(0), render(1)
    assert np.abs(a - b).max() > 1e-3
    np.testing.assert_allclose(render(0, 1), a + b, atol=1e-6)
