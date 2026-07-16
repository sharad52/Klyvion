"""Token-credit + billing tests.

Billing is off by default (the open, unmetered behaviour the other tests rely
on). With it enabled, synthesis requires a login and debits credits, running
out returns HTTP 402, and a fake payment webhook tops the balance back up.

These run against the FastAPI app with a FakeEngine and a
:class:`FakePaymentProvider` — no model download, no Stripe account — and skip
cleanly when the ``server`` extra is not installed.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jwt")
pytest.importorskip("bcrypt")

from fastapi.testclient import TestClient  # noqa: E402

from klyvion.api.server import create_app  # noqa: E402
from klyvion.auth.store import JsonUserStore  # noqa: E402
from klyvion.billing import BillingService, FakePaymentProvider  # noqa: E402
from klyvion.config import Settings  # noqa: E402
from klyvion.core import Klyvion  # noqa: E402
from tests.test_klyvion import FakeEngine  # noqa: E402

GOOD_PASSWORD = "hunter2secret"
SIGNUP_CREDITS = 20


def _build_app(tmp_path, *, billing_enabled: bool, with_provider: bool = True):
    settings = Settings(
        engine="fake",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "out",
        secret_key="test-secret-key-that-is-at-least-32-bytes-long",
        billing_enabled=billing_enabled,
        signup_credits=SIGNUP_CREDITS,
        tokens_per_char=1,
    )
    settings.ensure_dirs()
    tts = Klyvion(settings)
    tts._engine = FakeEngine()
    store = JsonUserStore(settings.users_file)
    provider = FakePaymentProvider() if with_provider else None
    billing = BillingService.from_settings(settings, store=store, provider=provider)
    return create_app(tts, billing=billing)


@pytest.fixture
def metered(tmp_path):
    """A billing-enabled app with a fake payment provider."""
    return _build_app(tmp_path, billing_enabled=True)


@pytest.fixture
def open_app(tmp_path):
    """A billing-disabled app (the default, open behaviour)."""
    return _build_app(tmp_path, billing_enabled=False)


def _register(client, username="sharad"):
    res = client.post(
        "/auth/register", json={"username": username, "password": GOOD_PASSWORD}
    )
    assert res.status_code == 200, res.text
    return res.json()["user"]


# --------------------------------------------------------------------- #
# Billing off = unchanged open behaviour


def test_billing_off_synthesis_is_open_and_unmetered(open_app):
    res = TestClient(open_app).post(
        "/synthesize", json={"text": "Hello", "voice": "man"}
    )
    assert res.status_code == 200, res.text
    assert "credits_remaining" not in res.json()


def test_billing_config_reports_disabled(open_app):
    cfg = TestClient(open_app).get("/billing/config").json()
    assert cfg["billing_enabled"] is False


# --------------------------------------------------------------------- #
# Signup grant


def test_new_account_receives_signup_credits(metered):
    client = TestClient(metered)
    user = _register(client)
    assert user["credits"] == SIGNUP_CREDITS
    assert user["plan"] == "free"
    assert user["credits_used"] == 0
    assert user["credits_granted"] == SIGNUP_CREDITS


def test_pre_billing_account_is_backfilled_on_login(tmp_path):
    """An account created before the credit fields existed gets granted once."""
    app = _build_app(tmp_path, billing_enabled=True)
    _register(TestClient(app), "legacy")

    # Simulate a legacy record: drop the credit fields from users.json.
    users_file = tmp_path / "data" / "users.json"
    data = json.loads(users_file.read_text())
    for key in ("credits", "credits_used", "credits_granted", "plan"):
        data["legacy"].pop(key, None)
    users_file.write_text(json.dumps(data))

    fresh = TestClient(app)
    login = fresh.post(
        "/auth/login", json={"username": "legacy", "password": GOOD_PASSWORD}
    )
    assert login.status_code == 200, login.text
    me = fresh.get("/auth/me").json()["user"]
    assert me["credits"] == SIGNUP_CREDITS
    assert me["credits_granted"] == SIGNUP_CREDITS


def test_spent_account_is_not_re_granted_on_login(metered):
    """The backfill must not top up an account that legitimately spent credits."""
    client = TestClient(metered)
    _register(client, "spender")
    client.post("/synthesize", json={"text": "Hello", "voice": "man"})  # spend 5
    # A fresh login must not restore the spent credits.
    fresh = TestClient(metered)
    fresh.post("/auth/login", json={"username": "spender", "password": GOOD_PASSWORD})
    assert fresh.get("/auth/me").json()["user"]["credits"] == SIGNUP_CREDITS - len(
        "Hello"
    )


# --------------------------------------------------------------------- #
# Metered synthesis


def test_metered_synthesis_requires_login(metered):
    res = TestClient(metered).post(
        "/synthesize", json={"text": "Hello", "voice": "man"}
    )
    assert res.status_code == 401


def test_metered_synthesis_debits_credits(metered):
    client = TestClient(metered)
    _register(client)
    res = client.post("/synthesize", json={"text": "Hello", "voice": "man"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cost"] == len("Hello")
    assert body["credits_remaining"] == SIGNUP_CREDITS - len("Hello")
    # Usage stats reflect the spend without touching the lifetime grant.
    me = client.get("/auth/me").json()["user"]
    assert me["credits_used"] == len("Hello")
    assert me["credits_granted"] == SIGNUP_CREDITS


def test_running_out_of_credits_returns_402(metered):
    client = TestClient(metered)
    _register(client)
    text = "x" * SIGNUP_CREDITS  # spends the whole balance
    assert (
        client.post("/synthesize", json={"text": text, "voice": "man"}).status_code
        == 200
    )
    res = client.post("/synthesize", json={"text": "more", "voice": "man"})
    assert res.status_code == 402
    assert "credits" in res.json()["detail"].lower()


def test_failed_synthesis_refunds_the_charge(metered):
    client = TestClient(metered)
    _register(client)
    res = client.post(
        "/synthesize", json={"text": "Hello", "voice": "nope-not-a-voice"}
    )
    assert res.status_code == 404
    me = client.get("/auth/me").json()["user"]
    assert me["credits"] == SIGNUP_CREDITS
    assert me["credits_used"] == 0  # a failed generation is never counted as used


# --------------------------------------------------------------------- #
# Plans + purchasing


def test_plans_lists_three_tiers(metered):
    plans = TestClient(metered).get("/billing/plans").json()
    ids = {p["id"] for p in plans}
    assert {"free", "standard", "premium"} <= ids
    free = next(p for p in plans if p["id"] == "free")
    assert free["is_free"] is True and free["credits"] == SIGNUP_CREDITS


def test_checkout_requires_login(metered):
    res = TestClient(metered).post("/billing/checkout", json={"plan_id": "standard"})
    assert res.status_code == 401


def test_checkout_returns_a_url(metered):
    client = TestClient(metered)
    _register(client)
    res = client.post("/billing/checkout", json={"plan_id": "standard"})
    assert res.status_code == 200, res.text
    assert res.json()["checkout_url"]


def test_free_plan_cannot_be_purchased(metered):
    client = TestClient(metered)
    _register(client)
    res = client.post("/billing/checkout", json={"plan_id": "free"})
    assert res.status_code == 404


def test_webhook_credits_the_account(metered):
    client = TestClient(metered)
    _register(client, "buyer")
    payload = {
        "username": "buyer",
        "plan_id": "standard",
        "credits": 50_000,
        "reference": "test-1",
    }
    res = client.post("/billing/webhook", content=json.dumps(payload))
    assert res.status_code == 200, res.text
    assert res.json()["credited"] == 50_000
    me = client.get("/auth/me").json()["user"]
    assert me["credits"] == SIGNUP_CREDITS + 50_000
    assert me["credits_granted"] == SIGNUP_CREDITS + 50_000
    assert me["credits_used"] == 0
    assert me["plan"] == "standard"


# --------------------------------------------------------------------- #
# Purchasing disabled (billing on, no payment provider)


def test_purchase_disabled_when_no_provider(tmp_path):
    app = _build_app(tmp_path, billing_enabled=True, with_provider=False)
    client = TestClient(app)
    assert client.get("/billing/config").json()["purchase_enabled"] is False
    _register(client)
    res = client.post("/billing/checkout", json={"plan_id": "standard"})
    assert res.status_code == 503
