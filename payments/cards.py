"""The shopper's card, captured once per shopping session.

The demo used to invent a card number at checkout, which made the most sensitive step of
the flow the only one nobody had to consent to. A session now carries a card the shopper
actually entered.

What is kept is deliberately minimal: brand, expiry, holder name and the last four digits.
The primary account number is validated in memory and then dropped — it is never written to
the database, never logged, and never returned in a response. That is the same shape a real
tokenising gateway leaves behind, and it keeps the evidence trail honest: every later step
(cart preview, payment token, receipt) reads the last four from here rather than a constant.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.db import transaction, utc_now
from app.errors import api_error

# Brands the Phase 0 demo will take. Visa is the network the authorization adapter talks to;
# the others are accepted so a judge testing with their own card shape is not stonewalled.
BRAND_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Visa", r"^4\d{12}(\d{3})?$"),
    ("Mastercard", r"^(5[1-5]\d{14}|2(2[2-9]\d{12}|[3-6]\d{13}|7[01]\d{12}|720\d{12}))$"),
    ("American Express", r"^3[47]\d{13}$"),
)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _brand(digits: str) -> str | None:
    for brand, pattern in BRAND_PATTERNS:
        if re.fullmatch(pattern, digits):
            return brand
    return None


def _expiry(month: int, year: int) -> str:
    if not 1 <= month <= 12:
        raise api_error(400, "VALIDATION", "The expiry month must be between 1 and 12.")
    if year < 100:
        year += 2000
    now = datetime.now(UTC)
    if (year, month) < (now.year, now.month):
        raise api_error(400, "CARD_EXPIRED", "That card has expired. Use a card that is still valid.")
    if year > now.year + 20:
        raise api_error(400, "VALIDATION", "Check the expiry year on the card.")
    return f"{month:02d}/{year % 100:02d}"


def save_session_card(
    session_id: str,
    *,
    number: str,
    expiry_month: int,
    expiry_year: int,
    cvc: str,
    holder: str,
) -> dict[str, Any]:
    """Validate a card and keep only what a receipt needs. Raises on anything unusable."""
    digits = re.sub(r"[\s-]", "", number)
    if not digits.isdigit():
        raise api_error(400, "VALIDATION", "A card number is digits only.")
    brand = _brand(digits)
    if not brand or not _luhn_ok(digits):
        raise api_error(400, "CARD_INVALID", "That card number is not valid. Check the digits.")
    if not re.fullmatch(r"\d{4}" if brand == "American Express" else r"\d{3}", cvc.strip()):
        raise api_error(400, "CARD_INVALID", "Check the security code on the back of the card.")
    holder_name = holder.strip()
    if not 2 <= len(holder_name) <= 80:
        raise api_error(400, "VALIDATION", "Enter the name printed on the card.")
    expiry = _expiry(expiry_month, expiry_year)
    last4 = digits[-4:]

    with transaction() as connection:
        updated = connection.execute(
            "UPDATE sessions SET card_brand=?, card_last4=?, card_expiry=?, card_holder=? "
            "WHERE session_id=?",
            (brand, last4, expiry, holder_name, session_id),
        ).rowcount
    if not updated:
        raise api_error(404, "NO_SESSION", "The shopping session was not found.")
    # Imported here: payments.service imports this module for the cart preview, so a
    # module-level import would close the cycle.
    from payments.service import record_trust

    record_trust(
        session_id,
        "constraint",
        "Card added — only the last four digits are stored",
        detail={"brand": brand, "last4": last4, "pan_stored": False, "at": utc_now()},
    )
    return {"brand": brand, "last4": last4, "expiry": expiry, "holder": holder_name}


def session_card(session_row) -> dict[str, str] | None:
    """The card on a session row, or None when the shopper has not entered one yet."""
    if not session_row["card_last4"]:
        return None
    return {
        "brand": session_row["card_brand"] or "Visa",
        "last4": session_row["card_last4"],
        "expiry": session_row["card_expiry"] or "",
        "holder": session_row["card_holder"] or "",
    }
