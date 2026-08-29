"""Summarise any business content on the dashboard, without letting the model do the maths.

The merchant asks a question in their own words ("how did last week go?", "what should I fix
first?"). Routing that question to a report is deterministic keyword matching, the report is
built from `merchant.insights` figures, and the deterministic prose is written here and is
always correct on its own. Only then may a model reword it - and the rewrite is rejected
unless every number in it is one of the numbers it was handed.

That last check is the whole point. A merchant dashboard that hallucinates a revenue figure is
worse than no dashboard, so the failure mode is deliberately boring: the merchant reads the
deterministic sentence instead of a prettier one.
"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.settings import settings
from merchant.insights import money

SUMMARY_VERSION = "merchant-insights-summary.v1"

# The reports a question can be routed to. First match in this order wins, so the more
# specific intents are listed before the general ones.
SCOPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tasks", ("task", "to-do", "todo", "action", "priority", "fix", "next", "urgent", "attention")),
    (
        "customers",
        ("customer", "client", "shopper", "buyer", "retention", "repeat", "loyal", "churn", "who"),
    ),
    ("catalog", ("catalog", "product", "stock", "inventory", "photo", "sku", "listing", "sell")),
    (
        "payments",
        ("payment", "visa", "authorization", "authorisation", "decline", "consent", "trust", "fraud", "secure"),
    ),
    (
        "orders",
        ("order", "checkout", "cart", "basket", "abandon", "conversion", "convert", "funnel"),
    ),
    (
        "revenue",
        ("revenue", "sales", "money", "earning", "income", "takings", "forecast", "trend", "growth", "week", "month"),
    ),
)

SCOPE_TITLES = {
    "overview": "Business overview",
    "revenue": "Revenue and forecast",
    "orders": "Orders and conversion",
    "customers": "Customers",
    "catalog": "Catalog health",
    "tasks": "What to do next",
    "payments": "Payments and trust",
}

SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "bullets"],
}

SUMMARY_INSTRUCTIONS = (
    "You write one short briefing for a small-business owner about their own store. "
    "You are given a title, a deterministic summary and a list of facts already computed "
    "from their database. Rewrite the summary in at most three plain sentences and rewrite "
    "each fact as one short bullet. "
    "Every number, percentage and amount you write MUST appear verbatim in the facts you "
    "were given. Never compute, round, extrapolate or infer a new figure. Never invent a "
    "product, customer or date. If a fact is missing, leave it out rather than estimating it. "
    "No greetings, no advice about tools the merchant does not have, no emoji."
)

# What counts as a number for the guardrail: 1,234.50 / 12% / 8.4 / -3
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def route(question: str | None, requested_scope: str | None = None) -> str:
    """Pick the report this question is about. Deterministic, and biased to 'overview'."""
    if requested_scope in SCOPE_TITLES:
        return requested_scope
    text = (question or "").lower()
    if not text.strip():
        return "overview"
    for scope, keywords in SCOPES:
        if any(keyword in text for keyword in keywords):
            return scope
    return "overview"


def _facts_for(scope: str, insights: dict[str, Any]) -> tuple[str, list[str]]:
    """The deterministic briefing for one scope: a summary sentence set, and its facts."""
    currency = insights["merchant"]["currency"]
    window = insights["window"]["label"].lower()
    kpis = {kpi["key"]: kpi for kpi in insights["kpis"]}
    cards = {card["key"]: card for card in insights["scorecards"]}
    series = insights["revenue_series"]
    activity = insights["activity"]
    catalog = insights["catalog"]
    tasks = insights["tasks"]
    top = insights["top_products"]

    if scope == "revenue":
        forecast = series["forecast"]
        summary = (
            f"Revenue over the {window} is {kpis['revenue']['display']}, against "
            f"{kpis['revenue']['previous_display']} in the previous period "
            f"({kpis['revenue']['delta_display']}). At the current run rate the next "
            f"{forecast['horizon_days']} days add about {money(forecast['total_cents'], currency)}."
        )
        facts = [
            f"Revenue this period: {kpis['revenue']['display']} from {kpis['orders']['display']} orders.",
            f"Previous period: {kpis['revenue']['previous_display']}.",
            f"Average order value: {cards['aov']['display']}.",
            f"Forecast method: {forecast['method']}, {money(forecast['per_day_cents'], currency)} per day.",
        ]
        if series.get("peak"):
            facts.append(
                f"Best day: {series['peak']['label']} at "
                f"{money(series['peak']['actual_cents'], currency)}."
            )
        if top:
            facts.append(
                f"Top product by revenue: {top[0]['title']}, "
                f"{money(top[0]['revenue_cents'], currency)} across {top[0]['units']} units."
            )
        return summary, facts

    if scope == "orders":
        summary = (
            f"{kpis['orders']['display']} orders closed in the {window} at "
            f"{cards['aov']['display']} average value. {cards['conversion']['display']} of "
            f"assistant conversations end in a paid order, and "
            f"{cards['recoverable']['display']} is still sitting in carts that were priced "
            "and never authorized."
        )
        facts = [
            f"Orders: {kpis['orders']['display']} (previous period {kpis['orders']['previous_display']}).",
            f"Conversations: {activity['sessions']} (previous period {activity['sessions_previous']}).",
            f"Conversion: {cards['conversion']['display']} - {cards['conversion']['basis']}.",
            f"Abandoned carts: {activity['abandoned_carts']}, worth {money(activity['abandoned_cents'], currency)}.",
        ]
        return summary, facts

    if scope == "customers":
        tabs = {tab["key"]: tab["count"] for tab in insights["customer_tabs"]}
        summary = (
            f"{kpis['customers']['display']} customers bought in the {window}, "
            f"{kpis['customers']['delta_display']} on the previous period. "
            f"Repeat rate is {cards['repeat_rate']['display']} and average lifetime spend is "
            f"{cards['lifetime_value']['display']}."
        )
        facts = [
            f"Buying customers: {kpis['customers']['display']} (previous period {kpis['customers']['previous_display']}).",
            f"Repeat rate: {cards['repeat_rate']['display']} - {cards['repeat_rate']['basis']}.",
            f"Lifetime spend: {cards['lifetime_value']['display']} ({cards['lifetime_value']['basis']}).",
            f"Needing follow-up: {tabs.get('follow_up', 0)}. Abandoned carts: {tabs.get('abandoned', 0)}.",
        ]
        if insights["customers"]:
            best = insights["customers"][0]
            facts.append(
                f"Highest value customer: {best['name']}, "
                f"{money(best['value_cents'], currency)} {best['value_kind']}."
            )
        return summary, facts

    if scope == "catalog":
        summary = (
            f"{catalog['product_count']} products are live, "
            f"{catalog['in_stock_count']} of them in stock and "
            f"{catalog['with_photo_count']} with a photo. Average price is "
            f"{money(catalog['average_price_cents'], currency)}."
        )
        facts = [
            f"Products: {catalog['product_count']}, average price {money(catalog['average_price_cents'], currency)}.",
            f"Sold out: {len(catalog['out_of_stock'])}"
            + (f" ({', '.join(catalog['out_of_stock'][:3])})." if catalog["out_of_stock"] else "."),
            f"Low stock: {len(catalog['low_stock'])}"
            + (f" ({', '.join(catalog['low_stock'][:3])})." if catalog["low_stock"] else "."),
            f"Without a photo: {len(catalog['without_photo'])}.",
        ]
        if top:
            facts.append(f"Best seller: {top[0]['title']}, {top[0]['units']} units.")
        return summary, facts

    if scope == "tasks":
        if not tasks:
            return (
                "Nothing is waiting on you: stock, photos and catalog rows are all clear, "
                "and no checkout has failed in this period."
            ), []
        summary = (
            f"{len(tasks)} things need attention. Start with {tasks[0]['title'].lower()}: "
            f"{tasks[0]['detail']}"
        )
        facts = [f"{task['title']} - {task['chip']}. {task['detail']}" for task in tasks[:5]]
        return summary, facts

    if scope == "payments":
        summary = (
            f"{kpis['orders']['display']} authorizations settled in the {window}, worth "
            f"{kpis['revenue']['display']}. Every one is a simulated Visa authorization: the "
            "agent never prices a cart or authorizes a payment, and each order carries a "
            "signed mandate chain."
        )
        facts = [
            f"Approved authorizations: {kpis['orders']['display']}, {kpis['revenue']['display']}.",
            (
                f"Carts priced but never authorized: {activity['abandoned_carts']}, "
                f"{money(activity['abandoned_cents'], currency)}."
            ),
            "Payment mode: simulator. No real card is charged.",
            "Every payment request is Ed25519-signed and verified as a TAP-shaped HTTP Message Signature.",
        ]
        return summary, facts

    summary = (
        f"Over the {window} the store took {kpis['revenue']['display']} from "
        f"{kpis['orders']['display']} orders and {kpis['customers']['display']} customers, "
        f"against {kpis['revenue']['previous_display']} in the previous period "
        f"({kpis['revenue']['delta_display']}). {insights['insight']['text']}"
    )
    facts = [
        f"Revenue: {kpis['revenue']['display']} ({kpis['revenue']['delta_display']} on the previous period).",
        f"Orders: {kpis['orders']['display']}. Customers: {kpis['customers']['display']}.",
        f"Conversion: {cards['conversion']['display']} - {cards['conversion']['basis']}.",
        f"Recoverable carts: {cards['recoverable']['display']} across {activity['abandoned_carts']} carts.",
    ]
    if tasks:
        facts.append(f"Top task: {tasks[0]['title']} - {tasks[0]['chip']}.")
    if top:
        facts.append(f"Top product: {top[0]['title']}, {money(top[0]['revenue_cents'], currency)}.")
    return summary, facts


def _allowed_numbers(text_blocks: list[str]) -> set[str]:
    """Every number the model is permitted to write, normalised so 3,552.00 == 3552.0."""
    allowed: set[str] = set()
    for block in text_blocks:
        for match in _NUMBER.findall(block):
            allowed.add(_normalise(match))
    return allowed


def _normalise(number: str) -> str:
    cleaned = number.replace(",", "")
    try:
        return f"{float(cleaned):g}"
    except ValueError:
        return cleaned


class SummaryValidationError(ValueError):
    pass


def validate_summary(payload: Any, *, allowed: set[str]) -> dict[str, Any]:
    """Accept a rewrite only if it invented no figure of its own."""
    if not isinstance(payload, dict):
        raise SummaryValidationError("summary payload must be an object")
    summary = payload.get("summary")
    bullets = payload.get("bullets")
    if not isinstance(summary, str) or not summary.strip():
        raise SummaryValidationError("summary must be a non-empty string")
    if not isinstance(bullets, list) or not all(isinstance(item, str) for item in bullets):
        raise SummaryValidationError("bullets must be an array of strings")
    for block in [summary, *bullets]:
        for match in _NUMBER.findall(block):
            if _normalise(match) not in allowed:
                raise SummaryValidationError(f"invented figure {match!r}")
    return {
        "summary": " ".join(summary.split())[:700],
        "bullets": [" ".join(bullet.split())[:220] for bullet in bullets[:6]],
    }


async def _ask_model(title: str, summary: str, facts: list[str]) -> dict[str, Any]:
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=15.0, max_retries=0)
    from merchant.catalog_cleaner import response_format

    allowed = _allowed_numbers([summary, *facts])
    request = {"title": title, "deterministic_summary": summary, "facts": facts}
    validation_error = ""
    for attempt in range(2):
        repair = (
            f" Your previous output was rejected: {validation_error[:200]}. "
            "Use only figures that appear in the facts."
            if attempt
            else ""
        )
        response = await client.responses.create(
            model=settings.openai_model,
            instructions=SUMMARY_INSTRUCTIONS + repair,
            input=json.dumps(request, ensure_ascii=False),
            text=response_format("merchant_insights_summary", SUMMARY_SCHEMA),
            max_output_tokens=1200,
            store=False,
        )
        try:
            return validate_summary(json.loads(response.output_text), allowed=allowed)
        except (json.JSONDecodeError, SummaryValidationError) as exc:
            validation_error = str(exc)
    raise SummaryValidationError(validation_error or "summary could not be validated")


async def summarize_business(
    insights: dict[str, Any],
    *,
    question: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """Answer one business question from the dashboard's own figures."""
    resolved = route(question, scope)
    title = SCOPE_TITLES[resolved]
    summary, facts = _facts_for(resolved, insights)
    briefing = {
        "version": SUMMARY_VERSION,
        "scope": resolved,
        "title": title,
        "question": question,
        "summary": summary,
        "bullets": facts,
        "source": "deterministic",
        "window": insights["window"]["label"],
        "generated_at": insights["generated_at"],
    }
    if settings.demo_mode or not settings.openai_api_key:
        return briefing

    try:
        rewritten = await _ask_model(title, summary, facts)
    except Exception:  # noqa: BLE001 - the deterministic briefing is already correct
        return {**briefing, "source": "deterministic_failover"}

    return {
        **briefing,
        "summary": rewritten["summary"],
        "bullets": rewritten["bullets"] or facts,
        "source": "model_rephrased_deterministic_facts",
    }
