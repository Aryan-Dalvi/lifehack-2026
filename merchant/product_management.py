"""Merchant-owned product editing for the CRM dashboard.

Catalog uploads remain the best way to clean a whole feed. These helpers cover the other
ordinary merchant job: add one listing or correct a live product without replacing the
catalog. Every query carries ``merchant_id`` so a valid key can never widen a lookup to a
different tenant.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db import connect, json_load, transaction, utc_now
from app.errors import api_error

Sku = Annotated[str, Field(min_length=1, max_length=64)]
Title = Annotated[str, Field(min_length=1, max_length=200)]
PriceCents = Annotated[int, Field(strict=True, ge=0, le=100_000_000)]
Stock = Annotated[int, Field(strict=True, ge=0, le=10_000_000)]

_SKU_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _nonblank(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be blank")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _string_list(values: list[str] | None, *, field: str, limit: int) -> list[str] | None:
    if values is None:
        return None
    if len(values) > limit:
        raise ValueError(f"{field} accepts at most {limit} values")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            raise ValueError(f"{field} values must not be blank")
        if len(value) > 200:
            raise ValueError(f"{field} values must be at most 200 characters")
        folded = value.casefold()
        if folded not in seen:
            seen.add(folded)
            normalized.append(value)
    return normalized


def _safe_image_url(value: str | None) -> str | None:
    """Only allow image sources browsers may safely render in the storefront."""
    normalized = _optional_text(value)
    if normalized is None:
        return None
    if normalized.startswith("/") and not normalized.startswith("//"):
        return normalized
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() == "https" and parsed.hostname:
        return normalized
    if parsed.scheme.lower() == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return normalized
    raise ValueError("image_url must use https:// or be a path on this store")


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: Sku
    title: Title
    price_cents: PriceCents
    stock: Stock
    description: Annotated[str, Field(max_length=4_000)] = ""
    image_url: Annotated[str, Field(max_length=2_048)] | None = None
    product_type: Annotated[str, Field(max_length=100)] | None = None
    ingredients: list[str] | None = None
    skin_types: list[str] | None = None
    concerns: list[str] | None = None

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        normalized = _nonblank(value, field="sku")
        if not _SKU_PATTERN.fullmatch(normalized):
            raise ValueError("sku may contain only letters, numbers, dots, dashes and underscores")
        return normalized

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _nonblank(value, field="title")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return _safe_image_url(value)

    @field_validator("product_type")
    @classmethod
    def normalize_product_type(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("ingredients")
    @classmethod
    def validate_ingredients(cls, values: list[str] | None) -> list[str] | None:
        return _string_list(values, field="ingredients", limit=100)

    @field_validator("skin_types")
    @classmethod
    def validate_skin_types(cls, values: list[str] | None) -> list[str] | None:
        return _string_list(values, field="skin_types", limit=20)

    @field_validator("concerns")
    @classmethod
    def validate_concerns(cls, values: list[str] | None) -> list[str] | None:
        return _string_list(values, field="concerns", limit=30)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    price_cents: PriceCents | None = None
    stock: Stock | None = None
    description: Annotated[str, Field(max_length=4_000)] | None = None
    image_url: Annotated[str, Field(max_length=2_048)] | None = None
    product_type: Annotated[str, Field(max_length=100)] | None = None
    ingredients: list[str] | None = None
    skin_types: list[str] | None = None
    concerns: list[str] | None = None

    @model_validator(mode="after")
    def validate_update(self) -> ProductUpdate:
        if not self.model_fields_set:
            raise ValueError("provide at least one product field to update")
        for required in ("title", "price_cents", "stock"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null")
        return self

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return _nonblank(value, field="title") if value is not None else None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return _safe_image_url(value)

    @field_validator("product_type")
    @classmethod
    def normalize_product_type(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("ingredients")
    @classmethod
    def validate_ingredients(cls, values: list[str] | None) -> list[str] | None:
        return _string_list(values, field="ingredients", limit=100)

    @field_validator("skin_types")
    @classmethod
    def validate_skin_types(cls, values: list[str] | None) -> list[str] | None:
        return _string_list(values, field="skin_types", limit=20)

    @field_validator("concerns")
    @classmethod
    def validate_concerns(cls, values: list[str] | None) -> list[str] | None:
        return _string_list(values, field="concerns", limit=30)


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    attributes = json_load(row["attributes_json"], {})
    return {
        "sku": row["sku"],
        "title": row["title"],
        "description": row["description"],
        "price_cents": int(row["price_cents"]),
        "currency": row["currency"],
        "stock": int(row["stock"]),
        "image_url": row["image_url"],
        "product_type": attributes.get("product_type") or attributes.get("routine_step"),
        "ingredients": attributes.get("ingredients", []),
        "skin_types": attributes.get("skin_types", []),
        "concerns": attributes.get("concerns", []),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_products(merchant_id: str) -> dict[str, Any]:
    """Return the whole private catalog, including out-of-stock and draft products."""
    with connect() as connection:
        merchant = connection.execute(
            "SELECT currency FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
        rows = connection.execute(
            "SELECT * FROM products WHERE merchant_id=? ORDER BY title COLLATE NOCASE, sku",
            (merchant_id,),
        ).fetchall()
    if not merchant:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    products = [_payload(row) for row in rows]
    return {
        "merchant_id": merchant_id,
        "currency": merchant["currency"],
        "total": len(products),
        "products": products,
    }


def create_product(merchant_id: str, body: ProductCreate) -> dict[str, Any]:
    values = body.model_dump()
    attributes = {
        "product_type": values["product_type"],
        "product_types": [values["product_type"]] if values["product_type"] else [],
        "ingredients": values["ingredients"] or [],
        "skin_types": values["skin_types"] or [],
        "concerns": values["concerns"] or [],
    }
    now = utc_now()
    with transaction() as connection:
        merchant = connection.execute(
            "SELECT currency FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
        if not merchant:
            raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
        conflict = connection.execute(
            "SELECT 1 FROM products WHERE sku=?", (values["sku"],)
        ).fetchone()
        if conflict:
            raise api_error(409, "SKU_EXISTS", "That SKU is already in use. Choose another SKU.")
        connection.execute(
            "INSERT INTO products(sku,merchant_id,title,description,price_cents,currency,image_url,"
            "category,attributes_json,stock,rating_avg,rating_count,rating_source,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,'skincare',?,?,NULL,NULL,'none',?,?)",
            (
                values["sku"],
                merchant_id,
                values["title"],
                values["description"],
                values["price_cents"],
                merchant["currency"],
                values["image_url"],
                json.dumps(attributes, ensure_ascii=False, separators=(",", ":")),
                values["stock"],
                now,
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM products WHERE merchant_id=? AND sku=?",
            (merchant_id, values["sku"]),
        ).fetchone()
    assert row is not None
    return _payload(row)


def update_product(merchant_id: str, sku: str, body: ProductUpdate) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    with transaction() as connection:
        existing = connection.execute(
            "SELECT * FROM products WHERE merchant_id=? AND sku=?", (merchant_id, sku)
        ).fetchone()
        if not existing:
            raise api_error(404, "NO_PRODUCT", "The product was not found.")

        attributes = json_load(existing["attributes_json"], {})
        attribute_changed = False
        for field in ("ingredients", "skin_types", "concerns"):
            if field in changes:
                attributes[field] = changes.pop(field) or []
                attribute_changed = True
        if "product_type" in changes:
            product_type = changes.pop("product_type")
            attributes["product_type"] = product_type
            attributes["product_types"] = [product_type] if product_type else []
            attribute_changed = True

        columns: list[str] = []
        parameters: list[Any] = []
        for field in ("title", "description", "price_cents", "stock", "image_url"):
            if field in changes:
                columns.append(f"{field}=?")
                value = changes[field]
                parameters.append("" if field == "description" and value is None else value)
        if attribute_changed:
            columns.append("attributes_json=?")
            parameters.append(json.dumps(attributes, ensure_ascii=False, separators=(",", ":")))
        columns.append("updated_at=?")
        parameters.append(utc_now())
        parameters.extend((merchant_id, sku))
        connection.execute(
            f"UPDATE products SET {', '.join(columns)} WHERE merchant_id=? AND sku=?", parameters
        )
        row = connection.execute(
            "SELECT * FROM products WHERE merchant_id=? AND sku=?", (merchant_id, sku)
        ).fetchone()
    assert row is not None
    return _payload(row)
