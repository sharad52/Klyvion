"""Billing subsystem: token credits and plan purchases.

Public surface:
    - :class:`BillingService` — the facade the API talks to.
    - :class:`Plan` / :class:`PlanCatalog` — the tier value objects.
    - :class:`PaymentProvider` and its :class:`StripeProvider` /
      :class:`FakePaymentProvider` implementations — the payment seam.
    - :func:`build_billing_router` — FastAPI wiring.
    - The :class:`BillingError` hierarchy for typed failures.

Concrete Stripe support pulls in the optional ``stripe`` dependency lazily, so
importing this package stays cheap for CLI/library callers who never bill.
"""

from __future__ import annotations

from klyvion.billing.errors import (
    BillingDisabledError,
    BillingError,
    InsufficientCreditsError,
    PaymentProviderError,
    PlanNotFoundError,
    WebhookVerificationError,
)
from klyvion.billing.plans import Plan, PlanCatalog
from klyvion.billing.provider import (
    CheckoutSession,
    FakePaymentProvider,
    PaymentProvider,
    PurchaseEvent,
    StripeProvider,
)
from klyvion.billing.service import BillingService

__all__ = [
    "BillingService",
    "Plan",
    "PlanCatalog",
    "PaymentProvider",
    "StripeProvider",
    "FakePaymentProvider",
    "CheckoutSession",
    "PurchaseEvent",
    "BillingError",
    "BillingDisabledError",
    "PlanNotFoundError",
    "InsufficientCreditsError",
    "PaymentProviderError",
    "WebhookVerificationError",
    "build_billing_router",
]


def __getattr__(name: str):
    # Router wiring imports FastAPI; keep it lazy like klyvion.auth does.
    if name == "build_billing_router":
        from klyvion.billing import router

        return router.build_billing_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
