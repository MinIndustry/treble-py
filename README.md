# Treble-py

Python bindings for treble, built with [maturin](https://github.com/PyO3/maturin).

Exposes offline headless rendering of `GraphSpec` synthesis graphs to numpy arrays:

- `render(spec_dict)` — render one spec to a stereo `(N, 2)` float32 array
- `render_batch(spec_dicts)` — render many specs in parallel on a rayon thread
  pool (the GIL is released; order is preserved)
- `GraphSpec` / `MultiSourceSpec` / `SourceSpec` / `ADSRSpec` dataclasses, with
  `GraphSpec.random()`, `.canonical()`, `.render()`, and `GraphSpec.render_batch()`
- `available_filters()` / `available_sources()` — live registry metadata

## Installation in the treble-ml workspace

The [treble-ml](https://github.com/MinIndustry/treble-ml) workspace references
`treble-py` as an editable path dependency (`../treble-py`). To build and install it:

```bash
cd ../treble-ml
uv sync
```

`uv` will automatically invoke `maturin` to compile the Rust extension and install it into the workspace's virtual environment.

To rebuild after making changes to the Rust code:

```bash
cd ../treble-ml
uv sync --reinstall-package treble-py
```

## Native tests

The `extension-module` pyo3 feature is only enabled by maturin at wheel-build
time (see `pyproject.toml`), so plain `cargo test` links against libpython and
works out of the box.
