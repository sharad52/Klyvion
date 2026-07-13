"""FastAPI wiring for authentication.

Exposes a router factory (:func:`build_auth_router`) and a dependency factory
(:func:`current_user_dependency`) so the API server can mount the ``/auth``
endpoints and gate protected routes without importing auth internals.

The session token rides in a ``HttpOnly`` cookie: it survives the Google
redirect round-trip and is never readable by page scripts.
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

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
from klyvion.config import Settings

#: Name of the HttpOnly cookie carrying the signed session token.
COOKIE_NAME = "klyvion_session"

#: Where the Google callback returns to once a session is established.
_POST_LOGIN_REDIRECT = "/"


class RegisterRequest(BaseModel):
    """Body for ``POST /auth/register``."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginRequest(BaseModel):
    """Body for ``POST /auth/login``."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


def current_user_dependency(service: AuthService) -> Callable[[Request], User]:
    """Return a FastAPI dependency that resolves the logged-in user.

    The returned dependency reads the session cookie and returns the live
    :class:`User`, or raises ``401`` if the caller is not authenticated. Use it
    to gate any protected route (e.g. downloads).
    """

    def get_current_user(request: Request) -> User:
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            raise HTTPException(
                status_code=401, detail="Log in to download generated audio."
            )
        try:
            return service.user_from_token(token)
        except (InvalidTokenError, InvalidCredentialsError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    return get_current_user


def build_auth_router(service: AuthService, settings: Settings) -> APIRouter:
    """Build the ``/auth`` router bound to ``service`` and ``settings``."""
    router = APIRouter(prefix="/auth", tags=["auth"])
    get_current_user = current_user_dependency(service)

    def _login_response(user: User, request: Request, response: Response) -> dict:
        _set_session_cookie(response, service.issue_token(user), request, settings)
        return {"user": user.public_view()}

    @router.get("/config")
    def auth_config() -> dict:
        """Public capability probe so the UI knows which options to show."""
        return {"google_enabled": service.google_enabled}

    @router.get("/me")
    def me(user: User = Depends(get_current_user)) -> dict:
        return {"user": user.public_view()}

    @router.post("/register")
    def register(body: RegisterRequest, request: Request, response: Response) -> dict:
        try:
            user = service.register(body.username, body.password)
        except UserExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except WeakPasswordError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _login_response(user, request, response)

    @router.post("/login")
    def login(body: LoginRequest, request: Request, response: Response) -> dict:
        try:
            user = service.login(body.username, body.password)
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return _login_response(user, request, response)

    @router.post("/logout")
    def logout(response: Response) -> dict:
        response.delete_cookie(COOKIE_NAME, samesite="lax")
        return {"ok": True}

    @router.get("/google/login")
    async def google_login(request: Request):
        try:
            client = service.google_client()
        except GoogleNotConfiguredError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        redirect_uri = _google_redirect_uri(request, settings)
        return await client.redirect(request, redirect_uri)

    @router.get("/google/callback")
    async def google_callback(request: Request):
        try:
            client = service.google_client()
            profile = await client.profile(request)
            user = service.authenticate_google(profile)
        except GoogleNotConfiguredError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (GoogleAuthError, AuthError) as exc:
            # Send the user back to the UI with a readable reason.
            return RedirectResponse(
                url=f"{_POST_LOGIN_REDIRECT}?auth_error={_quote(str(exc))}",
                status_code=303,
            )
        response = RedirectResponse(url=_POST_LOGIN_REDIRECT, status_code=303)
        _set_session_cookie(response, service.issue_token(user), request, settings)
        return response

    return router


# ---------------------------------------------------------------------- #


def _set_session_cookie(
    response: Response, token: str, request: Request, settings: Settings
) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.token_ttl_hours * 3600,
        httponly=True,
        secure=_is_secure(request, settings),
        samesite="lax",
        path="/",
    )


def _is_secure(request: Request, settings: Settings) -> bool:
    if settings.public_base_url.startswith("https://"):
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded == "https"


def _google_redirect_uri(request: Request, settings: Settings) -> str:
    base = settings.public_base_url or str(request.base_url).rstrip("/")
    return f"{base}/auth/google/callback"


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text[:200])
