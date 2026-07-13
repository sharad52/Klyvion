"""Value objects for authenticated users."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """A registered account.

    A user signs in either with a local username/password (``provider ==
    "local"``, ``password_hash`` set) or via Google (``provider == "google"``,
    ``password_hash`` is ``None`` and ``email``/``display_name`` come from the
    Google profile).

    Attributes:
        username: unique, case-insensitive identifier used for login.
        provider: "local" or "google".
        password_hash: bcrypt hash for local accounts; ``None`` for Google.
        email: verified email address (Google accounts) or empty.
        display_name: friendly name shown in the UI; falls back to username.
    """

    username: str
    provider: str = "local"
    password_hash: str | None = None
    email: str = ""
    display_name: str = ""

    @property
    def public_name(self) -> str:
        """Name safe to show in the UI."""
        return self.display_name or self.username

    def public_view(self) -> dict[str, str]:
        """Serialise the non-secret fields for API responses."""
        return {
            "username": self.username,
            "provider": self.provider,
            "email": self.email,
            "display_name": self.public_name,
        }
