from __future__ import annotations

import re
from typing import Any

from app.errors import api_error

ALLOWED_ROUTES = {
    "clarify",
    "answer",
    "search",
    "recommend",
    "categories",
    "compare",
    "product_detail",
    "cart",
    "unsupported",
}
ALLOWED_FILTERS = {
    "routine_step",
    "skin_types",
    "concerns",
    "ingredients",
    "excludes",
    "fragrance_free",
}


def validate_interpretation(
    value: dict[str, Any],
    *,
    merchant_id: str,
    visible_skus: list[str],
    catalog_skus: list[str] | None = None,
) -> dict[str, Any]:
    route = value.get("route")
    if route not in ALLOWED_ROUTES:
        raise api_error(422, "SCHEMA_REJECTED", "The interpreter returned an invalid route.")
    query = value.get("catalog_query") or {}
    if query:
        merchant_ids = query.get("merchant_ids") or [merchant_id]
        if merchant_ids != [merchant_id] or query.get("category", "skincare") != "skincare":
            raise api_error(422, "OUT_OF_SCOPE_PRODUCT", "The interpreter widened merchant scope.")
        filters = query.get("filters") or {}
        if unknown := set(filters) - ALLOWED_FILTERS:
            raise api_error(
                422,
                "SCHEMA_REJECTED",
                "The interpreter returned unsupported skincare filters.",
                fields=sorted(unknown),
            )
        if query.get("limit", 5) > 5:
            query["limit"] = 5
        max_price = query.get("max_price_cents")
        if max_price is not None and max_price < 0:
            raise api_error(422, "SCHEMA_REJECTED", "A price filter cannot be negative.")
        query["merchant_ids"] = [merchant_id]
        query["category"] = "skincare"
        value["catalog_query"] = query
    selected = value.get("selected_skus") or []
    # A shopper may name a product that is not on screen - "tell me about the Gentle Cloud
    # Cleanser" on a fresh session - and that is a fair question about this shop. What must
    # never be allowed is a SKU from outside this merchant, so the allowed set is this
    # merchant's own catalog, scoped by the caller, rather than only what is displayed.
    grounded = set(visible_skus) | set(catalog_skus or [])
    if any(sku not in grounded for sku in selected):
        raise api_error(
            422, "OUT_OF_SCOPE_PRODUCT", "The interpreter selected a product from another shop."
        )
    return value


# One source of truth for the medical boundary, used on the way in (interpreter, before the
# model is consulted) and on the way out (phrasing, below). These were previously two separate
# lists that disagreed: naming a condition was refused in generated advice but accepted as a
# shopping filter, so "my eczema is flaring" was routed to search instead of the safety boundary.
MEDICAL_CONDITIONS = {
    "eczema",
    "psoriasis",
    "dermatitis",
    "rosacea",
    "melanoma",
    "impetigo",
    "shingles",
    "cellulitis",
}

# Acts only a clinician performs. "treat"/"treatment" is deliberately absent: "treatment" is a
# legitimate routine step in the catalog schema, so it cannot mean a medical request on its own.
MEDICAL_ACTS = {
    "diagnose",
    "diagnosed",
    "diagnosis",
    "cure",
    "cures",
    "cured",
    "heal",
    "heals",
    "prescribe",
    "prescribed",
    "prescription",
}

MEDICAL_MARKETING_CLAIMS = {
    "clinically proven",
    "medical grade",
    "medical-grade",
}

MEDICAL_CLAIM_TERMS = MEDICAL_CONDITIONS | MEDICAL_ACTS | MEDICAL_MARKETING_CLAIMS

_MEDICAL_REQUEST_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(
        sorted((re.escape(term) for term in MEDICAL_CONDITIONS | MEDICAL_ACTS), key=len, reverse=True)
    )
    + r")\b"
)


def is_medical_request(message: str) -> bool:
    """True when a shopper message names a medical condition or asks for a clinical act.

    Word-boundary matched on purpose. The previous check tested for contiguous phrases like
    "treat eczema", so inserting a single word — "treat my eczema" — walked straight past it.
    """
    return bool(_MEDICAL_REQUEST_PATTERN.search(message.lower()))


MAX_SUMMARY_CHARS = 400
MAX_ADVICE_CHARS = 240
MAX_ANSWER_CHARS = 900

