"""Emailing a shopper their receipt.

An agent that pays on your behalf has to leave you a copy of what it did somewhere you own,
not only inside the tab you happened to have open. This module renders that copy and gets it
out of the process.

Delivery has two channels, and the API is honest about which one ran:

- ``smtp``        — a real message, when SMTP_HOST is configured.
- ``demo_outbox`` — the rendered message written to ``var/outbox`` and to the database, for a
  laptop with no mail server. Nothing is claimed to have been sent.

Sending is never allowed to break a payment that already succeeded: the money moved and the
order exists, so a mail failure is recorded against the order and reported as ``failed``
rather than raised.
"""

from __future__ import annotations

import html
import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any

from app.db import transaction, utc_now
from app.ids import new_id
from app.settings import settings

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
MAX_EMAIL_LENGTH = 254


def valid_email(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip()
    return len(value) <= MAX_EMAIL_LENGTH and bool(EMAIL_PATTERN.match(value))


def _money(cents: int, currency: str) -> str:
    symbol = "S$" if currency == "SGD" else f"{currency} "
    return f"{symbol}{cents / 100:,.2f}"


def render_receipt(
    receipt: dict[str, Any], *, shipping: dict[str, Any] | None
) -> tuple[str, str, str]:
    """Return (subject, plain text, HTML) for one paid order."""
    currency = receipt.get("currency", "SGD")
    total = _money(int(receipt["total_cents"]), currency)
    merchant = str(receipt.get("merchant", "the merchant"))
    subject = f"Your {merchant} order — {total}"

    item_lines = [
        f"{item['title']} x{item['quantity']} — "
        f"{_money(item['unit_price_cents'] * item['quantity'], currency)}"
        for item in receipt.get("items", [])
    ]
    address_lines: list[str] = []
    if shipping:
        address_lines = [
            str(shipping.get("recipient", "")),
            ", ".join(shipping.get("lines", [])),
            f"{shipping.get('country', 'Singapore')} {shipping.get('postal_code', '')}".strip(),
        ]
    address_lines = [line for line in address_lines if line]
    card = f"{receipt.get('card_brand', 'Visa')} •••• {receipt.get('last4', '')}"
    simulated = bool(receipt.get("simulated", True))

    text_parts = [
        f"Thank you — your order with {merchant} is confirmed.",
        "",
        *item_lines,
        "",
        f"Total paid: {total}",
        f"Card: {card}",
        f"Order: {receipt.get('order_id', '')}",
        f"Authorization: {receipt.get('auth_code', '')} ({receipt.get('issuer', '')})",
        f"Paid at: {receipt.get('at', '')}",
    ]
    if address_lines:
        text_parts += ["", "Ship to:", *address_lines]
    text_parts += [
        "",
        (
            "This purchase was authorised for this exact cart, at this merchant, for this "
            "amount, and cannot be reused."
        ),
    ]
    if simulated:
        text_parts += ["", "Simulated authorization — no real charge was made."]
    text = "\n".join(text_parts)

    item_rows = "".join(
        "<tr><td style=\"padding:6px 0\">"
        + html.escape(str(item["title"]))
        + f" &times; {item['quantity']}</td>"
        + "<td style=\"padding:6px 0;text-align:right\">"
        + _money(item["unit_price_cents"] * item["quantity"], currency)
        + "</td></tr>"
        for item in receipt.get("items", [])
    )
    address_html = ""
    if address_lines:
        address_html = (
            "<p style=\"color:#5c6357;font-size:13px;line-height:1.5\">Ship to<br>"
            + "<br>".join(html.escape(line) for line in address_lines)
            + "</p>"
        )
    simulated_html = (
        "<br><strong>Simulated authorization — no real charge was made.</strong>"
        if simulated
        else ""
    )
    body_html = (
        "<!doctype html><html><body style=\"margin:0;background:#fdfcf9;"
        "font-family:-apple-system,Segoe UI,sans-serif;color:#1f2a1c\">"
        "<div style=\"max-width:560px;margin:0 auto;padding:28px\">"
        "<p style=\"margin:0 0 4px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;"
        "color:#6f8066\">Order confirmed</p>"
        f"<h1 style=\"margin:0 0 18px;font-size:24px;font-weight:500\">{html.escape(total)} paid "
        f"to {html.escape(merchant)}</h1>"
        "<table style=\"width:100%;border-collapse:collapse;font-size:14px\">"
        f"{item_rows}"
        "<tr><td style=\"padding:10px 0 0;border-top:1px solid #e4e2da\"><strong>Total</strong></td>"
        "<td style=\"padding:10px 0 0;border-top:1px solid #e4e2da;text-align:right\">"
        f"<strong>{html.escape(total)}</strong></td></tr></table>"
        "<p style=\"color:#5c6357;font-size:13px;line-height:1.6\">"
        f"Card {html.escape(card)}<br>"
        f"Order {html.escape(str(receipt.get('order_id', '')))}<br>"
        f"Authorization {html.escape(str(receipt.get('auth_code', '')))} &middot; "
        f"{html.escape(str(receipt.get('issuer', '')))}<br>"
        f"Paid at {html.escape(str(receipt.get('at', '')))}</p>"
        f"{address_html}"
        "<p style=\"margin-top:22px;padding-top:14px;border-top:1px solid #e4e2da;color:#5c6357;"
        "font-size:12px;line-height:1.6\">This purchase was authorised for this exact cart, at "
        "this merchant, for this amount, and cannot be reused."
        f"{simulated_html}</p></div></body></html>"
    )
    return subject, text, body_html


def _send_smtp(recipient: str, subject: str, text: str, body_html: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.receipt_from_name} <{settings.receipt_from_email}>"
    message["To"] = recipient
    message.set_content(text)
    message.add_alternative(body_html, subtype="html")
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_receipt_email(
    *,
    recipient: str,
    order_id: str,
    session_id: str,
    receipt: dict[str, Any],
    shipping: dict[str, Any] | None,
) -> dict[str, str]:
    """Deliver one receipt. Returns the delivery record shown to the shopper."""
    subject, text, body_html = render_receipt(receipt, shipping=shipping)
    channel = "smtp" if settings.smtp_host else "demo_outbox"
    status = "sent" if channel == "smtp" else "simulated"
    error: str | None = None

    if channel == "smtp":
        try:
            _send_smtp(recipient, subject, text, body_html)
        # Deliberately broad: the money has already moved and the order exists, so no
        # mail fault of any kind may be allowed to turn a completed purchase into an error.
        except Exception as failure:  # noqa: BLE001
            logger.warning("receipt email failed for order %s: %s", order_id, failure)
            status, error = "failed", str(failure)[:400]
    else:
        try:
            settings.receipt_outbox_path.mkdir(parents=True, exist_ok=True)
            (settings.receipt_outbox_path / f"{order_id}.html").write_text(
                body_html, encoding="utf-8"
            )
        except OSError as failure:  # the database copy below is still the record of truth
            logger.warning("receipt outbox write failed for order %s: %s", order_id, failure)

    with transaction() as connection:
        connection.execute(
            "INSERT INTO receipt_emails(email_id,order_id,session_id,recipient,subject,body_text,"
            "body_html,channel,status,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id("eml"),
                order_id,
                session_id,
                recipient,
                subject,
                text,
                body_html,
                channel,
                status,
                error,
                utc_now(),
            ),
        )
    return {"recipient": recipient, "status": status, "channel": channel}
