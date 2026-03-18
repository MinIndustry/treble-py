# Rustic-py

Python bindings for rustic, built with [maturin](https://github.com/PyO3/maturin).

## Installation in the dev workspace

The `dev` workspace references `rustic-py` as an editable path dependency. To build and install it:

```bash
cd dev
uv sync
```

`uv` will automatically invoke `maturin` to compile the Rust extension and install it into the workspace's virtual environment.

To rebuild after making changes to the Rust code:

```bash
cd dev
uv sync --reinstall-package rustic-py
```
