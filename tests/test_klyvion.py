"""Tests that run fast with no model downloads.

A FakeEngine stands in for XTTS so the facade, registry and CLI logic can
be exercised in CI.
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from klyvion.config import Settings
from klyvion.core import Klyvion
from klyvion.engine.base import TTSEngine
from klyvion.voices.registry import VoiceRegistry, DEFAULT_PRESETS


class FakeEngine(TTSEngine):
    supports_cloning = True

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def synthesize(
        self,
        text,
        out_path,
        *,
        speaker=None,
        speaker_wav=None,
        language="en",
        speed=1.0,
    ):
        self.calls.append(
            dict(
                text=text,
                speaker=speaker,
                speaker_wav=speaker_wav,
                language=language,
                speed=speed,
            )
        )
        _write_silent_wav(out_path)
        return out_path

    def available_speakers(self):
        return ["Damien Black", "Claribel Dervla"]


def _write_silent_wav(path: Path, seconds: float = 0.2, sr: int = 16000) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(seconds * sr))


@pytest.fixture
def forge(tmp_path, monkeypatch):
    settings = Settings(
        engine="fake",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "out",
    )
    settings.ensure_dirs()
    vf = Klyvion(settings)
    vf._engine = FakeEngine()
    return vf


# --------------------------------------------------------------------- #
# Registry


def test_default_presets_exist(tmp_path):
    reg = VoiceRegistry(tmp_path)
    for name in ("man", "woman", "boy", "girl"):
        assert name in reg.names()


def test_unknown_voice_raises(tmp_path):
    reg = VoiceRegistry(tmp_path)
    with pytest.raises(KeyError):
        reg.get("does-not-exist")


def test_custom_voice_persists(tmp_path):
    reg = VoiceRegistry(tmp_path)
    reg.add_custom("alex", tmp_path / "alex.wav")
    # Fresh instance reads the JSON index from disk
    reg2 = VoiceRegistry(tmp_path)
    assert reg2.get("alex").kind == "custom"


def test_reserved_names_rejected(tmp_path):
    reg = VoiceRegistry(tmp_path)
    with pytest.raises(ValueError):
        reg.add_custom("man", tmp_path / "x.wav")


def test_invalid_names_rejected(tmp_path):
    reg = VoiceRegistry(tmp_path)
    with pytest.raises(ValueError):
        reg.add_custom("../evil", tmp_path / "x.wav")


# --------------------------------------------------------------------- #
# Facade


def test_speak_with_preset(forge):
    out = forge.speak(
        "Hello", voice="man", out_path=forge.settings.output_dir / "a.wav"
    )
    assert out.exists()
    call = forge._engine.calls[-1]
    assert call["speaker"] == DEFAULT_PRESETS["man"].speaker
    assert call["speaker_wav"] is None


def test_speak_empty_text_raises(forge):
    with pytest.raises(ValueError):
        forge.speak("   ")


def test_clone_and_speak(forge, tmp_path):
    sample = tmp_path / "sample.wav"
    _write_silent_wav(sample, seconds=8.0)
    # Bypass audio-cleanup deps by monkeypatching prepare to a copy
    from klyvion.voices import cloning

    stored = cloning.copy_raw_sample(sample, forge.settings.voices_dir, "alex")
    forge.registry.add_custom("alex", stored)

    out = forge.speak("Hi", voice="alex", out_path=forge.settings.output_dir / "b.wav")
    assert out.exists()
    call = forge._engine.calls[-1]
    assert call["speaker_wav"] is not None
    assert call["speaker"] is None


def test_remove_voice(forge, tmp_path):
    sample = tmp_path / "s.wav"
    _write_silent_wav(sample)
    from klyvion.voices import cloning

    stored = cloning.copy_raw_sample(sample, forge.settings.voices_dir, "temp")
    forge.registry.add_custom("temp", stored)
    forge.remove_voice("temp")
    with pytest.raises(KeyError):
        forge.registry.get("temp")
