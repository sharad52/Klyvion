"""Session tokens.

Issues and verifies the signed JWT that rides in the ``klyvion_session``
cookie. The token carries only the username; the full user is re-read from the
store on each request so a token never outruns the account behind it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    import jwt
except ImportError as exc:  # pragma: no cover - exercised via the auth extra
    raise ImportError(
        "Session tokens need PyJWT. Install the server extra: "
        "pip install 'klyvion[server]'."
    ) from exc

from klyvion.auth.errors import InvalidTokenError

_ALGORITHM = "HS256"


class TokenService:
    """Signs and verifies stateless session tokens (HS256 JWT)."""

    def __init__(self, secret_key: str, ttl_hours: int = 168) -> None:
        """Initialise the service.

        Args:
            secret_key: HMAC signing secret. Must be stable across restarts
                for sessions to persist.
            ttl_hours: how long an issued token stays valid.
        """
        if not secret_key:
            raise ValueError("TokenService requires a non-empty secret key.")
        self._secret = secret_key
        self._ttl = timedelta(hours=ttl_hours)

    def issue(self, username: str) -> str:
        """Return a signed token identifying ``username``."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def subject(self, token: str) -> str:
        """Return the username encoded in ``token``.

        Raises:
            InvalidTokenError: if the token is missing, malformed, expired or
                signed with the wrong key.
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("Session token is invalid or expired.") from exc
        subject = payload.get("sub")
        if not subject:
            raise InvalidTokenError("Session token has no subject.")
        return str(subject)
