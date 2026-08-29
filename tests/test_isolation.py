"""Tenant isolation: no merchant can reach another merchant, no buyer another buyer.

These are the regression tests for a set of holes found by audit: an agent session pinned to
one merchant could read a rival's catalog rows through /agent/action, any caller could rewrite
any merchant's config or inject products into any catalog, any caller could read any buyer's
saved addresses, and identity was taken from the request body so a session could be opened as
someone else and resolve their shipping address into a cart.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.db import init_databases, transaction, utc_now
from app.main import app
from seed.reset import MERCHANT_KEY_FILE, seed
from tests.conftest import SessionAwareClient

RIVAL_SKU = "RIVAL-SEC-001"


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with SessionAwareClient(app) as test_client:
        yield test_client


@pytest.fixture()
def merchant_a_key() -> str:
    return MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()


@pytest.fixture()
def rival(client: TestClient) -> dict:
    """A second merchant with a product of its own, to be isolated from.

    The product is written straight to the catalog rather than pushed through the cleaning
    pipeline: what is under test here is whether merchant A can reach merchant B's rows, not
    how rows get there, and going through the pipeline would tie these tests to its schema.
    """
    created = client.post("/merchant/onboard", json={"name": "Rival Skin Co", "size": "sme"})
    assert created.status_code == 200, created.text
    body = created.json()
    now = utc_now()
    with transaction() as connection:
        connection.execute(
            "INSERT INTO products(sku,merchant_id,title,description,price_cents,currency,"
            "image_url,category,attributes_json,stock,rating_avg,rating_count,rating_source,"
            "created_at,updated_at) VALUES (?,?,?,?,?,'SGD',NULL,'skincare',?,?,?,?, "
            "'merchant_feed',?,?)",
            (
                RIVAL_SKU,
                body["merchant_id"],
                "Rival Secret Serum",
                "confidential",
                9900,
                json.dumps(
                    {
                        "routine_step": "serum",
                        "skin_types": ["dry"],
                        "concerns": ["dryness"],
                        "ingredients": ["rival peptide", "trade secret"],
                    }
                ),
                5,
                4.9,
                11,
                now,
                now,
            ),
        )
    return body


def register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/consumer/register",
        json={"email": email, "password": "a-long-enough-password", "display_name": email},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- merchants


def test_merchant_key_does_not_open_another_merchant(client, rival, merchant_a_key) -> None:
    key = {"X-Merchant-Key": merchant_a_key}
    assert client.get(f"/merchant/{rival['merchant_id']}/config", headers=key).status_code == 403
    assert (
        client.put(
            f"/merchant/{rival['merchant_id']}/config", json={"name": "taken over"}, headers=key
        ).status_code
        == 403
    )


def test_merchant_writes_require_a_key(client, rival) -> None:
    assert (
        client.put(
            f"/merchant/{rival['merchant_id']}/config", json={"name": "taken over"}
        ).status_code
        == 401
    )
    assert (
        client.post(f"/merchant/{rival['merchant_id']}/catalog", json={"products": []}).status_code
        == 401
    )


def test_merchant_cannot_inject_products_into_another_catalog(client, rival, merchant_a_key) -> None:
    response = client.post(
        f"/merchant/{rival['merchant_id']}/catalog",
        json={
            "products": [
                {
                    "sku": "RIVAL-FAKE-666",
                    "title": "Injected",
                    "description": "x",
                    "price": 0.01,
                    "stock": 9,
                    "routine_step": "serum",
                    "skin_types": "dry",
                    "concerns": "dryness",
                    "ingredients": "x",
                }
            ]
        },
        headers={"X-Merchant-Key": merchant_a_key},
    )
    assert response.status_code == 403


def test_agent_cannot_compare_a_rival_merchants_product(client, rival) -> None:
    session_id = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()["session_id"]
    response = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "compare", "skus": ["MYSA-CLN-101", RIVAL_SKU]},
    )
    assert response.status_code >= 400
    assert "Rival Secret" not in response.text
    assert "trade secret" not in response.text


def test_agent_cannot_cart_a_rival_merchants_product(client, rival) -> None:
    session_id = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()["session_id"]
    response = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "items": [{"sku": RIVAL_SKU}]},
    )
    assert response.status_code >= 400


def test_product_reads_are_merchant_scoped(client, rival) -> None:
    # No merchant scope at all is a validation error, not an open read.
    assert client.get(f"/catalog/product/{RIVAL_SKU}").status_code == 422
    # Naming the wrong merchant is a 404, not someone else's row.
    assert client.get(f"/catalog/product/{RIVAL_SKU}?merchant_id=m_mysa").status_code == 404


# --------------------------------------------------------------------------- buyers


def test_buyer_cannot_read_another_buyers_addresses(client) -> None:
    alice = register(client, "alice@test.io")
    bob = register(client, "bob@test.io")
    response = client.get(
        f"/consumer/{bob['consumer_id']}/addresses",
        headers={"Authorization": f"Bearer {alice['token']}"},
    )
    assert response.status_code == 403
    assert client.get(f"/consumer/{bob['consumer_id']}/addresses").status_code == 401


def test_buyer_cannot_change_another_buyers_default_address(client) -> None:
    alice = register(client, "alice@test.io")
    bob = register(client, "bob@test.io")
    response = client.put(
        f"/consumer/{bob['consumer_id']}/addresses/adr_demo/default",
        headers={"Authorization": f"Bearer {alice['token']}"},
    )
    assert response.status_code == 403


def test_identity_cannot_be_claimed_from_the_request_body(client) -> None:
    body = client.post(
        "/agent/session", json={"merchant_id": "m_mysa", "consumer_id": "usr_demo"}
    ).json()
    assert body["consumer_id"] != "usr_demo"
    assert body["anonymous"] is True


def test_session_token_is_required_and_not_transferable(client) -> None:
    first = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    second = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()

    # No token at all.
    assert (
        client.post(
            "/agent/turn",
            json={"session_id": second["session_id"], "text": "hello"},
            headers={"X-Session-Token": ""},
        ).status_code
        == 401
    )
    # A valid token for a different session.
    assert (
        client.post(
            "/agent/turn",
            json={"session_id": second["session_id"], "text": "hello"},
            headers={"X-Session-Token": first["session_token"]},
        ).status_code
        == 403
    )


def test_trust_log_is_not_readable_across_sessions(client) -> None:
    first = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    second = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    response = client.get(
        f"/trust/events/snapshot?session_id={second['session_id']}",
        headers={"X-Session-Token": first["session_token"]},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- anonymous


def test_anonymous_shoppers_can_still_browse(client) -> None:
    body = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    assert body["anonymous"] is True
    response = client.post(
        "/agent/turn",
        json={"session_id": body["session_id"], "text": "I have dry sensitive skin"},
    )
    assert response.status_code == 200
    assert "product_cards" in [event["type"] for event in response.json()["events"]]


def test_two_anonymous_shoppers_are_isolated_from_each_other(client) -> None:
    first = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    second = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    assert first["consumer_id"] != second["consumer_id"]


def test_signing_in_binds_the_session_to_that_buyer(client) -> None:
    alice = register(client, "alice@test.io")
    body = client.post(
        "/agent/session",
        json={"merchant_id": "m_mysa"},
        headers={"Authorization": f"Bearer {alice['token']}"},
    ).json()
    assert body["consumer_id"] == alice["consumer_id"]
    assert body["anonymous"] is False


def test_wrong_password_is_rejected(client) -> None:
    register(client, "alice@test.io")
    response = client.post(
        "/consumer/login", json={"email": "alice@test.io", "password": "not-the-password"}
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- claiming


def test_signing_in_mid_visit_claims_the_session_in_progress(client) -> None:
    """A basket built as a guest must survive reaching the till."""
    started = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    assert started["anonymous"] is True
    alice = register(client, "alice@test.io")

    claimed = client.put(
        f"/agent/session/{started['session_id']}/identity",
        headers={
            "X-Session-Token": started["session_token"],
            "Authorization": f"Bearer {alice['token']}",
        },
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["consumer_id"] == alice["consumer_id"]
    assert claimed.json()["anonymous"] is False


def test_claiming_needs_both_credentials(client) -> None:
    started = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    alice = register(client, "alice@test.io")

    # Signed in, but not the client that opened this session.
    assert (
        client.put(
            f"/agent/session/{started['session_id']}/identity",
            headers={
                "X-Session-Token": "st_not-the-right-token",
                "Authorization": f"Bearer {alice['token']}",
            },
        ).status_code
        == 403
    )
    # Holds the session, but is not signed in as anyone.
    assert (
        client.put(
            f"/agent/session/{started['session_id']}/identity",
            headers={"X-Session-Token": started["session_token"]},
        ).status_code
        == 401
    )


def test_a_session_already_signed_in_cannot_be_re_bound(client) -> None:
    alice = register(client, "alice@test.io")
    bob = register(client, "bob@test.io")
    started = client.post(
        "/agent/session",
        json={"merchant_id": "m_mysa"},
        headers={"Authorization": f"Bearer {alice['token']}"},
    ).json()
    assert started["anonymous"] is False

    stolen = client.put(
        f"/agent/session/{started['session_id']}/identity",
        headers={
            "X-Session-Token": started["session_token"],
            "Authorization": f"Bearer {bob['token']}",
        },
    )
    assert stolen.status_code == 403


# --------------------------------------------------------------------------- payment paths


def test_consent_cannot_be_recorded_for_someone_elses_session(client) -> None:
    """/pay/consent reached record_consent() with no session token at all.

    It is an undeclared duplicate of /agent/confirm with no caller, and it skipped both the
    session check and the human-confirmation check, so knowing a session_id and cart_id was
    enough to record a shopper's consent for them.
    """
    victim = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    attacker = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()

    assert (
        client.post(
            "/pay/consent",
            json={"session_id": victim["session_id"], "cart_id": "cart_anything"},
            headers={"X-Session-Token": ""},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/pay/consent",
            json={"session_id": victim["session_id"], "cart_id": "cart_anything"},
            headers={"X-Session-Token": attacker["session_token"]},
        ).status_code
        == 403
    )


def test_trust_log_cannot_be_written_through_the_bank_simulator(client) -> None:
    """The bank routes take a session_id purely to write into that session's trust log.

    Unguarded, that let anyone append entries to another shopper's audit trail - the record
    the demo asks judges to read as evidence.
    """
    victim = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    attacker = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    challenge = {
        "consumer_id": "usr_demo",
        "cart_hash": "sha256:whatever",
        "amount_cents": 100,
        "currency": "SGD",
        "merchant_id": "m_mysa",
        "session_id": victim["session_id"],
    }

    assert (
        client.post("/bank/challenge", json=challenge, headers={"X-Session-Token": ""}).status_code
        == 401
    )
    assert (
        client.post(
            "/bank/challenge",
            json=challenge,
            headers={"X-Session-Token": attacker["session_token"]},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/bank/verify",
            json={"challenge_id": "chl_x", "code": "492118", "session_id": victim["session_id"]},
            headers={"X-Session-Token": attacker["session_token"]},
        ).status_code
        == 403
    )

    # The victim's trust log is untouched by any of that.
    log = client.get(
        f"/trust/events/snapshot?session_id={victim['session_id']}",
        headers={"X-Session-Token": victim["session_token"]},
    ).json()
    assert not [e for e in log["events"] if e["stage"] == "issuer"]
