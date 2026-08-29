"""Sixty days of trading history for the demo merchant, so the CRM dashboard has a past.

The dashboard computes every figure from real rows. A freshly seeded database has none, so
Mysa Skin would open on a wall of zeroes and nothing about the product would be visible. This
writes the history those figures are computed from: sessions, signed mandates, server-priced
carts, approved authorizations, orders and trust events, exactly as the live code writes them.

Two properties matter and are both deliberate:

* It is **fully deterministic** - the same day plan, roster and baskets every time, so a demo
  rehearsed at midnight shows the same numbers on stage, and a reset never changes the story.
* It is **inert** - historic sessions get no session-token hash, so none of them can be resumed
  or spent against. They are a ledger to read, not credentials.

The history spans two windows on purpose: the dashboard's "compare" is the 30 days before the
30 being shown, and that comparison is only honest if the earlier period is populated too.
Everything here belongs to `m_mysa`, the fictional demo merchant, and is labelled as simulated
in the payment records, the same as a live demo checkout.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from app.db import connect, transaction
from payments.tap import canonical_json, sign_record

WINDOW_DAYS = 30

# Orders per day, oldest first: 30 days of the comparison window, then 30 of the shown window.
# Written out rather than generated so the shape of the month - a quiet start, a launch spike
# on day 14, a steady close - is reviewable at a glance and identical on every machine.
ORDERS_BY_DAY: tuple[int, ...] = (
    0, 1, 0, 1, 0, 0, 1, 1, 0, 0,
    1, 0, 2, 0, 0, 1, 0, 1, 0, 0,
    1, 0, 1, 0, 1, 1, 0, 1, 1, 1,
    0, 1, 1, 0, 1, 0, 1, 1, 0, 1,
    0, 1, 0, 4, 1, 0, 1, 0, 1, 0,
    1, 0, 1, 1, 0, 1, 2, 0, 1, 1,
)

# Named shoppers for the customer table. Fictional, on the reserved .test domain, so nothing
# here can collide with or be mistaken for a real person's address. The first fourteen buy in
# the window on screen, ten more bought in the comparison window (four of them in both), and
# the last five never completed a purchase - which is what gives the dashboard something other
# than success to show.
ROSTER: tuple[tuple[str, str], ...] = (
    ("Sophie Tan", "sophie.tan"),
    ("Marcus Lim", "marcus.lim"),
    ("Priya Nair", "priya.nair"),
    ("Daniel Ong", "daniel.ong"),
    ("Aisha Rahman", "aisha.rahman"),
    ("Wei Jie Koh", "weijie.koh"),
    ("Hannah Goh", "hannah.goh"),
    ("Ravi Menon", "ravi.menon"),
    ("Clara Sim", "clara.sim"),
    ("Jonas Teo", "jonas.teo"),
    ("Mei Ling Chua", "meiling.chua"),
    ("Arjun Patel", "arjun.patel"),
    ("Nadia Yusof", "nadia.yusof"),
    ("Bryan Ng", "bryan.ng"),
    ("Farah Ismail", "farah.ismail"),
    ("Kenneth Yeo", "kenneth.yeo"),
    ("Divya Raman", "divya.raman"),
    ("Samuel Chia", "samuel.chia"),
    ("Yuki Tanaka", "yuki.tanaka"),
    ("Amirah Hassan", "amirah.hassan"),
    ("Elena Fischer", "elena.fischer"),
    ("Tomas Reyes", "tomas.reyes"),
    ("Grace Ho", "grace.ho"),
    ("Idris Karim", "idris.karim"),
    ("Lena Wong", "lena.wong"),
)

# Which roster member buys which order. Four people buy three times in the window on screen
# and three did in the one before it, so the repeat rate the dashboard reports is a real
# minority of real customers rather than an artefact of a small cast buying over and over.
PREVIOUS_BUYERS: tuple[int, ...] = (10, 13, 11, 14, 12, 15, 10, 16, 11, 17, 12, 18, 10, 19, 11, 12)
CURRENT_BUYERS: tuple[int, ...] = (
    0, 4, 1, 5, 2, 6, 3, 7, 0, 8, 1, 9, 2, 10, 3, 11, 0, 12, 1, 13, 2, 3,
)

# Baskets, cycled in order. A skincare order is usually a routine rather than one bottle,
# which is why most of these are two to four steps. The comparison window is weighted to full
# routines and the current one to single steps: revenue slips while customer count grows,
# which is the pattern a merchant most needs a dashboard to make visible.
PREVIOUS_BASKETS: tuple[tuple[tuple[str, int], ...], ...] = (
    (("MYSA-CLN-101", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
    (("MYSA-CLN-101", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
    (("MYSA-CLN-205", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
    (("MYSA-CLN-310", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1)),
    (("MYSA-CLN-101", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
    (("MYSA-CLN-310", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1)),
    (("MYSA-CLN-205", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
    (("MYSA-CLN-310", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
)
CURRENT_BASKETS: tuple[tuple[tuple[str, int], ...], ...] = (
    (("MYSA-CLN-101", 1), ("MYSA-SRM-010", 1), ("MYSA-MST-120", 1)),
    (("MYSA-SPF-050", 1),),
    (("MYSA-CLN-310", 1), ("MYSA-SRM-010", 1)),
    (("MYSA-CLN-205", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1)),
    (("MYSA-SRM-010", 2),),
    (("MYSA-CLN-101", 1), ("MYSA-MST-120", 1), ("MYSA-SPF-050", 1), ("MYSA-SRM-010", 1)),
    (("MYSA-CLN-310", 1), ("MYSA-MST-120", 1)),
    (("MYSA-CLN-205", 1), ("MYSA-SRM-010", 1), ("MYSA-SPF-050", 1)),
)

# Concerns the assistant recorded on the session, so the customer table's note column carries
# something a merchant can act on rather than a blank.
CONCERNS: tuple[tuple[str, ...], ...] = (
    ("dryness", "sensitivity"),
    ("dullness",),
    ("texture", "dryness"),
    ("oiliness",),
    ("sensitivity",),
    ("dark spots", "dullness"),
)

# Shoppers who reached a priced cart and stopped, and shoppers the simulated issuer declined.
# All five are people who never completed a purchase, so they surface as open work rather than
# disappearing inside a buyer's history. Offsets are days before today.
ABANDONED: tuple[tuple[int, int, int], ...] = (  # (days ago, roster index, basket index)
    (2, 20, 0),
    (5, 21, 3),
    (11, 22, 5),
)
DECLINED: tuple[tuple[int, int, int], ...] = ((3, 23, 2), (8, 24, 4))


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _at(now: datetime, days_ago: int, hour: int, minute: int = 0) -> datetime:
    day = now - timedelta(days=days_ago)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _digest(value: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


class _Writer:
    """Writes one shopper's visit the way the live code does, backdated."""

    def __init__(self, connection, merchant_id: str, prices: dict[str, dict]) -> None:
        self.connection = connection
        self.merchant_id = merchant_id
        self.prices = prices
        self.counter = 0

    def _id(self, prefix: str) -> str:
        """Stable ids: a reset must reproduce the same history, so these cannot be random."""
        self.counter += 1
        return f"{prefix}_demo{self.counter:04d}"

    def _mandate(
        self,
        *,
        mandate_type: str,
        session_id: str,
        payload: dict,
        at: datetime,
        parent_id: str | None = None,
        cart_hash: str | None = None,
    ) -> str:
        """A real signed mandate. The chain on a historic order verifies like a live one."""
        mandate_id = self._id("mnd")
        record = {
            "mandate_id": mandate_id,
            "type": mandate_type,
            "parent_id": parent_id,
            "session_id": session_id,
            "version": 1,
            "supersedes": None,
            "payload": payload,
            "cart_hash": cart_hash,
            "issued_at": _iso(at),
            "expires_at": _iso(at + timedelta(minutes=15)),
        }
        self.connection.execute(
            "INSERT INTO mandates(mandate_id,type,parent_id,session_id,version,supersedes,"
            "payload_json,cart_hash,signature,issued_at,expires_at,active) "
            "VALUES (?,?,?,?,1,NULL,?,?,?,?,?,0)",
            (
                mandate_id,
                mandate_type,
                parent_id,
                session_id,
                json.dumps(payload),
                cart_hash,
                sign_record(record),
                _iso(at),
                _iso(at + timedelta(minutes=15)),
            ),
        )
        return mandate_id

    def session(self, consumer_id: str, at: datetime, *, anonymous: bool, concerns: tuple) -> str:
        """A closed visit: no token hash, so it can never be resumed or spent against."""
        session_id = self._id("ses")
        self.connection.execute(
            "INSERT INTO sessions(session_id,session_token_hash,merchant_id,consumer_id,"
            "is_anonymous,category,profile_json,created_at,expires_at) "
            "VALUES (?,NULL,?,?,?, 'skincare',?,?,?)",
            (
                session_id,
                self.merchant_id,
                consumer_id,
                1 if anonymous else 0,
                json.dumps({"concerns": list(concerns)} if concerns else {}),
                _iso(at),
                _iso(at + timedelta(hours=1)),
            ),
        )
        self.trust(session_id, at, "intent", "Session opened with a skincare category pack")
        return session_id

    def trust(
        self, session_id: str, at: datetime, stage: str, label: str, status: str = "ok", **detail
    ) -> None:
        self.connection.execute(
            "INSERT INTO trust_events(session_id,at,stage,label,status,detail_json) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, _iso(at), stage, label, status, json.dumps(detail)),
        )

    def cart(
        self, session_id: str, address_id: str, basket: tuple, at: datetime
    ) -> tuple[str, int, str]:
        """A server-priced cart. Prices come from the catalog, never from the basket plan."""
        items = [
            {
                "sku": sku,
                "title": self.prices[sku]["title"],
                "quantity": quantity,
                "unit_price_cents": self.prices[sku]["price_cents"],
            }
            for sku, quantity in basket
        ]
        total = sum(item["unit_price_cents"] * item["quantity"] for item in items)
        intent_id = self._mandate(
            mandate_type="intent",
            session_id=session_id,
            payload={"merchant_id": self.merchant_id, "category": "skincare"},
            at=at,
        )
        fingerprint = _digest({"address_id": address_id})
        cart_value = {
            "items": items,
            "total_cents": total,
            "currency": "SGD",
            "merchant_id": self.merchant_id,
            "shipping_address_id": address_id,
            "shipping_address_fingerprint": fingerprint,
        }
        cart_hash = _digest(cart_value)
        cart_mandate_id = self._mandate(
            mandate_type="cart",
            session_id=session_id,
            payload=cart_value,
            at=at,
            parent_id=intent_id,
            cart_hash=cart_hash,
        )
        cart_id = self._id("cart")
        self.connection.execute(
            "INSERT INTO carts(cart_id,session_id,intent_id,cart_mandate_id,merchant_id,items_json,"
            "total_cents,currency,shipping_address_id,shipping_fingerprint,cart_hash,status,"
            "created_at,expires_at) VALUES (?,?,?,?,?,?,?, 'SGD',?,?,?,?,?,?)",
            (
                cart_id,
                session_id,
                intent_id,
                cart_mandate_id,
                self.merchant_id,
                json.dumps(items),
                total,
                address_id,
                fingerprint,
                cart_hash,
                "preview",
                _iso(at),
                _iso(at + timedelta(minutes=10)),
            ),
        )
        self.trust(session_id, at, "cart", "Cart priced by the merchant, not by the model")
        return cart_id, total, cart_mandate_id

    def order(
        self, session_id: str, cart_id: str, cart_mandate_id: str, total: int, at: datetime
    ) -> None:
        payment_mandate_id = self._mandate(
            mandate_type="payment",
            session_id=session_id,
            payload={"cart_id": cart_id, "amount_cents": total, "currency": "SGD"},
            at=at,
            parent_id=cart_mandate_id,
        )
        transaction_id = self._id("txn")
        order_id = self._id("ord")
        auth_code = hashlib.sha256(transaction_id.encode()).hexdigest()[:6].upper()
        self.connection.execute(
            "INSERT INTO transactions(transaction_id,idempotency_key,session_id,cart_id,status,"
            "amount_cents,currency,auth_code,issuer,eci,simulated,created_at) "
            "VALUES (?,?,?,?, 'approved',?, 'SGD',?, 'Mock Issuer Bank', '05',1,?)",
            (transaction_id, f"demo-{transaction_id}", session_id, cart_id, total, auth_code, _iso(at)),
        )
        self.connection.execute(
            "INSERT INTO orders(order_id,transaction_id,session_id,evidence_json,created_at) "
            "VALUES (?,?,?,?,?)",
            (
                order_id,
                transaction_id,
                session_id,
                json.dumps(
                    {
                        "payment_mandate_id": payment_mandate_id,
                        "receipt": {"total_cents": total, "currency": "SGD", "simulated": True},
                    }
                ),
                _iso(at),
            ),
        )
        self.connection.execute(
            "UPDATE carts SET status='paid' WHERE cart_id=?", (cart_id,)
        )
        self.trust(session_id, at, "consent", "Shopper confirmed the exact cart and amount")
        self.trust(
            session_id, at, "decision", "Simulated Visa authorization approved", simulated=True
        )
        self.trust(session_id, at, "order", "Order and authorization evidence recorded")


