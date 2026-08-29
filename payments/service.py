from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db import connect, issuer_connect, json_load, transaction, utc_now
from app.errors import api_error
from app.ids import new_id
from app.settings import settings
from payments.tap import canonical_json, sign_record, verify_record

DEMO_OTP = "492118"


def _expires(minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def _is_expired(value: str) -> bool:
    return datetime.fromisoformat(value) < datetime.now(UTC)


def record_trust(
    session_id: str,
    stage: str,
    label: str,
    status: str = "ok",
    detail: dict[str, Any] | None = None,
    *,
    connection=None,
) -> None:
    owns_connection = connection is None
    db = connection or connect()
    try:
        db.execute(
            "INSERT INTO trust_events(session_id, at, stage, label, status, detail_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, utc_now(), stage, label, status, json.dumps(detail or {})),
        )
        if owns_connection:
            db.commit()
    finally:
        if owns_connection:
            db.close()


def _create_mandate(
    connection,
    *,
    mandate_type: str,
    session_id: str,
    payload: dict[str, Any],
    parent_id: str | None = None,
    version: int = 1,
    supersedes: str | None = None,
    cart_hash: str | None = None,
    expires_minutes: int = 15,
) -> dict[str, Any]:
    issued_at = utc_now()
    expires_at = _expires(expires_minutes)
    mandate_id = new_id("mnd")
    signed_record = {
        "mandate_id": mandate_id,
        "type": mandate_type,
        "parent_id": parent_id,
        "session_id": session_id,
        "version": version,
        "supersedes": supersedes,
        "payload": payload,
        "cart_hash": cart_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    signature = sign_record(signed_record)
    connection.execute(
        "INSERT INTO mandates(mandate_id,type,parent_id,session_id,version,supersedes,payload_json,"
        "cart_hash,signature,issued_at,expires_at,active) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
        (
            mandate_id,
            mandate_type,
            parent_id,
            session_id,
            version,
            supersedes,
            json.dumps(payload),
            cart_hash,
            signature,
            issued_at,
            expires_at,
        ),
    )
    return {**signed_record, "signature": signature}


def create_session_scope(
    session_id: str,
    merchant_id: str,
    *,
    budget_cents: int | None,
) -> dict[str, Any]:
    if budget_cents is not None and budget_cents <= 0:
        raise api_error(400, "VALIDATION", "A spending limit must be greater than zero.")
    with transaction() as connection:
        mandate = _create_mandate(
            connection,
            mandate_type="intent",
            session_id=session_id,
            payload={
                "category": "skincare",
                "merchant_scope": [merchant_id],
                "currency": "SGD",
                "constraint_mode": "session_cap" if budget_cents is not None else "per_purchase",
                "max_amount_cents": budget_cents,
            },
            expires_minutes=180,
        )
        connection.execute(
            "UPDATE sessions SET active_intent_id=? WHERE session_id=?",
            (mandate["mandate_id"], session_id),
        )
        record_trust(
            session_id,
            "mandate",
            "Session permission created",
            detail={"cap_cents": budget_cents, "version": 1},
            connection=connection,
        )
    return mandate


def update_session_limit(session_id: str, budget_cents: int | None) -> dict[str, Any]:
    if budget_cents is not None:
        if budget_cents <= 0:
            raise api_error(400, "VALIDATION", "A spending limit must be greater than zero.")
        if budget_cents > settings.merchant_hard_ceiling_cents:
            raise api_error(
                400,
                "VALIDATION",
                "The spending limit is above this merchant's transaction ceiling.",
                ceiling_cents=settings.merchant_hard_ceiling_cents,
            )

    with transaction() as connection:
        session = connection.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not session:
            raise api_error(404, "NO_SESSION", "The shopping session was not found.")
        old = connection.execute(
            "SELECT * FROM mandates WHERE mandate_id=?", (session["active_intent_id"],)
        ).fetchone()
        version = int(old["version"]) + 1
        old_id = old["mandate_id"]
        connection.execute("UPDATE mandates SET active=0 WHERE mandate_id=?", (old_id,))
        invalidated = [
            row["cart_mandate_id"]
            for row in connection.execute(
                "SELECT cart_mandate_id FROM carts WHERE session_id=? AND status IN ('preview','consented')",
                (session_id,),
            ).fetchall()
        ]
        connection.execute(
            "UPDATE carts SET status='invalidated' WHERE session_id=? AND status IN ('preview','consented')",
            (session_id,),
        )
        connection.execute(
            "UPDATE mandates SET active=0 WHERE mandate_id IN "
            "(SELECT cart_mandate_id FROM carts WHERE session_id=? AND status='invalidated')",
            (session_id,),
        )
        mandate = _create_mandate(
            connection,
            mandate_type="intent",
            session_id=session_id,
            version=version,
            supersedes=old_id,
            payload={
                "category": "skincare",
                "merchant_scope": [session["merchant_id"]],
                "currency": "SGD",
                "constraint_mode": "session_cap" if budget_cents is not None else "per_purchase",
                "max_amount_cents": budget_cents,
            },
            expires_minutes=180,
        )
        connection.execute(
            "UPDATE sessions SET active_intent_id=?, active_cart_id=NULL WHERE session_id=?",
            (mandate["mandate_id"], session_id),
        )
        record_trust(
            session_id,
            "mandate",
            "Spending limit updated" if budget_cents is not None else "Spending limit cleared",
            detail={"cap_cents": budget_cents, "version": version, "supersedes": old_id},
            connection=connection,
        )
    return {
        "session_id": session_id,
        "intent_mandate_id": mandate["mandate_id"],
        "supersedes": old_id,
        "constraint_mode": mandate["payload"]["constraint_mode"],
        "max_amount_cents": budget_cents,
        "invalidated_cart_mandate_ids": invalidated,
        "message": (
            f"Your S${budget_cents / 100:.2f} spending limit now applies to this session."
            if budget_cents is not None
            else "Your session spending limit has been cleared. Every purchase still needs confirmation."
        ),
    }


def _default_address(connection, consumer_id: str):
    return connection.execute(
        "SELECT * FROM addresses WHERE consumer_id=? ORDER BY is_default DESC LIMIT 1",
        (consumer_id,),
    ).fetchone()


def create_cart(session_id: str, sku: str, quantity: int = 1) -> dict[str, Any]:
    if quantity < 1 or quantity > 10:
        raise api_error(400, "VALIDATION", "Quantity must be between 1 and 10.")

    with transaction() as connection:
        session = connection.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not session:
            raise api_error(404, "NO_SESSION", "The shopping session was not found.")
        product = connection.execute(
            "SELECT * FROM products WHERE sku=? AND merchant_id=? AND category='skincare'",
            (sku, session["merchant_id"]),
        ).fetchone()
        if not product:
            raise api_error(404, "OUT_OF_SCOPE_PRODUCT", "That product is outside this session.")
        if product["stock"] < quantity:
            raise api_error(409, "OUT_OF_STOCK", "The requested quantity is not available.")
        intent = connection.execute(
            "SELECT * FROM mandates WHERE mandate_id=? AND active=1",
            (session["active_intent_id"],),
        ).fetchone()
        if not intent or _is_expired(intent["expires_at"]):
            raise api_error(409, "MANDATE_EXPIRED", "The session permission has expired.")
        intent_payload = json_load(intent["payload_json"], {})
        total_cents = int(product["price_cents"]) * quantity
        cap = intent_payload.get("max_amount_cents")
        if cap is not None and total_cents > cap:
            over_by = total_cents - cap
            record_trust(
                session_id,
                "constraint",
                "Stopped above your spending limit",
                "fail",
                {"total_cents": total_cents, "cap_cents": cap, "over_by_cents": over_by},
                connection=connection,
            )
            return {
                "status": "declined",
                "decline_code": "AMOUNT_EXCEEDS_MANDATE",
                "reason": f"This cart is S${over_by / 100:.2f} over your spending limit.",
                "total_cents": total_cents,
                "cap_cents": cap,
                "bank_contacted": False,
                "order_created": False,
            }
        address = _default_address(connection, session["consumer_id"])
        if not address:
            raise api_error(409, "ADDRESS_REQUIRED", "Add a shipping address before checkout.")
        address_value = {
            "address_id": address["address_id"],
            "recipient": address["recipient"],
            "lines": json_load(address["lines_json"], []),
            "postal_code": address["postal_code"],
            "country": address["country"],
        }
        shipping_fingerprint = hashlib.sha256(canonical_json(address_value)).hexdigest()
        items = [
            {
                "sku": product["sku"],
                "title": product["title"],
                "quantity": quantity,
                "unit_price_cents": int(product["price_cents"]),
            }
        ]
        cart_value = {
            "items": items,
            "total_cents": total_cents,
            "currency": product["currency"],
            "merchant_id": session["merchant_id"],
            "shipping_address_id": address["address_id"],
            "shipping_address_fingerprint": shipping_fingerprint,
        }
        cart_hash = "sha256:" + hashlib.sha256(canonical_json(cart_value)).hexdigest()
        cart_mandate = _create_mandate(
            connection,
            mandate_type="cart",
            session_id=session_id,
            parent_id=intent["mandate_id"],
            payload=cart_value,
            cart_hash=cart_hash,
            expires_minutes=10,
        )
        cart_id = new_id("cart")
        connection.execute(
            "INSERT INTO carts(cart_id,session_id,intent_id,cart_mandate_id,merchant_id,items_json,"
            "total_cents,currency,shipping_address_id,shipping_fingerprint,cart_hash,status,created_at,"
            "expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cart_id,
                session_id,
                intent["mandate_id"],
                cart_mandate["mandate_id"],
                session["merchant_id"],
                json.dumps(items),
                total_cents,
                product["currency"],
                address["address_id"],
                shipping_fingerprint,
                cart_hash,
                "preview",
                utc_now(),
                cart_mandate["expires_at"],
            ),
        )
        connection.execute(
            "UPDATE sessions SET active_cart_id=? WHERE session_id=?", (cart_id, session_id)
        )
        record_trust(
            session_id,
            "mandate",
            "Cart and shipping address signed",
            detail={"cart_hash": cart_hash, "cart_mandate_id": cart_mandate["mandate_id"]},
            connection=connection,
        )
        if cap is not None:
            record_trust(
                session_id,
                "constraint",
                "Cart is within your spending limit",
                detail={"total_cents": total_cents, "cap_cents": cap},
                connection=connection,
            )

    return {
        "status": "preview",
        "cart_id": cart_id,
        "cart_mandate_id": cart_mandate["mandate_id"],
        "cart_hash": cart_hash,
        "items": items,
        "total_cents": total_cents,
        "currency": product["currency"],
        "merchant": "Mysa Skin",
        "shipping_address": address_value,
        "last4": "4821",
        "expires_at": cart_mandate["expires_at"],
        "simulated": True,
    }


def record_consent(session_id: str, cart_id: str) -> dict[str, Any]:
    with transaction() as connection:
        cart = connection.execute(
            "SELECT * FROM carts WHERE cart_id=? AND session_id=?", (cart_id, session_id)
        ).fetchone()
        if not cart or cart["status"] != "preview":
            raise api_error(409, "CART_HASH_MISMATCH", "The transaction preview is no longer active.")
        if _is_expired(cart["expires_at"]):
            raise api_error(409, "MANDATE_EXPIRED", "The transaction preview has expired.")
        session = connection.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        intent = connection.execute(
            "SELECT * FROM mandates WHERE mandate_id=? AND active=1", (cart["intent_id"],)
        ).fetchone()
        if not intent:
            raise api_error(409, "CART_HASH_MISMATCH", "Your permissions changed; review a new cart.")
        token_id = new_id("tok")
        intent_payload = json_load(intent["payload_json"], {})
        connection.execute(
            "INSERT INTO payment_tokens(token_id,consumer_id,network_token_last4,bound_agent_kid,"
            "constraints_json,status,created_at) VALUES (?,?,?,?,?,'active',?)",
            (
                token_id,
                session["consumer_id"],
                "4821",
                settings.agent_kid,
                json.dumps(
                    {
                        "max_amount_cents": intent_payload.get("max_amount_cents"),
                        "merchant_id": cart["merchant_id"],
                        "single_use": True,
                        "expires_at": cart["expires_at"],
                    }
                ),
                utc_now(),
            ),
        )
        payment_mandate = _create_mandate(
            connection,
            mandate_type="payment",
            session_id=session_id,
            parent_id=cart["cart_mandate_id"],
            payload={
                "cart_hash": cart["cart_hash"],
                "token_id": token_id,
                "human_confirmation": {"method": "click", "at": utc_now()},
            },
            cart_hash=cart["cart_hash"],
            expires_minutes=5,
        )
        connection.execute("UPDATE carts SET status='consented' WHERE cart_id=?", (cart_id,))
        record_trust(
            session_id,
            "consent",
            "You confirmed this exact transaction",
            detail={"cart_hash": cart["cart_hash"], "payment_mandate_id": payment_mandate["mandate_id"]},
            connection=connection,
        )
    return {
        "status": "confirmed",
        "cart_id": cart_id,
        "cart_hash": cart["cart_hash"],
        "amount_cents": cart["total_cents"],
        "currency": cart["currency"],
        "merchant_id": cart["merchant_id"],
        "payment_mandate_id": payment_mandate["mandate_id"],
        "token_id": token_id,
        "message": "Your bank will ask you to approve this next.",
    }


def create_bank_challenge(
    *,
    consumer_id: str,
    cart_hash: str,
    amount_cents: int,
    currency: str,
    merchant_id: str,
) -> dict[str, Any]:
    challenge_id = new_id("chl")
    expires_at = _expires(5)
    with transaction(issuer=True) as connection:
        connection.execute(
            "INSERT INTO challenges(challenge_id,consumer_id,cart_hash,amount_cents,currency,merchant_id,"
            "attempts,status,created_at,expires_at) VALUES (?,?,?,?,?,?,0,'pending',?,?)",
            (
                challenge_id,
                consumer_id,
                cart_hash,
                amount_cents,
                currency,
                merchant_id,
                utc_now(),
                expires_at,
            ),
        )
    return {
        "challenge_id": challenge_id,
        "method": "otp",
        "masked_target": "•••• 8821",
        "expires_at": expires_at,
        "issuer": "Meridian Bank",
        "simulated": True,
    }


def verify_bank_challenge(challenge_id: str, code: str) -> dict[str, Any]:
    normalized = "".join(character for character in code if character.isdigit())
    with transaction(issuer=True) as connection:
        challenge = connection.execute(
            "SELECT * FROM challenges WHERE challenge_id=?", (challenge_id,)
        ).fetchone()
        if not challenge:
            raise api_error(404, "BANK_AUTH_DECLINED", "The bank challenge was not found.")
        if challenge["attempts"] >= 3 or challenge["status"] == "locked":
            raise api_error(429, "BANK_AUTH_DECLINED", "Too many incorrect verification attempts.")
        if _is_expired(challenge["expires_at"]):
            connection.execute(
                "UPDATE challenges SET status='expired' WHERE challenge_id=?", (challenge_id,)
            )
            return {"status": "declined", "decline_code": "BANK_TOKEN_EXPIRED"}
        if normalized != DEMO_OTP:
            attempts = int(challenge["attempts"]) + 1
            status = "locked" if attempts >= 3 else "pending"
            connection.execute(
                "UPDATE challenges SET attempts=?, status=? WHERE challenge_id=?",
                (attempts, status, challenge_id),
            )
            if attempts >= 3:
                raise api_error(429, "BANK_AUTH_DECLINED", "Too many incorrect verification attempts.")
            return {
                "status": "declined",
                "decline_code": "BANK_AUTH_DECLINED",
                "attempts_remaining": 3 - attempts,
            }
        bank_token = new_id("btk")
        expires_at = _expires(5)
        connection.execute(
            "UPDATE challenges SET status='approved' WHERE challenge_id=?", (challenge_id,)
        )
        connection.execute(
            "INSERT INTO issuer_tokens(bank_token,challenge_id,issuer,eci,cart_hash,amount_cents,"
            "merchant_id,status,created_at,expires_at) VALUES (?,?, 'Meridian Bank','05',?,?,?,'issued',?,?)",
            (
                bank_token,
                challenge_id,
                challenge["cart_hash"],
                challenge["amount_cents"],
                challenge["merchant_id"],
                utc_now(),
                expires_at,
            ),
        )
    return {
        "status": "approved",
        "bank_token": bank_token,
        "eci": "05",
        "issuer": "Meridian Bank",
        "expires_at": expires_at,
        "simulated": True,
    }


def _transaction_result(connection, transaction_id: str) -> dict[str, Any]:
    transaction_row = connection.execute(
        "SELECT * FROM transactions WHERE transaction_id=?", (transaction_id,)
    ).fetchone()
    order = connection.execute(
        "SELECT * FROM orders WHERE transaction_id=?", (transaction_id,)
    ).fetchone()
    evidence = json_load(order["evidence_json"], {}) if order else {}
    return {
        "status": transaction_row["status"],
        "transaction_id": transaction_row["transaction_id"],
        "order_id": order["order_id"] if order else None,
        "auth_code": transaction_row["auth_code"],
        "issuer": transaction_row["issuer"],
        "eci": transaction_row["eci"],
        "amount_cents": transaction_row["amount_cents"],
        "currency": transaction_row["currency"],
        "simulated": bool(transaction_row["simulated"]),
        "receipt": evidence.get("receipt"),
        "idempotent_replay": True,
    }


def authorize_payment(payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    if not idempotency_key:
        raise api_error(400, "VALIDATION", "An idempotency key is required.")

    required = {"session_id", "cart_id", "payment_mandate_id", "token_id", "bank_token"}
    if missing := required - payload.keys():
        code = "BANK_TOKEN_MISSING" if "bank_token" in missing else "VALIDATION"
        raise api_error(400, code, "The payment request is incomplete.", missing=sorted(missing))

    with connect() as connection:
        prior = connection.execute(
            "SELECT transaction_id,session_id,cart_id FROM transactions WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if prior:
            if prior["session_id"] != payload["session_id"] or prior["cart_id"] != payload["cart_id"]:
                raise api_error(
                    409,
                    "IDEMPOTENCY_MISMATCH",
                    "This idempotency key is already bound to a different transaction.",
                )
            return _transaction_result(connection, prior["transaction_id"])

    with connect() as connection:
        cart = connection.execute(
            "SELECT * FROM carts WHERE cart_id=? AND session_id=?",
            (payload["cart_id"], payload["session_id"]),
        ).fetchone()
        mandate = connection.execute(
            "SELECT * FROM mandates WHERE mandate_id=? AND type='payment'",
            (payload["payment_mandate_id"],),
        ).fetchone()
        token = connection.execute(
            "SELECT * FROM payment_tokens WHERE token_id=?", (payload["token_id"],)
        ).fetchone()
        session = connection.execute(
            "SELECT * FROM sessions WHERE session_id=?", (payload["session_id"],)
        ).fetchone()
    if not cart or not mandate or not token or not session:
        raise api_error(409, "CART_HASH_MISMATCH", "The signed payment chain is incomplete.")
    if cart["status"] != "consented":
        raise api_error(409, "HUMAN_NOT_PRESENT", "Explicit confirmation is required.")
    mandate_record = {
        "mandate_id": mandate["mandate_id"],
        "type": mandate["type"],
        "parent_id": mandate["parent_id"],
        "session_id": mandate["session_id"],
        "version": mandate["version"],
        "supersedes": mandate["supersedes"],
        "payload": json_load(mandate["payload_json"], {}),
        "cart_hash": mandate["cart_hash"],
        "issued_at": mandate["issued_at"],
        "expires_at": mandate["expires_at"],
    }
    if not verify_record(mandate_record, mandate["signature"]):
        raise api_error(401, "SIGNATURE_INVALID", "The payment mandate signature is invalid.")
    mandate_payload = mandate_record["payload"]
    if (
        mandate["session_id"] != payload["session_id"]
        or mandate["parent_id"] != cart["cart_mandate_id"]
        or mandate_payload.get("token_id") != payload["token_id"]
        or mandate_payload.get("cart_hash") != cart["cart_hash"]
    ):
        raise api_error(
            409,
            "PAYMENT_CHAIN_MISMATCH",
            "The cart, consent mandate, and payment token do not belong to one transaction.",
        )
    if mandate["cart_hash"] != cart["cart_hash"]:
        raise api_error(409, "CART_HASH_MISMATCH", "The cart changed after confirmation.")
    if _is_expired(mandate["expires_at"]):
        raise api_error(409, "MANDATE_EXPIRED", "The payment permission has expired.")
    if token["status"] != "active":
        return {"status": "declined", "decline_code": "TOKEN_REUSED", "order_created": False}
    if token["bound_agent_kid"] != settings.agent_kid or token["consumer_id"] != session["consumer_id"]:
        return {
            "status": "declined",
            "decline_code": "TOKEN_BINDING_MISMATCH",
            "order_created": False,
        }
    constraints = json_load(token["constraints_json"], {})
    if constraints.get("expires_at") and _is_expired(constraints["expires_at"]):
        return {"status": "declined", "decline_code": "TOKEN_EXPIRED", "order_created": False}
    if constraints.get("merchant_id") != cart["merchant_id"]:
        return {"status": "declined", "decline_code": "MERCHANT_MISMATCH", "order_created": False}
    cap = constraints.get("max_amount_cents")
    if cap is not None and cart["total_cents"] > cap:
        return {
            "status": "declined",
            "decline_code": "AMOUNT_EXCEEDS_MANDATE",
            "order_created": False,
        }

    with issuer_connect() as connection:
        issuer_token = connection.execute(
            "SELECT * FROM issuer_tokens WHERE bank_token=?", (payload["bank_token"],)
        ).fetchone()
    if not issuer_token:
        return {"status": "declined", "decline_code": "BANK_TOKEN_MISSING", "order_created": False}
    if issuer_token["status"] != "issued":
        return {"status": "declined", "decline_code": "BANK_TOKEN_REUSED", "order_created": False}
    if _is_expired(issuer_token["expires_at"]):
        return {"status": "declined", "decline_code": "BANK_TOKEN_EXPIRED", "order_created": False}
    if (
        issuer_token["cart_hash"] != cart["cart_hash"]
        or issuer_token["amount_cents"] != cart["total_cents"]
        or issuer_token["merchant_id"] != cart["merchant_id"]
    ):
        return {
            "status": "declined",
            "decline_code": "BANK_TOKEN_CART_MISMATCH",
            "order_created": False,
        }

    with transaction(issuer=True) as issuer_db:
        updated = issuer_db.execute(
            "UPDATE issuer_tokens SET status='consumed' WHERE bank_token=? AND status='issued'",
            (payload["bank_token"],),
        ).rowcount
        if not updated:
            return {
                "status": "declined",
                "decline_code": "BANK_TOKEN_REUSED",
                "order_created": False,
            }

    try:
        with transaction() as connection:
            token_updated = connection.execute(
                "UPDATE payment_tokens SET status='used' WHERE token_id=? AND status='active'",
                (token["token_id"],),
            ).rowcount
            if not token_updated:
                raise api_error(409, "TOKEN_REUSED", "The constrained payment token was already used.")
            transaction_id = new_id("txn")
            order_id = new_id("ord")
            auth_code = secrets.token_hex(3).upper()
            items = json_load(cart["items_json"], [])
            receipt = {
                "transaction_id": transaction_id,
                "order_id": order_id,
                "merchant": "Mysa Skin",
                "items": items,
                "total_cents": cart["total_cents"],
                "currency": cart["currency"],
                "last4": "4821",
                "auth_code": auth_code,
                "issuer": issuer_token["issuer"],
                "eci": issuer_token["eci"],
                "at": utc_now(),
                "simulated": True,
            }
            connection.execute(
                "INSERT INTO transactions(transaction_id,idempotency_key,session_id,cart_id,status,"
                "amount_cents,currency,auth_code,issuer,eci,simulated,created_at) "
                "VALUES (?,?,?,?, 'approved',?,?,?,?,?,1,?)",
                (
                    transaction_id,
                    idempotency_key,
                    payload["session_id"],
                    cart["cart_id"],
                    cart["total_cents"],
                    cart["currency"],
                    auth_code,
                    issuer_token["issuer"],
                    issuer_token["eci"],
                    utc_now(),
                ),
            )
            connection.execute(
                "INSERT INTO orders(order_id,transaction_id,session_id,evidence_json,created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    order_id,
                    transaction_id,
                    payload["session_id"],
                    json.dumps(
                        {
                            "cart_hash": cart["cart_hash"],
                            "payment_mandate_id": mandate["mandate_id"],
                            "tap_keyid": settings.agent_kid,
                            "receipt": receipt,
                        }
                    ),
                    utc_now(),
                ),
            )
            connection.execute("UPDATE carts SET status='paid' WHERE cart_id=?", (cart["cart_id"],))
            record_trust(
                payload["session_id"],
                "decision",
                "Simulated Visa authorization approved",
                detail={"transaction_id": transaction_id, "simulated": True},
                connection=connection,
            )
            record_trust(
                payload["session_id"],
                "order",
                "Order and authorization evidence recorded",
                detail={"order_id": order_id},
                connection=connection,
            )
    except Exception:
        with transaction(issuer=True) as issuer_db:
            issuer_db.execute(
                "UPDATE issuer_tokens SET status='issued' WHERE bank_token=? AND status='consumed'",
                (payload["bank_token"],),
            )
        raise

    return {
        "status": "approved",
        "transaction_id": transaction_id,
        "order_id": order_id,
        "auth_code": auth_code,
        "issuer": issuer_token["issuer"],
        "eci": issuer_token["eci"],
        "amount_cents": cart["total_cents"],
        "currency": cart["currency"],
        "simulated": True,
        "receipt": receipt,
        "idempotent_replay": False,
    }


def mandate_chain(mandate_id: str) -> dict[str, Any]:
    links: list[dict[str, Any]] = []
    with connect() as connection:
        current_id: str | None = mandate_id
        while current_id:
            row = connection.execute(
                "SELECT * FROM mandates WHERE mandate_id=?", (current_id,)
            ).fetchone()
            if not row:
                links.append({"mandate_id": current_id, "verified": False, "failed_check": "missing"})
                break
            value = {
                "mandate_id": row["mandate_id"],
                "type": row["type"],
                "parent_id": row["parent_id"],
                "session_id": row["session_id"],
                "version": row["version"],
                "supersedes": row["supersedes"],
                "payload": json_load(row["payload_json"], {}),
                "cart_hash": row["cart_hash"],
                "issued_at": row["issued_at"],
                "expires_at": row["expires_at"],
            }
            valid = verify_record(value, row["signature"])
            links.append(
                {
                    "mandate_id": row["mandate_id"],
                    "type": row["type"],
                    "verified": valid and not _is_expired(row["expires_at"]),
                    "failed_check": None if valid else "signature",
                }
            )
            current_id = row["parent_id"]
    links.reverse()
    return {"links": links, "verified": bool(links) and all(link["verified"] for link in links)}
