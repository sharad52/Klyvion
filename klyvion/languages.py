"""Language support registry.

Klyvion v0.1 ships with **English enabled only**, but the underlying
XTTS v2 engine is already multilingual. Each language below is marked
``enabled`` or not; enabling one that XTTS supports is usually a
one-line change plus tests (see docs/EXTENDING_LANGUAGES.md).

Languages fall into three tiers:

1. **Tier A — engine-native** (listed in ``XTTS_NATIVE``): flip
   ``enabled=True`` and add tests. No model work needed.
2. **Tier B — engine-native but needs text normalization**: numbers,
   dates and abbreviations must be expanded before synthesis. Register a
   normalizer in ``_NORMALIZERS``.
3. **Tier C — not supported by the engine**: requires a different
   backend (e.g. a fine-tuned model or another engine class).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

#: Languages the XTTS v2 engine natively supports (Tier A/B candidates).
XTTS_NATIVE = {
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "pl",
    "tr",
    "ru",
    "nl",
    "cs",
    "ar",
    "zh-cn",
    "ja",
    "hu",
    "ko",
    "hi",
}


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1 (plus region where needed, e.g. zh-cn)
    name: str
    enabled: bool = False
    engine_native: bool = False


_LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", enabled=True, engine_native=True),
    "hi": Language("hi", "Hindi", enabled=True, engine_native=True),
    # --- Ready to enable (Tier A): flip `enabled=True` and add tests ---
    "es": Language("es", "Spanish", engine_native=True),
    "fr": Language("fr", "French", engine_native=True),
    "de": Language("de", "German", engine_native=True),
    "it": Language("it", "Italian", engine_native=True),
    "pt": Language("pt", "Portuguese", engine_native=True),
    "pl": Language("pl", "Polish", engine_native=True),
    "tr": Language("tr", "Turkish", engine_native=True),
    "ru": Language("ru", "Russian", engine_native=True),
    "nl": Language("nl", "Dutch", engine_native=True),
    "cs": Language("cs", "Czech", engine_native=True),
    "ar": Language("ar", "Arabic", engine_native=True),
    "zh-cn": Language("zh-cn", "Chinese (Simplified)", engine_native=True),
    "ja": Language("ja", "Japanese", engine_native=True),
    "hu": Language("hu", "Hungarian", engine_native=True),
    "ko": Language("ko", "Korean", engine_native=True),
    # --- Tier C examples (need a new engine/model): ---
    # "ne": Language("ne", "Nepali"),
    # "bn": Language("bn", "Bengali"),
}

#: Optional per-language text normalizers, applied before synthesis.
#: Signature: (text: str) -> str
_NORMALIZERS: dict[str, Callable[[str], str]] = {}


class LanguageNotEnabledError(ValueError):
    pass


def enabled_languages() -> list[Language]:
    return [lang for lang in _LANGUAGES.values() if lang.enabled]


def all_languages() -> list[Language]:
    return list(_LANGUAGES.values())


def validate(code: str) -> str:
    """Return the canonical code, or raise if unknown/disabled."""
    key = code.lower()
    lang = _LANGUAGES.get(key)
    if lang is None:
        raise LanguageNotEnabledError(
            f"Unknown language '{code}'. Known codes: "
            f"{', '.join(sorted(_LANGUAGES))}"
        )
    if not lang.enabled:
        hint = (
            "it is engine-native — see docs/EXTENDING_LANGUAGES.md to enable it"
            if lang.engine_native
            else "it needs a new engine backend — see docs/EXTENDING_LANGUAGES.md"
        )
        raise LanguageNotEnabledError(
            f"Language '{lang.name}' ({key}) is not enabled in this build; {hint}."
        )
    return key


def normalize_text(text: str, code: str) -> str:
    """Apply the language's text normalizer, if one is registered."""
    fn = _NORMALIZERS.get(code.lower())
    return fn(text) if fn else text


def register_normalizer(code: str, fn: Callable[[str], str]) -> None:
    """Plugin hook: register a text normalizer for a language."""
    _NORMALIZERS[code.lower()] = fn
