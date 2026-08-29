"""Many merchants, one deployment.

The isolation suite proves merchant A cannot reach merchant B's data. This proves the other
half: that a second merchant can actually *use* the product - sign up, be recognised by their
own key, and drive their own store - without the app assuming which merchant it is serving.
"""

from __future__ import annotations

import dataclasses
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import init_databases
from app.main import app
from merchant import router as merchant_router
from seed.reset import MERCHANT_KEY_FILE, seed


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_key() -> str:
    return MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()


def onboard(client: TestClient, name: str) -> dict:
    created = client.post("/merchant/onboard", json={"name": name, "size": "sme"})
    assert created.status_code == 200, created.text
    return created.json()


def keyed(key: str) -> TestClient:
    api = TestClient(app)
    api.headers["X-Merchant-Key"] = key
    return api


def catalog_bytes(sku: str, title: str) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Products"
    sheet.append(["sku", "title", "price", "stock", "ingredients", "product_type", "description"])
    sheet.append([sku, title, 25.00, 5, "aqua, glycerin", "serum", "A light serum for dry skin"])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_a_key_identifies_its_own_store(client: TestClient, seeded_key: str) -> None:
    first = onboard(client, "Aurora Skin")
    second = onboard(client, "Bloom Botanicals")

    assert keyed(first["api_key"]).get("/merchant/me").json()["merchant_id"] == first["merchant_id"]
    assert keyed(second["api_key"]).get("/merchant/me").json()["merchant_id"] == second["merchant_id"]
    assert keyed(seeded_key).get("/merchant/me").json()["merchant_id"] == "m_mysa"

    # Names come back too, so the admin page can say which store it opened.
    assert keyed(first["api_key"]).get("/merchant/me").json()["name"] == "Aurora Skin"


def test_brand_accent_is_validated_and_returned_to_the_storefront(client: TestClient) -> None:
    merchant = onboard(client, "Aurora Skin")
    api = keyed(merchant["api_key"])

    invalid = api.put(
        f"/merchant/{merchant['merchant_id']}/config",
        json={"accent_color": "friendly blue"},
    )
    assert invalid.status_code == 422

    updated = api.put(
        f"/merchant/{merchant['merchant_id']}/config",
        json={"accent_color": "#255B78"},
    )
    assert updated.status_code == 200
    assert updated.json()["accent_color"] == "#255B78"

    session = client.post(
        "/agent/session",
        json={"merchant_id": merchant["merchant_id"], "category": "skincare"},
    )
    assert session.status_code == 200
    assert session.json()["merchant"] == {
        "name": "Aurora Skin",
        "accent_color": "#255B78",
        "logo_url": None,
    }


def test_me_refuses_a_missing_or_wrong_key(client: TestClient) -> None:
    onboard(client, "Aurora Skin")
    assert TestClient(app).get("/merchant/me").status_code == 401
    assert keyed("mk_not-a-real-key").get("/merchant/me").status_code == 401


def test_each_merchant_drives_only_their_own_catalog(client: TestClient, seeded_key: str) -> None:
    aurora = onboard(client, "Aurora Skin")
    bloom = onboard(client, "Bloom Botanicals")

    for merchant, sku in ((aurora, "AUR-1"), (bloom, "BLM-1")):
        api = keyed(merchant["api_key"])
        upload = api.post(
            f"/merchant/{merchant['merchant_id']}/catalog/uploads",
            files={"file": ("catalog.xlsx", catalog_bytes(sku, f"{sku} Serum"), "application/vnd.ms-excel")},
        ).json()
        plan = upload["approval"]["modes"]["replace"]
        approved = api.post(
            f"/merchant/{merchant['merchant_id']}/catalog/uploads/{upload['upload_id']}/approve",
            json={
                "approval_token": plan["approval_token"],
                "reviewed_row_count": upload["approval"]["reviewed_row_count_required"],
                "mode": "replace",
            },
        )
        assert approved.status_code == 200, approved.text
        api.put(f"/merchant/{merchant['merchant_id']}/config", json={"status": "published"})

    aurora_skus = [
        p["sku"]
        for p in client.get(f"/catalog/search?merchant_id={aurora['merchant_id']}").json()["results"]
    ]
    bloom_skus = [
        p["sku"]
        for p in client.get(f"/catalog/search?merchant_id={bloom['merchant_id']}").json()["results"]
    ]
    assert aurora_skus == ["AUR-1"]
    assert bloom_skus == ["BLM-1"]

    # And the seeded demo store is untouched by either of them.
    mysa = client.get("/catalog/search?merchant_id=m_mysa").json()["results"]
    assert mysa and "AUR-1" not in [p["sku"] for p in mysa]


