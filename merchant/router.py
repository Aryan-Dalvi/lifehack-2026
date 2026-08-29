from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.db import connect, json_load, transaction, utc_now
from app.errors import api_error
from app.ids import new_id
from app.settings import settings
from merchant.catalog_pipeline import (
    approve_catalog_upload,
    catalog_upload_preview,
    parse_catalog,
    stage_and_clean_catalog,
)

merchant_router = APIRouter(prefix="/merchant", tags=["merchant"])
catalog_router = APIRouter(prefix="/catalog", tags=["catalog"])
consumer_router = APIRouter(prefix="/consumer", tags=["consumer"])


class OnboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    size: str = "sme"
    category: str = "skincare"
    currency: str = "SGD"


class ConfigUpdate(BaseModel):
    name: str | None = None
    size: str | None = None
    currency: str | None = None
    accent_color: str | None = None
    persona: str | None = None
    policies: dict[str, Any] | None = None
    status: str | None = None


class ApproveCatalogRequest(BaseModel):
    approval_token: str = Field(min_length=64, max_length=64)
    reviewed_row_count: int = Field(ge=1, le=10_000)
    mode: Literal["replace", "upsert"] = "replace"


def _snippet(merchant_id: str) -> str:
    return (
        f'<script src="{settings.web_base_url}/widget.js" '
        f'data-merchant="{merchant_id}" data-position="bottom-right"></script>'
    )


def _merchant_payload(row) -> dict[str, Any]:
    return {
        "merchant_id": row["merchant_id"],
        "name": row["name"],
        "size": row["size"],
        "category": row["category"],
        "currency": row["currency"],
        "accent_color": row["accent_color"],
        "persona": row["persona"],
        "policies": json_load(row["policies_json"], {}),
        "status": row["status"],
        "hosted_url": f"{settings.web_base_url}/storefront?merchant={row['merchant_id']}",
        "embed_snippet": _snippet(row["merchant_id"]),
    }


@merchant_router.post("/onboard")
def onboard(body: OnboardRequest) -> dict[str, Any]:
    if body.category != "skincare":
        raise api_error(400, "VALIDATION", "The Phase 0 agent supports skincare only.")
    if body.size not in {"sme", "enterprise"}:
        raise api_error(400, "VALIDATION", "Merchant size must be sme or enterprise.")
    merchant_id = new_id("m")
    with transaction() as connection:
        connection.execute(
            "INSERT INTO merchants(merchant_id,name,size,category,currency,created_at) VALUES (?,?,?,?,?,?)",
            (merchant_id, body.name.strip(), body.size, "skincare", body.currency, utc_now()),
        )
    return {
        "merchant_id": merchant_id,
        "api_key": f"demo_{new_id('key')}",
        "embed_snippet": _snippet(merchant_id),
        "hosted_url": f"{settings.web_base_url}/storefront?merchant={merchant_id}",
    }


