"""Tests for the language registry and its integration with the facade."""

from __future__ import annotations

import pytest

from klyvion import languages
from klyvion.languages import LanguageNotEnabledError

# Reuse the FakeEngine-backed facade fixture
from tests.test_klyvion import forge  # noqa: F401


def test_english_enabled():
    assert languages.validate("en") == "en"
    assert languages.validate("EN") == "en"


def test_hindi_enabled():
    assert languages.validate("hi") == "hi"
    assert languages.validate("HI") == "hi"


def test_native_but_disabled_language_raises():
    with pytest.raises(LanguageNotEnabledError) as exc:
        languages.validate("es")
    assert "engine-native" in str(exc.value)


def test_unknown_language_raises():
    with pytest.raises(LanguageNotEnabledError):
        languages.validate("xx")


def test_enabled_languages_are_english_and_hindi():
    codes = {lang.code for lang in languages.enabled_languages()}
    assert codes == {"en", "hi"}


def test_normalizer_hook():
    previous = languages._NORMALIZERS.get("en")
    languages.register_normalizer("en", lambda t: t.replace("&", "and"))
    try:
        assert languages.normalize_text("A & B", "en") == "A and B"
    finally:
        # Restore any normalizer registered at import so ordering stays hermetic.
        if previous is None:
            languages._NORMALIZERS.pop("en", None)
        else:
            languages._NORMALIZERS["en"] = previous


def test_speak_rejects_disabled_language(forge):  # noqa: F811
    with pytest.raises(LanguageNotEnabledError):
        forge.speak("Hola", voice="woman", language="es")


def test_speak_passes_validated_language(forge):  # noqa: F811
    forge.speak(
        "Hello",
        voice="man",
        out_path=forge.settings.output_dir / "l.wav",
        language="EN",
    )
    assert forge._engine.calls[-1]["language"] == "en"


def test_speak_hindi_reaches_engine(forge):  # noqa: F811
    forge.speak(
        "नमस्ते",
        voice="woman",
        out_path=forge.settings.output_dir / "hi.wav",
        language="hi",
    )
    assert forge._engine.calls[-1]["language"] == "hi"


def test_speak_expands_numbers_before_synthesis(forge):  # noqa: F811
    pytest.importorskip("num2words")
    forge.speak(
        "I have 3 cats",
        voice="man",
        out_path=forge.settings.output_dir / "n.wav",
        language="en",
    )
    spoken = forge._engine.calls[-1]["text"]
    assert "three" in spoken and "3" not in spoken
