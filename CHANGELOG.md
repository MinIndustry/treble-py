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
- `GraphSpec.random()` now draws realistic patches from sound-design archetypes
  (`ARCHETYPES`: bass, lead, pad, keys, bell, percussive), each with priors over
  note range, voices and frequency relations, amplitude envelope and effect
  chain. Envelopes complete inside the held note, cutoffs follow the note's
  pitch, chains follow signal flow, time effects can run as parallel sends, and
  the duration covers every release and effect tail. New keyword arguments
  `archetype=` and `rng=`. The previous sampler is `GraphSpec.random_uniform()`.
- `ADSRSpec.random(note_len=, tail=, rng=)` draws an envelope inside a note
  budget; without arguments it behaves as before.
- Fix: the renderer summed nothing at the sink. With several sources or
  terminal filters wired to it, their blocks were appended one after another
  in time and then truncated, instead of mixed. A summing sink replaces
  `SimpleSink`. This affected most `random_uniform()` patches at complexity
  0.5 and above.
- Fix: `GraphSpec.canonical()` reordered source blocks without renumbering the
  source indices in connections, silently rewiring multi-block patches.
- Add a pytest suite (`tests/`) and a CI job that builds the extension and runs it.
