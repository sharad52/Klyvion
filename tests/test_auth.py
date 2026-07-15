"""Auth + download-gating tests.

Everyone can generate and preview audio; only a logged-in session can download
the file. These run against the FastAPI app with a FakeEngine — no model
download — and skip cleanly when the ``server`` extra is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jwt")
pytest.importorskip("bcrypt")

from fastapi.testclient import TestClient  # noqa: E402

from klyvion.api.server import create_app  # noqa: E402
from klyvion.config import Settings  # noqa: E402
from klyvion.core import Klyvion  # noqa: E402
from tests.test_klyvion import FakeEngine  # noqa: E402

GOOD_PASSWORD = "hunter2secret"


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        engine="fake",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "out",
        secret_key="test-secret-key-that-is-at-least-32-bytes-long",
    )
    settings.ensure_dirs()
    tts = Klyvion(settings)
    tts._engine = FakeEngine()
    return create_app(tts)


@pytest.fixture
def client(app):
    return TestClient(app)


def _synthesize(client) -> dict:
    res = client.post("/synthesize", json={"text": "Hello", "voice": "man"})
    assert res.status_code == 200, res.text
    return res.json()


# --------------------------------------------------------------------- #
# Open generation + preview


def test_synthesize_open_returns_urls(client):
    body = _synthesize(client)
    assert body["audio_id"]
    assert body["preview_url"].endswith(body["audio_id"])
    assert body["download_url"].endswith(body["audio_id"])


def test_preview_needs_no_login(app):
    anon = TestClient(app)
    preview = _synthesize(anon)["preview_url"]
    res = anon.get(preview)
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"


# --------------------------------------------------------------------- #
# Download gating


def test_download_without_login_is_401(app):
    download = _synthesize(TestClient(app))["download_url"]
    res = TestClient(app).get(download)  # fresh client -> no session cookie
    assert res.status_code == 401


def test_download_after_register_succeeds(client):
    download = _synthesize(client)["download_url"]
    reg = client.post(
        "/auth/register", json={"username": "sharad", "password": GOOD_PASSWORD}
    )
    assert reg.status_code == 200, reg.text
    res = client.get(download)
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]


def test_login_after_register_grants_download(app):
    reg_client = TestClient(app)
    reg_client.post(
        "/auth/register", json={"username": "amy", "password": GOOD_PASSWORD}
    )
    download = _synthesize(reg_client)["download_url"]

    fresh = TestClient(app)  # no cookie until we log in
    assert fresh.get(download).status_code == 401
    login = fresh.post(
        "/auth/login", json={"username": "amy", "password": GOOD_PASSWORD}
    )
    assert login.status_code == 200, login.text
    assert fresh.get(download).status_code == 200


# --------------------------------------------------------------------- #
# Account rules


def test_wrong_password_is_401(client):
    client.post("/auth/register", json={"username": "bob", "password": GOOD_PASSWORD})
    res = client.post(
        "/auth/login", json={"username": "bob", "password": "wrong-password"}
    )
    assert res.status_code == 401


def test_duplicate_username_is_409(client):
    payload = {"username": "dup", "password": GOOD_PASSWORD}
    assert client.post("/auth/register", json=payload).status_code == 200
    assert (
        TestClient(client.app).post("/auth/register", json=payload).status_code == 409
    )


def test_weak_password_is_400(client):
    res = client.post("/auth/register", json={"username": "weak", "password": "short"})
    assert res.status_code == 400


# --------------------------------------------------------------------- #
# Session lifecycle + capability probe


def test_me_without_login_is_401(client):
    assert client.get("/auth/me").status_code == 401


def test_logout_clears_session(client):
    client.post(
        "/auth/register", json={"username": "leaver", "password": GOOD_PASSWORD}
    )
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_google_disabled_by_default(client):
    res = client.get("/auth/config")
    assert res.status_code == 200
    assert res.json()["google_enabled"] is False


# --------------------------------------------------------------------- #
# Public static + metadata endpoints


def test_favicon_is_served(client):
    res = client.get("/favicon.ico")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/x-icon"
    assert res.content[:4] == b"\x00\x00\x01\x00"  # ICO magic number


def test_languages_lists_enabled(client):
    res = client.get("/languages")
    assert res.status_code == 200
    codes = {lang["code"] for lang in res.json()}
    assert {"en", "hi"} <= codes
