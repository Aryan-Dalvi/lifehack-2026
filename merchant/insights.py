"""The merchant CRM: every number on the admin dashboard, computed from the merchant's own rows.

A merchant who has finished onboarding stops caring about upload mechanics and starts asking
CRM questions - who is buying, what is selling, what needs attention today. This module answers
those from `orders`, `transactions`, `carts`, `sessions`, `trust_events` and `products`, scoped
to one merchant, with no model anywhere near the arithmetic. `merchant/insights_summary.py` is
allowed to reword what this produces; it is never allowed to produce a number of its own.

The shape follows the CRM dashboard conventions NetSuite documents: a small set of KPIs with a
period-over-period comparison, one revenue trend carrying both actuals and a forecast, a task
list that turns state into today's work, and a customer table - five reports, inside the five
to seven a reader can actually hold in their head.

Every derived figure states its own denominator (`basis`) so the UI never has to guess what a
percentage was taken over, and so a summary can quote it honestly.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db import connect, json_load

INSIGHTS_VERSION = "merchant-insights.v1"

# A product at or under this many units is worth a restock prompt rather than a silent number.
LOW_STOCK_THRESHOLD = 4
# The trend is a per-day dot column; more days than this stops being readable at dashboard size.
MAX_TREND_DAYS = 45
# How far the deterministic forecast is allowed to run past today.
FORECAST_DAYS = 7
# Rows in the customer table. The table is a working list, not an export.
MAX_CUSTOMER_ROWS = 12


def money(cents: int, currency: str = "SGD") -> str:
    """Format like the storefront does, so one amount reads identically everywhere."""
    symbol = {"SGD": "S$", "USD": "$", "EUR": "\u20ac", "GBP": "\u00a3"}.get(currency, f"{currency} ")
    return f"{symbol}{cents / 100:,.2f}"


def _parse(value: str | None) -> datetime | None:
    """Read a stored ISO timestamp as an aware datetime, or None if it is unusable."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _day(value: str | None) -> str:
    return (value or "")[:10]


def _pct(part: float, whole: float) -> float | None:
    """A percentage, or None when there is no denominator - never a zero standing in for 'unknown'."""
    if not whole:
        return None
    return round(part / whole * 100, 1)


