"""FastAPI wiring for billing.

Exposes a router factory (:func:`build_billing_router`) mounting the ``/billing``
endpoints: a public capability/plan probe, an authenticated checkout starter,
and the payment-provider webhook that credits accounts.
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from klyvion.auth.models import User
from klyvion.billing.errors import (
    PaymentProviderError,
    PlanNotFoundError,
    WebhookVerificationError,
)
from klyvion.billing.service import BillingService
from klyvion.config import Settings

#: Query flags the UI reads on the post-checkout redirect back to the app.
_SUCCESS_FLAG = "purchase=success"
_CANCEL_FLAG = "purchase=cancelled"


class CheckoutRequest(BaseModel):
    """Body for ``POST /billing/checkout``."""

    plan_id: str = Field(..., min_length=1, max_length=64)


def build_billing_router(
    service: BillingService,
    settings: Settings,
    get_current_user: Callable[[Request], User],
) -> APIRouter:
    """Build the ``/billing`` router.

    Args:
        service: the billing facade.
        settings: process settings (currency, public base URL, Stripe key).
        get_current_user: the auth dependency gating the checkout endpoint, so
            billing need not import auth internals.
    """
    router = APIRouter(prefix="/billing", tags=["billing"])

    @router.get("/config")
    def billing_config() -> dict:
        """Public probe so the UI knows whether to show credits and buy buttons."""
        return {
            "billing_enabled": service.enabled,
            "purchase_enabled": service.purchase_enabled,
            "currency": service.currency,
            "tokens_per_char": service.tokens_per_char,
            "publishable_key": settings.stripe_publishable_key,
        }

    @router.get("/plans")
    def list_plans() -> list[dict]:
        """List the advertised plans. Open to everyone."""
        return [plan.public_view(service.currency) for plan in service.plans()]

    @router.post("/checkout")
    def create_checkout(body: CheckoutRequest, request: Request) -> dict:
        """Start a hosted checkout and return its redirect URL. Login required."""
        user = get_current_user(request)
        base = settings.public_base_url or str(request.base_url).rstrip("/")
        try:
            session = service.create_checkout(
                user,
                body.plan_id,
                success_url=f"{base}/?{_SUCCESS_FLAG}",
                cancel_url=f"{base}/?{_CANCEL_FLAG}",
            )
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PaymentProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"checkout_url": session.url, "checkout_id": session.id}

    @router.post("/webhook")
    async def webhook(request: Request) -> dict:
        """Payment-provider callback that credits the buyer's account."""
        payload = await request.body()
        signature = request.headers.get("stripe-signature", "")
        try:
            event = service.handle_webhook(payload, signature)
        except WebhookVerificationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PaymentProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True, "credited": event.credits if event else 0}

    return router
