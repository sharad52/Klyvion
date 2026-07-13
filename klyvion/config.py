"""Central configuration for Klyvion.

All paths and engine choices live here so the CLI, the Python API and the
HTTP server share one source of truth. Values can be overridden with
environment variables prefixed with ``KLYVION_``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"KLYVION_{name}", default)


@dataclass
class Settings:
    """Runtime settings.

    Attributes:
        engine: "xtts" (neural, supports cloning) or "pyttsx3"
            (lightweight offline fallback, no cloning).
        data_dir: where cloned-voice samples and metadata are stored.
        output_dir: default directory for synthesized audio.
        sample_rate: output sample rate in Hz.
        device: "auto", "cpu" or "cuda".
        language: default language code for the neural engine.
    """

    engine: str = field(default_factory=lambda: _env("ENGINE", "xtts"))
    data_dir: Path = field(
        default_factory=lambda: Path(_env("DATA_DIR", "~/.klyvion")).expanduser()
    )
    output_dir: Path = field(
        default_factory=lambda: Path(_env("OUTPUT_DIR", "./outputs")).expanduser()
    )
    sample_rate: int = field(default_factory=lambda: int(_env("SAMPLE_RATE", "24000")))
    device: str = field(default_factory=lambda: _env("DEVICE", "auto"))
    language: str = field(default_factory=lambda: _env("LANGUAGE", "en"))

    @property
    def voices_dir(self) -> Path:
        return self.data_dir / "voices"

    def ensure_dirs(self) -> None:
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a process-wide singleton of :class:`Settings`."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
