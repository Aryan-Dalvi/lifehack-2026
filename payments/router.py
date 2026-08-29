from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import connect, issuer_connect, json_load
from app.errors import api_error
from payments.service import (
    authorize_payment,
    create_bank_challenge,
    mandate_chain,
    record_consent,
    record_trust,
    verify_bank_challenge,
)
from payments.tap import verify_tap_request

bank_router = APIRouter(prefix="/bank", tags=["issuer"])
pay_router = APIRouter(prefix="/pay", tags=["payments"])
trust_router = APIRouter(prefix="/trust", tags=["trust"])


class BankChallengeRequest(BaseModel):
    consumer_id: str
    cart_hash: str
    amount_cents: int = Field(gt=0)
    currency: str = "SGD"
    merchant_id: str
    session_id: str | None = None


class BankVerifyRequest(BaseModel):
    challenge_id: str
    code: str
    session_id: str | None = None


class ConsentRequest(BaseModel):
    session_id: str
    cart_id: str


@bank_router.post("/challenge")
def bank_challenge(body: BankChallengeRequest) -> dict[str, Any]:
    response = create_bank_challenge(**body.model_dump(exclude={"session_id"}))
    if body.session_id:
        record_trust(
            body.session_id,
            "issuer",
            "Bank verification requested",
            detail={"challenge_id": response["challenge_id"]},
        )
    return response


@bank_router.post("/verify")
def bank_verify(body: BankVerifyRequest) -> dict[str, Any]:
    response = verify_bank_challenge(body.challenge_id, body.code)
    if body.session_id and response["status"] == "approved":
        record_trust(
            body.session_id,
            "issuer",
            "Bank verified this transaction",
            detail={"issuer": response["issuer"], "eci": response["eci"]},
        )
    return response


@bank_router.get("/token/{bank_token}")
def bank_token_status(bank_token: str) -> dict[str, Any]:
    with issuer_connect() as connection:
        row = connection.execute(
            "SELECT bank_token,issuer,eci,status,expires_at FROM issuer_tokens WHERE bank_token=?",
            (bank_token,),
        ).fetchone()
    if not row:
        raise api_error(404, "BANK_TOKEN_MISSING", "The bank token was not found.")
    return dict(row)


@pay_router.post("/consent")
def consent(body: ConsentRequest) -> dict[str, Any]:
    return record_consent(body.session_id, body.cart_id)


@pay_router.post("/authorize")
async def authorize(
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    raw_body = await request.body()
    authority = request.headers.get("host", "localhost:8000")
    verification = verify_tap_request(
        method=request.method,
        authority=authority,
        path=request.url.path,
        body=raw_body,
        headers=dict(request.headers),
        expected_tag="agent-payer-auth",
    )
    payload = json.loads(raw_body)
    record_trust(
        payload["session_id"],
        "signature",
        "Trusted agent payer request verified",
        detail={"keyid": verification["keyid"], "tag": verification["tag"]},
    )
    return authorize_payment(payload, idempotency_key)


@pay_router.get("/mandates/{mandate_id}/chain")
def chain(mandate_id: str) -> dict[str, Any]:
    result = mandate_chain(mandate_id)
    if not result["links"]:
        raise api_error(404, "NO_MANDATE", "The mandate was not found.")
    return result


@pay_router.get("/receipt/{transaction_id}")
def receipt(transaction_id: str) -> dict[str, Any]:
    with connect() as connection:
        order = connection.execute(
            "SELECT evidence_json FROM orders WHERE transaction_id=?", (transaction_id,)
        ).fetchone()
    if not order:
        raise api_error(404, "NO_TRANSACTION", "The receipt was not found.")
    return json_load(order["evidence_json"], {})["receipt"]


def _trust_rows(session_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM trust_events WHERE session_id=? ORDER BY seq", (session_id,)
        ).fetchall()
    return [
        {
            **dict(row),
            "detail": json_load(row["detail_json"], {}),
        }
        for row in rows
    ]


@trust_router.get("/events/snapshot")
def trust_snapshot(session_id: str) -> dict[str, Any]:
    return {"events": _trust_rows(session_id)}


@trust_router.get("/events")
def trust_events(session_id: str) -> StreamingResponse:
    def stream():
        for event in _trust_rows(session_id):
            yield f"event: trust_event\ndata: {json.dumps(event)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

