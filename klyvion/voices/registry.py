"""Voice registry.

Two kinds of voices exist in Klyvion:

1. **Presets** — friendly names ("man", "woman", "boy", "girl") mapped to
   built-in XTTS studio speakers, optionally with a pitch shift applied in
   post-processing (used to approximate child voices, since XTTS has no
   native child speakers).

2. **Custom voices** — created by :meth:`Klyvion.clone_voice` from a
   user-provided recording. Metadata is persisted as JSON so custom voices
   survive restarts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,40}$")


@dataclass
class VoicePreset:
    """A named voice.

    Attributes:
        name: user-facing name ("man", "girl", "alex", ...).
        kind: "preset" or "custom".
        speaker: XTTS built-in speaker name (presets only).
        sample_path: reference WAV for cloning (custom voices only).
        pitch_semitones: pitch shift applied after synthesis
            (positive = higher). Used to fake child voices.
        speed: default speaking-rate multiplier.
        description: shown in ``klyvion voices``.
    """

    name: str
    kind: str = "preset"
    speaker: str | None = None
    sample_path: str | None = None
    pitch_semitones: float = 0.0
    speed: float = 1.0
    description: str = ""


#: Default presets. Speaker names come from the XTTS v2 studio-speaker set.
DEFAULT_PRESETS: dict[str, VoicePreset] = {
    "man": VoicePreset(
        name="man",
        speaker="Damien Black",
        description="Deep adult male voice",
    ),
    "woman": VoicePreset(
        name="woman",
        speaker="Claribel Dervla",
        description="Warm adult female voice",
    ),
    "boy": VoicePreset(
        name="boy",
        speaker="Craig Gutsy",
        pitch_semitones=3.0,
        speed=1.05,
        description="Young male voice (pitch-shifted)",
    ),
    "girl": VoicePreset(
        name="girl",
        speaker="Daisy Studious",
        pitch_semitones=2.5,
        speed=1.05,
        description="Young female voice (pitch-shifted)",
    ),
}


class VoiceRegistry:
    """Stores presets in memory and custom voices on disk (JSON)."""

    def __init__(self, voices_dir: Path) -> None:
        self._voices_dir = voices_dir
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = voices_dir / "index.json"
        self._custom: dict[str, VoicePreset] = {}
        self._load()

    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if self._index_path.exists():
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._custom = {k: VoicePreset(**v) for k, v in raw.items()}

    def _save(self) -> None:
        payload = {k: asdict(v) for k, v in self._custom.items()}
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ #

    def get(self, name: str) -> VoicePreset:
        key = name.lower()
        if key in self._custom:
            return self._custom[key]
        if key in DEFAULT_PRESETS:
            return DEFAULT_PRESETS[key]
        raise KeyError(
            f"Unknown voice '{name}'. Known voices: {', '.join(self.names())}"
        )

    def names(self) -> list[str]:
        return sorted(set(DEFAULT_PRESETS) | set(self._custom))

    def all(self) -> list[VoicePreset]:
        return [self.get(n) for n in self.names()]

    def add_custom(
        self,
        name: str,
        sample_path: Path,
        *,
        description: str = "",
        pitch_semitones: float = 0.0,
        speed: float = 1.0,
    ) -> VoicePreset:
        key = name.lower()
        if not _NAME_RE.match(key):
            raise ValueError(
                "Voice names must be 1-40 chars of letters, digits, '_' or '-'."
            )
        if key in DEFAULT_PRESETS:
            raise ValueError(f"'{name}' is a reserved preset name.")
        preset = VoicePreset(
            name=key,
            kind="custom",
            sample_path=str(sample_path),
            description=description or f"Custom cloned voice '{name}'",
            pitch_semitones=pitch_semitones,
            speed=speed,
        )
        self._custom[key] = preset
        self._save()
        return preset

    def remove_custom(self, name: str) -> None:
        key = name.lower()
        if key not in self._custom:
            raise KeyError(f"No custom voice named '{name}'.")
        preset = self._custom.pop(key)
        self._save()
        if preset.sample_path:
            sample = Path(preset.sample_path)
            if sample.exists() and self._voices_dir in sample.parents:
                sample.unlink()
