"""Credential handling and data exposure, beyond who-can-reach-which-route.

The route audit answers "is this endpoint guarded". These answer the questions it cannot:
whether an unlaunched merchant's catalog is visible, whether a password can be ground down,
whether a session lives forever, and whether signing out on one device signs you out on all
of them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_databases, transaction
from app.main import app
from seed.reset import MERCHANT_KEY_FILE, seed
from tests.conftest import SessionAwareClient

DRAFT_SKU = "UNRELEASED-1"


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with SessionAwareClient(app) as test_client:
        yield test_client


@pytest.fixture()
def unlaunched(client: TestClient) -> dict:
    """A merchant who has onboarded and loaded stock but has not published yet."""
    body = client.post(
        "/merchant/onboard", json={"name": "Not Launched Yet", "size": "sme"}
    ).json()
    with transaction() as connection:
        connection.execute(
            "INSERT INTO products(sku,merchant_id,title,description,price_cents,currency,"
            "image_url,category,attributes_json,stock,rating_avg,rating_count,rating_source,"
            "created_at,updated_at) VALUES (?,?,'Unreleased Serum','confidential',12345,'SGD',"
            "NULL,'skincare','{}',9,NULL,NULL,'none','now','now')",
            (DRAFT_SKU, body["merchant_id"]),
        )
    return body


# --------------------------------------------------------------- unpublished merchant data


def test_an_unpublished_merchants_catalog_is_not_public(client, unlaunched) -> None:
    """Onboarding is not launching: a merchant's prices are theirs until they publish."""
    merchant_id = unlaunched["merchant_id"]

    search = client.get(f"/catalog/search?merchant_id={merchant_id}&category=skincare&q=serum")
    assert search.status_code == 200
    assert DRAFT_SKU not in search.text
    assert "12345" not in search.text

    assert client.get(f"/catalog/product/{DRAFT_SKU}?merchant_id={merchant_id}").status_code == 404


def test_a_merchant_can_still_see_their_own_unpublished_catalog(client, unlaunched) -> None:
    """The point is to hide it from everyone else, not from its owner."""
    merchant_id = unlaunched["merchant_id"]
    key = {"X-Merchant-Key": unlaunched["api_key"]}

    search = client.get(
        f"/catalog/search?merchant_id={merchant_id}&category=skincare&q=serum", headers=key
    )
    assert DRAFT_SKU in search.text
    assert (
        client.get(f"/catalog/product/{DRAFT_SKU}?merchant_id={merchant_id}", headers=key).status_code
        == 200
    )


def test_another_merchants_key_does_not_reveal_unpublished_stock(client, unlaunched) -> None:
    other = MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()
    merchant_id = unlaunched["merchant_id"]
    search = client.get(
        f"/catalog/search?merchant_id={merchant_id}&category=skincare&q=serum",
        headers={"X-Merchant-Key": other},
    )
    assert DRAFT_SKU not in search.text


def test_the_published_demo_store_is_still_public(client) -> None:
    """The guard must not take the storefront offline."""
    search = client.get("/catalog/search?merchant_id=m_mysa&category=skincare&q=cleanser")
    assert search.status_code == 200
    assert "MYSA-CLN-101" in search.text


# --------------------------------------------------------------------------- credentials


def register(client: TestClient, email: str, password: str = "a-long-enough-password") -> dict:
    return client.post(
        "/consumer/register", json={"email": email, "password": password, "display_name": "x"}
    ).json()


def test_password_guessing_is_throttled(client) -> None:
    register(client, "victim@test.io")
    codes = [
        client.post(
            "/consumer/login", json={"email": "victim@test.io", "password": f"guess-{i}"}
        ).status_code
        for i in range(12)
    ]
    assert 429 in codes, f"no throttle kicked in: {codes}"


def test_a_correct_login_clears_the_throttle(client) -> None:
    """Ordinary use — a typo, then the right password — must not accumulate into a lockout."""
    register(client, "typo@test.io", "the-right-password")
    for _ in range(3):
        client.post("/consumer/login", json={"email": "typo@test.io", "password": "wrong"})
    good = client.post(
        "/consumer/login", json={"email": "typo@test.io", "password": "the-right-password"}
    )
    assert good.status_code == 200
    for _ in range(6):
        again = client.post(
            "/consumer/login", json={"email": "typo@test.io", "password": "the-right-password"}
        )
    assert again.status_code == 200


def test_trivial_passwords_are_refused(client) -> None:
    for weak in ("password", "12345678", "aaaaaaaa"):
        response = client.post(
            "/consumer/register", json={"email": f"{weak}@test.io", "password": weak}
        )
        assert response.status_code == 400, f"{weak!r} was accepted"


def test_signing_out_on_one_device_leaves_the_other_signed_in(client) -> None:
    laptop = register(client, "two-devices@test.io")
    phone = client.post(
        "/consumer/login",
        json={"email": "two-devices@test.io", "password": "a-long-enough-password"},
    ).json()

    client.post("/consumer/logout", headers={"Authorization": f"Bearer {laptop['token']}"})

    assert (
        client.get("/consumer/me", headers={"Authorization": f"Bearer {laptop['token']}"}).status_code
        == 401
    )
    assert (
        client.get("/consumer/me", headers={"Authorization": f"Bearer {phone['token']}"}).status_code
        == 200
    )


# --------------------------------------------------------------------------- session life


def test_a_session_does_not_live_forever(client) -> None:
    started = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    with connect() as connection:
        row = connection.execute(
            "SELECT expires_at FROM sessions WHERE session_id=?", (started["session_id"],)
        ).fetchone()
    assert row["expires_at"], "sessions are created without an expiry"

    with transaction() as connection:
        connection.execute(
            "UPDATE sessions SET expires_at=? WHERE session_id=?",
            ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), started["session_id"]),
        )

    expired = client.post(
        "/agent/turn",
        json={"session_id": started["session_id"], "text": "hello"},
        headers={"X-Session-Token": started["session_token"]},
    )
    assert expired.status_code == 401
    assert expired.json()["detail"]["error"]["code"] == "SESSION_EXPIRED"
