"""Payment providers — the extension seam for how credits are bought.

:class:`PaymentProvider` is the abstraction the :class:`~klyvion.billing.service.
BillingService` depends on (dependency inversion). Two implementations ship:

* :class:`StripeProvider` — hosted Stripe Checkout; the production path. In
  development it runs against Stripe *test mode* (``sk_test_...`` keys), where
  card ``4242 4242 4242 4242`` completes a payment without moving real money.
* :class:`FakePaymentProvider` — no network, no Stripe account. Used by the test
  suite and handy for offline local development; it "completes" instantly and
  parses a plain-JSON webhook body.

A new backend (PayPal, Paddle, …) is one more subclass — nothing else changes.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from klyvion.billing.errors import PaymentProviderError, WebhookVerificationError
from klyvion.billing.plans import Plan


@dataclass(frozen=True)
class CheckoutSession:
    """A created checkout the caller redirects the browser to."""

    id: str
    url: str


@dataclass(frozen=True)
class PurchaseEvent:
    """A completed purchase parsed from a provider webhook.

    Attributes:
        username: account to credit (carried through as checkout metadata).
        plan_id: the purchased plan's id.
        credits: token credits to grant.
        reference: provider-side id (checkout session / payment) for logging.
    """

    username: str
    plan_id: str
    credits: int
    reference: str


class PaymentProvider(ABC):
    """Creates checkouts and parses their completion webhooks."""

    @abstractmethod
    def create_checkout(
        self,
        *,
        plan: Plan,
        username: str,
        currency: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        """Start a hosted checkout for ``plan`` on behalf of ``username``."""

    @abstractmethod
    def parse_purchase(self, payload: bytes, signature: str) -> PurchaseEvent | None:
        """Verify a webhook body and return the purchase it describes.

        Returns ``None`` for well-formed but irrelevant events (e.g. anything
        other than a completed checkout), which the caller safely ignores.

        Raises:
            WebhookVerificationError: if the payload fails signature checks.
        """


class StripeProvider(PaymentProvider):
    """Stripe Checkout backend (test mode in dev, live mode in prod)."""

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        try:
            import stripe
        except ImportError as exc:  # pragma: no cover - exercised via server extra
            raise ImportError(
                "Stripe payments need the 'stripe' package. Install the server "
                "extra: pip install 'klyvion[server]'."
            ) from exc
        if not secret_key:
            raise PaymentProviderError("StripeProvider requires a secret key.")
        self._stripe = stripe
        self._secret = secret_key
        self._webhook_secret = webhook_secret

    def create_checkout(
        self,
        *,
        plan: Plan,
        username: str,
        currency: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        metadata = {
            "username": username,
            "plan_id": plan.id,
            "credits": str(plan.credits),
        }
        try:
            session = self._stripe.checkout.Session.create(
                api_key=self._secret,
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=username,
                metadata=metadata,
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": currency,
                            "unit_amount": plan.price_cents,
                            "product_data": {
                                "name": f"Klyvion {plan.name} — "
                                f"{plan.credits:,} credits",
                            },
                        },
                    }
                ],
            )
        except self._stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise PaymentProviderError(f"Stripe rejected the checkout: {exc}") from exc
        return CheckoutSession(id=session["id"], url=session["url"])

    def parse_purchase(self, payload: bytes, signature: str) -> PurchaseEvent | None:
        if not self._webhook_secret:
            raise WebhookVerificationError(
                "No Stripe webhook secret configured; refusing to trust the "
                "payload. Set KLYVION_STRIPE_WEBHOOK_SECRET."
            )
        try:
            event = self._stripe.Webhook.construct_event(
                payload, signature, self._webhook_secret
            )
        except (ValueError, self._stripe.error.SignatureVerificationError) as exc:  # type: ignore[attr-defined]
            raise WebhookVerificationError(
                "Stripe webhook signature verification failed."
            ) from exc
        if event["type"] != "checkout.session.completed":
            return None
        session = event["data"]["object"]
        meta = session.get("metadata") or {}
        return PurchaseEvent(
            username=meta.get("username", ""),
            plan_id=meta.get("plan_id", ""),
            credits=int(meta.get("credits", 0)),
            reference=str(session.get("id", "")),
        )


class FakePaymentProvider(PaymentProvider):
    """In-process provider for tests and offline dev — no Stripe, no network.

    Checkout "URLs" point back at the app's success URL so a manual flow still
    round-trips. Webhooks are trusted plain JSON: post a body of
    ``{"username", "plan_id", "credits"}`` to fulfil a purchase.
    """

    def create_checkout(
        self,
        *,
        plan: Plan,
        username: str,
        currency: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:
        session_id = f"fake_cs_{plan.id}_{username}"
        return CheckoutSession(id=session_id, url=success_url)

    def parse_purchase(self, payload: bytes, signature: str) -> PurchaseEvent | None:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise WebhookVerificationError("Malformed fake webhook body.") from exc
        if not data.get("username"):
            return None
        return PurchaseEvent(
            username=str(data["username"]),
            plan_id=str(data.get("plan_id", "")),
            credits=int(data.get("credits", 0)),
            reference=str(data.get("reference", "fake")),
        )
