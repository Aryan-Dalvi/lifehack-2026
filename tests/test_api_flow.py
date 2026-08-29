from __future__ import annotations

import dataclasses
import json

import pytest
from fastapi.testclient import TestClient

from agent.guardian import validate_recommendation
from app.db import connect, init_databases
from app.errors import api_error
from app.main import app
from payments import service as payment_service
from payments import visa_client
from payments.tap import canonical_json, sign_tap_request
from seed.reset import DEMO_CONSUMER_EMAIL, MERCHANT_KEY_FILE, seed
from tests.conftest import SessionAwareClient


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with SessionAwareClient(app) as test_client:
        # The purchase journey is a signed-in one: a cart resolves the shopper's saved
        # shipping address, which an anonymous session does not have.
        login = test_client.post(
            "/consumer/login",
            json={"email": DEMO_CONSUMER_EMAIL, "password": "mysa-demo-password"},
        )
        assert login.status_code == 200, login.text
        test_client.consumer_token = login.json()["token"]
        yield test_client


def create_session(client: TestClient, budget_cents: int | None = None) -> str:
    response = client.post(
        "/agent/session",
        json={
            "merchant_id": "m_mysa",
            "category": "skincare",
            "budget_cents": budget_cents,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def confirm_cart(client: TestClient, session_id: str, cart: dict) -> dict:
    consent_response = client.post(
        "/agent/confirm",
        json={
            "session_id": session_id,
            "cart_id": cart["cart_id"],
            "confirmation": {"method": "click"},
        },
    )
    assert consent_response.status_code == 200, consent_response.text
    return {"cart": cart, "consent": consent_response.json()}


def build_consented_cart(client: TestClient, session_id: str) -> dict:
    cart_response = client.post(
        "/agent/action",
        json={
            "session_id": session_id,
            "action": "select",
            "sku": "MYSA-CLN-101",
            "quantity": 1,
        },
    )
    assert cart_response.status_code == 200, cart_response.text
    return confirm_cart(client, session_id, cart_response.json()["data"])


def issue_bank_token(client: TestClient, session_id: str, consent: dict) -> str:
    challenge_response = client.post(
        "/bank/challenge",
        json={
            "consumer_id": "usr_demo",
            "cart_hash": consent["cart_hash"],
            "amount_cents": consent["amount_cents"],
            "currency": consent["currency"],
            "merchant_id": consent["merchant_id"],
            "session_id": session_id,
        },
    )
    assert challenge_response.status_code == 200, challenge_response.text
    challenge_id = challenge_response.json()["challenge_id"]

    wrong = client.post(
        "/bank/verify",
        json={"challenge_id": challenge_id, "code": "000000", "session_id": session_id},
    )
    assert wrong.status_code == 200
    assert wrong.json()["decline_code"] == "BANK_AUTH_DECLINED"

    approved = client.post(
        "/bank/verify",
        json={"challenge_id": challenge_id, "code": "492 118", "session_id": session_id},
    )
    assert approved.status_code == 200, approved.text
    return approved.json()["bank_token"]


def test_discover_compare_consent_bank_tap_pay_and_idempotency(client: TestClient) -> None:
    session_id = create_session(client)

    discovery = client.post(
        "/agent/turn",
        json={
            "session_id": session_id,
            "text": "I need a gentle cleanser for sensitive dry skin with no fragrance",
        },
    )
    assert discovery.status_code == 200, discovery.text
    events = discovery.json()["events"]
    products = next(event["data"]["products"] for event in events if event["type"] == "product_cards")
    assert len(products) >= 2
    assert all(product["category"] == "skincare" for product in products)
    assert all(product["attributes"]["fragrance_free"] for product in products)

    comparison = client.post(
        "/agent/action",
        json={
            "session_id": session_id,
            "action": "compare",
            "skus": [product["sku"] for product in products[:2]],
        },
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["data"]["source"] == "catalog_database"
    assert comparison.json()["data"]["llm_calls"] == 0

    checkout = build_consented_cart(client, session_id)
    bank_token = issue_bank_token(client, session_id, checkout["consent"])
    payment_payload = {
        "session_id": session_id,
        "cart_id": checkout["consent"]["cart_id"],
        "payment_mandate_id": checkout["consent"]["payment_mandate_id"],
        "token_id": checkout["consent"]["token_id"],
        "bank_token": bank_token,
    }

    approved = client.post(
        "/agent/pay",
        json=payment_payload,
        headers={"Idempotency-Key": "happy-path-1"},
    )
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert result["status"] == "approved"
    assert result["simulated"] is True
    assert result["receipt"]["issuer"] == "Meridian Bank"

    replay = client.post(
        "/agent/pay",
        json=payment_payload,
        headers={"Idempotency-Key": "happy-path-1"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["transaction_id"] == result["transaction_id"]
    assert replay.json()["idempotent_replay"] is True

    conflicting_reuse = client.post(
        "/agent/pay",
        json={**payment_payload, "cart_id": "cart_different"},
        headers={"Idempotency-Key": "happy-path-1"},
    )
    assert conflicting_reuse.status_code == 409
    assert conflicting_reuse.json()["detail"]["error"]["code"] == "IDEMPOTENCY_MISMATCH"

    with connect() as connection:
        # Scoped to this session: the database also carries the demo merchant's seeded
        # trading history, and the claim here is about what this flow created.
        orders = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE session_id=?", (session_id,)
        ).fetchone()[0]
        assert orders == 1


def test_visa_configuration_is_checked_before_the_bank_challenge(client, monkeypatch) -> None:
    session_id = create_session(client)
    checkout = build_consented_cart(client, session_id)
    monkeypatch.setattr(
        payment_service,
        "settings",
        dataclasses.replace(payment_service.settings, payment_adapter="visa"),
    )
    monkeypatch.setattr(
        visa_client,
        "settings",
        dataclasses.replace(visa_client.settings, visa_mle_encrypt_cert_path=None),
    )

    response = client.post(
        "/bank/challenge",
        json={
            "consumer_id": "usr_demo",
            "cart_hash": checkout["consent"]["cart_hash"],
            "amount_cents": checkout["consent"]["amount_cents"],
            "currency": checkout["consent"]["currency"],
            "merchant_id": checkout["consent"]["merchant_id"],
            "session_id": session_id,
        },
    )

    assert response.status_code == 503
    error = response.json()["detail"]["error"]
    assert error["code"] == "PAYMENT_NOT_READY"
    assert "VISA_MLE" not in error["message"]


def test_operational_authorization_fault_releases_the_bank_token(client, monkeypatch) -> None:
    session_id = create_session(client)
    checkout = build_consented_cart(client, session_id)
    bank_token = issue_bank_token(client, session_id, checkout["consent"])

    def fail_authorization(**_kwargs):
        raise api_error(502, "VISA_ADAPTER_UNAVAILABLE", "Temporary payment failure.")

    monkeypatch.setattr(payment_service, "_run_authorization", fail_authorization)
    response = client.post(
        "/agent/pay",
        json={
            "session_id": session_id,
            "cart_id": checkout["consent"]["cart_id"],
            "payment_mandate_id": checkout["consent"]["payment_mandate_id"],
            "token_id": checkout["consent"]["token_id"],
            "bank_token": bank_token,
        },
        headers={"Idempotency-Key": "operational-fault"},
    )

    assert response.status_code == 502
    token_status = client.get(f"/bank/token/{bank_token}")
    assert token_status.status_code == 200
    assert token_status.json()["status"] == "issued"


def test_new_consumer_can_add_a_shipping_address_and_then_checkout(client: TestClient) -> None:
    """A freshly registered consumer has zero addresses, and until this endpoint existed
    there was no way to add one — checkout's ADDRESS_REQUIRED could never be satisfied for
    anyone but the pre-seeded demo shopper."""
    register = client.post(
        "/consumer/register",
        json={"email": "newshopper@example.com", "password": "correct horse battery staple"},
    )
    assert register.status_code == 200, register.text
    consumer_id = register.json()["consumer_id"]
    client.consumer_token = register.json()["token"]

    session_id = create_session(client)
    blocked = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["error"]["code"] == "ADDRESS_REQUIRED"

    added = client.post(
        f"/consumer/{consumer_id}/addresses",
        json={
            "recipient": "New Shopper",
            "lines": ["1 Example Ave", "#01-01"],
            "postal_code": "123456",
            "country": "SG",
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["is_default"] is True

    now_works = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    assert now_works.status_code == 200, now_works.text
    assert now_works.json()["data"]["shipping_address"]["recipient"] == "New Shopper"


def test_adding_an_address_requires_the_owning_consumer(client: TestClient) -> None:
    register = client.post(
        "/consumer/register",
        json={"email": "other-shopper@example.com", "password": "correct horse battery staple"},
    )
    consumer_id = register.json()["consumer_id"]
    other_token = register.json()["token"]
    saved_token = client.consumer_token
    client.consumer_token = other_token
    try:
        forbidden = client.post(
            f"/consumer/{'usr_demo_impersonated'}/addresses",
            json={"recipient": "X", "lines": ["1 St"], "postal_code": "123456", "country": "SG"},
        )
        assert forbidden.status_code in (403, 401)
    finally:
        client.consumer_token = saved_token
    # Sanity: the legitimate owner path still works, proving the 403 above was real auth,
    # not a broken endpoint.
    own = client.post(
        f"/consumer/{consumer_id}/addresses",
        json={"recipient": "X", "lines": ["1 St"], "postal_code": "123456", "country": "SG"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert own.status_code == 200, own.text


def test_choosing_a_second_product_adds_to_the_same_cart(client: TestClient) -> None:
    session_id = create_session(client)

    first = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101", "quantity": 1},
    )
    assert first.status_code == 200, first.text

    combined = client.post(
        "/agent/action",
        json={
            "session_id": session_id,
            "action": "select",
            "items": [
                {"sku": "MYSA-CLN-101", "quantity": 1},
                {"sku": "MYSA-MST-120", "quantity": 2},
            ],
        },
    )
    assert combined.status_code == 200, combined.text
    cart = combined.json()["data"]
    assert cart["status"] == "preview"
    assert [item["sku"] for item in cart["items"]] == ["MYSA-CLN-101", "MYSA-MST-120"]
    assert cart["items"][1]["quantity"] == 2
    expected_total = cart["items"][0]["unit_price_cents"] + cart["items"][1]["unit_price_cents"] * 2
    assert cart["total_cents"] == expected_total

    checkout = confirm_cart(client, session_id, cart)
    bank_token = issue_bank_token(client, session_id, checkout["consent"])
    approved = client.post(
        "/agent/pay",
        json={
            "session_id": session_id,
            "cart_id": checkout["consent"]["cart_id"],
            "payment_mandate_id": checkout["consent"]["payment_mandate_id"],
            "token_id": checkout["consent"]["token_id"],
            "bank_token": bank_token,
        },
        headers={"Idempotency-Key": "multi-item-1"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert len(approved.json()["receipt"]["items"]) == 2


def test_routine_plan_is_ordered_and_grounded_without_a_model(client: TestClient) -> None:
    session_id = create_session(client)
    response = client.post(
        "/agent/turn",
        json={
            "session_id": session_id,
            "text": "i have dry skin, suggest a morning and night routine and the steps",
        },
    )
    assert response.status_code == 200, response.text
    events = response.json()["events"]
    routine = next(event["data"] for event in events if event["type"] == "routine")

    assert routine["plan_source"] == "catalog_database"
    # DEMO_MODE is on under test, so the plan must stand up with no model call at all.
    assert routine["phrasing_source"] == "deterministic_plan"

    orders = [step["order"] for step in routine["steps"]]
    assert orders == sorted(orders), "routine steps must be in pack order"
    assert len({step["step"] for step in routine["steps"]}) == len(routine["steps"])

    with connect() as connection:
        for step in routine["steps"]:
            row = connection.execute(
                "SELECT title, attributes_json FROM products WHERE sku=?", (step["sku"],)
            ).fetchone()
            assert row is not None, f"{step['sku']} is not a real catalog product"
            assert step["title"] == row["title"]
            assert step["step"] == json.loads(row["attributes_json"])["routine_step"]

    sunscreen = [step for step in routine["steps"] if step["step"] == "sunscreen"]
    assert all(step["when"] == ["morning"] for step in sunscreen), "sunscreen is morning-only"


def test_routine_is_simple_until_usage_detail_is_asked_for(client: TestClient) -> None:
    session_id = create_session(client)
    plain = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "dry skin, what routine should i use morning and night"},
    )
    routine = next(
        event["data"] for event in plain.json()["events"] if event["type"] == "routine"
    )
    assert routine["steps"], "expected a routine"
    assert routine["usage_detail"] is False
    assert all(step["advice"] is None for step in routine["steps"]), (
        "usage advice should not appear until the shopper asks for it"
    )

    asked = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "how do i use these products"},
    )
    detailed = next(
        event["data"] for event in asked.json()["events"] if event["type"] == "routine"
    )
    assert detailed["usage_detail"] is True
    for step in detailed["steps"]:
        assert step["advice"], f"{step['sku']} was shown with no usage guidance"


def test_usage_question_reuses_visible_products_instead_of_dead_ending(client: TestClient) -> None:
    session_id = create_session(client)
    first = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "dry sensitive skin morning and night routine"},
    )
    shown = next(
        event["data"]["products"]
        for event in first.json()["events"]
        if event["type"] == "product_cards"
    )
    assert shown

    # A phrase with no catalog terms in it: the search behind it can legitimately
    # return nothing, and the shopper must still get an answer about what is on screen.
    follow_up = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "how do i use these products"},
    )
    assert follow_up.status_code == 200, follow_up.text
    types = [event["type"] for event in follow_up.json()["events"]]
    assert "routine" in types, f"usage question dead-ended with {types}"
    routine = next(
        event["data"] for event in follow_up.json()["events"] if event["type"] == "routine"
    )
    assert all(step["advice"] for step in routine["steps"])


def test_guardian_drops_ungrounded_and_medical_recommendation_lines() -> None:
    safe, violations = validate_recommendation(
        {
            "summary": "A gentle routine for dry skin.",
            "steps": [
                {"sku": "MYSA-CLN-101", "advice": "Use morning and night on damp skin."},
                {"sku": "NOT-A-REAL-SKU", "advice": "Apply this invented product first."},
                {"sku": "MYSA-MST-120", "advice": "This cures eczema overnight."},
            ],
        },
        allowed_skus=["MYSA-CLN-101", "MYSA-MST-120"],
    )
    assert [step["sku"] for step in safe["steps"]] == ["MYSA-CLN-101"]
    assert set(violations) == {"UNGROUNDED_CLAIM", "MEDICAL_CLAIM"}
    assert safe["summary"] == "A gentle routine for dry skin."


def test_guardian_drops_a_medical_summary_but_keeps_valid_steps() -> None:
    safe, violations = validate_recommendation(
        {
            "summary": "This routine will cure your rosacea.",
            "steps": [{"sku": "MYSA-CLN-101", "advice": "Cleanse morning and night."}],
        },
        allowed_skus=["MYSA-CLN-101"],
    )
    assert safe["summary"] == ""
    assert violations == ["MEDICAL_CLAIM"]
    assert len(safe["steps"]) == 1


def test_optional_limit_can_be_added_changed_and_cleared(client: TestClient) -> None:
    session_id = create_session(client)
    initial = client.get(f"/agent/session/{session_id}").json()
    assert initial["budget_cents"] is None
    assert initial["constraint_mode"] == "per_purchase"

    search_budget = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "Show me a cleanser under S$35"},
    )
    assert search_budget.status_code == 200
    assert client.get(f"/agent/session/{session_id}").json()["budget_cents"] is None

    first = client.put(
        f"/agent/session/{session_id}/limit",
        json={"budget_cents": 5000, "currency": "SGD", "source": "shopper_ui"},
    )
    assert first.status_code == 200
    assert first.json()["max_amount_cents"] == 5000

    preview = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101"},
    ).json()["data"]
    changed = client.put(
        f"/agent/session/{session_id}/limit",
        json={"budget_cents": 4000, "currency": "SGD", "source": "shopper_ui"},
    )
    assert preview["cart_mandate_id"] in changed.json()["invalidated_cart_mandate_ids"]

    stale_consent = client.post(
        "/agent/confirm",
        json={
            "session_id": session_id,
            "cart_id": preview["cart_id"],
            "confirmation": {"method": "click"},
        },
    )
    assert stale_consent.status_code == 409

    cleared = client.put(
        f"/agent/session/{session_id}/limit",
        json={"budget_cents": None, "currency": "SGD", "source": "shopper_ui"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["constraint_mode"] == "per_purchase"


def test_over_limit_stops_before_bank_and_creates_no_order(client: TestClient) -> None:
    session_id = create_session(client, budget_cents=3000)
    result = client.post(
        "/agent/action",
        json={"session_id": session_id, "action": "select", "sku": "MYSA-CLN-101"},
    )
    assert result.status_code == 200
    decline = result.json()["data"]
    assert decline["decline_code"] == "AMOUNT_EXCEEDS_MANDATE"
    assert decline["bank_contacted"] is False
    assert decline["order_created"] is False
    with connect() as connection:
        orders = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE session_id=?", (session_id,)
        ).fetchone()[0]
        assert orders == 0


def test_tap_nonce_replay_is_rejected(client: TestClient) -> None:
    payload = {
        "session_id": "ses_missing",
        "cart_id": "cart_missing",
        "payment_mandate_id": "mnd_missing",
        "token_id": "tok_missing",
        "bank_token": "btk_missing",
    }
    raw = canonical_json(payload)
    headers = sign_tap_request(
        method="POST",
        authority="testserver",
        path="/pay/authorize",
        body=raw,
        tag="agent-payer-auth",
    )
    headers["Idempotency-Key"] = "tap-replay-test"
    first = client.post("/pay/authorize", content=raw, headers=headers)
    assert first.status_code == 409
    second = client.post("/pay/authorize", content=raw, headers=headers)
    assert second.status_code == 401
    assert second.json()["detail"]["error"]["code"] == "NONCE_REPLAY"


def test_payment_mandate_rejects_token_from_another_cart(client: TestClient) -> None:
    first_session = create_session(client)
    first = build_consented_cart(client, first_session)
    first_bank_token = issue_bank_token(client, first_session, first["consent"])

    second_session = create_session(client)
    second = build_consented_cart(client, second_session)

    substituted = client.post(
        "/agent/pay",
        json={
            "session_id": first_session,
            "cart_id": first["consent"]["cart_id"],
            "payment_mandate_id": first["consent"]["payment_mandate_id"],
            "token_id": second["consent"]["token_id"],
            "bank_token": first_bank_token,
        },
        headers={"Idempotency-Key": "substituted-token"},
    )
    assert substituted.status_code == 409
    assert substituted.json()["detail"]["error"]["code"] == "PAYMENT_CHAIN_MISMATCH"
    with connect() as connection:
        orders = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE session_id IN (?,?)",
            (first_session, second_session),
        ).fetchone()[0]
        assert orders == 0


def test_catalog_upload_keeps_valid_rows_and_reports_invalid_ones(client: TestClient) -> None:
    catalog = (
        "SKU,Name,Price,Ingredients,Skin types,Stock,Routine step,Fragrance free\n"
        'NEW-1,Soft Water Cleanser,29.90,"glycerin,panthenol",sensitive,10,cleanser,true\n'
        "NEW-2,Incomplete Product,N/A,,dry,2,cleanser,true"
    )
    response = client.post(
        "/merchant/m_mysa/catalog",
        files={"file": ("catalog.csv", catalog.encode(), "text/csv")},
        headers={"X-Merchant-Key": MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ready"] == 1
    assert result["ingested"] == 0
    assert result["skipped"] == 1
    assert result["partial_success"] is True
    assert result["errors"][0]["row"] == 3


def test_medical_request_gets_safe_boundary_without_catalog_tool(client: TestClient) -> None:
    session_id = create_session(client)
    response = client.post(
        "/agent/turn",
        json={"session_id": session_id, "text": "Diagnose this rash and cure my eczema"},
    )
    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["type"] for event in events] == ["safety_boundary"]
    assert "diagnose" in events[0]["data"]["message"]
