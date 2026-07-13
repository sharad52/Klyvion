"""Authentication subsystem for the Klyvion API.

Public surface:
    - :class:`AuthService` — the facade the API talks to.
    - :class:`User` — the account value object.
    - :func:`build_auth_router` / :func:`current_user_dependency` — FastAPI wiring.
    - The :class:`AuthError` hierarchy for typed failures.

Concrete collaborators (password hashing, JWT signing, the Google client) pull
in the ``server`` extra's dependencies lazily, so importing this package does
not require them until an :class:`AuthService` is actually constructed.
"""

from __future__ import annotations

from klyvion.auth.errors import (
    AuthError,
    GoogleAuthError,
    GoogleNotConfiguredError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserExistsError,
    WeakPasswordError,
)
from klyvion.auth.models import User
from klyvion.auth.service import AuthService

__all__ = [
    "AuthService",
    "User",
    "AuthError",
    "UserExistsError",
    "InvalidCredentialsError",
    "WeakPasswordError",
    "InvalidTokenError",
    "GoogleNotConfiguredError",
    "GoogleAuthError",
    "build_auth_router",
    "current_user_dependency",
]


def __getattr__(name: str):
    # Router wiring imports FastAPI; keep it lazy so `import klyvion.auth`
    # stays cheap and dependency-light for CLI/library callers.
    if name in ("build_auth_router", "current_user_dependency"):
        from klyvion.auth import router

        return getattr(router, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
