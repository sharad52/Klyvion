"""Voice-cloning helpers.

Cloning with XTTS v2 is *zero-shot*: no training loop is needed. The user
supplies a short, clean recording (ideally 6-30 seconds of one person
speaking, no music/noise) and the model conditions on it at inference
time. This module validates and normalizes that recording so results are
as good as possible.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from klyvion.audio.processing import (
    load_audio,
    save_wav,
    trim_silence,
    normalize_loudness,
)

logger = logging.getLogger(__name__)

MIN_SECONDS = 3.0
MAX_SECONDS = 60.0
TARGET_SR = 22050  # XTTS conditioning sample rate


class SampleTooShortError(ValueError):
    pass


class SampleTooLongError(ValueError):
    pass


def prepare_voice_sample(src: Path, dest_dir: Path, voice_name: str) -> Path:
    """Validate and clean a user recording, returning the stored WAV path.

    Steps: decode (any format soundfile/librosa supports) -> mono ->
    resample to 22.05 kHz -> trim leading/trailing silence -> loudness
    normalize -> save as ``<dest_dir>/<voice_name>.wav``.
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"Sample not found: {src}")

    audio, sr = load_audio(src, target_sr=TARGET_SR, mono=True)
    audio = trim_silence(audio, sr)
    duration = len(audio) / sr

    if duration < MIN_SECONDS:
        raise SampleTooShortError(
            f"Sample is {duration:.1f}s after trimming silence; "
            f"need at least {MIN_SECONDS:.0f}s of clear speech."
        )
    if duration > MAX_SECONDS:
        logger.info("Sample is %.1fs; keeping the first %.0fs.", duration, MAX_SECONDS)
        audio = audio[: int(MAX_SECONDS * sr)]

    audio = normalize_loudness(audio)

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{voice_name}.wav"
    save_wav(dest, audio, sr)
    logger.info("Stored cleaned voice sample at %s (%.1fs)", dest, len(audio) / sr)
    return dest


def copy_raw_sample(src: Path, dest_dir: Path, voice_name: str) -> Path:
    """Fallback used when audio libs are unavailable: copy as-is."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{voice_name}{Path(src).suffix or '.wav'}"
    shutil.copyfile(src, dest)
    return dest