@merchant_router.get("/{merchant_id}/config")
def merchant_config(merchant_id: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
    if not row:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    return _merchant_payload(row)


@merchant_router.put("/{merchant_id}/config")
def update_config(merchant_id: str, body: ConfigUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_none=True)
    if values.get("size") not in {None, "sme", "enterprise"}:
        raise api_error(400, "VALIDATION", "Merchant size must be sme or enterprise.")
    if values.get("status") not in {None, "draft", "published"}:
        raise api_error(400, "VALIDATION", "Merchant status must be draft or published.")
    if not values:
        return merchant_config(merchant_id)

    columns: list[str] = []
    parameters: list[Any] = []
    for key, value in values.items():
        column = "policies_json" if key == "policies" else key
        columns.append(f"{column}=?")
        parameters.append(json.dumps(value) if key == "policies" else value)
    parameters.append(merchant_id)
    with transaction() as connection:
        updated = connection.execute(
            f"UPDATE merchants SET {', '.join(columns)} WHERE merchant_id=?", parameters
        ).rowcount
    if not updated:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    return merchant_config(merchant_id)


@merchant_router.get("/{merchant_id}/snippet")
def merchant_snippet(merchant_id: str) -> dict[str, str]:
    merchant_config(merchant_id)
    return {
        "snippet": _snippet(merchant_id),
        "hosted_url": f"{settings.web_base_url}/storefront?merchant={merchant_id}",
    }


async def _catalog_source(request: Request):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise api_error(400, "BAD_CATALOG", "Choose a CSV, XLSX or JSON catalog file.")
        content = await upload.read()
        filename = getattr(upload, "filename", "catalog.csv") or "catalog.csv"
        requested_sheet = form.get("sheet_name")
        return parse_catalog(
            content,
            filename,
            sheet_name=str(requested_sheet) if requested_sheet else None,
        )

    if "application/json" in content_type:
        return parse_catalog(await request.body(), "catalog.json")
    raise api_error(400, "BAD_CATALOG", "Use multipart file upload or application/json.")


@merchant_router.post("/{merchant_id}/catalog")
@merchant_router.post("/{merchant_id}/catalog/uploads")
async def ingest_catalog(merchant_id: str, request: Request) -> dict[str, Any]:
    merchant = merchant_config(merchant_id)
    parsed = await _catalog_source(request)
    return await stage_and_clean_catalog(merchant=merchant, parsed=parsed)


@merchant_router.get("/{merchant_id}/catalog/uploads/{upload_id}")
def catalog_upload(
    merchant_id: str,
    upload_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    merchant_config(merchant_id)
    return catalog_upload_preview(merchant_id, upload_id, offset=offset, limit=limit)


@merchant_router.post("/{merchant_id}/catalog/uploads/{upload_id}/approve")
def approve_catalog(
    merchant_id: str, upload_id: str, body: ApproveCatalogRequest
) -> dict[str, Any]:
    merchant_config(merchant_id)
    return approve_catalog_upload(
        merchant_id=merchant_id,
        upload_id=upload_id,
        approval_token=body.approval_token,
        reviewed_row_count=body.reviewed_row_count,
        mode=body.mode,
    )


def _product_payload(row) -> dict[str, Any]:
    return {
        "sku": row["sku"],
        "merchant_id": row["merchant_id"],
        "merchant_name": row["merchant_name"],
        "merchant_size": row["merchant_size"],
        "title": row["title"],
        "description": row["description"],
        "price_cents": int(row["price_cents"]),
        "currency": row["currency"],
        "image_url": row["image_url"],
        "category": row["category"],
        "attributes": json_load(row["attributes_json"], {}),
        "stock": int(row["stock"]),
        "rating_avg": row["rating_avg"],
        "rating_count": row["rating_count"],
        "rating_source": row["rating_source"],
    }


@catalog_router.get("/search")
def catalog_search(
    q: str = "",
    merchant_id: str = "m_mysa",
    category: str = "skincare",
    max_price_cents: int | None = None,
    attrs: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    if category != "skincare":
        raise api_error(400, "VALIDATION", "The Phase 0 catalog supports skincare only.")
    limit = max(1, min(limit, 5))
    try:
        attr_filters = json.loads(attrs) if attrs else {}
    except json.JSONDecodeError as exc:
        raise api_error(400, "VALIDATION", "Attribute filters must be valid JSON.") from exc
    with connect() as connection:
        rows = connection.execute(
            "SELECT p.*,m.name AS merchant_name,m.size AS merchant_size FROM products p "
            "JOIN merchants m ON m.merchant_id=p.merchant_id "
            "WHERE p.merchant_id=? AND p.category='skincare' AND p.stock>0",
            (merchant_id,),
        ).fetchall()
    query_tokens = {token for token in q.lower().replace("-", " ").split() if len(token) > 2}
    candidates: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        product = _product_payload(row)
        if max_price_cents is not None and product["price_cents"] > max_price_cents:
            continue
        attributes = product["attributes"]
        if any(
            isinstance(expected, list)
            and not set(map(str.lower, expected)).issubset(set(map(str.lower, attributes.get(key, []))))
            for key, expected in attr_filters.items()
            if isinstance(expected, list)
        ):
            continue
        rejected = False
        for key, expected in attr_filters.items():
            actual = attributes.get(key)
            if isinstance(expected, list):
                continue
            if isinstance(expected, bool) and actual is not expected or expected is not None and not isinstance(expected, bool) and str(actual).lower() != str(expected).lower():
                rejected = True
        if rejected:
            continue
        searchable = " ".join(
            [
                product["title"],
                product["description"],
                json.dumps(attributes),
            ]
        ).lower()
        score = sum(4 if token in product["title"].lower() else 1 for token in query_tokens if token in searchable)
        if query_tokens and score == 0:
            continue
        candidates.append((score, product))
    candidates.sort(
        key=lambda entry: (
            -entry[0],
            -(entry[1]["rating_avg"] or 0),
            entry[1]["price_cents"],
            entry[1]["sku"],
        )
    )
    results = [product for _, product in candidates[:limit]]
    return {
        "results": results,
        "total": len(candidates),
        "facets": {
            "routine_steps": sorted(
                {product["attributes"].get("routine_step") for _, product in candidates}
                - {None, ""}
            ),
            "currency": "SGD",
        },
        "source": "catalog_database",
    }


@catalog_router.get("/product/{sku}")
def catalog_product(sku: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            "SELECT p.*,m.name AS merchant_name,m.size AS merchant_size FROM products p "
            "JOIN merchants m ON m.merchant_id=p.merchant_id WHERE p.sku=?",
            (sku,),
        ).fetchone()
    if not row:
        raise api_error(404, "NO_PRODUCT", "The product was not found.")
    return _product_payload(row)


@consumer_router.get("/{consumer_id}/addresses")
def addresses(consumer_id: str) -> dict[str, Any]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM addresses WHERE consumer_id=? ORDER BY is_default DESC", (consumer_id,)
        ).fetchall()
    if not rows:
        raise api_error(404, "NO_CONSUMER", "No saved addresses were found.")
    values = [
        {
            "address_id": row["address_id"],
            "consumer_id": row["consumer_id"],
            "recipient": row["recipient"],
            "lines": json_load(row["lines_json"], []),
            "postal_code": row["postal_code"],
            "country": row["country"],
            "is_default": bool(row["is_default"]),
        }
        for row in rows
    ]
    return {
        "addresses": values,
        "default_address_id": next(
            (value["address_id"] for value in values if value["is_default"]), None
        ),
    }


@consumer_router.put("/{consumer_id}/addresses/{address_id}/default")
def set_default_address(consumer_id: str, address_id: str) -> dict[str, str]:
    with transaction() as connection:
        exists = connection.execute(
            "SELECT 1 FROM addresses WHERE consumer_id=? AND address_id=?",
            (consumer_id, address_id),
        ).fetchone()
        if not exists:
            raise api_error(404, "NO_ADDRESS", "The shipping address was not found.")
        connection.execute("UPDATE addresses SET is_default=0 WHERE consumer_id=?", (consumer_id,))
        connection.execute(
            "UPDATE addresses SET is_default=1 WHERE address_id=?", (address_id,)
        )
    return {"default_address_id": address_id}
