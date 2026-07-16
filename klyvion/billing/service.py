"""Billing service — the facade the API talks to for credits and purchases.

Like :class:`~klyvion.auth.service.AuthService`, the router never touches the
store, catalog or payment provider directly: it calls this facade, whose
collaborators are injected. :meth:`from_settings` wires the production graph.

The service shares the *same* :class:`~klyvion.auth.store.UserStore` instance as
the auth service so credit mutations and account writes serialise on one lock.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from klyvion.auth.models import User
from klyvion.auth.store import JsonUserStore, UserStore
from klyvion.billing.errors import (
    InsufficientCreditsError,
    PaymentProviderError,
    PlanNotFoundError,
)
from klyvion.billing.plans import Plan, PlanCatalog
from klyvion.billing.provider import (
    CheckoutSession,
    PaymentProvider,
    PurchaseEvent,
    StripeProvider,
)
from klyvion.config import Settings

logger = logging.getLogger(__name__)


class BillingService:
    """Coordinates credit accounting and plan purchases."""

    def __init__(
        self,
        store: UserStore,
        catalog: PlanCatalog,
        provider: PaymentProvider | None,
        *,
        enabled: bool,
        tokens_per_char: int,
        currency: str,
    ) -> None:
        self._store = store
        self._catalog = catalog
        self._provider = provider
        self._enabled = enabled
        self._tokens_per_char = max(1, tokens_per_char)
        self._currency = currency

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        store: UserStore | None = None,
        provider: PaymentProvider | None = None,
    ) -> "BillingService":
        """Build the default service graph from ``settings``.

        Args:
            settings: process settings (billing switch, credit rate, Stripe).
            store: shared user store; defaults to one over ``settings.users_file``.
            provider: payment provider; defaults to a :class:`StripeProvider`
                when a Stripe secret key is configured, else ``None`` (billing
                may still meter credits without a way to buy more).
        """
        if provider is None and settings.stripe_enabled:
            provider = StripeProvider(
                settings.stripe_secret_key, settings.stripe_webhook_secret
            )
        return cls(
            store=store or JsonUserStore(settings.users_file),
            catalog=PlanCatalog.default(settings.signup_credits),
            provider=provider,
            enabled=settings.billing_enabled,
            tokens_per_char=settings.tokens_per_char,
            currency=settings.currency,
        )

    # ------------------------------------------------------------------ #
    # Capability probes

    @property
    def enabled(self) -> bool:
        """True when credit metering is switched on for this instance."""
        return self._enabled

    @property
    def purchase_enabled(self) -> bool:
        """True when a payment provider is wired up (users can buy credits)."""
        return self._provider is not None

    @property
    def currency(self) -> str:
        return self._currency

    def plans(self) -> list[Plan]:
        """Return every advertised plan."""
        return self._catalog.all()

    # ------------------------------------------------------------------ #
    # Credit accounting

    def cost_of(self, text: str) -> int:
        """Return the credit cost of synthesizing ``text`` (minimum 1)."""
        return max(1, len(text) * self._tokens_per_char)

    def debit(self, user: User, cost: int) -> User:
        """Atomically subtract ``cost`` credits and return the updated user.

        Raises:
            InsufficientCreditsError: if the balance would go negative; nothing
                is written in that case.
            KeyError: if the account no longer exists.
        """

        def mutator(current: User) -> User:
            if current.credits < cost:
                raise InsufficientCreditsError(
                    f"This needs {cost} credits but you have "
                    f"{current.credits}. Buy more to continue."
                )
            return replace(current, credits=current.credits - cost)

        return self._store.atomic_update(user.username, mutator)

    def refund(self, user: User, amount: int) -> User:
        """Return ``amount`` credits to ``user`` (used when synthesis fails)."""

        def mutator(current: User) -> User:
            return replace(current, credits=current.credits + amount)

        return self._store.atomic_update(user.username, mutator)

    # ------------------------------------------------------------------ #
    # Purchases

    def create_checkout(
        self, user: User, plan_id: str, *, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        """Start a checkout for ``plan_id`` on behalf of ``user``.

        Raises:
            PaymentProviderError: if no payment provider is configured.
            PlanNotFoundError: if the plan is unknown or is the free tier.
        """
        if self._provider is None:
            raise PaymentProviderError("Payments are not configured on this server.")
        plan = self._catalog.get(plan_id)
        if plan.is_free:
            raise PlanNotFoundError("The free plan cannot be purchased.")
        return self._provider.create_checkout(
            plan=plan,
            username=user.username,
            currency=self._currency,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    def handle_webhook(self, payload: bytes, signature: str) -> PurchaseEvent | None:
        """Verify a provider webhook and fulfil the purchase it describes.

        Returns the fulfilled :class:`PurchaseEvent`, or ``None`` for events
        that carry no purchase to apply.

        Raises:
            PaymentProviderError: if no payment provider is configured.
            WebhookVerificationError: if the payload fails verification.
        """
        if self._provider is None:
            raise PaymentProviderError("Payments are not configured on this server.")
        event = self._provider.parse_purchase(payload, signature)
        if event is None:
            return None
        self._fulfil(event)
        return event

    def _fulfil(self, event: PurchaseEvent) -> None:
        def mutator(current: User) -> User:
            return replace(
                current,
                credits=current.credits + event.credits,
                plan=event.plan_id or current.plan,
            )

        try:
            self._store.atomic_update(event.username, mutator)
        except KeyError:
            logger.warning(
                "Purchase %s credited no account: user '%s' not found.",
                event.reference,
                event.username,
            )
            return
        logger.info(
            "Granted %d credits to '%s' (plan '%s', ref %s).",
            event.credits,
            event.username,
            event.plan_id,
            event.reference,
        )
