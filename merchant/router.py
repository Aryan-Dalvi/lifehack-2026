from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    SIGNUP_ATTEMPT_LIMIT,
    assert_consumer,
    assert_merchant,
    assert_usable_password,
    check_rate_limit,
    hash_password,
    is_merchant,
    issue_consumer_token,
    new_secret,
    require_consumer,
    require_merchant,
    reset_rate_limit,
    revoke_consumer_token,
    token_digest,
    verify_password,
)
from app.db import connect, json_load, transaction, utc_now
from app.errors import api_error
from app.ids import new_id
from app.settings import settings
from merchant.catalog_images import MAX_ARCHIVE_BYTES
from merchant.catalog_pipeline import (
    approve_catalog_upload,
    attach_product_images,
    catalog_image_url,
    catalog_upload_preview,
    parse_catalog,
    stage_and_clean_catalog,
)
from merchant.catalog_template import TEMPLATE_FILENAME, build_template

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
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
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
    api_key = new_secret("mk")
    with transaction() as connection:
        connection.execute(
            "INSERT INTO merchants(merchant_id,api_key_hash,name,size,category,currency,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                merchant_id,
                token_digest(api_key),
                body.name.strip(),
                body.size,
                "skincare",
                body.currency,
                utc_now(),
            ),
        )
    return {
        "merchant_id": merchant_id,
        # Shown once. Only the digest is stored, so this response is the only copy.
        "api_key": api_key,
        "embed_snippet": _snippet(merchant_id),
        "hosted_url": f"{settings.web_base_url}/storefront?merchant={merchant_id}",
    }


def merchant_config(merchant_id: str) -> dict[str, Any]:
    """Internal read. Callers that are reachable over HTTP must authorise first."""
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
    if not row:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    return _merchant_payload(row)


