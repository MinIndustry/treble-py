"""Envelope segments are read as (duration, level, control_time, control_level).

Every spec writer (ADSRSpec, the archetype sampler, treble-ml's tokenizer)
writes the tuples that way: a segment moves to `level` over `duration`
seconds, and its Bezier control point sits `control_time` seconds in.
"""
from __future__ import annotations

import numpy as np

from treble_py.treble_py import render_batch

SR = 44100
FLAT = {"attack": [0.001, 1.0, 0.0005, 1.0], "decay": [0.001, 1.0, 0.0005, 1.0],
        "sustain": 1.0, "release": [0.01, 0.0, 0.005, 0.0]}


def _render(envelope: dict, note_on: float = 0.1, note_off: float = 2.5) -> np.ndarray:
    spec = {"note": 69, "note_on": note_on, "note_off": note_off, "duration": 3.0,
            "sample_rate": float(SR), "block_size": 512,
            "sources": [{"sources": [{"waveform": "sine", "frequency_relation": "identity",
                                      "envelope": envelope}],
                         "base_frequency": 440.0, "mix_mode": "Sum", "glob_ampl": FLAT}],
            "filters": [], "connections": [{"SourceSink": {"source": 0, "sink": 0}}]}
    audio = np.asarray(render_batch([spec])[0], np.float64)
    return audio[:, 0] if audio.ndim == 2 else audio


def _level(audio: np.ndarray, t: float, width: float = 0.01) -> float:
    """Peak of the sine around time t: its envelope there."""
    a, b = int((t - width / 2) * SR), int((t + width / 2) * SR)
    return float(np.abs(audio[a:b]).max())


def _note_on(t: float = 0.1) -> float:
    return int(t * SR / 512) * 512 / SR            # notes start on a block


def test_decay_falls_to_its_level_over_its_duration():
    env = {"attack": [0.005, 1.0, 0.0025, 1.0], "decay": [0.4, 0.25, 0.2, 0.625],
           "sustain": 0.25, "release": [0.2, 0.0, 0.1, 0.125]}
    audio = _render(env)
    on = _note_on()
    peak = _level(audio, on + 0.006, 0.004)
    held = _level(audio, on + 1.5)
    assert abs(held / peak - 0.25) < 0.02
    # Still falling halfway through the decay: the duration is 0.4 s.
    mid = _level(audio, on + 0.005 + 0.2, 0.004) / peak
    assert 0.5 < mid < 0.75


def test_control_time_is_seconds_into_the_segment():
    """A control point halfway along in time and level makes a straight line,
    whatever the segment's duration."""
    for dur in (0.4, 1.6):
        env = {"attack": [0.005, 1.0, 0.0025, 1.0], "decay": [dur, 0.2, dur / 2, 0.6],
               "sustain": 0.2, "release": [0.2, 0.0, 0.1, 0.1]}
        audio = _render(env)
        on = _note_on()
        peak = _level(audio, on + 0.006, 0.004)
        quarter = _level(audio, on + 0.005 + dur / 4, 0.004) / peak
        assert abs(quarter - 0.8) < 0.03, (dur, quarter)


def test_release_falls_from_the_held_level():
    env = {"attack": [0.005, 1.0, 0.0025, 1.0], "decay": [0.1, 0.5, 0.05, 0.75],
           "sustain": 0.5, "release": [0.4, 0.0, 0.2, 0.25]}
    audio = _render(env, note_off=1.0)
    off = _note_on(1.0)
    peak = _level(audio, _note_on() + 0.006, 0.004)
    assert abs(_level(audio, off - 0.05) / peak - 0.5) < 0.02
    assert _level(audio, off + 0.6) / peak < 0.01
