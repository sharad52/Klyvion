"""Password hashing.

Isolates the bcrypt dependency behind a small collaborator so the rest of the
auth code depends on the :class:`PasswordHasher` abstraction, not on bcrypt.
"""

from __future__ import annotations

try:
    import bcrypt
except ImportError as exc:  # pragma: no cover - exercised via the auth extra
    raise ImportError(
        "Password hashing needs bcrypt. Install the server extra: "
        "pip install 'klyvion[server]'."
    ) from exc

#: bcrypt hashes at most 72 bytes of input; longer passwords are rejected at
#: the service boundary rather than silently truncated.
MAX_PASSWORD_BYTES = 72


class PasswordHasher:
    """Hashes and verifies passwords with bcrypt."""

    def hash(self, password: str) -> str:
        """Return a bcrypt hash of ``password``.

        Args:
            password: the plaintext password (already length-validated).

        Returns:
            The bcrypt hash as an ASCII string, safe to persist.
        """
        salt = bcrypt.gensalt()
        digest = bcrypt.hashpw(password.encode("utf-8"), salt)
        return digest.decode("ascii")

    def verify(self, password: str, hashed: str) -> bool:
        """Return True if ``password`` matches the stored ``hashed`` value."""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
        except ValueError:
            # Malformed stored hash — treat as a non-match rather than crash.
            return False
