"""Abstract base class every TTS engine must implement.

Keeping the interface tiny makes it easy to add new backends
(e.g. Piper, Bark, StyleTTS2, or a custom C/C++ engine exposed
through pybind11) without touching the rest of the codebase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TTSEngine(ABC):
    """Minimal contract for a text-to-speech backend."""

    #: True if the engine can imitate a voice from a reference recording.
    supports_cloning: bool = False

    @abstractmethod
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
        """Render ``text`` to a WAV file at ``out_path``.

        Args:
            text: the text to speak.
            out_path: destination WAV path (parent dirs must exist).
            speaker: name of a built-in speaker, if the engine has any.
            speaker_wav: path to a reference recording for voice cloning.
            language: ISO language code, if supported.
            speed: playback speed multiplier.

        Returns:
            The path of the written file.
        """

    @abstractmethod
    def available_speakers(self) -> list[str]:
        """Return the engine's built-in speaker names (may be empty)."""

    def close(self) -> None:  # pragma: no cover - optional hook
        """Release any resources (models, audio drivers)."""
