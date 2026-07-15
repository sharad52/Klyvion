"""English text normalizer.

Expands standalone integers into words before synthesis (``in 2026`` ->
``in two thousand and twenty-six``). Registration is a no-op if the optional
``num2words`` dependency is missing, so a minimal install still synthesizes
English — it just leaves digits for the engine to read.
"""

from __future__ import annotations

import logging

from klyvion.languages import register_normalizer
from klyvion.normalizers.numbers import expand_integers

logger = logging.getLogger(__name__)

try:
    from num2words import num2words as _num2words
except ImportError:  # pragma: no cover - number expansion is optional
    _num2words = None


def normalize_english(text: str) -> str:
    """Expand standalone integers in English ``text`` into words."""
    if _num2words is None:
        return text
    return expand_integers(text, lambda value: _num2words(value, lang="en"))


if _num2words is not None:
    register_normalizer("en", normalize_english)
else:  # pragma: no cover - depends on install extras
    logger.debug("num2words not installed; English numbers left un-expanded.")
