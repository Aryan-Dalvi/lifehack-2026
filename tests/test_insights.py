"""The CRM dashboard reports one merchant's own figures, and only ever their real ones.

Two failures would matter more than any layout bug on this screen. A merchant seeing another
merchant's revenue is a tenancy breach; a merchant seeing a number the model made up is worse
than showing them nothing, because they would act on it. Both are covered here, alongside the
arithmetic the cards depend on.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import init_databases, transaction, utc_now
from app.main import app
from merchant.insights import _kpi, merchant_insights
from merchant.insights_summary import (
    SummaryValidationError,
    route,
    validate_summary,
)
from seed.reset import MERCHANT_KEY_FILE, seed
from tests.conftest import SessionAwareClient


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with SessionAwareClient(app) as test_client:
        yield test_client


@pytest.fixture()
def merchant_key() -> str:
    return MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()


def headers(key: str) -> dict[str, str]:
    return {"X-Merchant-Key": key}


def test_insights_need_the_merchants_own_key(client: TestClient, merchant_key: str) -> None:
    assert client.get("/merchant/m_mysa/insights").status_code == 401
    assert client.get("/merchant/m_mysa/insights", headers=headers("mk_wrong")).status_code == 403
    assert client.get("/merchant/m_mysa/insights", headers=headers(merchant_key)).status_code == 200


def test_a_rival_merchants_key_cannot_read_this_dashboard(client: TestClient) -> None:
    rival = client.post("/merchant/onboard", json={"name": "Rival Skin Co", "size": "sme"})
    assert rival.status_code == 200, rival.text
    forbidden = client.get(
        "/merchant/m_mysa/insights", headers=headers(rival.json()["api_key"])
    )
    assert forbidden.status_code == 403


def test_a_new_merchant_sees_zeroes_rather_than_someone_elses_trade(client: TestClient) -> None:
    """An empty store is a real state: it must report nothing, not the demo merchant's history."""
    rival = client.post("/merchant/onboard", json={"name": "Rival Skin Co", "size": "sme"}).json()
    report = client.get(
        f"/merchant/{rival['merchant_id']}/insights", headers=headers(rival["api_key"])
    ).json()
    figures = {kpi["key"]: kpi["value"] for kpi in report["kpis"]}
    assert figures == {"customers": 0, "revenue": 0, "orders": 0}
    assert report["customers"] == []
    assert report["top_products"] == []
    # No orders means no conversion rate, and an em dash rather than a fabricated 0%.
    conversion = next(card for card in report["scorecards"] if card["key"] == "conversion")
    assert conversion["display"] == "—"


def test_kpis_compare_the_window_against_the_one_before_it(client: TestClient) -> None:
    report = merchant_insights("m_mysa", days=30)
    revenue = next(kpi for kpi in report["kpis"] if kpi["key"] == "revenue")
    orders = next(kpi for kpi in report["kpis"] if kpi["key"] == "orders")
    customers = next(kpi for kpi in report["kpis"] if kpi["key"] == "customers")

    # The seeded history is written to these totals deliberately: fourteen buyers this window
    # against ten before it, on slightly lower revenue.
    assert orders["value"] == 22
    assert orders["previous"] == 16
    assert customers["value"] == 14
    assert customers["previous"] == 10
    assert revenue["value"] < revenue["previous"]
    assert revenue["direction"] == "down"
    assert revenue["delta_display"].startswith("-")


def test_money_kpi_does_not_show_raw_cents_when_the_previous_window_is_zero() -> None:
    revenue = _kpi(
        "revenue",
        "Revenue",
        7200,
        0,
        display="S$72.00",
        previous_display="S$0.00",
        unit="money",
        as_percent=True,
    )

    assert revenue["change_percent"] is None
    assert revenue["delta_display"] == "New"


