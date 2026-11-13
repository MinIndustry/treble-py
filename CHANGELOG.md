# Changelog

## 0.4.0

- Build against crates.io `treble` 0.6.0 and `treble-meta` 0.4.0 instead of git
  tags (`treble-core` 0.3.0 / `treble-meta` 0.2.0). Renders reflect the core DSP
  changes between those versions; `HighPassFilter` and `LowPassFilter` gain a
  `resonance` parameter.
- `available_filters()` inputs now carry `access` (`"user"` | `"engine"`) and
  `scale` (`"linear"` | `"logarithmic"` | `None`).
- Engine-owned parameters (`sample_rate`) are set by the renderer only. A spec
  value for them is ignored; previously it overrode the render rate and detuned
  rate-dependent filters.
- Breaking: generated filter classes no longer have engine-owned fields, so
  `LowPassFilter(sample_rate=...)` raises `TypeError`, and `to_spec()` / `random()`
  omit them.
- Filter `random()` draws logarithmic parameters in log space around their
  default. `GainFilter.factor` keeps a lognormal(0, 0.3) prior around unity
  despite its declared -16..16 range.
- `SourceSpec.random()` samples all six frequency relations (identity 45%,
  ratio 15%, semitones 15%, harmonic 10%, offset 10%, constant 5%) via the new
  `random_frequency_relation()`; it previously always returned `"identity"`.
- `SourceSpec.frequency_relation` accepts `"identity"`, `"<kind>:<value>"` or a
  single-key dict, and is validated. The renderer now parses `"constant:<hz>"`.
- Add a pytest suite (`tests/`) and a CI job that builds the extension and runs it.
