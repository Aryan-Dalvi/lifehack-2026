from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.guardian import validate_interpretation, validate_products, validate_recommendation
from agent.interpreter import PACK, USAGE_DETAIL_TERMS, interpret
from agent.recommender import build_routine, deterministic_recommendation, phrase_routine
from app.auth import (
    anonymous_consumer_id,
    assert_session,
    consumer_from_token,
    new_secret,
    require_consumer,
    token_digest,
)
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
    """No consumer_id field, on purpose.

    Identity comes from the Authorization header or it is anonymous. While it was read from
    the body, anyone could open a session as any shopper and have that shopper's saved
    address resolved into their cart.
    """

    merchant_id: str = "m_mysa"
    category: str = "skincare"
    budget_cents: int | None = Field(default=None, gt=0)


class LimitRequest(BaseModel):
    budget_cents: int | None = Field(default=None, gt=0)
    currency: str = "SGD"
    source: str = "shopper_ui"


class MessageRequest(BaseModel):
    session_id: str
    text: str = Field(max_length=2000)


class CartItemInput(BaseModel):
    sku: str
    quantity: int = Field(default=1, ge=1, le=10)


class ActionRequest(BaseModel):
    session_id: str
    action: str
    skus: list[str] = Field(default_factory=list)
    sku: str | None = None
    quantity: int = Field(default=1, ge=1, le=10)
    items: list[CartItemInput] = Field(default_factory=list)
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
def create_session(
    body: SessionRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if body.category != "skincare":
        raise api_error(400, "VALIDATION", "The Phase 0 agent supports skincare only.")
    with connect() as connection:
        merchant = connection.execute(
            "SELECT * FROM merchants WHERE merchant_id=?", (body.merchant_id,)
        ).fetchone()
    if not merchant:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    signed_in = consumer_from_token(authorization)
    consumer_id = signed_in or anonymous_consumer_id()
    session_id = new_id("ses")
    session_token = new_secret("st")
    with transaction() as connection:
        connection.execute(
            "INSERT INTO sessions(session_id,session_token_hash,merchant_id,consumer_id,"
            "is_anonymous,category,created_at) VALUES (?,?,?,?,?,?,?)",
            (
                session_id,
                token_digest(session_token),
                body.merchant_id,
                consumer_id,
                0 if signed_in else 1,
                "skincare",
                utc_now(),
            ),
        )
    intent = create_session_scope(
        session_id, body.merchant_id, budget_cents=body.budget_cents
    )
    return {
        "session_id": session_id,
        # Shown once. Every later call on this session must present it in X-Session-Token.
        "session_token": session_token,
        "consumer_id": consumer_id,
        "anonymous": signed_in is None,
        "intent_mandate_id": intent["mandate_id"],
        "category_pack_id": PACK["id"],
        "greeting": PACK["greeting"],
        "budget_cents": body.budget_cents,
        "payment_mode": "simulator",
    }


@router.get("/session/{session_id}")
def session_status(
    session_id: str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    assert_session(session_id, x_session_token)
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


@router.put("/session/{session_id}/identity")
def claim_session(
    session_id: str,
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    """Attach a signed-in shopper to a session they started as a guest.

    Guest browsing then signing in at checkout is the normal path, and re-opening the
    session there would throw away the basket the shopper just built. Claiming needs both
    credentials: the session token proves you opened this session, the consumer token
    proves who you are. A session already bound to someone else is never re-bound.
    """
    session = assert_session(session_id, x_session_token)
    consumer_id = require_consumer(authorization)
    if not session["is_anonymous"]:
        if session["consumer_id"] != consumer_id:
            raise api_error(403, "SESSION_FORBIDDEN", "That session belongs to another account.")
        return {"session_id": session_id, "consumer_id": consumer_id, "anonymous": False}
    with transaction() as connection:
        connection.execute(
            "UPDATE sessions SET consumer_id=?, is_anonymous=0 "
            "WHERE session_id=? AND is_anonymous=1",
            (consumer_id, session_id),
        )
    record_trust(
        session_id,
        "agent",
        "Guest session signed in",
        "ok",
        {"consumer_id": consumer_id},
    )
    return {"session_id": session_id, "consumer_id": consumer_id, "anonymous": False}


@router.put("/session/{session_id}/limit")
def set_limit(
    session_id: str,
    body: LimitRequest,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    assert_session(session_id, x_session_token)
    if body.currency != "SGD":
        raise api_error(400, "VALIDATION", "The Mysa Skin demo uses SGD.")
    return update_session_limit(session_id, body.budget_cents)


def _comparison(skus: list[str], merchant_id: str) -> dict[str, Any]:
    """Compare products, never leaving the session's merchant.

    Every SKU is read scoped to merchant_id and re-checked by the Guardian, so a SKU from
    another merchant is a 404 rather than a cross-tenant read.
    """
    unique = list(dict.fromkeys(skus))[:3]
    if len(unique) < 2:
        raise api_error(400, "VALIDATION", "Choose at least two products to compare.")
    products = validate_products(
        [catalog_product(sku, merchant_id) for sku in unique], merchant_id
    )
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


def _remember_profile(session_id: str, profile: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    """Carry a stated skin type or concern forward, so later turns stay in context.

    Only shopper-stated preference fields are kept — never identity or payment data.
    """
    updated = dict(profile)
    for key in ("skin_types", "concerns"):
        values = [value for value in (filters.get(key) or []) if isinstance(value, str)]
        if values:
            updated[key] = sorted({*updated.get(key, []), *values})
    if updated == profile:
        return profile
    with transaction() as connection:
        connection.execute(
            "UPDATE sessions SET profile_json=? WHERE session_id=?",
            (json.dumps(updated), session_id),
        )
    return updated


async def _routine_events(
    session_id: str,
    products: list[dict[str, Any]],
    *,
    message: str,
    skin_types: list[str],
    concerns: list[str],
    include_usage: bool = False,
) -> list[dict[str, Any]]:
    """Build a routine in code; phrase it only when the shopper asked how to use it.

    The routine itself is always deterministic. The optional model call is spent only
    on an explicit request for usage detail, so the default answer stays simple and
    costs nothing extra.
    """
    routine = build_routine(products, skin_types)
    if not routine:
        return [
            {
                "type": "clarification",
                "data": {
                    "message": "I could not build a routine from what is in stock. Which step would you like to start with?",
                    "missing_fields": ["routine_step"],
                },
            }
        ]

    allowed_skus = [entry["product"]["sku"] for entry in routine]
    advice_by_sku: dict[str, str] = {}

    if include_usage:
        recommendation, rec_source = await phrase_routine(
            routine, message=message, skin_types=skin_types, concerns=concerns
        )
        recommendation, violations = validate_recommendation(
            recommendation, allowed_skus=allowed_skus
        )
        # Whatever the model skipped — or the Guardian removed — still gets pack-grounded
        # guidance, so no step is ever shown without saying how to use it.
        advice_by_sku = {step["sku"]: step["advice"] for step in recommendation["steps"]}
        for entry in routine:
            sku = entry["product"]["sku"]
            if not advice_by_sku.get(sku):
                advice_by_sku[sku] = PACK["routine_usage"][entry["step"]]["usage_hint"]
    else:
        recommendation = deterministic_recommendation(routine, skin_types)
        recommendation["steps"] = []
        rec_source, violations = "deterministic_plan", []

    record_trust(
        session_id,
        "agent",
        "Routine explanation grounded in catalog",
        "warn" if violations else "ok",
        {
            "source": rec_source,
            "llm_calls": int(rec_source == "openai_responses"),
            "steps": len(routine),
            "usage_detail": include_usage,
            "dropped": sorted(set(violations)),
        },
    )

    if not recommendation["summary"]:
        recommendation["summary"] = deterministic_recommendation(routine, skin_types)["summary"]
    routine_products = [entry["product"] for entry in routine]
    with transaction() as connection:
        connection.execute(
            "UPDATE sessions SET visible_skus_json=? WHERE session_id=?",
            (json.dumps(allowed_skus), session_id),
        )

    events: list[dict[str, Any]] = []
    if recommendation["summary"]:
        events.append(
            {"type": "token", "data": {"text": recommendation["summary"], "source": rec_source}}
        )
    events.append(
        {
            "type": "routine",
            "data": {
                "steps": [
                    {
                        "step": entry["step"],
                        "label": entry["label"],
                        "order": entry["order"],
                        "when": entry["when"],
                        "sku": entry["product"]["sku"],
                        "title": entry["product"]["title"],
                        "advice": advice_by_sku.get(entry["product"]["sku"]),
                        "alternatives": entry["alternatives"],
                    }
                    for entry in routine
                ],
                "missing_steps": [
                    {"step": step, "label": usage["label"]}
                    for step, usage in sorted(
                        PACK["routine_usage"].items(), key=lambda item: item[1]["order"]
                    )
                    if step not in {entry["step"] for entry in routine}
                ],
                "usage_detail": include_usage,
                "plan_source": "catalog_database",
                "phrasing_source": rec_source,
            },
        }
    )
    events.append(
        {"type": "product_cards", "data": {"products": routine_products, "source": "catalog_database"}}
    )
    return events


async def _turn(session_id: str, text: str) -> list[dict[str, Any]]:
    session, intent_payload = _session(session_id)
    visible_skus = json_load(session["visible_skus_json"], [])
    profile = json_load(session["profile_json"], {})
    interpretation, source = await interpret(
        session_id=session_id,
        message=text,
        merchant_id=session["merchant_id"],
        visible_skus=visible_skus,
        profile=profile,
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
    # A plainly worded "how do I use these?" must reach the routine even if the model
    # routed it elsewhere — the wording is unambiguous enough to trust over the model.
    asked_for_usage = any(term in text.lower() for term in USAGE_DETAIL_TERMS)
    include_usage = bool(interpretation.get("wants_usage_detail")) or asked_for_usage
    if asked_for_usage and interpretation["route"] == "compare" and visible_skus:
        interpretation["route"] = "recommend"

    if interpretation["route"] == "compare":
        return [
            {
                "type": "comparison",
                "data": _comparison(interpretation["selected_skus"], session["merchant_id"]),
            }
        ]
    wants_routine = interpretation["route"] == "recommend"
    query = interpretation["catalog_query"]
    if wants_routine and not query and visible_skus:
        # "Which of these do I use at night?" — plan over what is already on screen.
        products = validate_products(
            [catalog_product(sku, session["merchant_id"]) for sku in visible_skus],
            session["merchant_id"],
        )
        return await _routine_events(
            session_id,
            products,
            message=text,
            skin_types=[],
            concerns=[],
            include_usage=include_usage,
        )
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
    profile = _remember_profile(session_id, profile, filters)
    if wants_routine:
        # A routine covers every step, so a single-step filter would starve it. The wider
        # limit is set here in code, not by the model, so the Guardian cap still holds.
        filters.pop("routine_step", None)
        # A routine spans the whole face, so honour a skin type stated earlier in the
        # conversation rather than planning around whatever this one sentence mentioned.
        for key in ("skin_types", "concerns"):
            if profile.get(key) and not filters.get(key):
                filters[key] = profile[key]
    result = catalog_search(
        q=query["q"],
        merchant_id=session["merchant_id"],
        category="skincare",
        max_price_cents=query["max_price_cents"],
        attrs=json.dumps(filters),
        limit=12 if wants_routine else query["limit"],
    )
    products = validate_products(result["results"], session["merchant_id"])
    if wants_routine and visible_skus:
        # "How do I use these?" is a question about what is already on screen. Keep those
        # products in play so a narrow or empty re-search can never strand the shopper.
        known = {product["sku"] for product in products}
        products = products + validate_products(
            [
                catalog_product(sku, session["merchant_id"])
                for sku in visible_skus
                if sku not in known
            ],
            session["merchant_id"],
        )
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
    if wants_routine:
        return await _routine_events(
            session_id,
            products,
            message=text,
            skin_types=filters.get("skin_types") or [],
            concerns=filters.get("concerns") or [],
            include_usage=include_usage,
        )
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
async def message(
    body: MessageRequest,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> StreamingResponse:
    assert_session(body.session_id, x_session_token)
    events = await _turn(body.session_id, body.text)

    def stream():
        for event in events:
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/turn")
async def turn(
    body: MessageRequest,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    assert_session(body.session_id, x_session_token)
    return {"events": await _turn(body.session_id, body.text)}


@router.post("/action")
async def action(
    body: ActionRequest,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    assert_session(body.session_id, x_session_token)
    if body.action == "compare":
        session, _ = _session(body.session_id)
        return {"type": "comparison", "data": _comparison(body.skus, session["merchant_id"])}
    if body.action == "select":
        if body.items:
            cart_items = [item.model_dump() for item in body.items]
        elif body.sku:
            cart_items = [{"sku": body.sku, "quantity": body.quantity}]
        else:
            raise api_error(400, "VALIDATION", "Choose a product before checkout.")
        return {"type": "cart", "data": create_cart(body.session_id, cart_items)}
    if body.action == "search":
        if not body.text:
            raise api_error(400, "VALIDATION", "Describe what you want to find.")
        return {"type": "events", "data": {"events": await _turn(body.session_id, body.text)}}
    raise api_error(400, "VALIDATION", "The requested shopper action is not supported.")


@router.post("/confirm")
def confirm(
    body: ConfirmRequest,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    assert_session(body.session_id, x_session_token)
    if body.confirmation.get("method") not in {"click", "button"}:
        raise api_error(400, "HUMAN_NOT_PRESENT", "Use the confirmation control for this cart.")
    return record_consent(body.session_id, body.cart_id)


@router.post("/pay")
def pay(
    body: PayRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, Any]:
    assert_session(body.session_id, x_session_token)
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
