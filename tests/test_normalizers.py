"""Unit tests for the per-language text normalizers.

These exercise the normalizer functions directly as pure text-in/text-out —
no model download, no global-registry coupling. Number-expansion tests skip
cleanly if the optional number-words libraries are not installed.
"""

from __future__ import annotations

import pytest

from klyvion.normalizers.numbers import expand_integers


def _english(value: int) -> str:
    from num2words import num2words

    return num2words(value, lang="en")


def test_expand_integers_leaves_decimals_and_versions_untouched():
    # A pure helper test with a trivial converter — no external dependency.
    src = "Version 3.14 of v2 released at 12:30 on line 42"
    out = expand_integers(src, lambda v: f"<{v}>")
    assert "3.14" in out  # decimal untouched
    assert "v2" in out  # alphanumeric identifier untouched
    assert "12:30" in out  # time untouched
    assert "<42>" in out  # standalone integer expanded


def test_expand_integers_handles_comma_groups_and_devanagari():
    out = expand_integers("पास ४२ और 1,250 हैं", lambda v: f"<{v}>")
    assert "<42>" in out  # Devanagari digits normalized then expanded
    assert "<1250>" in out  # comma group parsed as one number


def test_expand_integers_skips_overlong_identifiers():
    out = expand_integers("call 1234567890123456 now", lambda v: f"<{v}>")
    assert "1234567890123456" in out  # 16 digits: left as-is


def test_english_normalizer_expands_year():
    pytest.importorskip("num2words")
    from klyvion.normalizers.en import normalize_english

    out = normalize_english("Recorded in 2026.")
    assert "2026" not in out
    assert "twenty-six" in out


def test_hindi_normalizer_expands_devanagari_number():
    pytest.importorskip("num_to_words")
    from klyvion.normalizers.hi import normalize_hindi

    out = normalize_hindi("मेरे पास ४२ रुपये हैं")
    assert "४२" not in out
    assert "बयालिस" in out


def test_english_number_converter_smoke():
    pytest.importorskip("num2words")
    assert expand_integers("just 7 apples", _english) == "just seven apples"
