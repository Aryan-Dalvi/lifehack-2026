from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.guardian import validate_interpretation, validate_products
from agent.interpreter import PACK, interpret
from app.db import connect, json_load, transaction, utc_now
from app.errors import api_error
from app.ids import new_id
from merchant.router import catalog_product, catalog_search
from payments.service import (
    authorize_payment,
    create_cart,
    create_session_scope,
    record_consent,
    record_trust,
    update_session_limit,
)
from payments.tap import canonical_json, sign_tap_request, verify_tap_request

router = APIRouter(prefix="/agent", tags=["agent"])


class SessionRequest(BaseModel):
    merchant_id: str = "m_mysa"
    category: str = "skincare"
    consumer_id: str = "usr_demo"
    budget_cents: int | None = Field(default=None, gt=0)


class LimitRequest(BaseModel):
    budget_cents: int | None = Field(default=None, gt=0)
    currency: str = "SGD"
    source: str = "shopper_ui"


class MessageRequest(BaseModel):
    session_id: str
    text: str = Field(max_length=2000)


class ActionRequest(BaseModel):
    session_id: str
    action: str
    skus: list[str] = Field(default_factory=list)
    sku: str | None = None
    quantity: int = Field(default=1, ge=1, le=10)
    text: str | None = None


class ConfirmRequest(BaseModel):
    session_id: str
    cart_id: str
    confirmation: dict[str, Any] = Field(default_factory=lambda: {"method": "click"})


class PayRequest(BaseModel):
    session_id: str
    cart_id: str
    payment_mandate_id: str
    token_id: str
    bank_token: str


def _session(session_id: str):
    with connect() as connection:
        session = connection.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not session:
            raise api_error(404, "NO_SESSION", "The shopping session was not found.")
        intent = connection.execute(
            "SELECT payload_json FROM mandates WHERE mandate_id=?", (session["active_intent_id"],)
        ).fetchone()
    return session, json_load(intent["payload_json"], {}) if intent else {}


@router.post("/session")
def create_session(body: SessionRequest) -> dict[str, Any]:
    if body.category != "skincare":
        raise api_error(400, "VALIDATION", "The Phase 0 agent supports skincare only.")
    with connect() as connection:
        merchant = connection.execute(
            "SELECT * FROM merchants WHERE merchant_id=?", (body.merchant_id,)
        ).fetchone()
    if not merchant:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    session_id = new_id("ses")
    with transaction() as connection:
        connection.execute(
            "INSERT INTO sessions(session_id,merchant_id,consumer_id,category,created_at) "
            "VALUES (?,?,?,?,?)",
            (session_id, body.merchant_id, body.consumer_id, "skincare", utc_now()),
        )
    intent = create_session_scope(
        session_id, body.merchant_id, budget_cents=body.budget_cents
    )
    return {
        "session_id": session_id,
        "intent_mandate_id": intent["mandate_id"],
        "category_pack_id": PACK["id"],
        "greeting": PACK["greeting"],
        "budget_cents": body.budget_cents,
        "payment_mode": "simulator",
    }


@router.get("/session/{session_id}")
def session_status(session_id: str) -> dict[str, Any]:
    session, intent = _session(session_id)
    return {
        "session_id": session_id,
        "merchant_id": session["merchant_id"],
        "category": session["category"],
        "active_intent_id": session["active_intent_id"],
        "active_cart_id": session["active_cart_id"],
        "visible_skus": json_load(session["visible_skus_json"], []),
        "profile": json_load(session["profile_json"], {}),
        "budget_cents": intent.get("max_amount_cents"),
        "constraint_mode": intent.get("constraint_mode"),
    }


@router.put("/session/{session_id}/limit")
def set_limit(session_id: str, body: LimitRequest) -> dict[str, Any]:
    if body.currency != "SGD":
        raise api_error(400, "VALIDATION", "The Mysa Skin demo uses SGD.")
    return update_session_limit(session_id, body.budget_cents)


def _comparison(skus: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(skus))[:3]
    if len(unique) < 2:
        raise api_error(400, "VALIDATION", "Choose at least two products to compare.")
    products = [catalog_product(sku) for sku in unique]
    dimensions = []
    for dimension in PACK["comparison_dimensions"]:
        cells = []
        for product in products:
            if dimension["key"] == "price_cents":
                value = product["price_cents"]
            elif dimension["key"] == "rating":
                value = {
                    "average": product["rating_avg"],
                    "count": product["rating_count"],
                }
            else:
                value = product["attributes"].get(dimension["key"])
            cells.append({"sku": product["sku"], "value": value})
        dimensions.append({**dimension, "cells": cells})
    return {
        "products": products,
        "dimensions": dimensions,
        "source": "catalog_database",
        "llm_calls": 0,
    }


