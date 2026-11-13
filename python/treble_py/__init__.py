"""
treble-py — Python bindings for the Treble audio synthesis engine.

Treble models audio synthesis as a directed graph: a **source** generates a waveform
and a chain of **filters** transforms it.  The Python API exposes this through a small
set of dataclasses and two discovery functions.

## Quick start

```python
import treble_py

# 1. Describe the sound
spec = treble_py.GraphSpec(
    note=60,          # MIDI note (middle C)
    note_on=0.0,
    note_off=0.5,
    duration=0.7,
    sources=[treble_py.MultiSourceSpec(
        sources=[treble_py.SourceSpec(waveform="sine")],
        base_frequency=440.0,
    )],
    filters=[treble_py.LowPassFilter(cutoff_frequency=2000.0)],
    connections=[{"SourceFilter": {"source": 0, "filter": 0}},
                 {"FilterSink": {"filter": 0, "sink": 0}}],
)

# 2. Render to a (N, 2) float32 numpy array
audio = spec.render()

# 3. Save
import soundfile as sf
sf.write("out.wav", audio, samplerate=44100)
```

## API overview

| Symbol | Description |
|---|---|
| `GraphSpec` | Top-level render spec (note, timing, source, filter chain) |
| `MultiSourceSpec` | Combines multiple `SourceSpec` voices with a shared envelope |
| `SourceSpec` | Single waveform generator with its own ADSR envelope |
| `ADSRSpec` | Bezier-curve ADSR envelope (attack/decay/release are 4-tuples) |
| `available_filters()` | List metadata for every registered filter |
| `available_sources()` | List metadata for every registered waveform source |
| `render(spec_dict)` | Low-level render from a plain `dict` |
| `render_batch(spec_dicts)` | Parallel render of many `dict` specs (GIL released) |

Filter classes (e.g. `LowPassFilter`, `HighPassFilter`, `Compressor`, …) are generated
at import time from `available_filters()` and injected into this namespace.  Each one
is a dataclass whose fields map directly to the filter's user parameters; engine-owned
parameters such as `sample_rate` are set by the renderer and are not fields.
"""
from ._classes import (
    ADSRSpec,
    GraphSpec,
    MultiSourceSpec,
    SourceSpec,
    filter_classes,
    random_frequency_relation,
)
from .treble_py import render, render_batch, available_filters, available_sources
import sys as _sys

# Re-export filters
_mod = _sys.modules[__name__]
for _type_id, _cls in filter_classes.items():
    setattr(_mod, _cls.__name__, _cls)

