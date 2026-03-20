# rustic-py

Python bindings for the Rustic audio synthesis engine.

Rustic models audio synthesis as a directed graph: a **source** generates a waveform
and a chain of **filters** transforms it. The Python API exposes this through a small
set of dataclasses and two discovery functions.

## Quick start

```python
import rustic_py

# 1. Describe the sound
spec = rustic_py.GraphSpec(
    note=60,          # MIDI note (middle C)
    note_on=0.0,
    note_off=0.5,
    duration=0.7,
    source=rustic_py.SourceSpec(waveform="sine", attack=0.01, decay=0.1,
                                sustain=0.8, release=0.2),
    filters=[rustic_py.lowpass(cutoff_frequency=2000.0)],
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
| `SourceSpec` | Waveform generator + ADSR envelope |
| `available_filters()` | List metadata for every registered filter |
| `available_sources()` | List metadata for every registered waveform source |
| `render(spec_dict)` | Low-level render from a plain `dict` |

Filter classes (e.g. `lowpass`, `highpass`, `compressor`, …) are generated at import
time from `available_filters()` and injected into the `rustic_py` namespace. Each one
is a dataclass whose fields map directly to the filter's parameters.