def test_a_catalog_search_must_name_its_merchant(client: TestClient) -> None:
    """Without this, an unscoped search silently answered for whichever store was default."""
    response = client.get("/catalog/search")
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "VALIDATION"


def test_a_shopping_session_must_name_its_merchant(client: TestClient) -> None:
    response = client.post("/agent/session", json={"category": "skincare"})
    assert response.status_code == 422


def test_each_new_store_gets_its_own_storefront_and_snippet(client: TestClient) -> None:
    aurora = onboard(client, "Aurora Skin")
    bloom = onboard(client, "Bloom Botanicals")

    assert aurora["merchant_id"] != bloom["merchant_id"]
    assert aurora["merchant_id"] in aurora["hosted_url"]
    assert aurora["merchant_id"] in aurora["embed_snippet"]
    assert bloom["merchant_id"] in bloom["hosted_url"]
    assert aurora["merchant_id"] not in bloom["embed_snippet"]


def test_a_new_store_starts_unpublished_and_private(client: TestClient) -> None:
    aurora = onboard(client, "Aurora Skin")
    api = keyed(aurora["api_key"])

    assert api.get("/merchant/me").json()["status"] == "draft"
    # Nobody can browse a store that has not opened, even by naming it directly.
    assert client.get(f"/catalog/search?merchant_id={aurora['merchant_id']}").json()["results"] == []


def test_the_api_key_is_returned_once_and_never_again(client: TestClient) -> None:
    aurora = onboard(client, "Aurora Skin")
    config = keyed(aurora["api_key"]).get("/merchant/me").json()
    assert "api_key" not in config
    assert aurora["api_key"] not in str(config)


# --- one-click demo sign-in ---------------------------------------------------------------


def test_the_demo_store_can_be_opened_without_finding_a_key(client: TestClient) -> None:
    """The admin page's front door. It hands out one key, for one store, on purpose."""
    offered = client.get("/merchant/demo-store")
    assert offered.status_code == 200, offered.text
    payload = offered.json()
    assert payload["available"] is True
    assert payload["merchant_id"] == "m_mysa"
    assert payload["name"] == "Mysa Skin"

    # The key it hands out actually opens that store, and only that store.
    opened = keyed(payload["api_key"]).get("/merchant/me")
    assert opened.status_code == 200
    assert opened.json()["merchant_id"] == "m_mysa"


def test_the_demo_key_is_not_served_when_demo_login_is_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One environment variable takes the convenience away for a real deployment."""
    monkeypatch.setattr(
        merchant_router, "settings", dataclasses.replace(merchant_router.settings, demo_login_enabled=False)
    )
    payload = client.get("/merchant/demo-store").json()
    assert payload == {"available": False, "merchant_id": None, "name": None, "api_key": None}


def test_the_demo_route_never_serves_another_merchants_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It is pinned to the seeded store: pointing it at a merchant whose key is not the one
    on file yields nothing rather than that merchant's credentials."""
    other = onboard(client, "Aurora Skin")
    monkeypatch.setattr(
        merchant_router,
        "settings",
        dataclasses.replace(merchant_router.settings, demo_merchant_id=other["merchant_id"]),
    )
    payload = client.get("/merchant/demo-store").json()
    assert payload["available"] is False
    assert payload["api_key"] is None


def test_a_missing_key_file_is_an_unavailable_demo_not_an_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A host that was never seeded has nothing to give away, and says so calmly."""
    monkeypatch.setattr(merchant_router, "DEMO_KEY_FILE", tmp_path / "absent.txt")
    response = client.get("/merchant/demo-store")
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_a_storefronts_public_face_is_readable_without_a_key(client: TestClient) -> None:
    """The embeddable widget reads this to wear the merchant's brand, from any origin."""
    profile = client.get("/merchant/m_mysa/profile")
    assert profile.status_code == 200, profile.text
    assert profile.json() == {
        "merchant_id": "m_mysa",
        "name": "Mysa Skin",
        "accent_color": "#6f8066",
        "logo_url": None,
        "status": "published",
    }
    # Brand fields only — nothing that would let a stranger act as the merchant.
    assert set(profile.json()) == {"merchant_id", "name", "accent_color", "logo_url", "status"}

    assert client.get("/merchant/m_nonexistent/profile").status_code == 404


def test_each_merchants_profile_is_their_own(client: TestClient) -> None:
    first = onboard(client, "Aurora Skin")
    api = keyed(first["api_key"])
    api.put(f"/merchant/{first['merchant_id']}/config", json={"accent_color": "#255B78"})

    profile = client.get(f"/merchant/{first['merchant_id']}/profile").json()
    assert profile["name"] == "Aurora Skin"
    assert profile["accent_color"] == "#255B78"
    assert profile["merchant_id"] != "m_mysa"
