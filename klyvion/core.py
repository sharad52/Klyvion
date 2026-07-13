"""High-level facade tying engines, the voice registry and audio
post-processing together. This is the class most users interact with.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from klyvion import languages
from klyvion.config import Settings, get_settings
from klyvion.engine import TTSEngine, create_engine
from klyvion.voices.registry import VoiceRegistry, VoicePreset
from klyvion.voices import cloning

logger = logging.getLogger(__name__)


class Klyvion:
    """Multi-voice text-to-speech with zero-shot voice cloning.

    Example:
        >>> tts = Klyvion()
        >>> tts.speak("Hello!", voice="woman", out_path="hello.wav")
        >>> tts.clone_voice("alex", "recording_of_alex.wav")
        >>> tts.speak("Hi, I'm Alex.", voice="alex", out_path="alex.wav")
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.registry = VoiceRegistry(self.settings.voices_dir)
        self._engine: TTSEngine | None = None  # lazy — model load is slow

    # ------------------------------------------------------------------ #
    @property
    def engine(self) -> TTSEngine:
        if self._engine is None:
            self._engine = create_engine(
                self.settings.engine, device=self.settings.device
            )
        return self._engine

    # ------------------------------------------------------------------ #
    def speak(
        self,
        text: str,
        *,
        voice: str = "woman",
        out_path: str | Path | None = None,
        language: str | None = None,
        speed: float | None = None,
    ) -> Path:
        """Synthesize ``text`` with the given voice and return the WAV path."""
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        preset = self.registry.get(voice)
        out = Path(out_path) if out_path else self._default_out_path(preset)
        out.parent.mkdir(parents=True, exist_ok=True)

        lang = languages.validate(language or self.settings.language)
        text = languages.normalize_text(text, lang)
        rate = speed if speed is not None else preset.speed

        speaker_wav = None
        speaker = None
        if preset.kind == "custom":
            if not self.engine.supports_cloning:
                raise RuntimeError(
                    f"Engine '{self.settings.engine}' cannot use cloned voices. "
                    "Switch to the 'xtts' engine."
                )
            speaker_wav = Path(preset.sample_path)  # type: ignore[arg-type]
        else:
            speaker = preset.speaker

        logger.info("Synthesizing %d chars with voice '%s'...", len(text), preset.name)
        self.engine.synthesize(
            text,
            out,
            speaker=speaker,
            speaker_wav=speaker_wav,
            language=lang,
            speed=rate,
        )
        self._post_process(out, preset)
        return out

    # ------------------------------------------------------------------ #
    def clone_voice(
        self,
        name: str,
        sample_path: str | Path,
        *,
        description: str = "",
    ) -> VoicePreset:
        """Register a custom voice from a user recording.

        The recording should contain 6-30 seconds of a single person
        speaking clearly, without background music or noise.
        """
        sample_path = Path(sample_path)
        try:
            stored = cloning.prepare_voice_sample(
                sample_path, self.settings.voices_dir, name.lower()
            )
        except ImportError:
            logger.warning("librosa/soundfile missing; storing raw sample.")
            stored = cloning.copy_raw_sample(
                sample_path, self.settings.voices_dir, name.lower()
            )
        return self.registry.add_custom(name, stored, description=description)

    def remove_voice(self, name: str) -> None:
        self.registry.remove_custom(name)

    def list_voices(self) -> list[VoicePreset]:
        return self.registry.all()

    # ------------------------------------------------------------------ #
    def _post_process(self, wav_path: Path, preset: VoicePreset) -> None:
        if abs(preset.pitch_semitones) < 1e-3:
            return
        try:
            from klyvion.audio.processing import apply_post_effects

            apply_post_effects(wav_path, pitch_semitones=preset.pitch_semitones)
        except ImportError:  # pragma: no cover
            logger.warning(
                "librosa not installed; skipping pitch shift for '%s'.", preset.name
            )

    def _default_out_path(self, preset: VoicePreset) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return self.settings.output_dir / f"{preset.name}-{stamp}.wav"

    def close(self) -> None:
        if self._engine is not None:
            self._engine.close()
            self._engine = None

    # ------------------------------------------------------------------ #
    @staticmethod
    def list_languages(include_disabled: bool = False):
        """Return supported :class:`~klyvion.languages.Language` objects."""
        return (
            languages.all_languages()
            if include_disabled
            else languages.enabled_languages()
        )
