"""Central configuration for Klyvion.

All paths and engine choices live here so the CLI, the Python API and the
HTTP server share one source of truth. Values can be overridden with
environment variables prefixed with ``KLYVION_``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"KLYVION_{name}", default)


@dataclass
class Settings:
    """Runtime settings.

    Attributes:
        engine: "xtts" (neural, supports cloning) or "pyttsx3"
            (lightweight offline fallback, no cloning).
        data_dir: where cloned-voice samples and metadata are stored.
        output_dir: default directory for synthesized audio.
        sample_rate: output sample rate in Hz.
        device: "auto", "cpu" or "cuda".
        language: default language code for the neural engine.
        secret_key: HMAC secret used to sign session tokens. If empty, the
            server generates an ephemeral key at startup (sessions will not
            survive a restart) and logs a warning.
        google_client_id: OAuth 2.0 client ID for "Log in with Google". When
            either Google credential is empty, Google login is disabled and the
            web UI hides its button.
        google_client_secret: OAuth 2.0 client secret paired with
            ``google_client_id``.
        token_ttl_hours: lifetime of an issued session token, in hours.
        public_base_url: externally reachable base URL (e.g.
            ``https://klyvion.example.com``) used to build the Google OAuth
            redirect URI. If empty, it is derived from the incoming request.
        billing_enabled: master switch for the token-credit system. When
            ``False`` (the default), synthesis is open and unmetered exactly as
            before. When ``True``, every synthesis requires a logged-in user
            and debits credits, and out-of-credit callers get HTTP 402.
        signup_credits: credits granted to a brand-new account on registration.
        tokens_per_char: credits charged per character of synthesized text.
        stripe_secret_key: Stripe API secret (``sk_test_...`` in development,
            ``sk_live_...`` in production). When empty, purchasing is disabled
            and the UI hides its buy buttons even if billing is enabled.
        stripe_publishable_key: Stripe publishable key exposed to the browser.
        stripe_webhook_secret: signing secret used to verify Stripe webhook
            payloads (``whsec_...``). Obtain it from the Stripe dashboard or
            from ``stripe listen`` during local development.
        currency: ISO currency code used for checkout, e.g. ``usd``.
    """

    engine: str = field(default_factory=lambda: _env("ENGINE", "xtts"))
    data_dir: Path = field(
        default_factory=lambda: Path(_env("DATA_DIR", "~/.klyvion")).expanduser()
    )
    output_dir: Path = field(
        default_factory=lambda: Path(_env("OUTPUT_DIR", "./outputs")).expanduser()
    )
    sample_rate: int = field(default_factory=lambda: int(_env("SAMPLE_RATE", "24000")))
    device: str = field(default_factory=lambda: _env("DEVICE", "auto"))
    language: str = field(default_factory=lambda: _env("LANGUAGE", "en"))
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", ""))
    google_client_id: str = field(default_factory=lambda: _env("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(
        default_factory=lambda: _env("GOOGLE_CLIENT_SECRET", "")
    )
    token_ttl_hours: int = field(
        default_factory=lambda: int(_env("TOKEN_TTL_HOURS", "168"))
    )
    public_base_url: str = field(
        default_factory=lambda: _env("PUBLIC_BASE_URL", "").rstrip("/")
    )
    billing_enabled: bool = field(
        default_factory=lambda: _env("BILLING_ENABLED", "0") == "1"
    )
    signup_credits: int = field(
        default_factory=lambda: int(_env("SIGNUP_CREDITS", "5000"))
    )
    tokens_per_char: int = field(
        default_factory=lambda: int(_env("TOKENS_PER_CHAR", "1"))
    )
    stripe_secret_key: str = field(
        default_factory=lambda: _env("STRIPE_SECRET_KEY", "")
    )
    stripe_publishable_key: str = field(
        default_factory=lambda: _env("STRIPE_PUBLISHABLE_KEY", "")
    )
    stripe_webhook_secret: str = field(
        default_factory=lambda: _env("STRIPE_WEBHOOK_SECRET", "")
    )
    currency: str = field(default_factory=lambda: _env("CURRENCY", "usd").lower())

    @property
    def stripe_enabled(self) -> bool:
        """True when a Stripe secret key is configured (purchasing is live)."""
        return bool(self.stripe_secret_key)

    @property
    def voices_dir(self) -> Path:
        return self.data_dir / "voices"

    @property
    def users_file(self) -> Path:
        """JSON file where local-account and linked-Google users persist."""
        return self.data_dir / "users.json"

    @property
    def google_enabled(self) -> bool:
        """True when both Google OAuth credentials are configured."""
        return bool(self.google_client_id and self.google_client_secret)

    def ensure_dirs(self) -> None:
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a process-wide singleton of :class:`Settings`."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