def seed_demo_history(merchant_id: str = "m_mysa", *, now: datetime | None = None) -> bool:
    """Write the history once. Returns False if this merchant already has orders."""
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    with connect() as connection:
        existing = connection.execute(
            "SELECT 1 FROM orders o JOIN transactions t ON t.transaction_id=o.transaction_id "
            "JOIN carts c ON c.cart_id=t.cart_id WHERE c.merchant_id=? LIMIT 1",
            (merchant_id,),
        ).fetchone()
        products = connection.execute(
            "SELECT sku, title, price_cents FROM products WHERE merchant_id=?", (merchant_id,)
        ).fetchall()
    if existing or not products:
        return False
    prices = {row["sku"]: dict(row) for row in products}
    known = PREVIOUS_BASKETS + CURRENT_BASKETS
    if not all(sku in prices for basket in known for sku, _ in basket):
        return False  # the catalog was replaced; the demo baskets no longer describe it

    total_days = len(ORDERS_BY_DAY)
    with transaction() as connection:
        writer = _Writer(connection, merchant_id, prices)
        addresses: dict[int, str] = {}
        for index, (name, handle) in enumerate(ROSTER):
            consumer_id = f"usr_demo{index:02d}"
            address_id = f"adr_demo{index:02d}"
            addresses[index] = address_id
            connection.execute(
                "INSERT INTO consumers(consumer_id,email,password_hash,display_name,created_at) "
                "VALUES (?,?,'!disabled-demo-history',?,?)",
                (
                    consumer_id,
                    f"{handle}@example.test",
                    name,
                    _iso(now - timedelta(days=total_days)),
                ),
            )
            connection.execute(
                "INSERT INTO addresses(address_id,consumer_id,recipient,lines_json,postal_code,"
                "country,is_default) VALUES (?,?,?,?, '118420', 'SG',1)",
                (address_id, consumer_id, name, json.dumps(["21 Lower Kent Ridge Rd"])),
            )

        # Both cursors are per window so each window walks its own rotation from the start.
        cursor = {"previous": 0, "current": 0}
        for day_index, order_count in enumerate(ORDERS_BY_DAY):
            days_ago = total_days - 1 - day_index
            window = "previous" if day_index < total_days - WINDOW_DAYS else "current"
            plan = PREVIOUS_BUYERS if window == "previous" else CURRENT_BUYERS

            # Browsing that did not buy: enough for the conversion rate to mean something.
            for visit in range(2 + (day_index * 7) % 3):
                at = _at(now, days_ago, 9 + visit * 3, 20)
                writer.session(
                    f"anon_demo{day_index:02d}{visit}",
                    at,
                    anonymous=True,
                    concerns=CONCERNS[(day_index + visit) % len(CONCERNS)],
                )

            for order_index in range(order_count):
                baskets = PREVIOUS_BASKETS if window == "previous" else CURRENT_BASKETS
                roster_index = plan[cursor[window] % len(plan)]
                basket = baskets[cursor[window] % len(baskets)]
                cursor[window] += 1
                at = _at(now, days_ago, 11 + order_index * 2, 35)
                session_id = writer.session(
                    f"usr_demo{roster_index:02d}",
                    at,
                    anonymous=False,
                    concerns=CONCERNS[roster_index % len(CONCERNS)],
                )
                cart_id, total, cart_mandate_id = writer.cart(
                    session_id, addresses[roster_index], basket, at + timedelta(minutes=4)
                )
                writer.order(
                    session_id, cart_id, cart_mandate_id, total, at + timedelta(minutes=6)
                )

        for days_ago, roster_index, basket_index in ABANDONED:
            at = _at(now, days_ago, 21, 10)
            session_id = writer.session(
                f"usr_demo{roster_index:02d}",
                at,
                anonymous=False,
                concerns=CONCERNS[roster_index % len(CONCERNS)],
            )
            writer.cart(
                session_id, addresses[roster_index], CURRENT_BASKETS[basket_index], at + timedelta(minutes=3)
            )

        for days_ago, roster_index, basket_index in DECLINED:
            at = _at(now, days_ago, 20, 5)
            session_id = writer.session(
                f"usr_demo{roster_index:02d}",
                at,
                anonymous=False,
                concerns=CONCERNS[roster_index % len(CONCERNS)],
            )
            writer.cart(
                session_id, addresses[roster_index], CURRENT_BASKETS[basket_index], at + timedelta(minutes=3)
            )
            writer.trust(
                session_id,
                at + timedelta(minutes=5),
                "decision",
                "Simulated issuer declined the authorization",
                "fail",
                decline_code="BANK_AUTH_DECLINED",
                simulated=True,
            )
    return True


def demo_history_totals(merchant_id: str = "m_mysa") -> dict[str, int]:
    """What was written, for the seeding script to print. Read back, not assumed."""
    with connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS orders, COALESCE(SUM(t.amount_cents),0) AS revenue "
            "FROM orders o JOIN transactions t ON t.transaction_id=o.transaction_id "
            "JOIN carts c ON c.cart_id=t.cart_id WHERE c.merchant_id=?",
            (merchant_id,),
        ).fetchone()
        customers = connection.execute(
            "SELECT COUNT(DISTINCT s.consumer_id) AS people FROM orders o "
            "JOIN transactions t ON t.transaction_id=o.transaction_id "
            "JOIN carts c ON c.cart_id=t.cart_id JOIN sessions s ON s.session_id=c.session_id "
            "WHERE c.merchant_id=?",
            (merchant_id,),
        ).fetchone()
    return {
        "orders": row["orders"],
        "revenue_cents": row["revenue"],
        "customers": customers["people"],
    }


__all__ = ["demo_history_totals", "seed_demo_history"]