def test_revenue_totals_match_the_transactions_they_came_from(client: TestClient) -> None:
    report = merchant_insights("m_mysa", days=30)
    revenue = next(kpi for kpi in report["kpis"] if kpi["key"] == "revenue")
    charted = sum(point["actual_cents"] or 0 for point in report["revenue_series"]["points"])
    assert charted == revenue["value"]

    from app.db import connect

    with connect() as connection:
        start = report["window"]["start"]
        banked = connection.execute(
            "SELECT COALESCE(SUM(t.amount_cents),0) FROM orders o "
            "JOIN transactions t ON t.transaction_id=o.transaction_id "
            "JOIN carts c ON c.cart_id=t.cart_id "
            "WHERE c.merchant_id='m_mysa' AND t.status='approved' AND o.created_at >= ?",
            (start,),
        ).fetchone()[0]
    assert banked == revenue["value"]


def test_the_forecast_is_arithmetic_and_says_so(client: TestClient) -> None:
    series = merchant_insights("m_mysa", days=30)["revenue_series"]
    forecast = series["forecast"]
    assert forecast["source"] == "deterministic"
    assert "trailing" in forecast["method"]

    trailing = [
        point["actual_cents"]
        for point in series["points"]
        if not point["is_forecast"]
    ][-7:]
    assert forecast["per_day_cents"] == round(sum(trailing) / len(trailing))
    projected = [point for point in series["points"] if point["is_forecast"]]
    assert projected and all(point["actual_cents"] is None for point in projected)


def test_open_carts_and_declines_become_work_rather_than_disappearing(client: TestClient) -> None:
    report = merchant_insights("m_mysa", days=30)
    codes = {task["code"] for task in report["tasks"]}
    assert {"ABANDONED_CARTS", "FAILED_PAYMENTS"} <= codes
    statuses = {row["status"] for row in report["customers"]}
    assert "abandoned" in statuses

    recoverable = next(card for card in report["scorecards"] if card["key"] == "recoverable")
    assert report["activity"]["abandoned_cents"] > 0
    assert str(report["activity"]["abandoned_carts"]) in recoverable["basis"]


def test_a_draft_store_is_told_to_publish(client: TestClient) -> None:
    with transaction() as connection:
        connection.execute("UPDATE merchants SET status='draft' WHERE merchant_id='m_mysa'")
    tasks = merchant_insights("m_mysa", days=30)["tasks"]
    assert tasks[0]["code"] == "PUBLISH_AGENT"


def test_stock_and_photo_gaps_surface_as_tasks(client: TestClient) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE products SET stock=0 WHERE sku='MYSA-SPF-050'"
        )
        connection.execute(
            "UPDATE products SET image_url=NULL WHERE sku='MYSA-CLN-101'"
        )
    report = merchant_insights("m_mysa", days=30)
    tasks = {task["code"]: task for task in report["tasks"]}
    assert "RESTOCK" in tasks
    assert "MISSING_PHOTOS" in tasks
    # The progress chip is a real remainder, not a decoration.
    assert tasks["RESTOCK"]["progress"]["done"] == report["catalog"]["product_count"] - 1
    assert tasks["MISSING_PHOTOS"]["progress"]["total"] == report["catalog"]["product_count"]


def test_repeat_rate_counts_every_buyer_not_the_visible_rows(client: TestClient) -> None:
    report = merchant_insights("m_mysa", days=30)
    repeat = next(card for card in report["scorecards"] if card["key"] == "repeat_rate")

    from app.db import connect

    with connect() as connection:
        rows = connection.execute(
            "SELECT s.consumer_id, COUNT(*) AS orders FROM orders o "
            "JOIN transactions t ON t.transaction_id=o.transaction_id "
            "JOIN carts c ON c.cart_id=t.cart_id "
            "JOIN sessions s ON s.session_id=c.session_id "
            "WHERE c.merchant_id='m_mysa' AND t.status='approved' "
            "GROUP BY s.consumer_id"
        ).fetchall()
    buyers = len(rows)
    repeats = len([row for row in rows if row["orders"] >= 2])
    # More buyers exist than the table shows, which is exactly the trap: counting the rows
    # on screen would report the retention of the top twelve customers as the whole store's.
    assert buyers > len(report["customers"])
    assert repeat["basis"] == f"{repeats} of {buyers} customers bought more than once"


