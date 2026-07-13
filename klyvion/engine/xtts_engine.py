"""Neural TTS backend built on Coqui XTTS v2.

XTTS v2 is a multilingual, zero-shot voice-cloning model released under
the Coqui Public Model License. It can:

* speak with ~50 built-in "studio" speakers, and
* clone any voice from a 6-30 second reference WAV (``speaker_wav``).

The model (~2 GB) is downloaded on first use into the standard
Coqui cache directory. GPU (CUDA) is strongly recommended but CPU works.
"""

from __future__ import annotations

import logging
from pathlib import Path

from klyvion.engine.base import TTSEngine

logger = logging.getLogger(__name__)

_MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"


class XTTSEngine(TTSEngine):
    supports_cloning = True

    def __init__(self, device: str = "auto") -> None:
        # Imports are done lazily so that installing the heavy `coqui-tts`
        # dependency is only required when this engine is actually used.
        try:
            import torch
            from TTS.api import TTS  # provided by the `coqui-tts` package
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The XTTS engine requires the 'coqui-tts' package. "
                "Install it with: pip install klyvion[neural]"
            ) from exc

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info("Loading XTTS v2 on %s (first run downloads ~2 GB)...", device)
        self._tts = TTS(_MODEL_ID).to(device)
        self._device = device

    # ------------------------------------------------------------------ #

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
        if speaker_wav is None and speaker is None:
            speaker = self.available_speakers()[0]

        kwargs: dict = {
            "text": text,
            "file_path": str(out_path),
            "language": language,
            "speed": speed,
        }
        if speaker_wav is not None:
            kwargs["speaker_wav"] = str(speaker_wav)
        else:
            kwargs["speaker"] = speaker

        self._tts.tts_to_file(**kwargs)
        return out_path

    def available_speakers(self) -> list[str]:
        speakers = getattr(self._tts, "speakers", None) or []
        return list(speakers)

    def close(self) -> None:  # pragma: no cover
        self._tts = None
