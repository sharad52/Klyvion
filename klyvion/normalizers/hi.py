"""Hindi text normalizer.

Expands standalone integers into Devanagari number words before synthesis
(``42`` and ``४२`` both become ``बयालिस``). Number words come from the
``indic-num2words`` package (imported as ``num_to_words``); if it is missing,
registration is skipped and Hindi still synthesizes with digits left as-is.
"""

from __future__ import annotations

import logging

from klyvion.languages import register_normalizer
from klyvion.normalizers.numbers import expand_integers

logger = logging.getLogger(__name__)

try:
    from num_to_words import num_to_word as _num_to_word
except ImportError:  # pragma: no cover - number expansion is optional
    _num_to_word = None


def normalize_hindi(text: str) -> str:
    """Expand standalone integers in Hindi ``text`` into words."""
    if _num_to_word is None:
        return text
    return expand_integers(text, lambda value: _num_to_word(value, "hi"))


if _num_to_word is not None:
    register_normalizer("hi", normalize_hindi)
else:  # pragma: no cover - depends on install extras
    logger.debug("indic-num2words not installed; Hindi numbers left un-expanded.")
