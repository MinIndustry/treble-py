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
    import rustic_py
    import soundfile as sf

    audio = rustic_py.render({
        "note": 60, "note_on": 0.0, "note_off": 0.5, "duration": 0.7,
        "source": {"waveform": "sine", "attack": 0.01, "decay": 0.1,
                   "sustain": 0.8, "release": 0.2},
        "filters": [{"type": "lowpass", "params": {"cutoff_frequency": 2000.0}}],
    })
    # audio.shape == (N, 2), dtype float32
    sf.write("out.wav", audio, samplerate=44100)
    ```
    """
    ...

def available_filters() -> list[dict[str, Any]]:
    """Returns metadata for all registered filter types.

    Returns:
        list of dicts, each with keys: name, description, inputs, outputs.

    Example:

    ```python
    import rustic_py

    for f in rustic_py.available_filters():
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
    import rustic_py

    for s in rustic_py.available_sources():
        params = [p["name"] for p in s["parameters"]]
        print(f'{s["name"]}: {", ".join(params)}')
    # sine: attack, decay, sustain, release
    # square: attack, decay, sustain, release
    # ...
    ```
    """
    ...