def _delta_percent(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def _initials(name: str) -> str:
    parts = [part for part in name.replace(".", " ").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _order_rows(connection, merchant_id: str) -> list[dict[str, Any]]:
    """Every paid order for this merchant, newest first, with the buyer and basket attached.

    `transactions` carries no merchant column, so the tenant boundary is the cart: an order
    belongs to this merchant only because the cart it settled did.
    """
    rows = connection.execute(
        """
        SELECT o.order_id, o.created_at AS ordered_at, o.evidence_json,
               t.transaction_id, t.amount_cents, t.currency, t.status, t.auth_code, t.issuer,
               c.cart_id, c.items_json, c.session_id,
               s.consumer_id, s.is_anonymous,
               u.display_name, u.email
          FROM orders o
          JOIN transactions t ON t.transaction_id = o.transaction_id
          JOIN carts c        ON c.cart_id = t.cart_id
          JOIN sessions s     ON s.session_id = c.session_id
          LEFT JOIN consumers u ON u.consumer_id = s.consumer_id
         WHERE c.merchant_id = ? AND t.status = 'approved'
         ORDER BY o.created_at DESC
        """,
        (merchant_id,),
    ).fetchall()
    return [{**dict(row), "items": json_load(row["items_json"], [])} for row in rows]


def _kpi(
    key: str,
    label: str,
    value: float,
    previous: float,
    *,
    display: str,
    previous_display: str,
    unit: str,
    as_percent: bool = False,
) -> dict[str, Any]:
    """One KPI card: the figure, and what the same figure was in the previous window.

    Counts compare as a difference (+4 customers) and money as a percentage (-8%), which is
    how each is actually read. `direction` is the truth about the arrow; `is_good` is separate
    because a fall is not automatically bad for every metric a later card may add.
    """
    change = value - previous
    percent = _delta_percent(value, previous)
    return {
        "key": key,
        "label": label,
        "value": round(value, 2),
        "display": display,
        "previous": round(previous, 2),
        "previous_display": previous_display,
        "change": round(change, 2),
        "change_percent": percent,
        "delta_display": (
            f"{percent:+.0f}%" if as_percent and percent is not None else f"{change:+.0f}"
        ),
        "direction": "up" if change > 0 else "down" if change < 0 else "flat",
        "is_good": change >= 0,
        "unit": unit,
    }


def _revenue_series(
    orders: list[dict[str, Any]], *, start: datetime, end: datetime, currency: str
) -> dict[str, Any]:
    """Daily takings across the window, plus a forecast that says how it was made.

    The forecast is the trailing seven-day mean carried forward - deliberately the dullest
    method that still answers "if the last week repeats, where does this month land". It is
    labelled as that in the payload so the dashboard can print the method beside the number,
    and it is arithmetic, not a model: nothing here is a prediction anyone should be surprised by.
    """
    days = min((end.date() - start.date()).days + 1, MAX_TREND_DAYS)
    dates = [start.date() + timedelta(days=offset) for offset in range(days)]
    totals = {date.isoformat(): 0 for date in dates}
    for order in orders:
        key = _day(order["ordered_at"])
        if key in totals:
            totals[key] += int(order["amount_cents"])

    actuals = [totals[date.isoformat()] for date in dates]
    trailing = [value for value in actuals[-7:]]
    run_rate = round(sum(trailing) / len(trailing)) if trailing else 0

    points = [
        {
            "date": date.isoformat(),
            "label": date.strftime("%b %-d") if hasattr(date, "strftime") else date.isoformat(),
            "actual_cents": totals[date.isoformat()],
            "projected_cents": None,
            "is_forecast": False,
        }
        for date in dates
    ]
    last = dates[-1] if dates else end.date()
    for offset in range(1, FORECAST_DAYS + 1):
        date = last + timedelta(days=offset)
        points.append(
            {
                "date": date.isoformat(),
                "label": date.strftime("%b %-d"),
                "actual_cents": None,
                "projected_cents": run_rate,
                "is_forecast": True,
            }
        )

    best = max(points[:days], key=lambda point: point["actual_cents"] or 0, default=None)
    return {
        "currency": currency,
        "points": points,
        "actual_days": days,
        "forecast_days": FORECAST_DAYS,
        "peak": best if best and best["actual_cents"] else None,
        "forecast": {
            "method": "trailing 7-day mean, carried forward",
            "source": "deterministic",
            "per_day_cents": run_rate,
            "horizon_days": FORECAST_DAYS,
            "total_cents": run_rate * FORECAST_DAYS,
        },
        "max_cents": max([point["actual_cents"] or 0 for point in points] + [run_rate, 1]),
    }


def _catalog_health(connection, merchant_id: str) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT sku, title, price_cents, stock, image_url FROM products WHERE merchant_id=?",
        (merchant_id,),
    ).fetchall()
    products = [dict(row) for row in rows]
    out_of_stock = [product for product in products if product["stock"] == 0]
    low_stock = [
        product for product in products if 0 < product["stock"] <= LOW_STOCK_THRESHOLD
    ]
    without_photo = [product for product in products if not product["image_url"]]
    prices = [product["price_cents"] for product in products]
    return {
        "product_count": len(products),
        "out_of_stock": [product["title"] for product in out_of_stock],
        "low_stock": [product["title"] for product in low_stock],
        "without_photo": [product["title"] for product in without_photo],
        "in_stock_count": len(products) - len(out_of_stock),
        "with_photo_count": len(products) - len(without_photo),
        "average_price_cents": round(sum(prices) / len(prices)) if prices else 0,
    }


def _top_products(orders: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ranked: dict[str, dict[str, Any]] = {}
    for order in orders:
        for item in order["items"]:
            entry = ranked.setdefault(
                item["sku"],
                {"sku": item["sku"], "title": item["title"], "units": 0, "revenue_cents": 0},
            )
            entry["units"] += int(item.get("quantity", 1))
            entry["revenue_cents"] += int(item.get("unit_price_cents", 0)) * int(
                item.get("quantity", 1)
            )
    return sorted(ranked.values(), key=lambda entry: entry["revenue_cents"], reverse=True)[:limit]


def _customer_rows(
    connection,
    merchant_id: str,
    orders: list[dict[str, Any]],
    *,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """The customer table, and the tab counts above it.

    A row's status is the honest state of that relationship, not a workflow someone has to
    keep updated: repeat buyers have bought twice, an abandoned row has a cart that was
    priced and never paid, follow-up means their last payment attempt failed. Anonymous
    sessions stay anonymous - the row is labelled a guest rather than given a fake identity.
    """
    sessions = connection.execute(
        """
        SELECT s.session_id, s.consumer_id, s.is_anonymous, s.created_at, s.profile_json,
               u.display_name, u.email
          FROM sessions s
          LEFT JOIN consumers u ON u.consumer_id = s.consumer_id
         WHERE s.merchant_id = ?
        """,
        (merchant_id,),
    ).fetchall()
    unpaid_carts = connection.execute(
        """
        SELECT c.cart_id, c.session_id, c.total_cents, c.created_at, c.items_json, c.status
          FROM carts c
          LEFT JOIN transactions t
                 ON t.cart_id = c.cart_id AND t.status = 'approved'
         WHERE c.merchant_id = ? AND t.transaction_id IS NULL
        """,
        (merchant_id,),
    ).fetchall()
    failures = connection.execute(
        """
        SELECT e.session_id, e.at, e.label
          FROM trust_events e
          JOIN sessions s ON s.session_id = e.session_id
         WHERE s.merchant_id = ? AND e.status = 'fail'
        """,
        (merchant_id,),
    ).fetchall()

    by_session = {row["session_id"]: dict(row) for row in sessions}
    people: dict[str, dict[str, Any]] = {}

    def person(session_id: str) -> dict[str, Any] | None:
        session = by_session.get(session_id)
        if not session:
            return None
        consumer_id = session["consumer_id"]
        entry = people.setdefault(
            consumer_id,
            {
                "consumer_id": consumer_id,
                "name": session["display_name"] or "Guest shopper",
                "handle": (session["email"] or consumer_id).split("@")[0],
                "is_anonymous": bool(session["is_anonymous"]) and not session["display_name"],
                "orders": 0,
                "spend_cents": 0,
                "last_activity": session["created_at"],
                "last_item": None,
                "open_cart_cents": 0,
                "failed": False,
                "interests": [],
            },
        )
        profile = json_load(session["profile_json"], {})
        interests = [
            str(value)
            for key in ("concerns", "skin_type", "skin_types")
            for value in (
                profile.get(key) if isinstance(profile.get(key), list) else [profile.get(key)]
            )
            if value
        ]
        entry["interests"] = list(dict.fromkeys(entry["interests"] + interests))[:3]
        return entry

    for session in sessions:
        person(session["session_id"])

    for order in orders:
        entry = person(order["session_id"])
        if not entry:
            continue
        entry["orders"] += 1
        entry["spend_cents"] += int(order["amount_cents"])
        if order["ordered_at"] > (entry["last_activity"] or ""):
            entry["last_activity"] = order["ordered_at"]
        if entry["last_item"] is None and order["items"]:
            entry["last_item"] = order["items"][0]["title"]

    for cart in unpaid_carts:
        entry = person(cart["session_id"])
        if not entry:
            continue
        entry["open_cart_cents"] += int(cart["total_cents"])
        items = json_load(cart["items_json"], [])
        if entry["last_item"] is None and items:
            entry["last_item"] = items[0]["title"]
        if cart["created_at"] > (entry["last_activity"] or ""):
            entry["last_activity"] = cart["created_at"]

    for failure in failures:
        entry = person(failure["session_id"])
        if entry:
            entry["failed"] = True

    rows: list[dict[str, Any]] = []
    for entry in people.values():
        seen = _parse(entry["last_activity"])
        hours_ago = (now - seen).total_seconds() / 3600 if seen else 9999
        if entry["failed"] and entry["orders"] == 0:
            status, status_label = "follow_up", "Follow up"
        elif entry["orders"] >= 2:
            status, status_label = "repeat", "Repeat buyer"
        elif entry["orders"] == 1:
            status, status_label = "paid", "Paid"
        elif entry["open_cart_cents"]:
            status, status_label = "abandoned", "Abandoned cart"
        elif hours_ago <= 48:
            status, status_label = "active", "Browsing"
        else:
            status, status_label = "lapsed", "No purchase"
        note = (
            f"Interested in {', '.join(entry['interests'])}"
            if entry["interests"]
            else "No stated concern yet"
        )
        rows.append(
            {
                **entry,
                "initials": _initials(entry["name"]),
                "status": status,
                "status_label": status_label,
                "note": note,
                "value_cents": entry["spend_cents"] or entry["open_cart_cents"],
                "value_kind": "spent" if entry["spend_cents"] else "in cart",
                "last_activity_label": (
                    seen.strftime("%b %-d") if seen else "—"
                ),
            }
        )

    rows.sort(key=lambda row: (row["value_cents"], row["last_activity"] or ""), reverse=True)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    tabs = [
        {"key": "follow_up", "label": "Follow up", "count": counts.get("follow_up", 0)},
        {"key": "active", "label": "Browsing", "count": counts.get("active", 0)},
        {"key": "repeat", "label": "Repeat", "count": counts.get("repeat", 0)},
        {"key": "paid", "label": "Paid", "count": counts.get("paid", 0)},
        {"key": "abandoned", "label": "Abandoned", "count": counts.get("abandoned", 0)},
    ]
    return rows[:MAX_CUSTOMER_ROWS], tabs, counts


def _tasks(
    *,
    catalog: dict[str, Any],
    abandoned_cents: int,
    abandoned_count: int,
    follow_up_count: int,
    held_rows: int,
    reviewed_rows: int,
    published: bool,
) -> list[dict[str, Any]]:
    """Today's work, derived from state rather than typed in by anyone.

    Each entry is a real queue with a real remainder, so the progress chip is a fact: it can
    only be cleared by fixing the thing it names. Severity orders the list; the dashboard
    shows the top few and links the rest.
    """
    tasks: list[dict[str, Any]] = []
    if not published:
        tasks.append(
            {
                "code": "PUBLISH_AGENT",
                "title": "Publish your agent",
                "detail": "Your catalog is ready but the storefront is still a draft.",
                "progress": None,
                "chip": "Not live",
                "severity": 0,
                "action": "/admin/setup",
            }
        )
    if catalog["out_of_stock"]:
        tasks.append(
            {
                "code": "RESTOCK",
                "title": "Restock sold-out products",
                "detail": f"The assistant stops recommending these: {', '.join(catalog['out_of_stock'][:3])}.",
                "progress": {
                    "done": catalog["in_stock_count"],
                    "total": catalog["product_count"],
                    "noun": "in stock",
                },
                "chip": f"{len(catalog['out_of_stock'])} sold out",
                "severity": 1,
                "action": "/admin/setup",
            }
        )
    if follow_up_count:
        tasks.append(
            {
                "code": "FAILED_PAYMENTS",
                "title": "Follow up failed checkouts",
                "detail": "These shoppers reached payment and the authorization did not complete.",
                "progress": None,
                "chip": f"{follow_up_count} to contact",
                "severity": 1,
                "action": "#customers",
            }
        )
    if abandoned_count:
        tasks.append(
            {
                "code": "ABANDONED_CARTS",
                "title": "Recover abandoned carts",
                "detail": "Carts were priced and consented to, then left before authorization.",
                "progress": None,
                "chip": f"{abandoned_count} open",
                "severity": 2,
                "action": "#customers",
                "value_cents": abandoned_cents,
            }
        )
    if held_rows:
        tasks.append(
            {
                "code": "HELD_ROWS",
                "title": "Clear held catalog rows",
                "detail": "Rows from your last upload are still held out of the live catalog.",
                "progress": {
                    "done": max(reviewed_rows - held_rows, 0),
                    "total": reviewed_rows,
                    "noun": "cleared",
                },
                "chip": f"{held_rows} held",
                "severity": 2,
                "action": "/admin/setup",
            }
        )
    if catalog["low_stock"]:
        tasks.append(
            {
                "code": "LOW_STOCK",
                "title": "Top up low stock",
                "detail": f"At or below {LOW_STOCK_THRESHOLD} units: {', '.join(catalog['low_stock'][:3])}.",
                "progress": None,
                "chip": f"{len(catalog['low_stock'])} low",
                "severity": 3,
                "action": "/admin/setup",
            }
        )
    if catalog["without_photo"]:
        tasks.append(
            {
                "code": "MISSING_PHOTOS",
                "title": "Add missing product photos",
                "detail": "Products without a photo convert worse in the storefront and the widget.",
                "progress": {
                    "done": catalog["with_photo_count"],
                    "total": catalog["product_count"],
                    "noun": "have photos",
                },
                "chip": f"{len(catalog['without_photo'])} missing",
                "severity": 3,
                "action": "/admin/setup",
            }
        )
    tasks.sort(key=lambda task: task["severity"])
    return tasks


def _headline(
    *,
    revenue_cents: int,
    revenue_previous: int,
    orders_count: int,
    conversion: float | None,
    top_products: list[dict[str, Any]],
    abandoned_cents: int,
    currency: str,
) -> dict[str, str]:
    """The one sentence in the trend panel. Deterministic, and always about the largest fact."""
    if not orders_count:
        return {
            "text": (
                "No orders yet in this window. Share your storefront link or widget snippet "
                "to start the first conversation."
            ),
            "source": "deterministic",
        }
    change = _delta_percent(revenue_cents, revenue_previous)
    if abandoned_cents > revenue_cents * 0.2 and abandoned_cents:
        text = (
            f"{money(abandoned_cents, currency)} is sitting in carts that were priced and never "
            "paid - the largest single thing you can recover this week."
        )
    elif change is not None and change < -5:
        text = (
            f"Revenue is {abs(change):.0f}% below the previous window. "
            f"{top_products[0]['title']} is still your strongest product; the drop is in volume, "
            "not in what people choose."
        )
    elif change is not None and change > 5:
        text = (
            f"Revenue is up {change:.0f}% on the previous window, led by "
            f"{top_products[0]['title']}."
        )
    elif conversion is not None:
        text = (
            f"{conversion:.0f}% of assistant conversations end in a paid order. "
            f"{top_products[0]['title']} carries the most revenue."
        )
    else:
        text = f"{top_products[0]['title']} carries the most revenue in this window."
    return {"text": text, "source": "deterministic"}


def merchant_insights(
    merchant_id: str, *, days: int = 30, now: datetime | None = None
) -> dict[str, Any]:
    """The whole CRM dashboard for one merchant, as facts.

    Two windows are read: the one being shown, and the one immediately before it of the same
    length, which is what every "compare" on the dashboard means.
    """
    now = now or datetime.now(UTC)
    days = max(1, min(days, MAX_TREND_DAYS))
    start = now - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    previous_start = start - timedelta(days=days)

    with connect() as connection:
        merchant = connection.execute(
            "SELECT merchant_id, name, currency, status, accent_color, size, created_at "
            "FROM merchants WHERE merchant_id=?",
            (merchant_id,),
        ).fetchone()
        if not merchant:
            return {}
        merchant = dict(merchant)
        currency = merchant["currency"]

        all_orders = _order_rows(connection, merchant_id)
        catalog = _catalog_health(connection, merchant_id)
        customers, customer_tabs, status_counts = _customer_rows(
            connection, merchant_id, all_orders, now=now
        )
        session_rows = connection.execute(
            "SELECT created_at, is_anonymous FROM sessions WHERE merchant_id=?", (merchant_id,)
        ).fetchall()
        unpaid = connection.execute(
            """
            SELECT c.total_cents, c.created_at
              FROM carts c
              LEFT JOIN transactions t ON t.cart_id = c.cart_id AND t.status = 'approved'
             WHERE c.merchant_id = ? AND t.transaction_id IS NULL
            """,
            (merchant_id,),
        ).fetchall()
        latest_run = connection.execute(
            "SELECT summary_json, status, created_at FROM catalog_clean_runs "
            "WHERE merchant_id=? ORDER BY created_at DESC LIMIT 1",
            (merchant_id,),
        ).fetchone()

    in_window = [order for order in all_orders if _parse(order["ordered_at"]) >= start]
    in_previous = [
        order
        for order in all_orders
        if previous_start <= _parse(order["ordered_at"]) < start
    ]
    sessions_in_window = [
        row for row in session_rows if (_parse(row["created_at"]) or now) >= start
    ]
    sessions_previous = [
        row
        for row in session_rows
        if previous_start <= (_parse(row["created_at"]) or now) < start
    ]
    abandoned = [cart for cart in unpaid if (_parse(cart["created_at"]) or now) >= start]

    revenue = sum(int(order["amount_cents"]) for order in in_window)
    revenue_previous = sum(int(order["amount_cents"]) for order in in_previous)
    buyers = {order["consumer_id"] for order in in_window}
    buyers_previous = {order["consumer_id"] for order in in_previous}
    abandoned_cents = sum(int(cart["total_cents"]) for cart in abandoned)
    conversion = _pct(len(in_window), len(sessions_in_window))

    kpis = [
        _kpi(
            "customers",
            "Customers",
            len(buyers),
            len(buyers_previous),
            display=str(len(buyers)),
            previous_display=str(len(buyers_previous)),
            unit="count",
        ),
        _kpi(
            "revenue",
            "Revenue",
            revenue,
            revenue_previous,
            display=money(revenue, currency),
            previous_display=money(revenue_previous, currency),
            unit="money",
            as_percent=True,
        ),
        _kpi(
            "orders",
            "Orders",
            len(in_window),
            len(in_previous),
            display=str(len(in_window)),
            previous_display=str(len(in_previous)),
            unit="count",
        ),
    ]

    held_rows = 0
    reviewed_rows = 0
    if latest_run:
        summary = json_load(latest_run["summary_json"], {})
        reviewed_rows = int(summary.get("input_rows") or 0)
        held_rows = int(summary.get("review_required") or 0) + int(summary.get("rejected") or 0)

    top_products = _top_products(in_window)
    # All-time and across every buyer - the customer table is truncated for reading, so
    # counting its rows would quietly report the retention of the top twelve customers only.
    orders_per_customer = Counter(order["consumer_id"] for order in all_orders)
    lifetime_by_customer: Counter[str] = Counter()
    for order in all_orders:
        lifetime_by_customer[order["consumer_id"]] += int(order["amount_cents"])
    all_buyers = len(orders_per_customer)
    repeat_buyers = len([count for count in orders_per_customer.values() if count >= 2])

    scorecards = [
        {
            "key": "conversion",
            "label": "Conversation conversion",
            "display": f"{conversion:.1f}%" if conversion is not None else "—",
            "basis": f"{len(in_window)} paid orders from {len(sessions_in_window)} conversations",
            "hint": "The share of assistant conversations that end in a paid order.",
        },
        {
            "key": "aov",
            "label": "Average order value",
            "display": money(round(revenue / len(in_window)) if in_window else 0, currency),
            "basis": f"{money(revenue, currency)} across {len(in_window)} orders",
            "hint": "Total revenue divided by paid orders in this window.",
        },
        {
            "key": "repeat_rate",
            "label": "Repeat rate",
            "display": (
                f"{_pct(repeat_buyers, all_buyers):.0f}%"
                if _pct(repeat_buyers, all_buyers) is not None
                else "—"
            ),
            "basis": f"{repeat_buyers} of {all_buyers} customers bought more than once",
            "hint": "Customer retention: repeat buyers over all buyers, all time.",
        },
        {
            "key": "lifetime_value",
            "label": "Lifetime spend",
            "display": money(
                round(sum(lifetime_by_customer.values()) / len(lifetime_by_customer))
                if lifetime_by_customer
                else 0,
                currency,
            ),
            "basis": f"average across {len(lifetime_by_customer)} customers, all time",
            "hint": "Average spend per customer to date - not an extrapolated CLTV.",
        },
        {
            "key": "recoverable",
            "label": "Recoverable carts",
            "display": money(abandoned_cents, currency),
            "basis": f"{len(abandoned)} carts priced and never authorized",
            "hint": "Server-priced carts with no approved transaction against them.",
        },
    ]

    return {
        "version": INSIGHTS_VERSION,
        "generated_at": now.isoformat(),
        "merchant": {
            "merchant_id": merchant["merchant_id"],
            "name": merchant["name"],
            "currency": currency,
            "status": merchant["status"],
            "accent_color": merchant["accent_color"],
            "size": merchant["size"],
        },
        "window": {
            "days": days,
            "start": start.isoformat(),
            "end": now.isoformat(),
            "previous_start": previous_start.isoformat(),
            "label": f"Last {days} days",
        },
        "kpis": kpis,
        "revenue_series": _revenue_series(in_window, start=start, end=now, currency=currency),
        "insight": _headline(
            revenue_cents=revenue,
            revenue_previous=revenue_previous,
            orders_count=len(in_window),
            conversion=conversion,
            top_products=top_products,
            abandoned_cents=abandoned_cents,
            currency=currency,
        ),
        "tasks": _tasks(
            catalog=catalog,
            abandoned_cents=abandoned_cents,
            abandoned_count=len(abandoned),
            follow_up_count=status_counts.get("follow_up", 0),
            held_rows=held_rows,
            reviewed_rows=reviewed_rows,
            published=merchant["status"] == "published",
        ),
        "customers": customers,
        "customer_tabs": customer_tabs,
        "scorecards": scorecards,
        "top_products": top_products,
        "catalog": catalog,
        "activity": {
            "sessions": len(sessions_in_window),
            "sessions_previous": len(sessions_previous),
            "signed_in_sessions": len(
                [row for row in sessions_in_window if not row["is_anonymous"]]
            ),
            "abandoned_carts": len(abandoned),
            "abandoned_cents": abandoned_cents,
        },
        "payments": {
            "mode": "simulator",
            "note": "Every authorization on this dashboard is a simulated Visa authorization.",
        },
    }
