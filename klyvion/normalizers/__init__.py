"""Per-language text normalizers.

Importing this package registers every bundled normalizer via
:func:`klyvion.languages.register_normalizer`, so ``core.speak`` picks them up
automatically. Add a new language by dropping a ``<code>.py`` module here that
calls ``register_normalizer`` at import time, then importing it below.
"""

from __future__ import annotations

from klyvion.normalizers import en, hi  # noqa: F401  (import for side effects)

__all__ = ["en", "hi"]