def test_a_live_order_moves_the_dashboard(client: TestClient) -> None:
    """The demo's whole claim: buy something, and the merchant's numbers change."""
    before = merchant_insights("m_mysa", days=30)
    before_revenue = next(kpi for kpi in before["kpis"] if kpi["key"] == "revenue")["value"]

    session = client.post("/agent/session", json={"merchant_id": "m_mysa"}).json()
    with transaction() as connection:
        connection.execute(
            "INSERT INTO carts(cart_id,session_id,intent_id,cart_mandate_id,merchant_id,items_json,"
            "total_cents,currency,shipping_address_id,shipping_fingerprint,cart_hash,status,"
            "created_at,expires_at) SELECT 'cart_live', ?, m.mandate_id, m.mandate_id, 'm_mysa', ?, "
            "4200, 'SGD', 'adr_demo', 'fp', 'sha256:live', 'paid', ?, ? "
            "FROM mandates m WHERE m.session_id=? LIMIT 1",
            (
                session["session_id"],
                json.dumps(
                    [
                        {
                            "sku": "MYSA-SPF-050",
                            "title": "Daily Veil SPF 50",
                            "quantity": 1,
                            "unit_price_cents": 4200,
                        }
                    ]
                ),
                utc_now(),
                utc_now(),
                session["session_id"],
            ),
        )
        connection.execute(
            "INSERT INTO transactions(transaction_id,idempotency_key,session_id,cart_id,status,"
            "amount_cents,currency,auth_code,issuer,eci,simulated,created_at) "
            "VALUES ('txn_live','live',?, 'cart_live', 'approved',4200,'SGD','ABC123',"
            "'Mock Issuer Bank','05',1,?)",
            (session["session_id"], utc_now()),
        )
        connection.execute(
            "INSERT INTO orders(order_id,transaction_id,session_id,evidence_json,created_at) "
            "VALUES ('ord_live','txn_live',?, '{}',?)",
            (session["session_id"], utc_now()),
        )

    after = merchant_insights("m_mysa", days=30)
    after_revenue = next(kpi for kpi in after["kpis"] if kpi["key"] == "revenue")["value"]
    assert after_revenue == before_revenue + 4200


def test_payment_copy_tracks_the_authorizations_in_the_reporting_window(
    client: TestClient, merchant_key: str
) -> None:
    seeded = merchant_insights("m_mysa", days=30)
    assert seeded["payments"]["mode"] == "simulator"
    assert "no real card" in seeded["payments"]["note"]

    with transaction() as connection:
        connection.execute("UPDATE transactions SET simulated=0")

    visa = merchant_insights("m_mysa", days=30)
    assert visa["payments"]["mode"] == "visa"
    assert "Visa sandbox adapter" in visa["payments"]["note"]

    summary = client.post(
        "/merchant/m_mysa/insights/summary",
        json={"scope": "payments", "days": 30},
        headers=headers(merchant_key),
    )
    assert summary.status_code == 200, summary.text
    assert "Visa sandbox adapter" in summary.json()["summary"]

    with transaction() as connection:
        connection.execute(
            "UPDATE transactions SET simulated=1 WHERE transaction_id=("
            "SELECT t.transaction_id FROM transactions t "
            "JOIN orders o ON o.transaction_id=t.transaction_id "
            "ORDER BY o.created_at DESC LIMIT 1)"
        )
    assert merchant_insights("m_mysa", days=30)["payments"]["mode"] == "mixed"


def test_a_question_is_routed_to_a_report_without_a_model() -> None:
    assert route("how did revenue do last month?") == "revenue"
    assert route("who are my best customers?") == "customers"
    assert route("what should I fix first?") == "tasks"
    assert route("is anything out of stock?") == "catalog"
    assert route("were any payments declined?") == "payments"
    assert route("how many carts were abandoned?") == "orders"
    assert route("") == "overview"
    assert route("tell me something nice") == "overview"
    # An explicit scope always wins over the words.
    assert route("how did revenue do?", "customers") == "customers"


