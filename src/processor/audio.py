"""Audio extraction, replacement, and the chainable audio-effects engine.

The extraction/replacement helpers are unchanged. The effects engine mirrors the
mask registry (:mod:`src.processor.mask`): each effect ``type`` maps to a builder
that returns an FFmpeg ``-af`` *fragment* (or ``None`` when the effect is a
no-op). :func:`effect_chain` joins the fragments for an
:class:`~.models.AudioEffectConfig` into one filter chain, and
:func:`apply_effects` runs it — always through :func:`execute` and therefore
:class:`FFmpegRunner`, so no new subprocess boundary is introduced.

Builders only produce strings; nothing here calls FFmpeg. Identity effects
(``volume`` gain 0, ``speed`` factor 1, ``pitch`` 0 semitones) return ``None`` so
they never emit a filter.
"""

from threading import Event
from typing import Callable

from .encode import execute
from .models import AudioEffect, AudioEffectConfig
from .runner import FFmpegRunner, ProgressCallback
from .utils import PathLike, input_path

# Base sample rate for pitch math. ``asetrate`` reinterprets the stream rate, so
# the pitch recipe below normalises around a fixed rate and resamples back to it.
SAMPLE_RATE = 44100

# Preset pitch shifts (in semitones) for the parameter-free voice effects.
DEEP_VOICE_SEMITONES = -5.0
CHIPMUNK_SEMITONES = 7.0
# Default boost when bass/treble are requested without an explicit gain.
DEFAULT_TONE_GAIN_DB = 5.0

# type name -> builder returning an ``-af`` fragment, or ``None`` for a no-op.
AudioBuilder = Callable[[AudioEffect], str | None]
AUDIO_BUILDERS: dict[str, AudioBuilder] = {}


def register_audio(name: str) -> Callable[[AudioBuilder], AudioBuilder]:
    """Register an audio-effect fragment builder under a ``type`` name."""
    def decorator(builder: AudioBuilder) -> AudioBuilder:
        AUDIO_BUILDERS[name.lower()] = builder
        return builder
    return decorator


def _fmt(value: float) -> str:
    return f"{value:g}"


def _atempo_chain(factor: float) -> str:
    """Decompose a tempo ``factor`` into ``atempo`` stages each within [0.5, 2.0].

    A single ``atempo`` only accepts 0.5–2.0, so large speed-ups or slow-downs
    are expressed as a product of in-range stages (their tempos multiply). The
    product always equals ``factor`` exactly.
    """
    if factor <= 0:
        raise ValueError("tempo factor must be positive")
    stages: list[float] = []
    remaining = factor
    while remaining > 2.0:
        stages.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        stages.append(0.5)
        remaining /= 0.5
    stages.append(remaining)
    return ",".join(f"atempo={_fmt(stage)}" for stage in stages)


def _pitch_fragment(semitones: float) -> str | None:
    """Pitch shift by ``semitones`` while preserving duration.

    ``asetrate`` shifts pitch (and tempo) up by ``2^(n/12)``; ``aresample``
    normalises the rate back; a compensating ``atempo`` chain restores the
    original duration so only pitch changes. ``0`` semitones is a no-op.
    """
    if semitones == 0:
        return None
    ratio = 2 ** (semitones / 12)
    shifted_rate = round(SAMPLE_RATE * ratio)
    tempo = _atempo_chain(1 / ratio)
    return f"asetrate={shifted_rate},aresample={SAMPLE_RATE},{tempo}"


@register_audio("pitch")
def _pitch(effect: AudioEffect) -> str | None:
    return _pitch_fragment(effect.semitones)


@register_audio("deep_voice")
def _deep_voice(effect: AudioEffect) -> str | None:
    return _pitch_fragment(effect.semitones or DEEP_VOICE_SEMITONES)


@register_audio("chipmunk")
def _chipmunk(effect: AudioEffect) -> str | None:
    return _pitch_fragment(effect.semitones or CHIPMUNK_SEMITONES)


@register_audio("volume")
def _volume(effect: AudioEffect) -> str | None:
    if effect.gain == 0:
        return None  # 0 dB is unity gain — emit nothing.
    return f"volume={_fmt(effect.gain)}dB"


@register_audio("speed")
def _speed(effect: AudioEffect) -> str | None:
    if effect.factor == 1:
        return None
    return _atempo_chain(effect.factor)


@register_audio("echo")
def _echo(effect: AudioEffect) -> str | None:
    # aecho=in_gain:out_gain:delays(ms):decays
    return f"aecho=0.8:0.9:{_fmt(effect.delay)}:{_fmt(effect.decay)}"


@register_audio("bass")
def _bass(effect: AudioEffect) -> str | None:
    return f"bass=g={_fmt(effect.gain or DEFAULT_TONE_GAIN_DB)}"


@register_audio("treble")
def _treble(effect: AudioEffect) -> str | None:
    return f"treble=g={_fmt(effect.gain or DEFAULT_TONE_GAIN_DB)}"


@register_audio("normalize")
def _normalize(effect: AudioEffect) -> str | None:
    return "loudnorm"


def effect_fragment(effect: AudioEffect) -> str | None:
    """Resolve one :class:`AudioEffect` to its ``-af`` fragment (or ``None``)."""
    builder = AUDIO_BUILDERS.get(effect.type.lower())
    if builder is None:
        raise ValueError(f"Unknown audio effect: {effect.type!r} (known: {sorted(AUDIO_BUILDERS)})")
    return builder(effect)


def effect_chain(config: AudioEffectConfig) -> str:
    """Join a config's effects into a single, identity-pruned ``-af`` chain.

    Effects apply left to right; no-op effects contribute nothing, so an
    all-identity chain is the empty string and the caller may skip processing.
    """
    fragments = [fragment for fragment in (effect_fragment(effect) for effect in config.effects) if fragment]
    return ",".join(fragments)


# --- operations (still executed only through FFmpegRunner) -----------------

def extract_audio(runner: FFmpegRunner, source: PathLike, output: PathLike, *, codec: str = "aac", progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    return execute(runner, ["-i", str(input_path(source)), "-vn", "-c:a", codec], output, progress=progress, cancel_event=cancel_event)


def replace_audio(runner: FFmpegRunner, source: PathLike, audio: PathLike, output: PathLike, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    return execute(runner, ["-i", str(input_path(source)), "-i", str(input_path(audio)), "-map", "0:v:0", "-map", "1:a:0", *encode], output, progress=progress, cancel_event=cancel_event)


def audio_filter(runner: FFmpegRunner, source: PathLike, output: PathLike, filter_value: str, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    return execute(runner, ["-i", str(input_path(source)), "-af", filter_value, *encode], output, progress=progress, cancel_event=cancel_event)


def apply_effects(runner: FFmpegRunner, source: PathLike, output: PathLike, config: AudioEffectConfig, *, encode: list[str], progress: ProgressCallback | None = None, cancel_event: Event | None = None):
    """Apply a chain of audio effects, re-encoding through the runner.

    An all-identity chain emits no ``-af`` and simply re-encodes, so the step
    stays a well-defined operation even when every effect is a no-op.
    """
    chain = effect_chain(config)
    filter_args = ["-af", chain] if chain else []
    return execute(runner, ["-i", str(input_path(source)), *filter_args, *encode], output, progress=progress, cancel_event=cancel_event)
