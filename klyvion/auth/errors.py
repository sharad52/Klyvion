"""Typed errors for the authentication subsystem.

Every failure a caller might reasonably branch on has its own class so the
API layer can map it to the right HTTP status with an actionable message,
instead of catching bare ``ValueError`` and guessing.
"""

from __future__ import annotations


class AuthError(Exception):
    """Base class for all authentication failures."""


class UserExistsError(AuthError):
    """Raised when registering a username that is already taken."""


class InvalidCredentialsError(AuthError):
    """Raised when a username/password pair does not match a stored user."""


class WeakPasswordError(AuthError):
    """Raised when a chosen password fails the minimum policy."""


class InvalidTokenError(AuthError):
    """Raised when a session token is missing, malformed or expired."""


class GoogleNotConfiguredError(AuthError):
    """Raised when a Google OAuth flow is attempted without credentials."""


class GoogleAuthError(AuthError):
    """Raised when the Google OAuth exchange fails or returns no identity."""
