from __future__ import annotations

from typing import Any

from app.errors import api_error

ALLOWED_ROUTES = {"clarify", "search", "compare", "product_detail", "cart", "unsupported"}
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
    if any(sku not in visible_skus for sku in selected):
        raise api_error(422, "UNGROUNDED_CLAIM", "The interpreter selected a product not shown.")
    return value


def validate_products(products: list[dict[str, Any]], merchant_id: str) -> list[dict[str, Any]]:
    for product in products:
        if product["merchant_id"] != merchant_id or product["category"] != "skincare":
            raise api_error(422, "OUT_OF_SCOPE_PRODUCT", "Catalog results escaped session scope.")
        if not isinstance(product["price_cents"], int):
            raise api_error(422, "UNGROUNDED_CLAIM", "A product price was not an integer amount.")
    return products