@merchant_router.get("/me")
def merchant_me(
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    """Which store does this key open?

    Declared before /{merchant_id}/config so "me" is never read as a merchant id. This is
    what lets the admin page serve any merchant: it resolves the caller from their key
    instead of being told which store to load.
    """
    return merchant_config(require_merchant(x_merchant_key))


@merchant_router.get("/{merchant_id}/config")
def merchant_config_route(
    merchant_id: str,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    assert_merchant(merchant_id, x_merchant_key)
    return merchant_config(merchant_id)


@merchant_router.put("/{merchant_id}/config")
def update_config(
    merchant_id: str,
    body: ConfigUpdate,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    assert_merchant(merchant_id, x_merchant_key)
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
def merchant_snippet(
    merchant_id: str,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, str]:
    assert_merchant(merchant_id, x_merchant_key)
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
async def ingest_catalog(
    merchant_id: str,
    request: Request,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    assert_merchant(merchant_id, x_merchant_key)
    merchant = merchant_config(merchant_id)
    parsed = await _catalog_source(request)
    return await stage_and_clean_catalog(merchant=merchant, parsed=parsed)


@merchant_router.post("/{merchant_id}/catalog/images")
async def ingest_product_images(
    merchant_id: str,
    request: Request,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    """Attach a ZIP of product photos to the live catalog, matched by file name.

    Photos do not go through the staged review that catalog rows do: they only ever set
    `image_url`, so the worst a bad match can do is show the wrong picture, which the
    merchant can see and correct by uploading a corrected archive.
    """
    assert_merchant(merchant_id, x_merchant_key)
    merchant = merchant_config(merchant_id)
    if "multipart/form-data" not in request.headers.get("content-type", ""):
        raise api_error(400, "BAD_IMAGE_ARCHIVE", "Upload the photos as a multipart .zip file.")
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise api_error(400, "BAD_IMAGE_ARCHIVE", "Choose a .zip file of product photos.")
    content = await upload.read()
    if len(content) > MAX_ARCHIVE_BYTES:
        raise api_error(413, "TOO_LARGE", "Image archives are limited to 25 MB.")
    return await attach_product_images(
        merchant=merchant,
        content=content,
        filename=getattr(upload, "filename", "photos.zip") or "photos.zip",
    )


@merchant_router.get("/{merchant_id}/catalog/uploads/{upload_id}")
def catalog_upload(
    merchant_id: str,
    upload_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    # A staged upload is this merchant's unpublished catalog - pricing and stock they have
    # not shipped yet - so it is read with their key, like the rest of their private data.
    assert_merchant(merchant_id, x_merchant_key)
    merchant_config(merchant_id)
    return catalog_upload_preview(merchant_id, upload_id, offset=offset, limit=limit)


@merchant_router.post("/{merchant_id}/catalog/uploads/{upload_id}/approve")
def approve_catalog(
    merchant_id: str,
    upload_id: str,
    body: ApproveCatalogRequest,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    # Approving publishes rows into the live catalog: a write, and the most consequential
    # one this router has.
    assert_merchant(merchant_id, x_merchant_key)
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


def catalog_search(
    q: str = "",
    merchant_id: str = "",
    category: str = "skincare",
    max_price_cents: int | None = None,
    attrs: str | None = None,
    limit: int = 5,
    *,
    include_unpublished: bool = False,
) -> dict[str, Any]:
    """Internal search. Kept free of request-layer types: the agent calls this directly, and
    a Header() default arrives as a Header object rather than None when it does."""
    if not merchant_id:
        raise api_error(400, "VALIDATION", "A merchant_id is required to search a catalog.")
    if category != "skincare":
        raise api_error(400, "VALIDATION", "The Phase 0 catalog supports skincare only.")
    limit = max(1, min(limit, 5))
    try:
        attr_filters = json.loads(attrs) if attrs else {}
    except json.JSONDecodeError as exc:
        raise api_error(400, "VALIDATION", "Attribute filters must be valid JSON.") from exc
    # A merchant who has not published is not open for business: their catalog and prices
    # are not public. They can still see their own, with their key.
    own_store = include_unpublished
    with connect() as connection:
        rows = connection.execute(
            "SELECT p.*,m.name AS merchant_name,m.size AS merchant_size FROM products p "
            "JOIN merchants m ON m.merchant_id=p.merchant_id "
            "WHERE p.merchant_id=? AND p.category='skincare' AND p.stock>0 "
            "AND (m.status='published' OR ?=1)",
            (merchant_id, 1 if own_store else 0),
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


def catalog_digest(merchant_id: str, *, include_unpublished: bool = False) -> list[dict[str, Any]]:
    """Every purchasable product for one merchant — the agent's view of the whole shop.

    Same tenant and published rules as `catalog_search`, but unranked and unlimited, so the
    agent can answer questions *about* the catalog rather than only search within it.
    """
    with connect() as connection:
        rows = connection.execute(
            "SELECT p.*,m.name AS merchant_name,m.size AS merchant_size FROM products p "
            "JOIN merchants m ON m.merchant_id=p.merchant_id "
            "WHERE p.merchant_id=? AND p.category='skincare' AND p.stock>0 "
            "AND (m.status='published' OR ?=1) ORDER BY p.sku",
            (merchant_id, 1 if include_unpublished else 0),
        ).fetchall()
    return [_product_payload(row) for row in rows]


def catalog_product(sku: str, merchant_id: str, *, include_unpublished: bool = False) -> dict[str, Any]:
    """Read one product, always scoped to a merchant.

    merchant_id is a required argument, not an option: while this lookup was unscoped, a
    session pinned to one merchant could read another merchant's rows — title, price and
    ingredient list — by naming their SKU through /agent/action.
    """
    with connect() as connection:
        row = connection.execute(
            "SELECT p.*,m.name AS merchant_name,m.size AS merchant_size FROM products p "
            "JOIN merchants m ON m.merchant_id=p.merchant_id "
            "WHERE p.sku=? AND p.merchant_id=? AND (m.status='published' OR ?=1)",
            (sku, merchant_id, 1 if include_unpublished else 0),
        ).fetchone()
    if not row:
        raise api_error(404, "NO_PRODUCT", "The product was not found.")
    return _product_payload(row)


@catalog_router.get("/search")
def catalog_search_route(
    q: str = "",
    merchant_id: str = "",
    category: str = "skincare",
    max_price_cents: int | None = None,
    attrs: str | None = None,
    limit: int = 5,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    return catalog_search(
        q=q,
        merchant_id=merchant_id,
        category=category,
        max_price_cents=max_price_cents,
        attrs=attrs,
        limit=limit,
        include_unpublished=is_merchant(merchant_id, x_merchant_key),
    )


@catalog_router.get("/product/{sku}")
def catalog_product_route(
    sku: str,
    merchant_id: str,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> dict[str, Any]:
    """merchant_id is a required query parameter — there is no unscoped product read."""
    return catalog_product(
        sku, merchant_id, include_unpublished=is_merchant(merchant_id, x_merchant_key)
    )


@catalog_router.get("/template")
def catalog_template() -> Response:
    """The blank catalog workbook. Public: it contains no merchant data, only the shape."""
    return Response(
        content=build_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{TEMPLATE_FILENAME}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@catalog_router.get("/images/{image_id}")
def catalog_image(
    image_id: str,
    x_merchant_key: str | None = Header(default=None, alias="X-Merchant-Key"),
) -> Response:
    """Serve a product picture from a merchant's uploaded archive.

    A picture is public once it is on a live product in a published store - shoppers load it
    from an <img> tag and cannot send a key. Before that it is part of an unpublished
    catalog, so it is only served to the merchant who uploaded it, like their staged rows.
    """
    with connect() as connection:
        row = connection.execute(
            "SELECT i.image_id,i.merchant_id,i.content_type,i.image_bytes,m.status,"
            "EXISTS(SELECT 1 FROM products p WHERE p.merchant_id=i.merchant_id "
            "AND p.image_url=?) AS is_live "
            "FROM catalog_images i JOIN merchants m ON m.merchant_id=i.merchant_id "
            "WHERE i.image_id=?",
            (catalog_image_url(image_id), image_id),
        ).fetchone()
    if not row:
        raise api_error(404, "NO_IMAGE", "The product image was not found.")
    if not (row["status"] == "published" and row["is_live"]):
        assert_merchant(row["merchant_id"], x_merchant_key)
    return Response(
        content=row["image_bytes"],
        media_type=row["content_type"],
        headers={
            # The bytes are immutable and keyed by a random id, so they cache hard. Rendered
            # inline only, and never sniffed into something executable.
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class AddressCreate(BaseModel):
    recipient: str = Field(min_length=1, max_length=200)
    lines: list[str] = Field(min_length=1, max_length=4)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="SG", min_length=2, max_length=2)


@consumer_router.post("/register")
def register(body: RegisterRequest, request: Request) -> dict[str, Any]:
    email = body.email.strip().lower()
    # Registration answers "does this email have an account?", which is worth throttling even
    # though the answer has to stay truthful for the person typing it.
    check_rate_limit(
        f"register:{request.client.host if request.client else '-'}", SIGNUP_ATTEMPT_LIMIT
    )
    assert_usable_password(body.password)
    consumer_id = new_id("usr")
    with transaction() as connection:
        taken = connection.execute(
            "SELECT 1 FROM consumers WHERE email=?", (email,)
        ).fetchone()
        if taken:
            raise api_error(409, "EMAIL_TAKEN", "That email already has an account.")
        connection.execute(
            "INSERT INTO consumers(consumer_id,email,password_hash,display_name,created_at) "
            "VALUES (?,?,?,?,?)",
            (consumer_id, email, hash_password(body.password), body.display_name.strip(), utc_now()),
        )
        token = issue_consumer_token(connection, consumer_id)
    return {"consumer_id": consumer_id, "email": email,
            "display_name": body.display_name.strip(), "token": token}


@consumer_router.post("/login")
def login(body: LoginRequest, request: Request) -> dict[str, Any]:
    email = body.email.strip().lower()
    # Throttle per account and per client, so one attacker cannot grind a password and cannot
    # lock a victim out by grinding it for them from elsewhere.
    client_host = request.client.host if request.client else "-"
    buckets = (f"login:{email}", f"login-ip:{client_host}")
    check_rate_limit(buckets[0])
    check_rate_limit(buckets[1], SIGNUP_ATTEMPT_LIMIT)
    with transaction() as connection:
        row = connection.execute(
            "SELECT consumer_id,password_hash,display_name FROM consumers WHERE email=?", (email,)
        ).fetchone()
        # One message for "no such account" and "wrong password" — a distinct reply would
        # turn this endpoint into a way to test which emails are registered.
        if not row or not verify_password(body.password, row["password_hash"]):
            raise api_error(401, "BAD_CREDENTIALS", "That email and password do not match.")
        token = issue_consumer_token(connection, row["consumer_id"])
    for bucket in buckets:
        reset_rate_limit(bucket)
    return {"consumer_id": row["consumer_id"], "email": email,
            "display_name": row["display_name"], "token": token}


@consumer_router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    require_consumer(authorization)
    with transaction() as connection:
        # Only this device. Signing out on a laptop should not sign you out on a phone.
        revoke_consumer_token(connection, authorization)
    return {"status": "signed_out"}


@consumer_router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    consumer_id = require_consumer(authorization)
    with connect() as connection:
        row = connection.execute(
            "SELECT consumer_id,email,display_name FROM consumers WHERE consumer_id=?",
            (consumer_id,),
        ).fetchone()
    if not row:
        raise api_error(404, "NO_CONSUMER", "The account was not found.")
    return dict(row)


@consumer_router.get("/{consumer_id}/addresses")
def addresses(
    consumer_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    assert_consumer(consumer_id, authorization)
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


@consumer_router.post("/{consumer_id}/addresses")
def add_address(
    consumer_id: str,
    body: AddressCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """The only way a shopper gets a shipping address on file. Without this, a newly
    registered account (anyone but the pre-seeded demo shopper) has no address at all and
    checkout's ADDRESS_REQUIRED can never be satisfied — there was no endpoint to fix it."""
    assert_consumer(consumer_id, authorization)
    address_id = new_id("adr")
    with transaction() as connection:
        # The address a shopper just added is the one checkout will use next.
        connection.execute("UPDATE addresses SET is_default=0 WHERE consumer_id=?", (consumer_id,))
        connection.execute(
            "INSERT INTO addresses(address_id,consumer_id,recipient,lines_json,postal_code,"
            "country,is_default) VALUES (?,?,?,?,?,?,1)",
            (
                address_id,
                consumer_id,
                body.recipient.strip(),
                json.dumps([line.strip() for line in body.lines if line.strip()]),
                body.postal_code.strip(),
                body.country.strip().upper(),
            ),
        )
    return {
        "address_id": address_id,
        "recipient": body.recipient.strip(),
        "lines": body.lines,
        "postal_code": body.postal_code,
        "country": body.country.strip().upper(),
        "is_default": True,
    }


@consumer_router.put("/{consumer_id}/addresses/{address_id}/default")
def set_default_address(
    consumer_id: str,
    address_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    assert_consumer(consumer_id, authorization)
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
