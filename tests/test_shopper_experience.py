"""The shopper-facing changes that made the demo honest, proved end to end.

Four things were true of the old flow and are not true here: nobody was ever asked for a
card, the receipt existed only inside the open tab, asking to compare or to browse in the
chat did nothing, and every storefront wore the seeded merchant's name. Each of those is a
test below, driven over HTTP rather than by reading the code.
"""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_databases
from app.main import app
from app.settings import settings
from seed.reset import DEMO_CONSUMER_EMAIL, seed
from tests.conftest import SessionAwareClient
from tests.test_api_flow import DEMO_CARD, add_card, create_session


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with SessionAwareClient(app) as test_client:
        login = test_client.post(
            "/consumer/login",
            json={"email": DEMO_CONSUMER_EMAIL, "password": "mysa-demo-password"},
        )
        assert login.status_code == 200, login.text
        test_client.consumer_token = login.json()["token"]
        yield test_client


def png_bytes() -> bytes:
    """A real 1x1 PNG, so the upload is judged on its bytes rather than its filename."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel = zlib.compress(b"\x00\xff\xff\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixel) + chunk(b"IEND", b"")


def buy(client: TestClient, session_id: str, *, receipt_email: str | None = None) -> dict:
    """Run one purchase to completion and return the receipt."""
    cart = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    assert cart.status_code == 200, cart.text
    cart_data = cart.json()["data"]
    consent = client.post(
        "/agent/confirm",
        json={
            "session_id": session_id,
            "cart_id": cart_data["cart_id"],
            "confirmation": {"method": "click"},
            "receipt_email": receipt_email,
        },
    )
    assert consent.status_code == 200, consent.text
    consented = consent.json()
    challenge = client.post(
        "/bank/challenge",
        json={
            "consumer_id": "usr_demo",
            "cart_hash": consented["cart_hash"],
            "amount_cents": consented["amount_cents"],
            "currency": consented["currency"],
            "merchant_id": consented["merchant_id"],
            "session_id": session_id,
        },
    )
    assert challenge.status_code == 200, challenge.text
    verified = client.post(
        "/bank/verify",
        json={"challenge_id": challenge.json()["challenge_id"], "code": "492118", "session_id": session_id},
    )
    assert verified.status_code == 200, verified.text
    paid = client.post(
        "/agent/pay",
        headers={"Idempotency-Key": f"key-{session_id}"},
        json={
            "session_id": session_id,
            "cart_id": consented["cart_id"],
            "payment_mandate_id": consented["payment_mandate_id"],
            "token_id": consented["token_id"],
            "bank_token": verified.json()["bank_token"],
        },
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "approved", paid.text
    return paid.json()["receipt"]


# --- the card the shopper actually enters -----------------------------------------------


def test_checkout_refuses_a_cart_until_the_shopper_has_entered_a_card(client: TestClient) -> None:
    session_id = create_session(client, with_card=False)

    blocked = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error"]["code"] == "CARD_REQUIRED"

    assert add_card(client, session_id).status_code == 200
    allowed = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["last4"] == "1111"
    assert allowed.json()["data"]["card_brand"] == "Visa"


def test_the_card_number_is_never_stored_anywhere(client: TestClient) -> None:
    """Only four digits may survive the call. Anything more is a card number at rest."""
    session_id = create_session(client)
    receipt = buy(client, session_id, receipt_email="shopper@example.com")
    assert receipt["last4"] == "1111"

    full_number = DEMO_CARD["number"].replace(" ", "")
    with connect() as connection:
        tables = [
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        for table in tables:
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            for row in rows:
                blob = " ".join(str(value) for value in tuple(row))
                assert full_number not in blob, f"the card number reached {table}"


def test_a_card_that_fails_its_checks_is_refused(client: TestClient) -> None:
    session_id = create_session(client, with_card=False)

    bad_digits = add_card(client, session_id, number="4111 1111 1111 1112")
    assert bad_digits.status_code == 400
    assert bad_digits.json()["detail"]["error"]["code"] == "CARD_INVALID"

    expired = add_card(client, session_id, expiry_month=1, expiry_year=2020)
    assert expired.status_code == 400
    assert expired.json()["detail"]["error"]["code"] == "CARD_EXPIRED"

    short_code = add_card(client, session_id, cvc="12")
    assert short_code.status_code == 422  # rejected by the request schema before it is read


def test_a_session_token_is_required_to_put_a_card_on_a_session(client: TestClient) -> None:
    session_id = create_session(client, with_card=False)
    unauthorized = client.put(
        f"/agent/session/{session_id}/card",
        headers={"X-Session-Token": "not-the-token"},
        json=DEMO_CARD,
    )
    assert unauthorized.status_code in {401, 403}


# --- the receipt leaves the tab ----------------------------------------------------------


def test_the_receipt_is_emailed_and_recorded(client: TestClient) -> None:
    session_id = create_session(client)
    receipt = buy(client, session_id, receipt_email="shopper@example.com")

    delivery = receipt["email_delivery"]
    assert delivery["recipient"] == "shopper@example.com"
    # No SMTP host is configured in the suite, so delivery is honest about being simulated.
    assert delivery["status"] == "simulated"
    assert delivery["channel"] == "demo_outbox"

    with connect() as connection:
        stored = connection.execute(
            "SELECT * FROM receipt_emails WHERE order_id=?", (receipt["order_id"],)
        ).fetchone()
    assert stored is not None
    assert stored["recipient"] == "shopper@example.com"
    assert receipt["auth_code"] in stored["body_text"]
    assert "Mysa Skin" in stored["subject"]
    assert (settings.receipt_outbox_path / f"{receipt['order_id']}.html").exists()

    trust = client.get(f"/trust/events/snapshot?session_id={session_id}").json()["events"]
    assert any("Receipt" in event["label"] for event in trust)


def test_a_signed_in_shopper_gets_the_receipt_without_typing_an_address(client: TestClient) -> None:
    session_id = create_session(client)
    receipt = buy(client, session_id)
    assert receipt["email_delivery"]["recipient"] == DEMO_CONSUMER_EMAIL


def test_an_unreachable_address_is_refused_before_the_charge(client: TestClient) -> None:
    session_id = create_session(client)
    cart = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    rejected = client.post(
        "/agent/confirm",
        json={
            "session_id": session_id,
            "cart_id": cart.json()["data"]["cart_id"],
            "confirmation": {"method": "click"},
            "receipt_email": "not-an-address",
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["error"]["code"] == "VALIDATION"


# --- asking in the chat ------------------------------------------------------------------


def test_asking_for_categories_returns_a_browsable_table(client: TestClient) -> None:
    session_id = create_session(client)
    turn = client.post("/agent/turn", json={"session_id": session_id, "text": "what categories do you have?"})
    assert turn.status_code == 200, turn.text
    events = turn.json()["events"]
    table = next(event for event in events if event["type"] == "category_table")
    assert table["data"]["llm_calls"] == 0
    keys = [group["key"] for group in table["data"]["categories"]]
    assert "cleanser" in keys and "sunscreen" in keys
    for group in table["data"]["categories"]:
        assert group["product_count"] >= 1
        assert group["from_price_cents"] > 0

    opened = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "browse_category", "routine_step": "cleanser"},
    )
    assert opened.status_code == 200, opened.text
    products = opened.json()["data"]["products"]
    assert products
    assert all(product["attributes"]["routine_step"] == "cleanser" for product in products)


def test_an_unknown_category_is_refused(client: TestClient) -> None:
    session_id = create_session(client)
    refused = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "browse_category", "routine_step": "handbags"},
    )
    assert refused.status_code == 400


def test_asking_to_compare_in_the_chat_returns_the_table(client: TestClient) -> None:
    session_id = create_session(client)
    shown = client.post("/agent/turn", json={"session_id": session_id, "text": "show me a cleanser for dry skin"})
    assert shown.status_code == 200, shown.text

    # "Compare these" names nothing: what is on screen is what the shopper means.
    compared = client.post("/agent/turn", json={"session_id": session_id, "text": "compare these"})
    assert compared.status_code == 200, compared.text
    events = compared.json()["events"]
    table = next(event for event in events if event["type"] == "comparison")
    assert len(table["data"]["products"]) >= 2
    assert table["data"]["llm_calls"] == 0


def test_compare_with_nothing_on_screen_asks_rather_than_failing(client: TestClient) -> None:
    session_id = create_session(client)
    compared = client.post("/agent/turn", json={"session_id": session_id, "text": "compare these"})
    assert compared.status_code == 200, compared.text
    assert compared.json()["events"][0]["type"] in {"clarification", "safety_boundary"}


def test_an_answer_marks_the_products_it_names_for_the_chat(client: TestClient) -> None:
    """Cards the answer cites are flagged inline, so the UI can put them under that message."""
    session_id = create_session(client)
    asked = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "do you sell a fragrance free cleanser?"},
    )
    assert asked.status_code == 200, asked.text
    trust = client.get(f"/trust/events/snapshot?session_id={session_id}").json()["events"]
    assert any(event["detail"].get("route") == "answer" for event in trust)
    cards = [event for event in asked.json()["events"] if event["type"] == "product_cards"]
    if cards:  # the adviser only cites products it actually named in the answer
        assert cards[0]["data"]["inline"] is True


def test_a_shopper_may_name_a_product_that_is_not_on_screen_yet(client: TestClient) -> None:
    """Naming a product in this shop is a fair question, not an ungrounded claim.

    The interpretation guard used to require every selected SKU to be already displayed, so
    "tell me about the Gentle Cloud Cleanser" on a fresh session came back as a 422.
    """
    from agent.guardian import validate_interpretation

    interpretation = {
        "route": "product_detail",
        "missing_required_fields": [],
        "clarification": None,
        "catalog_query": None,
        "selected_skus": ["MYSA-CLN-101"],
        "quantity": None,
        "wants_usage_detail": False,
    }
    validated = validate_interpretation(
        dict(interpretation),
        merchant_id="m_mysa",
        visible_skus=[],
        catalog_skus=["MYSA-CLN-101", "MYSA-SRM-010"],
    )
    assert validated["selected_skus"] == ["MYSA-CLN-101"]

    # A SKU that is not this merchant's is still refused - that is what the guard is for.
    with pytest.raises(Exception) as refused:
        validate_interpretation(
            {**interpretation, "selected_skus": ["OTHER-SHOP-001"]},
            merchant_id="m_mysa",
            visible_skus=[],
            catalog_skus=["MYSA-CLN-101"],
        )
    assert "OUT_OF_SCOPE_PRODUCT" in str(refused.value.detail)


def test_asking_about_a_named_product_answers_over_http(client: TestClient) -> None:
    session_id = create_session(client)
    asked = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "do you sell a gentle cleanser?"},
    )
    assert asked.status_code == 200, asked.text


# --- the merchant's own mark ---------------------------------------------------------------


def test_a_merchant_can_put_their_logo_on_their_storefront(client: TestClient) -> None:
    created = client.post("/merchant/onboard", json={"name": "Aurora Skin", "size": "sme"})
    merchant_id = created.json()["merchant_id"]
    key = {"X-Merchant-Key": created.json()["api_key"]}

    uploaded = client.post(
        f"/merchant/{merchant_id}/logo",
        headers=key,
        files={"file": ("aurora.png", io.BytesIO(png_bytes()), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    logo_url = uploaded.json()["logo_url"]
    assert f"/merchant/{merchant_id}/logo" in logo_url

    # The shopper's session carries it, which is what puts it in the storefront header.
    session = client.post(
        "/agent/session",
        json={"merchant_id": merchant_id, "category": "skincare", "budget_cents": None},
    )
    assert session.json()["merchant"]["logo_url"] == logo_url

    served = client.get(f"/merchant/{merchant_id}/logo")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.content == png_bytes()

    removed = client.delete(f"/merchant/{merchant_id}/logo", headers=key)
    assert removed.status_code == 200
    assert client.get(f"/merchant/{merchant_id}/logo").status_code == 404


def test_a_logo_upload_is_judged_on_its_bytes_and_needs_the_merchant_key(client: TestClient) -> None:
    created = client.post("/merchant/onboard", json={"name": "Bloom Botanicals", "size": "sme"})
    merchant_id = created.json()["merchant_id"]
    key = {"X-Merchant-Key": created.json()["api_key"]}

    # An SVG renamed to .png is still a document that can carry script.
    disguised = client.post(
        f"/merchant/{merchant_id}/logo",
        headers=key,
        files={"file": ("logo.png", io.BytesIO(b"<svg onload=alert(1)></svg>"), "image/png")},
    )
    assert disguised.status_code == 400
    assert disguised.json()["detail"]["error"]["code"] == "BAD_IMAGE"

    unkeyed = client.post(
        f"/merchant/{merchant_id}/logo",
        files={"file": ("logo.png", io.BytesIO(png_bytes()), "image/png")},
    )
    assert unkeyed.status_code == 401

    other = client.post("/merchant/onboard", json={"name": "Third Store", "size": "sme"})
    borrowed = client.post(
        f"/merchant/{merchant_id}/logo",
        headers={"X-Merchant-Key": other.json()["api_key"]},
        files={"file": ("logo.png", io.BytesIO(png_bytes()), "image/png")},
    )
    assert borrowed.status_code in {401, 403}


def test_a_receipt_names_the_merchant_that_was_paid(client: TestClient) -> None:
    session_id = create_session(client)
    receipt = buy(client, session_id)
    assert receipt["merchant"] == "Mysa Skin"