def test_the_summary_endpoint_only_quotes_figures_it_was_given(
    client: TestClient, merchant_key: str
) -> None:
    response = client.post(
        "/merchant/m_mysa/insights/summary",
        json={"question": "how did revenue do?", "days": 30},
        headers=headers(merchant_key),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "revenue"
    assert body["source"] == "deterministic"  # DEMO_MODE: no model is contacted at all

    report = merchant_insights("m_mysa", days=30)
    revenue = next(kpi for kpi in report["kpis"] if kpi["key"] == "revenue")
    assert revenue["display"] in body["summary"]


def test_an_unknown_report_is_refused_rather_than_guessed(
    client: TestClient, merchant_key: str
) -> None:
    response = client.post(
        "/merchant/m_mysa/insights/summary",
        json={"scope": "profit_margins"},
        headers=headers(merchant_key),
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "VALIDATION"


def test_a_rewrite_that_invents_a_figure_is_rejected() -> None:
    """The guardrail that lets a model near this screen at all."""
    allowed = {"22", "2036", "14"}
    accepted = validate_summary(
        {"summary": "22 orders from 14 customers.", "bullets": ["Revenue 2036."]},
        allowed=allowed,
    )
    assert accepted["summary"] == "22 orders from 14 customers."

    with pytest.raises(SummaryValidationError, match="invented figure"):
        validate_summary(
            {"summary": "Revenue grew 31% to 4000.", "bullets": []}, allowed=allowed
        )
    with pytest.raises(SummaryValidationError):
        validate_summary({"summary": "", "bullets": []}, allowed=allowed)


def test_thousands_separators_do_not_smuggle_a_new_number_past_the_check() -> None:
    """3,552.00 and 3552 are the same figure; 3,553 is not."""
    allowed = {"3552"}
    assert validate_summary({"summary": "S$3,552.00 banked.", "bullets": []}, allowed=allowed)
    with pytest.raises(SummaryValidationError):
        validate_summary({"summary": "S$3,553.00 banked.", "bullets": []}, allowed=allowed)


def test_the_window_is_bounded(client: TestClient, merchant_key: str) -> None:
    assert (
        client.get("/merchant/m_mysa/insights?days=999", headers=headers(merchant_key)).status_code
        == 422
    )
    narrow = client.get(
        "/merchant/m_mysa/insights?days=7", headers=headers(merchant_key)
    ).json()
    assert narrow["window"]["days"] == 7
    assert narrow["revenue_series"]["actual_days"] == 7


def test_the_seeded_history_is_inert(client: TestClient) -> None:
    """Historic sessions are a ledger. None of them may still be usable as a credential."""
    from app.db import connect

    with connect() as connection:
        resumable = connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE merchant_id='m_mysa' "
            "AND session_id LIKE 'ses_demo%' AND session_token_hash IS NOT NULL"
        ).fetchone()[0]
    assert resumable == 0


def test_the_history_is_written_once(client: TestClient) -> None:
    """Reseeding an already-populated store must not double its revenue."""
    from seed.demo_history import demo_history_totals, seed_demo_history

    before = demo_history_totals()
    assert seed_demo_history("m_mysa") is False
    assert demo_history_totals() == before


def test_the_history_covers_both_comparison_windows(client: TestClient) -> None:
    from app.db import connect

    now = datetime.now(UTC)
    with connect() as connection:
        oldest = connection.execute(
            "SELECT MIN(o.created_at) FROM orders o "
            "JOIN transactions t ON t.transaction_id=o.transaction_id "
            "JOIN carts c ON c.cart_id=t.cart_id WHERE c.merchant_id='m_mysa'"
        ).fetchone()[0]
    assert datetime.fromisoformat(oldest) <= now - timedelta(days=30)
