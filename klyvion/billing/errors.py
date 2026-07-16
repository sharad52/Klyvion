"""Typed errors for the billing subsystem.

Each failure the API layer maps to a distinct HTTP status has its own class, so
the router branches on the type rather than parsing messages — mirroring
:mod:`klyvion.auth.errors`.
"""

from __future__ import annotations


class BillingError(Exception):
    """Base class for all billing failures."""


class BillingDisabledError(BillingError):
    """Raised when a billing action is attempted while billing is disabled."""


class PlanNotFoundError(BillingError):
    """Raised when a requested plan id does not exist or is not purchasable."""


class InsufficientCreditsError(BillingError):
    """Raised when an account lacks the credits a synthesis would cost."""


class PaymentProviderError(BillingError):
    """Raised when the payment provider is unavailable or rejects a request."""


class WebhookVerificationError(BillingError):
    """Raised when a webhook payload fails signature verification."""