# Any money-shaped token in free prose, whether the currency leads ("S$36") or trails
# ("3600 cents"). The adviser is told never to quote a price; this is what makes that a rule
# rather than a request, since a wrong price is the most damaging thing it could invent —
# and the product card beside the answer already carries the real one.
_PRICE_PATTERN = re.compile(
    r"(?:(?:s\$|\$|sgd|usd)\s*\d+(?:[.,]\d+)?)"
    r"|(?:\d+(?:[.,]\d+)?\s*(?:cents?|dollars?|sgd|usd)\b)",
    re.IGNORECASE,
)


def validate_answer(
    value: dict[str, Any],
    *,
    allowed_skus: list[str],
) -> tuple[dict[str, Any], list[str]]:
    """Check a free-form adviser answer before a shopper ever sees it.

    The adviser is the only component allowed to contribute general skincare knowledge, so
    it is also the one whose output needs the widest check: no invented product, no quoted
    price, no medical claim. A rejected answer is dropped entirely rather than trimmed —
    there is no safe way to partially believe a paragraph.
    """
    violations: list[str] = []
    allowed = set(allowed_skus)
    cited = [sku for sku in (value.get("cited_skus") or []) if isinstance(sku, str)]
    grounded = [sku for sku in cited if sku in allowed]
    if len(grounded) != len(cited):
        violations.append("UNGROUNDED_CLAIM")

    answer = value.get("answer")
    if not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_ANSWER_CHARS:
        return {"answer": "", "cited_skus": grounded}, [*violations, "SCHEMA_REJECTED"]
    if any(term in answer.lower() for term in MEDICAL_CLAIM_TERMS):
        return {"answer": "", "cited_skus": []}, [*violations, "MEDICAL_CLAIM"]
    if _PRICE_PATTERN.search(answer):
        # The prose is dropped, but the products it pointed at are real and their cards
        # carry the authoritative price — so the shopper still gets an answer.
        return {"answer": "", "cited_skus": grounded}, [*violations, "PRICE_IN_PROSE"]

    return {"answer": answer.strip(), "cited_skus": grounded}, violations


def validate_recommendation(
    value: dict[str, Any],
    *,
    allowed_skus: list[str],
) -> tuple[dict[str, Any], list[str]]:
    """Strip anything the phraser was not entitled to say.

    Returns the safe recommendation plus the list of violations that were dropped.
    Prose is never trusted enough to fail the turn: an ungrounded or unsafe line is
    removed and the deterministic routine plan carries the answer on its own.
    """
    violations: list[str] = []
    allowed = set(allowed_skus)

    summary = value.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > MAX_SUMMARY_CHARS:
        summary = ""
        violations.append("SCHEMA_REJECTED")
    elif any(term in summary.lower() for term in MEDICAL_CLAIM_TERMS):
        summary = ""
        violations.append("MEDICAL_CLAIM")

    safe_steps = []
    for step in value.get("steps") or []:
        if not isinstance(step, dict):
            violations.append("SCHEMA_REJECTED")
            continue
        sku = step.get("sku")
        advice = step.get("advice")
        if sku not in allowed:
            violations.append("UNGROUNDED_CLAIM")
            continue
        if not isinstance(advice, str) or not advice.strip():
            violations.append("SCHEMA_REJECTED")
            continue
        if len(advice) > MAX_ADVICE_CHARS:
            violations.append("SCHEMA_REJECTED")
            continue
        if any(term in advice.lower() for term in MEDICAL_CLAIM_TERMS):
            violations.append("MEDICAL_CLAIM")
            continue
        safe_steps.append({"sku": sku, "advice": advice.strip()})

    return {"summary": summary.strip(), "steps": safe_steps}, violations


def validate_products(products: list[dict[str, Any]], merchant_id: str) -> list[dict[str, Any]]:
    for product in products:
        if product["merchant_id"] != merchant_id or product["category"] != "skincare":
            raise api_error(422, "OUT_OF_SCOPE_PRODUCT", "Catalog results escaped session scope.")
        if not isinstance(product["price_cents"], int):
            raise api_error(422, "UNGROUNDED_CLAIM", "A product price was not an integer amount.")
    return products

