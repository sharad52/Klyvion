"""Authentication service — the facade over the auth subsystem.

The API layer talks only to :class:`AuthService`; it never touches the store,
hasher, token signer or Google client directly. Collaborators are injected
through the constructor (dependency inversion), and :meth:`from_settings`
wires the default production graph from :class:`~klyvion.config.Settings`.
"""

from __future__ import annotations

import logging
import secrets

from klyvion.auth.errors import (
    GoogleNotConfiguredError,
    InvalidCredentialsError,
    UserExistsError,
    WeakPasswordError,
)
from klyvion.auth.google import GoogleOAuthClient, GoogleProfile
from klyvion.auth.models import User
from klyvion.auth.passwords import MAX_PASSWORD_BYTES, PasswordHasher
from klyvion.auth.store import JsonUserStore, UserStore
from klyvion.auth.tokens import TokenService
from klyvion.config import Settings

logger = logging.getLogger(__name__)

#: Minimum acceptable password length, in characters.
MIN_PASSWORD_LENGTH = 8


class AuthService:
    """Coordinates account creation, login and token issuance."""

    def __init__(
        self,
        store: UserStore,
        hasher: PasswordHasher,
        tokens: TokenService,
        google: GoogleOAuthClient | None = None,
        signup_credits: int = 0,
    ) -> None:
        self._store = store
        self._hasher = hasher
        self._tokens = tokens
        self._google = google
        self._signup_credits = signup_credits

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        secret_key: str,
        store: UserStore | None = None,
    ) -> "AuthService":
        """Build the default service graph from ``settings``.

        Args:
            settings: process settings (users file location, Google creds, TTL).
            secret_key: resolved HMAC secret for signing session tokens. The
                caller resolves it (and warns on an ephemeral one) so the same
                secret can also seed the session middleware.
            store: an optional pre-built user store. Pass a shared instance so
                the billing service mutates the *same* store (and lock);
                defaults to a :class:`JsonUserStore` over ``settings.users_file``.
        """
        google: GoogleOAuthClient | None = None
        if settings.google_enabled:
            google = GoogleOAuthClient(
                settings.google_client_id, settings.google_client_secret
            )
        return cls(
            store=store or JsonUserStore(settings.users_file),
            hasher=PasswordHasher(),
            tokens=TokenService(secret_key, ttl_hours=settings.token_ttl_hours),
            google=google,
            signup_credits=settings.signup_credits,
        )

    @property
    def store(self) -> UserStore:
        """The backing user store (shared with the billing service)."""
        return self._store

    # ------------------------------------------------------------------ #
    # Local accounts

    def register(self, username: str, password: str) -> User:
        """Create a local account and return it.

        Raises:
            WeakPasswordError: if the password fails the length policy.
            UserExistsError: if the username is already taken.
        """
        username = self._normalize_username(username)
        self._check_password(password)
        if self._store.get(username) is not None:
            raise UserExistsError(
                f"Username '{username}' is taken. Choose another or log in."
            )
        user = User(
            username=username,
            provider="local",
            password_hash=self._hasher.hash(password),
            credits=self._signup_credits,
        )
        self._store.save(user)
        logger.info(
            "Registered local user '%s' with %d starter credits.",
            username,
            self._signup_credits,
        )
        return user

    def login(self, username: str, password: str) -> User:
        """Verify credentials and return the user.

        Raises:
            InvalidCredentialsError: if no such local user exists or the
                password does not match.
        """
        username = self._normalize_username(username)
        user = self._store.get(username)
        if (
            user is None
            or user.provider != "local"
            or user.password_hash is None
            or not self._hasher.verify(password, user.password_hash)
        ):
            raise InvalidCredentialsError("Incorrect username or password.")
        return user

    # ------------------------------------------------------------------ #
    # Google accounts

    @property
    def google_enabled(self) -> bool:
        """True when Google login is configured on this instance."""
        return self._google is not None

    def google_client(self) -> GoogleOAuthClient:
        """Return the Google client, or raise if Google login is disabled."""
        if self._google is None:
            raise GoogleNotConfiguredError(
                "Google login is not configured on this server."
            )
        return self._google

    def authenticate_google(self, profile: GoogleProfile) -> User:
        """Upsert a Google-backed user from a verified profile and return it.

        Raises:
            UserExistsError: if a *local* account already owns the username.
        """
        username = self._normalize_username(profile.email or profile.subject)
        existing = self._store.get(username)
        if existing is not None and existing.provider != "google":
            raise UserExistsError(
                f"'{username}' already has a password account. "
                "Log in with your password instead."
            )
        # Preserve a returning user's balance and plan; only a first-time login
        # is granted the starter credits.
        user = User(
            username=username,
            provider="google",
            password_hash=None,
            email=profile.email,
            display_name=profile.name,
            plan=existing.plan if existing else "free",
            credits=existing.credits if existing else self._signup_credits,
        )
        self._store.save(user)
        logger.info("Authenticated Google user '%s'.", username)
        return user

    # ------------------------------------------------------------------ #
    # Tokens

    def issue_token(self, user: User) -> str:
        """Return a signed session token for ``user``."""
        return self._tokens.issue(user.username)

    def user_from_token(self, token: str) -> User:
        """Resolve a session token back to its live user.

        Raises:
            InvalidTokenError: if the token is invalid or expired.
            InvalidCredentialsError: if the token is valid but the account no
                longer exists.
        """
        username = self._tokens.subject(token)
        user = self._store.get(username)
        if user is None:
            raise InvalidCredentialsError("Account no longer exists.")
        return user

    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_username(username: str) -> str:
        cleaned = (username or "").strip().lower()
        if not cleaned:
            raise InvalidCredentialsError("Username must not be empty.")
        return cleaned

    @staticmethod
    def _check_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise WeakPasswordError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise WeakPasswordError(
                f"Password must be at most {MAX_PASSWORD_BYTES} bytes long."
            )

    @staticmethod
    def generate_secret() -> str:
        """Return a fresh random secret (for ephemeral, restart-scoped use)."""
        return secrets.token_urlsafe(48)