async def _turn(session_id: str, text: str) -> list[dict[str, Any]]:
    session, intent_payload = _session(session_id)
    visible_skus = json_load(session["visible_skus_json"], [])
    interpretation, source = await interpret(
        session_id=session_id,
        message=text,
        merchant_id=session["merchant_id"],
        visible_skus=visible_skus,
        profile=json_load(session["profile_json"], {}),
        shopper_cap_cents=intent_payload.get("max_amount_cents"),
    )
    interpretation = validate_interpretation(
        interpretation,
        merchant_id=session["merchant_id"],
        visible_skus=visible_skus,
    )
    record_trust(
        session_id,
        "agent",
        "Skincare request interpreted",
        detail={"route": interpretation["route"], "source": source, "llm_calls": int(source == "openai_responses")},
    )
    if interpretation["route"] in {"clarify", "unsupported"}:
        return [
            {
                "type": "clarification" if interpretation["route"] == "clarify" else "safety_boundary",
                "data": {
                    "message": interpretation["clarification"],
                    "missing_fields": interpretation["missing_required_fields"],
                },
            }
        ]
    if interpretation["route"] == "compare":
        return [{"type": "comparison", "data": _comparison(interpretation["selected_skus"])}]
    query = interpretation["catalog_query"]
    if not query:
        return [
            {
                "type": "clarification",
                "data": {
                    "message": (
                        interpretation.get("clarification")
                        or "Which product or skincare need would you like help with?"
                    ),
                    "missing_fields": interpretation.get("missing_required_fields")
                    or ["product_or_need"],
                },
            }
        ]
    filters = {
        key: value
        for key, value in query["filters"].items()
        if value is not None and value != "" and value != []
    }
    result = catalog_search(
        q=query["q"],
        merchant_id=session["merchant_id"],
        category="skincare",
        max_price_cents=query["max_price_cents"],
        attrs=json.dumps(filters),
        limit=query["limit"],
    )
    products = validate_products(result["results"], session["merchant_id"])
    with transaction() as connection:
        connection.execute(
            "UPDATE sessions SET visible_skus_json=? WHERE session_id=?",
            (json.dumps([product["sku"] for product in products]), session_id),
        )
    if not products:
        return [
            {
                "type": "clarification",
                "data": {
                    "message": "Nothing matches all of those preferences. Which non-safety preference may I relax?",
                    "missing_fields": ["relaxable_preference"],
                    "applied_filters": filters,
                },
            }
        ]
    return [
        {
            "type": "token",
            "data": {
                "text": f"I found {len(products)} grounded options from Mysa Skin’s catalog.",
                "source": source,
            },
        },
        {"type": "product_cards", "data": {"products": products, "source": "catalog_database"}},
    ]


@router.post("/message")
async def message(body: MessageRequest) -> StreamingResponse:
    events = await _turn(body.session_id, body.text)

    def stream():
        for event in events:
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/turn")
async def turn(body: MessageRequest) -> dict[str, Any]:
    return {"events": await _turn(body.session_id, body.text)}


@router.post("/action")
async def action(body: ActionRequest) -> dict[str, Any]:
    if body.action == "compare":
        return {"type": "comparison", "data": _comparison(body.skus)}
    if body.action == "select":
        if not body.sku:
            raise api_error(400, "VALIDATION", "Choose a product before checkout.")
        return {"type": "cart", "data": create_cart(body.session_id, body.sku, body.quantity)}
    if body.action == "search":
        if not body.text:
            raise api_error(400, "VALIDATION", "Describe what you want to find.")
        return {"type": "events", "data": {"events": await _turn(body.session_id, body.text)}}
    raise api_error(400, "VALIDATION", "The requested shopper action is not supported.")


@router.post("/confirm")
def confirm(body: ConfirmRequest) -> dict[str, Any]:
    if body.confirmation.get("method") not in {"click", "button"}:
        raise api_error(400, "HUMAN_NOT_PRESENT", "Use the confirmation control for this cart.")
    return record_consent(body.session_id, body.cart_id)


@router.post("/pay")
def pay(
    body: PayRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    payload = body.model_dump()
    raw_body = canonical_json(payload)
    headers = sign_tap_request(
        method="POST",
        authority="localhost:8000",
        path="/pay/authorize",
        body=raw_body,
        tag="agent-payer-auth",
    )
    verification = verify_tap_request(
        method="POST",
        authority="localhost:8000",
        path="/pay/authorize",
        body=raw_body,
        headers=headers,
        expected_tag="agent-payer-auth",
    )
    record_trust(
        body.session_id,
        "signature",
        "Trusted agent payer request verified",
        detail={"keyid": verification["keyid"], "tag": verification["tag"]},
    )
    return authorize_payment(payload, idempotency_key or str(uuid.uuid4()))
