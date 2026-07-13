"""Google OAuth 2.0 / OpenID Connect client.

Thin wrapper over Authlib's Starlette integration. It owns the redirect and
callback halves of the authorization-code flow and hands back a verified
profile; turning that profile into a Klyvion :class:`~klyvion.auth.models.User`
is the :class:`~klyvion.auth.service.AuthService`'s job.

The whole class is optional: it is only constructed when both Google
credentials are configured, so the ``authlib`` import is deferred to
construction rather than module import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from klyvion.auth.errors import GoogleAuthError

_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


@dataclass(frozen=True)
class GoogleProfile:
    """The subset of a Google profile Klyvion consumes."""

    subject: str
    email: str
    name: str


class GoogleOAuthClient:
    """Drives the Google authorization-code flow for a FastAPI app.

    Requires Starlette ``SessionMiddleware`` on the app: Authlib stores the
    OAuth ``state`` and OIDC ``nonce`` in the session between redirect and
    callback.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        try:
            from authlib.integrations.starlette_client import OAuth
        except ImportError as exc:  # pragma: no cover - exercised via the extra
            raise ImportError(
                "Google login needs Authlib. Install the server extra: "
                "pip install 'klyvion[server]'."
            ) from exc

        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=_DISCOVERY_URL,
            client_kwargs={"scope": "openid email profile"},
        )
        self._client = oauth.google

    async def redirect(self, request: Any, redirect_uri: str) -> Any:
        """Return a redirect response sending the user to Google's consent screen.

        Args:
            request: the Starlette/FastAPI request (carries the session).
            redirect_uri: the absolute callback URL Google will return to.
        """
        return await self._client.authorize_redirect(request, redirect_uri)

    async def profile(self, request: Any) -> GoogleProfile:
        """Complete the callback and return the verified Google profile.

        Args:
            request: the callback request carrying Google's ``code``/``state``.

        Raises:
            GoogleAuthError: if the token exchange fails or no verified email
                is returned.
        """
        try:
            token = await self._client.authorize_access_token(request)
        except Exception as exc:  # Authlib raises several unrelated types here.
            raise GoogleAuthError(f"Google sign-in failed: {exc}") from exc

        info = token.get("userinfo") or {}
        subject = info.get("sub")
        email = info.get("email", "")
        if not subject:
            raise GoogleAuthError("Google returned no account identifier.")
        if not info.get("email_verified", False):
            raise GoogleAuthError("Google account email is not verified.")
        return GoogleProfile(
            subject=str(subject),
            email=str(email),
            name=str(info.get("name", "") or email),
        )
