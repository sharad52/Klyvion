"""Shared helper for expanding digit sequences into spoken words.

TTS models read raw digits poorly, especially outside English ("42" is easy
to mispronounce, and years/currencies compound the problem). Each language
normalizer supplies its own integer-to-words function; this module owns the
*detection* of which substrings are safe to expand, so that logic is written
and tested once.

The matcher is deliberately conservative: it expands standalone integers and
comma-grouped integers, but leaves decimals (``3.14``), versions (``v0.1``),
times/IPs (``12:30``, ``127.0.0.1``) and alphanumeric identifiers (``mp3``)
untouched. Fractional and signed numbers are out of scope for v0.1.
"""

from __future__ import annotations

import re
from typing import Callable

#: Devanagari digits ``०``–``९`` mapped onto ASCII, so Hindi text written with
#: native numerals is expanded just like ``42``.
_DEVANAGARI_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")

#: ASCII or Devanagari digit.
_DIGIT = r"[0-9०-९]"

#: A standalone integer, optionally grouped with commas (``1,250``).
#:
#: The look-arounds keep three things intact: numbers glued to letters
#: (``mp3``) are rejected via ``\w``; and a dot/colon only disqualifies the run
#: when a digit sits on the *other* side of it — so ``3.14``, ``12:30`` and
#: ``127.0.0.1`` are skipped, while a trailing sentence period (``in 2026.``)
#: is not. ``\d`` matches Devanagari digits too, so those guards cover both
#: scripts.
_NUMBER_RE = re.compile(
    r"(?<!\w)(?<!\d[.:])"
    rf"(?:{_DIGIT}{{1,3}}(?:,{_DIGIT}{{3}})+|{_DIGIT}+)"
    r"(?!\w)(?![.:]\d)"
)

#: Digit strings longer than this are almost certainly identifiers (phone
#: numbers, account ids) rather than quantities, so they are left as-is.
_MAX_DIGITS = 15


def expand_integers(text: str, to_words: Callable[[int], str]) -> str:
    """Replace standalone integers in ``text`` with their spoken form.

    Args:
        text: the source text, which may mix ASCII and Devanagari digits.
        to_words: converts a non-negative integer to words in the target
            language (e.g. ``lambda v: num2words(v, lang="en")``).

    Returns:
        ``text`` with each detected integer replaced by ``to_words`` output.
        Tokens that are too long, or that ``to_words`` cannot render, are left
        unchanged so normalization never loses information.
    """

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        digits = token.replace(",", "").translate(_DEVANAGARI_TO_ASCII)
        if len(digits) > _MAX_DIGITS:
            return token
        try:
            return to_words(int(digits))
        except (ValueError, KeyError, AssertionError):
            return token

    return _NUMBER_RE.sub(_replace, text)
