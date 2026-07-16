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
        plan: identifier of the last plan the user was granted ("free",
            "standard", "premium"). Purely informational; entitlement is the
            ``credits`` balance, not the plan name.
        credits: remaining token-credit balance. Only meaningful when billing
            is enabled; each synthesized character debits ``tokens_per_char``.
    """

    username: str
    provider: str = "local"
    password_hash: str | None = None
    email: str = ""
    display_name: str = ""
    plan: str = "free"
    credits: int = 0

    @property
    def public_name(self) -> str:
        """Name safe to show in the UI."""
        return self.display_name or self.username

    def public_view(self) -> dict[str, object]:
        """Serialise the non-secret fields for API responses."""
        return {
            "username": self.username,
            "provider": self.provider,
            "email": self.email,
            "display_name": self.public_name,
            "plan": self.plan,
            "credits": self.credits,
        }
