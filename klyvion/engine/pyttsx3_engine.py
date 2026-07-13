"""Lightweight offline backend using pyttsx3 (SAPI5 / NSSpeech / eSpeak).

No downloads, no GPU — but the voices are robotic and cloning is not
possible. Useful for quick tests, CI, and low-resource machines.
"""

from __future__ import annotations

import logging
from pathlib import Path

from klyvion.engine.base import TTSEngine

logger = logging.getLogger(__name__)


class Pyttsx3Engine(TTSEngine):
    supports_cloning = False

    def __init__(self, device: str = "auto") -> None:  # device is ignored
        try:
            import pyttsx3
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The fallback engine requires 'pyttsx3'. "
                "Install it with: pip install pyttsx3"
            ) from exc
        self._engine = pyttsx3.init()

    def synthesize(
        self,
        text: str,
        out_path: Path,
        *,
        speaker: str | None = None,
        speaker_wav: Path | None = None,
        language: str = "en",
        speed: float = 1.0,
    ) -> Path:
        if speaker_wav is not None:
            logger.warning("pyttsx3 cannot clone voices; ignoring speaker_wav.")

        if speaker is not None:
            for voice in self._engine.getProperty("voices"):
                if speaker.lower() in (voice.name or "").lower() or speaker == voice.id:
                    self._engine.setProperty("voice", voice.id)
                    break

        base_rate = 200  # words per minute baseline
        self._engine.setProperty("rate", int(base_rate * speed))
        self._engine.save_to_file(text, str(out_path))
        self._engine.runAndWait()
        return out_path

    def available_speakers(self) -> list[str]:
        return [v.name or v.id for v in self._engine.getProperty("voices")]

    def close(self) -> None:  # pragma: no cover
        self._engine.stop()
