from typing import Any
import numpy as np

def render(spec_dict: dict[str, Any]) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]:
    """Render a synthesis graph spec to stereo audio.

    Args:
        spec_dict: Python dict conforming to the GraphSpec format.

    Returns:
        numpy.ndarray of shape (N_samples, 2), dtype float32.

    Example:

    ```python
    import treble_py
    import soundfile as sf

    audio = treble_py.render({
        "note": 60, "note_on": 0.0, "note_off": 0.5, "duration": 0.7,
        "sources": [{"sources": [{"waveform": "sine"}], "base_frequency": 440.0}],
        "filters": [{"type": "LowPassFilter", "params": {"cutoff_frequency": 2000.0}}],
        "connections": [{"SourceFilter": {"source": 0, "filter": 0}},
                        {"FilterSink": {"filter": 0, "sink": 0}}],
    })
    # audio.shape == (N, 2), dtype float32
    sf.write("out.wav", audio, samplerate=44100)
    ```
    """
    ...

def render_batch(
    spec_dicts: list[dict[str, Any]],
) -> list[np.ndarray[tuple[int, int], np.dtype[np.float32]]]:
    """Render many synthesis graph specs in parallel.

    The GIL is released and specs are rendered across a rayon thread pool.
    Order is preserved.

    Args:
        spec_dicts: list of GraphSpec dicts (same format as ``render``).

    Returns:
        list of numpy.ndarray, each of shape (N_samples, 2), dtype float32.
    """
    ...

def available_filters() -> list[dict[str, Any]]:
    """Returns metadata for all registered filter types.

    Returns:
        list of dicts, each with keys: name, description, inputs, outputs.

    Example:

    ```python
    import treble_py

    for f in treble_py.available_filters():
        print(f["name"], "-", f["description"])
    # lowpass - A simple lowpass filter
    # highpass - A simple highpass filter
    # ...
    ```
    """
    ...

def available_sources() -> list[dict[str, Any]]:
    """Returns metadata for all available source (generator/waveform) types.

    Returns:
        list of dicts, each with keys: name, type_id, description, parameters, output_count.

    Example:

    ```python
    import treble_py

    for s in treble_py.available_sources():
        params = [p["name"] for p in s["parameters"]]
        print(f'{s["name"]}: {", ".join(params)}')
    # sine: attack, decay, sustain, release
    # square: attack, decay, sustain, release
    # ...
    ```
    """
    ...
