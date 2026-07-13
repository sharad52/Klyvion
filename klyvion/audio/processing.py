"""Audio utilities: loading, saving, trimming, normalizing, pitch shift.

Built on numpy + soundfile + librosa. All functions operate on mono
float32 arrays in the range [-1, 1].
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def load_audio(path: Path, target_sr: int | None = None, mono: bool = True):
    """Load an audio file, optionally resampling. Returns (audio, sr)."""
    import librosa

    audio, sr = librosa.load(str(path), sr=target_sr, mono=mono)
    return audio.astype(np.float32), int(sr)


def save_wav(path: Path, audio: np.ndarray, sr: int) -> Path:
    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr)
    return path


def trim_silence(audio: np.ndarray, sr: int, top_db: float = 35.0) -> np.ndarray:
    """Remove leading/trailing silence."""
    import librosa

    trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
    return trimmed


def normalize_loudness(audio: np.ndarray, peak: float = 0.95) -> np.ndarray:
    """Simple peak normalization (no external loudness meter needed)."""
    max_amp = float(np.max(np.abs(audio))) if audio.size else 0.0
    if max_amp < 1e-8:
        return audio
    return (audio / max_amp * peak).astype(np.float32)


def pitch_shift(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Shift pitch by resampling (formant-shifting, artifact-free).

    We deliberately avoid ``librosa.effects.pitch_shift``: that method is a
    phase vocoder, which smears speech transients and adds a hollow,
    reverberant "distant hall" echo — very audible on the pitched-up
    ``boy``/``girl`` presets. Resampling instead speeds the waveform up (or
    slows it down) and relabels it at the original sample rate, moving pitch
    *and* formants together. That has no phase artifacts and yields a more
    natural child-voice timbre.

    The trade-off is duration: raising the pitch by ``ratio`` shortens the
    clip to ``1 / ratio`` of its length (and vice-versa). For the small
    child-voice shifts used here this reads as a slightly quicker delivery,
    which suits the effect.

    Args:
        audio: Mono float32 samples in [-1, 1].
        sr: Sample rate the clip is stored/played at.
        semitones: Shift amount; positive raises pitch, negative lowers it.

    Returns:
        The pitch-shifted samples (a different length than the input),
        intended to be saved/played back at the same ``sr``.
    """
    if abs(semitones) < 1e-3:
        return audio
    import librosa

    ratio = 2.0 ** (semitones / 12.0)
    shifted = librosa.resample(audio, orig_sr=sr, target_sr=int(round(sr / ratio)))
    return shifted.astype(np.float32)


def apply_post_effects(
    wav_path: Path,
    *,
    pitch_semitones: float = 0.0,
    normalize: bool = True,
) -> Path:
    """Apply in-place post-processing to a synthesized WAV file."""
    if abs(pitch_semitones) < 1e-3 and not normalize:
        return wav_path

    audio, sr = load_audio(wav_path)
    if abs(pitch_semitones) >= 1e-3:
        audio = pitch_shift(audio, sr, pitch_semitones)
    if normalize:
        audio = normalize_loudness(audio)
    return save_wav(wav_path, audio, sr)
