"""Credit plans and the catalog that holds them.

A :class:`Plan` is an immutable value object: a named bundle of token credits at
a fixed price. The :class:`PlanCatalog` is the lookup seam — the shipped default
offers *free* (the signup grant), *standard* and *premium*, but a deployment can
build a catalog with different tiers without touching the service.
"""

from __future__ import annotations

from dataclasses import dataclass

from klyvion.billing.errors import PlanNotFoundError

#: Shipped tier definitions: (id, name, credits, price in cents). ``free`` is the
#: signup grant and is never purchasable (price 0); its credit figure is filled
#: in from the configured signup grant when the catalog is built.
_STANDARD_CREDITS = 50_000
_STANDARD_PRICE_CENTS = 900
_PREMIUM_CREDITS = 200_000
_PREMIUM_PRICE_CENTS = 2_900


@dataclass(frozen=True)
class Plan:
    """A purchasable (or free) bundle of token credits.

    Attributes:
        id: stable identifier ("free", "standard", "premium").
        name: human-readable label shown in the UI.
        credits: token credits this plan grants on purchase.
        price_cents: one-time price in the smallest currency unit (0 = free).
        description: short marketing line for the UI.
    """

    id: str
    name: str
    credits: int
    price_cents: int
    description: str

    @property
    def is_free(self) -> bool:
        """True for a zero-price plan (the signup grant), which cannot be bought."""
        return self.price_cents <= 0

    def price_display(self, currency: str) -> str:
        """Return a human price like ``$9.00`` (uppercased currency fallback)."""
        symbol = {"usd": "$", "eur": "€", "gbp": "£"}.get(currency.lower())
        amount = f"{self.price_cents / 100:.2f}"
        return f"{symbol}{amount}" if symbol else f"{amount} {currency.upper()}"

    def public_view(self, currency: str) -> dict[str, object]:
        """Serialise for the ``/billing/plans`` response."""
        return {
            "id": self.id,
            "name": self.name,
            "credits": self.credits,
            "price_cents": self.price_cents,
            "price_display": self.price_display(currency),
            "is_free": self.is_free,
            "description": self.description,
        }


class PlanCatalog:
    """An ordered collection of plans, looked up by id."""

    def __init__(self, plans: list[Plan]) -> None:
        self._plans = {plan.id: plan for plan in plans}

    @classmethod
    def default(cls, signup_credits: int) -> "PlanCatalog":
        """Build the shipped three-tier catalog.

        Args:
            signup_credits: credits the free tier advertises, matching the grant
                a new account receives at registration.
        """
        return cls(
            [
                Plan(
                    id="free",
                    name="Free",
                    credits=signup_credits,
                    price_cents=0,
                    description="Starter credits on sign-up. No card required.",
                ),
                Plan(
                    id="standard",
                    name="Standard",
                    credits=_STANDARD_CREDITS,
                    price_cents=_STANDARD_PRICE_CENTS,
                    description="A top-up for regular use.",
                ),
                Plan(
                    id="premium",
                    name="Premium",
                    credits=_PREMIUM_CREDITS,
                    price_cents=_PREMIUM_PRICE_CENTS,
                    description="Best value for heavy synthesis.",
                ),
            ]
        )

    def get(self, plan_id: str) -> Plan:
        """Return the plan with ``plan_id``.

        Raises:
            PlanNotFoundError: if no plan has that id.
        """
        plan = self._plans.get(plan_id)
        if plan is None:
            raise PlanNotFoundError(
                f"Unknown plan '{plan_id}'. "
                f"Choose one of: {', '.join(self._plans)}."
            )
        return plan

    def all(self) -> list[Plan]:
        """Return every plan, in insertion order."""
        return list(self._plans.values())

    def purchasable(self) -> list[Plan]:
        """Return only the plans a user can actually buy (price > 0)."""
        return [plan for plan in self._plans.values() if not plan.is_free]
