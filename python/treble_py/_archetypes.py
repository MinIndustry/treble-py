"""Archetype-based patch sampler behind `GraphSpec.random()`.

A uniformly random graph rarely sounds like an instrument. Real patches follow
sound-design conventions: a bass has a resonant low-pass placed relative to its
pitch, a pad swells in slowly and sits in reverb, a bell is a stack of
inharmonic partials whose higher modes die first. This module samples from a
small set of such archetypes, each with its own priors over note range, voices,
frequency relations, envelope shape and effect chain.

Two invariants hold for every patch:

* **Envelopes fit the note.** Attack and decay are drawn inside the held
  note, and the render lasts until every release (and any delay or reverb
  tail) has finished.
* **Chains follow signal flow.** Stages are ordered tone shaping -> drive ->
  dynamics -> modulation -> time/space. Time effects are either inserted in the
  chain or, at higher complexity, fed as a parallel send.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Archetype names accepted by `GraphSpec.random(archetype=...)`.
ARCHETYPES: tuple[str, ...] = ("bass", "lead", "pad", "keys", "bell", "percussive")

#: Relative frequency of each archetype when none is requested.
ARCHETYPE_WEIGHTS: dict[str, float] = {
    "bass": 0.2, "lead": 0.2, "pad": 0.15, "keys": 0.2, "bell": 0.1, "percussive": 0.15,
}

NOTE_ON = 0.05
_NYQUIST_SAFE = 18000.0


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _log_uniform(rng: np.random.Generator, lo: float, hi: float) -> float:
    return float(math.exp(rng.uniform(math.log(lo), math.log(hi))))


def _chance(rng: np.random.Generator, p: float) -> bool:
    return bool(rng.random() < min(max(p, 0.0), 1.0))


def _hz(note: int) -> float:
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def _cutoff(rng: np.random.Generator, f0: float, lo: float, hi: float) -> float:
    """A cutoff placed `lo..hi` times the fundamental (log-uniform), clamped to audio range."""
    return float(np.clip(f0 * _log_uniform(rng, lo, hi), 20.0, _NYQUIST_SAFE))


def _detune(rng: np.random.Generator, lo_cents: float, hi_cents: float) -> dict[str, float]:
    cents = rng.uniform(lo_cents, hi_cents) * rng.choice([-1.0, 1.0])
    return {"ratio": float(2.0 ** (cents / 1200.0))}


# --------------------------------------------------------------------------
# Envelopes
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EnvelopeShape:
    """Priors for one amplitude envelope, in seconds (log-uniform) and levels."""
    attack: tuple[float, float]
    decay: tuple[float, float]
    sustain: tuple[float, float]
    release: tuple[float, float]


def budget_envelope(
    rng: np.random.Generator,
    shape: EnvelopeShape,
    note_len: float,
    *,
    decay_scale: float = 1.0,
    min_release: float = 0.0,
):
    """Draw an `ADSRSpec` from `shape` whose attack + decay complete inside the note.

    If the drawn attack + decay exceed 90% of the held note, both are scaled
    down together, preserving their ratio. `min_release` lets a voice envelope
    outlast the block envelope it sits under.
    """
    from ._classes import ADSRSpec

    atk = _log_uniform(rng, *shape.attack)
    dcy = _log_uniform(rng, *shape.decay) * decay_scale
    budget = 0.9 * note_len
    if atk + dcy > budget:
        k = budget / (atk + dcy)
        atk, dcy = atk * k, dcy * k
    atk, dcy = max(atk, 0.001), max(dcy, 0.001)
    rel = max(_log_uniform(rng, *shape.release), min_release, 0.001)

    peak = float(rng.uniform(0.85, 1.0))
    sustain = float(min(rng.uniform(*shape.sustain), peak))
    # Bezier control points: attacks bow upward, decays and releases fall
    # quickly first (exponential-like), as acoustic and analogue envelopes do.
    atk_ct, atk_cp = atk * rng.uniform(0.2, 0.6), peak * rng.uniform(0.5, 0.95)
    dcy_ct, dcy_cp = dcy * rng.uniform(0.1, 0.5), sustain + (peak - sustain) * rng.uniform(0.0, 0.35)
    rel_ct, rel_cp = rel * rng.uniform(0.1, 0.5), sustain * rng.uniform(0.0, 0.35)
    return ADSRSpec(
        attack=(atk, peak, float(atk_ct), float(atk_cp)),
        decay=(dcy, sustain, float(dcy_ct), float(dcy_cp)),
        sustain=sustain,
        release=(rel, 0.0, float(rel_ct), float(rel_cp)),
    )


#: A voice that leaves amplitude shaping to its block's global envelope.
OPEN_VOICE = EnvelopeShape(attack=(0.001, 0.005), decay=(0.01, 0.05), sustain=(0.9, 1.0), release=(0.01, 0.02))


# --------------------------------------------------------------------------
# Archetype definitions
# --------------------------------------------------------------------------

@dataclass
class _Ctx:
    rng: np.random.Generator
    complexity: float
    note: int

    @property
    def f0(self) -> float:
        return _hz(self.note)

    def voices(self, lo: int, hi: int) -> int:
        """Voice count growing with complexity, with one voice of jitter."""
        n = lo + round(self.complexity * (hi - lo)) + int(self.rng.integers(-1, 1))
        return int(np.clip(n, lo, hi))


@dataclass
class _Block:
    """One `MultiSourceSpec` worth of voices: (waveform, relation, decay_scale)."""
    voices: list[tuple[str, Any, float]]
    voice_shape: EnvelopeShape = OPEN_VOICE
    chain: list[Any] = field(default_factory=list)   # block-local filters, in order


@dataclass(frozen=True)
class Archetype:
    notes: tuple[int, int]
    note_len: tuple[float, float]
    envelope: EnvelopeShape
    blocks: Callable[[_Ctx], list[_Block]]
    chain: Callable[[_Ctx], list[Any]]     # shared post-mix chain (ordered stages)


def _f(type_id: str, **params: Any) -> Any:
    from ._classes import filter_classes
    return filter_classes[type_id](**params)


def _drive(c: _Ctx, p: float) -> list[Any]:
    if not _chance(c.rng, p):
        return []
    return [_f("GainFilter", factor=_log_uniform(c.rng, 1.5, 4.0)),
            _f("Clipper", max_ampl=float(c.rng.uniform(0.3, 0.8)))]


def _compressor(c: _Ctx, p: float) -> list[Any]:
    if not _chance(c.rng, p):
        return []
    return [_f("Compressor",
               threshold=float(c.rng.uniform(0.3, 0.7)),
               ratio=_log_uniform(c.rng, 2.0, 6.0),
               attack=_log_uniform(c.rng, 0.003, 0.03),
               release=_log_uniform(c.rng, 0.05, 0.3))]


def _delay(c: _Ctx, p: float) -> list[Any]:
    if not _chance(c.rng, p):
        return []
    return [_f("DelayFilter",
               delay_for=_log_uniform(c.rng, 0.06, 0.45),
               feedback=float(c.rng.uniform(0.15, 0.6)),
               mix=float(c.rng.uniform(0.1, 0.35)))]


def _reverb(c: _Ctx, p: float, lo: float = 0.1, hi: float = 0.5) -> list[Any]:
    if not _chance(c.rng, p):
        return []
    return [_f("ReverbFilter", amount=float(c.rng.uniform(lo, hi)))]


def _limiter(c: _Ctx) -> list[Any]:
    if not _chance(c.rng, 0.1 + 0.2 * c.complexity):
        return []
    return [_f("Limiter",
               threshold=float(c.rng.uniform(0.8, 0.98)),
               attack=_log_uniform(c.rng, 0.0005, 0.005),
               release=_log_uniform(c.rng, 0.05, 0.3))]


def _lowpass(c: _Ctx, lo: float, hi: float, res: tuple[float, float]) -> Any:
    return _f("LowPassFilter", cutoff_frequency=_cutoff(c.rng, c.f0, lo, hi),
              resonance=_log_uniform(c.rng, *res))


# --- bass ---------------------------------------------------------------

def _bass_blocks(c: _Ctx) -> list[_Block]:
    voices = [(str(c.rng.choice(["saw", "square"])), "identity", 1.0)]
    for _ in range(c.voices(1, 2) - 1):
        roll = c.rng.random()
        if roll < 0.45:
            voices.append(("sine", {"semitones": -12}, 1.0))          # sub
        elif roll < 0.8:
            voices.append((str(c.rng.choice(["saw", "square"])), _detune(c.rng, 4, 12), 1.0))
        else:
            voices.append(("square", {"semitones": 12}, 1.0))
    return [_Block(voices)]


def _bass_chain(c: _Ctx) -> list[Any]:
    return ([_lowpass(c, 2.0, 12.0, (0.7, 4.0))]
            + _drive(c, 0.2 + 0.3 * c.complexity)
            + _compressor(c, 0.15 + 0.3 * c.complexity))


# --- lead ---------------------------------------------------------------

def _lead_blocks(c: _Ctx) -> list[_Block]:
    voices = [(str(c.rng.choice(["saw", "square", "triangle"])), "identity", 1.0)]
    for _ in range(c.voices(1, 3) - 1):
        if c.rng.random() < 0.7:
            voices.append((voices[0][0], _detune(c.rng, 5, 15), 1.0))
        else:
            voices.append((str(c.rng.choice(["saw", "square"])),
                           {"semitones": int(c.rng.choice([7, 12, -12]))}, 1.0))
    return [_Block(voices)]


def _lead_chain(c: _Ctx) -> list[Any]:
    if c.rng.random() < 0.8:
        tone = [_lowpass(c, 3.0, 20.0, (0.7, 6.0))]
    else:
        lo = float(np.clip(c.f0 * c.rng.uniform(0.6, 1.0), 20.0, _NYQUIST_SAFE))
        tone = [_f("BandPass", low=lo, high=float(np.clip(lo * _log_uniform(c.rng, 4.0, 16.0), lo, _NYQUIST_SAFE)))]
    return (tone + _drive(c, 0.15 + 0.2 * c.complexity)
            + _delay(c, 0.2 + 0.4 * c.complexity)
            + _reverb(c, 0.1 + 0.3 * c.complexity, 0.1, 0.3))


# --- pad ----------------------------------------------------------------

def _pad_blocks(c: _Ctx) -> list[_Block]:
    wf = str(c.rng.choice(["saw", "triangle", "saw_raw"]))
    voices = [(wf, "identity", 1.0)]
    for _ in range(c.voices(2, 4) - 1):
        if c.rng.random() < 0.75:
            voices.append((wf, _detune(c.rng, 8, 25), 1.0))
        else:
            voices.append((str(c.rng.choice(["saw", "triangle", "sine"])),
                           {"semitones": int(c.rng.choice([12, -12]))}, 1.0))
    return [_Block(voices)]


def _pad_chain(c: _Ctx) -> list[Any]:
    chain = [_lowpass(c, 2.0, 10.0, (0.5, 2.0))]
    if _chance(c.rng, 0.2 + 0.4 * c.complexity):
        if c.rng.random() < 0.5:
            chain.append(_f("Tremolo", frequency=_log_uniform(c.rng, 0.5, 6.0),
                            depth=float(c.rng.uniform(0.1, 0.5))))
        else:
            chain.append(_f("AutoPanFilter", frequency=_log_uniform(c.rng, 0.1, 2.0),
                            depth=float(c.rng.uniform(0.3, 0.9)), waveform=0))
    return chain + _delay(c, 0.1 + 0.3 * c.complexity) + _reverb(c, 0.6 + 0.3 * c.complexity, 0.2, 0.5)


# --- keys / pluck -------------------------------------------------------

def _keys_blocks(c: _Ctx) -> list[_Block]:
    voices = [(str(c.rng.choice(["triangle", "square", "sine"])), "identity", 1.0)]
    for _ in range(c.voices(1, 2) - 1):
        voices.append((str(c.rng.choice(["sine", "triangle"])),
                       {"harmonic": int(c.rng.choice([2, 3, 4]))}, 0.6))
    return [_Block(voices)]


def _keys_chain(c: _Ctx) -> list[Any]:
    chain = [_lowpass(c, 4.0, 30.0, (0.5, 1.5))] if _chance(c.rng, 0.7) else []
    if _chance(c.rng, 0.3 * c.complexity):
        chain.append(_f("PanFilter", direction=float(c.rng.uniform(-0.6, 0.6))))
    return chain + _compressor(c, 0.1 + 0.2 * c.complexity) + _reverb(c, 0.2 + 0.4 * c.complexity, 0.1, 0.35)


# --- bell ---------------------------------------------------------------

#: Partial ratios of a struck bar/bell; the classic church-bell set first.
_BELL_PARTIALS: tuple[tuple[float, ...], ...] = (
    (1.0, 2.76, 5.40, 8.93),
    (1.0, 2.0, 3.01, 4.17),
    (1.0, 3.5, 7.0, 11.2),
)

_BELL_VOICE = EnvelopeShape(attack=(0.001, 0.004), decay=(0.6, 2.0), sustain=(0.0, 0.05), release=(0.3, 1.0))


def _bell_blocks(c: _Ctx) -> list[_Block]:
    partials = _BELL_PARTIALS[int(c.rng.integers(len(_BELL_PARTIALS)))]
    n = c.voices(2, 4)
    voices = []
    for ratio in partials[:n]:
        rel: Any = "identity" if ratio == 1.0 else {"ratio": float(ratio * c.rng.uniform(0.995, 1.005))}
        # Higher modes ring for a shorter time, roughly as 1/sqrt(ratio).
        voices.append(("sine", rel, 1.0 / math.sqrt(ratio)))
    return [_Block(voices, voice_shape=_BELL_VOICE)]


def _bell_chain(c: _Ctx) -> list[Any]:
    chain = []
    if _chance(c.rng, 0.3 + 0.2 * c.complexity):
        chain.append(_f("HighPassFilter", cutoff_frequency=_cutoff(c.rng, c.f0, 0.3, 0.9),
                        resonance=_log_uniform(c.rng, 0.5, 1.0)))
    return chain + _delay(c, 0.2 * c.complexity) + _reverb(c, 0.5 + 0.4 * c.complexity, 0.2, 0.5)


# --- percussive ---------------------------------------------------------

def _perc_blocks(c: _Ctx) -> list[_Block]:
    center = _log_uniform(c.rng, 800.0, 6000.0)
    if c.rng.random() < 0.5:
        width = _log_uniform(c.rng, 1.3, 3.0)
        shaper = _f("BandPass", low=float(center / width), high=float(min(center * width, _NYQUIST_SAFE)))
    else:
        shaper = _f("ResonantBandpassFilter", center_frequency=float(center),
                    quality=_log_uniform(c.rng, 1.0, 8.0))
    blocks = [_Block([(str(c.rng.choice(["whitenoise", "pinknoise"])), "identity", 1.0)], chain=[shaper])]
    if _chance(c.rng, 0.6):   # tonal body under the noise burst
        body = _Block([(str(c.rng.choice(["sine", "triangle"])), "identity", 1.0)])
        if _chance(c.rng, 0.5):
            body.chain.append(_lowpass(c, 2.0, 6.0, (0.7, 2.0)))
        blocks.append(body)
    return blocks


def _perc_chain(c: _Ctx) -> list[Any]:
    return _compressor(c, 0.2 + 0.4 * c.complexity) + _reverb(c, 0.1 + 0.3 * c.complexity, 0.05, 0.25)


SPECS: dict[str, Archetype] = {
    "bass": Archetype((28, 52), (0.2, 1.2),
                      EnvelopeShape((0.003, 0.02), (0.1, 0.4), (0.4, 0.8), (0.05, 0.25)),
                      _bass_blocks, _bass_chain),
    "lead": Archetype((55, 84), (0.3, 2.0),
                      EnvelopeShape((0.005, 0.05), (0.05, 0.3), (0.6, 0.95), (0.1, 0.4)),
                      _lead_blocks, _lead_chain),
    "pad": Archetype((40, 76), (1.5, 4.0),
                     EnvelopeShape((0.3, 1.2), (0.2, 0.8), (0.6, 0.9), (0.6, 2.0)),
                     _pad_blocks, _pad_chain),
    "keys": Archetype((45, 84), (0.2, 1.5),
                      EnvelopeShape((0.001, 0.01), (0.2, 0.8), (0.0, 0.3), (0.1, 0.5)),
                      _keys_blocks, _keys_chain),
    "bell": Archetype((55, 96), (1.0, 3.0),
                      EnvelopeShape((0.001, 0.005), (0.6, 2.0), (0.0, 0.1), (0.5, 2.0)),
                      _bell_blocks, _bell_chain),
    "percussive": Archetype((36, 72), (0.1, 0.4),
                            EnvelopeShape((0.001, 0.005), (0.03, 0.25), (0.0, 0.0), (0.02, 0.15)),
                            _perc_blocks, _perc_chain),
}


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

_TIME_EFFECTS = ("DelayFilter", "ReverbFilter")


def _tail_seconds(filters: list[Any]) -> float:
    """Extra render time so delay echoes and reverb decay are not cut off."""
    tail = 0.0
    for f in filters:
        name = type(f).__name__
        if name == "DelayFilter":
            fb = max(f.feedback, 1e-3)
            repeats = math.log(0.01) / math.log(fb)          # echoes until -40 dB
            tail = max(tail, min(f.delay_for * (1.0 + repeats), 2.0))
        elif name == "ReverbFilter":
            tail = max(tail, 0.5 + 1.5 * f.amount)
    return tail


def sample(complexity: float, archetype: str | None, rng: np.random.Generator):
    """Draw one archetype patch. See `GraphSpec.random`."""
    from ._classes import GraphSpec, MultiSourceSpec, SourceSpec

    complexity = float(np.clip(complexity, 0.0, 1.0))
    if archetype is None:
        names = list(ARCHETYPE_WEIGHTS)
        w = np.array([ARCHETYPE_WEIGHTS[n] for n in names])
        archetype = str(rng.choice(names, p=w / w.sum()))
    if archetype not in SPECS:
        raise ValueError(f"archetype must be one of {ARCHETYPES!r}, got {archetype!r}")
    spec = SPECS[archetype]

    note = int(rng.integers(spec.notes[0], spec.notes[1] + 1))
    ctx = _Ctx(rng, complexity, note)
    note_len = _log_uniform(rng, *spec.note_len)

    # Sources: each block shares the archetype envelope; voices sit under it.
    blocks = spec.blocks(ctx)
    sources, longest_release = [], 0.0
    for block in blocks:
        glob = budget_envelope(rng, spec.envelope, note_len)
        voices = []
        for waveform, relation, decay_scale in block.voices:
            env = budget_envelope(rng, block.voice_shape, note_len, decay_scale=decay_scale,
                                  min_release=glob.release[0] if block.voice_shape is OPEN_VOICE else 0.0)
            voices.append(SourceSpec(waveform=waveform, frequency_relation=relation, envelope=env))
            longest_release = max(longest_release, env.release[0])
        # Summing in-phase partials doubles the level, so bells always average.
        mix = "Sum" if archetype != "bell" and len(voices) <= 2 and rng.random() < 0.2 else "Average"
        sources.append(MultiSourceSpec(sources=voices, mix_mode=mix, glob_ampl=glob))
        longest_release = max(longest_release, glob.release[0])

    # Filters and wiring. Node refs: ("s", i) source block, ("f", j) filter.
    filters: list[Any] = []
    connections: list[dict] = []

    def add(f: Any, parents: list[tuple[str, int]]) -> tuple[str, int]:
        j = len(filters)
        filters.append(f)
        for kind, i in parents:
            if kind == "s":
                connections.append({"SourceFilter": {"source": i, "filter": j}})
            else:
                connections.append({"FilterFilter": {"filter_out": i, "filter_in": j}})
        return ("f", j)

    heads: list[tuple[str, int]] = []
    for i, block in enumerate(blocks):
        node = ("s", i)
        for f in block.chain:
            node = add(f, [node])
        heads.append(node)

    chain = spec.chain(ctx) + _limiter(ctx)
    limiter = chain.pop() if chain and type(chain[-1]).__name__ == "Limiter" else None
    outputs: list[tuple[str, int]] = heads
    for f in chain:
        is_send = (type(f).__name__ in _TIME_EFFECTS and _chance(rng, 0.6 * complexity))
        if is_send:
            # Parallel send: the dry path continues; the effect runs fully wet
            # beside it behind a send level, as on a mixer's aux bus.
            if type(f).__name__ == "DelayFilter":
                f.mix = 1.0
            level = add(_f("GainFilter", factor=float(rng.uniform(0.2, 0.5))), outputs)
            outputs = outputs + [add(f, [level])]
        else:
            outputs = [add(f, outputs)]
    if limiter is not None:
        outputs = [add(limiter, outputs)]

    for kind, i in outputs:
        if kind == "s":
            connections.append({"SourceSink": {"source": i, "sink": 0}})
        else:
            connections.append({"FilterSink": {"filter": i, "sink": 0}})

    note_off = NOTE_ON + note_len
    duration = note_off + longest_release + _tail_seconds(filters) + 0.05
    return GraphSpec(
        note=note,
        note_on=NOTE_ON,
        note_off=note_off,
        duration=float(duration),
        sources=sources,
        filters=filters,
        connections=connections,
    ).canonical()
