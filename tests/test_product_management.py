"""The CRM can manage live products without crossing tenants or rewriting sales history."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_databases
from app.main import app
from seed.reset import MERCHANT_KEY_FILE, seed


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def merchant_key() -> str:
    return MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()


def keyed(key: str) -> dict[str, str]:
    return {"X-Merchant-Key": key}


def onboard(client: TestClient, name: str = "Other Skin") -> dict:
    response = client.post("/merchant/onboard", json={"name": name, "size": "sme"})
    assert response.status_code == 200, response.text
    return response.json()


def order_snapshot() -> list[tuple[str, str, str]]:
    with connect() as connection:
        return [
            (row["order_id"], row["evidence_json"], row["created_at"])
            for row in connection.execute(
                "SELECT order_id,evidence_json,created_at FROM orders ORDER BY order_id"
            ).fetchall()
        ]


def new_product(**overrides) -> dict:
    product = {
        "sku": "MYSA-NGT-900",
        "title": "Overnight Recovery Mask",
        "description": "A replenishing night mask for dry skin.",
        "price_cents": 4900,
        "stock": 12,
        "image_url": "https://images.example.test/night-mask.png",
        "product_type": "sleeping mask",
        "ingredients": ["Squalane", "Ceramides", "squalane"],
        "skin_types": ["Dry", "Sensitive"],
        "concerns": ["Dryness", "Barrier support"],
    }
    product.update(overrides)
    return product


def test_product_routes_require_the_right_merchants_key(
    client: TestClient, merchant_key: str
) -> None:
    rival = onboard(client)

    assert client.get("/merchant/m_mysa/products").status_code == 401
    forbidden = client.get(
        "/merchant/m_mysa/products", headers=keyed(rival["api_key"])
    )
    assert forbidden.status_code == 403

    own_catalog = client.get(
        f"/merchant/{rival['merchant_id']}/products", headers=keyed(rival["api_key"])
    )
    assert own_catalog.status_code == 200
    assert own_catalog.json()["products"] == []

    hidden_product = client.put(
        f"/merchant/{rival['merchant_id']}/products/MYSA-CLN-101",
        headers=keyed(rival["api_key"]),
        json={"title": "Stolen listing"},
    )
    assert hidden_product.status_code == 404
    unchanged = client.get(
        "/catalog/product/MYSA-CLN-101?merchant_id=m_mysa"
    ).json()
    assert unchanged["title"] == "Gentle Cloud Cleanser"

    # A valid key is still scoped to its owner when the URL names another tenant.
    forbidden_write = client.post(
        "/merchant/m_mysa/products",
        headers=keyed(rival["api_key"]),
        json=new_product(),
    )
    assert forbidden_write.status_code == 403
    assert client.get(
        "/merchant/m_mysa/products", headers=keyed(merchant_key)
    ).status_code == 200


def test_list_returns_the_entire_private_catalog(
    client: TestClient, merchant_key: str
) -> None:
    with connect() as connection:
        connection.execute("UPDATE products SET stock=0 WHERE sku='MYSA-SPF-050'")
        connection.commit()

    response = client.get("/merchant/m_mysa/products", headers=keyed(merchant_key))
    assert response.status_code == 200
    payload = response.json()
    assert payload["merchant_id"] == "m_mysa"
    assert payload["currency"] == "SGD"
    assert payload["total"] == 6
    sunscreen = next(product for product in payload["products"] if product["sku"] == "MYSA-SPF-050")
    assert sunscreen["stock"] == 0
    assert sunscreen["product_type"] == "sunscreen"


def test_create_is_live_immediately_and_does_not_change_orders(
    client: TestClient, merchant_key: str
) -> None:
    before_orders = order_snapshot()

    response = client.post(
        "/merchant/m_mysa/products", headers=keyed(merchant_key), json=new_product()
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created == {
        "sku": "MYSA-NGT-900",
        "title": "Overnight Recovery Mask",
        "description": "A replenishing night mask for dry skin.",
        "price_cents": 4900,
        "currency": "SGD",
        "stock": 12,
        "image_url": "https://images.example.test/night-mask.png",
        "product_type": "sleeping mask",
        "ingredients": ["Squalane", "Ceramides"],
        "skin_types": ["Dry", "Sensitive"],
        "concerns": ["Dryness", "Barrier support"],
        "created_at": created["created_at"],
        "updated_at": created["updated_at"],
    }

    private_catalog = client.get(
        "/merchant/m_mysa/products", headers=keyed(merchant_key)
    ).json()
    assert "MYSA-NGT-900" in {product["sku"] for product in private_catalog["products"]}

    storefront = client.get(
        "/catalog/search",
        params={"merchant_id": "m_mysa", "q": "overnight replenishing"},
    )
    assert storefront.status_code == 200
    assert [product["sku"] for product in storefront.json()["results"]] == ["MYSA-NGT-900"]
    detail = client.get(
        "/catalog/product/MYSA-NGT-900", params={"merchant_id": "m_mysa"}
    ).json()
    assert detail["price_cents"] == 4900
    assert detail["attributes"]["ingredients"] == ["Squalane", "Ceramides"]
    assert order_snapshot() == before_orders


def test_update_merges_attributes_and_preserves_purchase_history(
    client: TestClient, merchant_key: str
) -> None:
    before_orders = order_snapshot()
    with connect() as connection:
        before_attributes = json.loads(
            connection.execute(
                "SELECT attributes_json FROM products WHERE sku='MYSA-SRM-010'"
            ).fetchone()["attributes_json"]
        )

    response = client.put(
        "/merchant/m_mysa/products/MYSA-SRM-010",
        headers=keyed(merchant_key),
        json={
            "title": "Niacinamide Balance Serum",
            "description": "Updated merchant description.",
            "price_cents": 3700,
            "stock": 7,
            "image_url": "/products/niacinamide-balance.png",
            "product_type": "balancing serum",
            "ingredients": ["Niacinamide", "Zinc PCA"],
            "skin_types": ["Oily", "Combination"],
            "concerns": ["Uneven tone", "Oiliness"],
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["title"] == "Niacinamide Balance Serum"
    assert updated["price_cents"] == 3700
    assert updated["stock"] == 7
    assert updated["product_type"] == "balancing serum"

    detail = client.get(
        "/catalog/product/MYSA-SRM-010", params={"merchant_id": "m_mysa"}
    ).json()
    assert detail["title"] == "Niacinamide Balance Serum"
    assert detail["price_cents"] == 3700
    assert detail["attributes"]["concerns"] == ["Uneven tone", "Oiliness"]
    # Fields outside the CRM editor survive the merge instead of being replaced by a small form.
    for preserved in ("excludes", "fragrance_free", "texture", "size_ml", "routine_step"):
        assert detail["attributes"][preserved] == before_attributes[preserved]
    assert order_snapshot() == before_orders

    search = client.get(
        "/catalog/search",
        params={"merchant_id": "m_mysa", "q": "balance uneven"},
    ).json()
    assert [product["sku"] for product in search["results"]] == ["MYSA-SRM-010"]


def test_partial_updates_clear_optional_fields_and_remove_zero_stock_from_search(
    client: TestClient, merchant_key: str
) -> None:
    client.post("/merchant/m_mysa/products", headers=keyed(merchant_key), json=new_product())
    response = client.put(
        "/merchant/m_mysa/products/MYSA-NGT-900",
        headers=keyed(merchant_key),
        json={
            "stock": 0,
            "image_url": None,
            "product_type": None,
            "ingredients": None,
            "skin_types": None,
            "concerns": None,
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Overnight Recovery Mask"
    assert updated["price_cents"] == 4900
    assert updated["stock"] == 0
    assert updated["image_url"] is None
    assert updated["product_type"] is None
    assert updated["ingredients"] == []
    assert updated["skin_types"] == []
    assert updated["concerns"] == []

    search = client.get(
        "/catalog/search", params={"merchant_id": "m_mysa", "q": "overnight"}
    )
    assert search.json()["results"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"sku": "replacement"},
        {},
        {"title": None},
        {"title": "   "},
        {"price_cents": -1},
        {"price_cents": "1200"},
        {"stock": -1},
        {"image_url": "javascript:alert(1)"},
        {"ingredients": [""]},
    ],
)
def test_update_rejects_invalid_or_immutable_fields(
    client: TestClient, merchant_key: str, changes: dict
) -> None:
    response = client.put(
        "/merchant/m_mysa/products/MYSA-CLN-101",
        headers=keyed(merchant_key),
        json=changes,
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "product",
    [
        new_product(sku="bad sku"),
        new_product(title="   "),
        new_product(price_cents=-1),
        new_product(price_cents="4900"),
        new_product(stock=-1),
        new_product(image_url="http://merchant.example.test/image.png"),
        new_product(image_url="http://localhost.evil/image.png"),
        new_product(concerns=[""]),
    ],
)
def test_create_validates_product_facts(
    client: TestClient, merchant_key: str, product: dict
) -> None:
    response = client.post(
        "/merchant/m_mysa/products", headers=keyed(merchant_key), json=product
    )
    assert response.status_code == 422


def test_sku_uniqueness_is_enforced_without_disclosing_the_owner(
    client: TestClient, merchant_key: str
) -> None:
    duplicate = client.post(
        "/merchant/m_mysa/products",
        headers=keyed(merchant_key),
        json=new_product(sku="MYSA-CLN-101"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"]["code"] == "SKU_EXISTS"

    rival = onboard(client)
    cross_tenant = client.post(
        f"/merchant/{rival['merchant_id']}/products",
        headers=keyed(rival["api_key"]),
        json=new_product(sku="MYSA-CLN-101"),
    )
    assert cross_tenant.status_code == 409
    error = cross_tenant.json()["detail"]["error"]
    assert error["code"] == "SKU_EXISTS"
    assert "m_mysa" not in json.dumps(error).lower()
