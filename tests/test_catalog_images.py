"""Product images, AI-assisted column mapping, and the merchant-facing error summary.

The suite runs in DEMO_MODE, so every model call is skipped and the deterministic path is
what executes end to end. The model's own contribution is tested where it actually matters:
the validators that decide whether its answer is allowed to touch anything.
"""

from __future__ import annotations

import asyncio
import io
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import connect, init_databases
from app.main import app
from merchant import catalog_diagnostics, catalog_images, catalog_mapping
from merchant.catalog_diagnostics import (
    DiagnosticsValidationError,
    build_groups,
    classify_issue,
    deterministic_headline,
    validate_diagnostics_payload,
)
from merchant.catalog_images import (
    ImageArchiveError,
    ImageMatchValidationError,
    ImageTarget,
    extract_image_archive,
    match_images,
    normalize_name,
    validate_match_payload,
)
from merchant.catalog_mapping import (
    MappingValidationError,
    detect_mappings,
    validate_mapping_payload,
)
from merchant.catalog_pipeline import SourceRow, _descriptive_fields
from seed.reset import MERCHANT_KEY_FILE, seed

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture()
def client() -> TestClient:
    init_databases(reset=True)
    seed()
    with TestClient(app) as test_client:
        test_client.headers["X-Merchant-Key"] = MERCHANT_KEY_FILE.read_text(
            encoding="utf-8"
        ).strip()
        yield test_client


def make_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def workbook_bytes(rows: list[list[object]], headers: list[str]) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Products"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


CATALOG_HEADERS = ["SKU", "Name", "Price", "Ingredients", "Stock", "Product Type", "Description"]
CATALOG_ROWS = [
    ["MYSA-01", "Gentle Cloud Cleanser", 29.90, "glycerin, panthenol", 10, "face wash",
     "A gentle hydrating face wash for dry skin"],
    ["MYSA-02", "Barrier Milk Moisturiser", 42.00, "ceramide, squalane", 6, "moisturiser",
     "A soothing cream for barrier support"],
    ["MYSA-03", "Calm Gel Serum", 35.00, "niacinamide", 4, "serum",
     "A light serum for oily skin and redness"],
]


def stage_catalog(client: TestClient) -> dict:
    response = client.post(
        "/merchant/m_mysa/catalog/uploads",
        files={
            "file": (
                "catalog.xlsx",
                workbook_bytes(CATALOG_ROWS, CATALOG_HEADERS),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- images from a ZIP -------------------------------------------------------------------


def test_zip_images_match_rows_by_sku_and_by_product_name(client: TestClient) -> None:
    upload = stage_catalog(client)
    assert upload["summary"]["ready"] == 3

    archive = make_zip(
        {
            "MYSA-01.png": PNG,  # matches the SKU exactly
            "barrier milk moisturiser.png": PNG,  # matches the product name exactly
            "Calm-Gel-Serum.png": PNG,  # matches the name once separators are folded
            "not-a-product.png": PNG,  # matches nothing and must stay unmatched
        }
    )
    response = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", archive, "application/zip")},
    )
    assert response.status_code == 200, response.text
    preview = response.json()

    report = preview["images"]
    assert report["image_count"] == 4
    assert report["matched_count"] == 3
    assert report["unmatched_images"] == ["not-a-product.png"]
    assert report["match_source"] == "deterministic"

    methods = {
        image["entry_name"]: image.get("method") for image in report["images"] if image["matched"]
    }
    assert methods == {
        "MYSA-01.png": "exact_sku",
        "barrier milk moisturiser.png": "exact_name",
        "Calm-Gel-Serum.png": "exact_name",
    }

    by_sku = {row["canonical"]["sku"]: row["canonical"] for row in preview["products"]}
    assert by_sku["MYSA-01"]["image_url"].startswith("/api/catalog/images/img_")
    assert by_sku["MYSA-01"]["attributes"]["catalog_cleaning"]["image_source"] == "image_archive"
    assert by_sku["MYSA-01"]["attributes"]["catalog_cleaning"]["image_match"]["method"] == "exact_sku"


def test_attached_images_publish_and_then_serve_to_shoppers(client: TestClient) -> None:
    upload = stage_catalog(client)
    with_images = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    ).json()

    image_url = next(
        row["canonical"]["image_url"]
        for row in with_images["products"]
        if row["canonical"] and row["canonical"]["sku"] == "MYSA-01"
    )
    path = image_url.removeprefix("/api")

    # Before publication the picture belongs to an unpublished catalog: merchant-only.
    anonymous = TestClient(app)
    assert anonymous.get(path).status_code == 401
    assert client.get(path).status_code == 200

    plan = with_images["approval"]["modes"]["replace"]
    approved = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/approve",
        json={
            "approval_token": plan["approval_token"],
            "reviewed_row_count": with_images["approval"]["reviewed_row_count_required"],
            "mode": "replace",
        },
    )
    assert approved.status_code == 200, approved.text
    client.put("/merchant/m_mysa/config", json={"status": "published"})

    live = anonymous.get(path)
    assert live.status_code == 200
    assert live.headers["content-type"] == "image/png"
    assert live.headers["x-content-type-options"] == "nosniff"
    assert live.content == PNG

    product = client.get("/catalog/product/MYSA-01?merchant_id=m_mysa").json()
    assert product["image_url"] == image_url


def test_attaching_images_invalidates_the_earlier_approval_token(client: TestClient) -> None:
    upload = stage_catalog(client)
    stale_token = upload["approval"]["modes"]["replace"]["approval_token"]
    with_images = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    ).json()
    assert with_images["approval"]["modes"]["replace"]["approval_token"] != stale_token

    replay = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/approve",
        json={
            "approval_token": stale_token,
            "reviewed_row_count": with_images["approval"]["reviewed_row_count_required"],
            "mode": "replace",
        },
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["error"]["code"] == "STALE_CATALOG_PREVIEW"


def test_images_cannot_be_attached_to_another_merchants_upload(client: TestClient) -> None:
    upload = stage_catalog(client)
    other = client.post(
        "/merchant/onboard", json={"name": "Rival Skin", "size": "sme"}, headers={}
    ).json()
    intruder = TestClient(app)
    intruder.headers["X-Merchant-Key"] = other["api_key"]
    response = intruder.post(
        f"/merchant/{other['merchant_id']}/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "NO_CATALOG_UPLOAD"


def test_images_are_refused_once_the_upload_is_published(client: TestClient) -> None:
    upload = stage_catalog(client)
    plan = upload["approval"]["modes"]["replace"]
    client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/approve",
        json={
            "approval_token": plan["approval_token"],
            "reviewed_row_count": upload["approval"]["reviewed_row_count_required"],
            "mode": "replace",
        },
    )
    late = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    )
    assert late.status_code == 409
    assert late.json()["detail"]["error"]["code"] == "CATALOG_NOT_READY"


def test_a_second_archive_replaces_the_first(client: TestClient) -> None:
    upload = stage_catalog(client)
    client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("a.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    )
    second = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("b.zip", make_zip({"MYSA-02.png": PNG}), "application/zip")},
    ).json()

    assert second["images"]["image_count"] == 1
    with connect() as connection:
        stored = connection.execute(
            "SELECT entry_name FROM catalog_images WHERE upload_id=?", (upload["upload_id"],)
        ).fetchall()
    assert [row["entry_name"] for row in stored] == ["MYSA-02.png"]


def test_a_zip_never_overwrites_an_image_url_from_the_workbook(client: TestClient) -> None:
    headers = [*CATALOG_HEADERS, "Image URL"]
    rows = [
        [*CATALOG_ROWS[0], "https://cdn.example.com/cloud.png"],
        [*CATALOG_ROWS[1], ""],
    ]
    upload = client.post(
        "/merchant/m_mysa/catalog/uploads",
        files={"file": ("catalog.xlsx", workbook_bytes(rows, headers), "application/vnd.ms-excel")},
    ).json()

    archive = make_zip({"MYSA-01.png": PNG, "MYSA-02.png": PNG})
    preview = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", archive, "application/zip")},
    ).json()

    by_sku = {row["canonical"]["sku"]: row["canonical"] for row in preview["products"]}
    assert by_sku["MYSA-01"]["image_url"] == "https://cdn.example.com/cloud.png"
    assert by_sku["MYSA-02"]["image_url"].startswith("/api/catalog/images/img_")
    assert preview["images"]["kept_workbook_images"] == 1
    assert preview["images"]["unmatched_images"] == ["MYSA-01.png"]


def test_a_corrected_zip_replaces_the_previous_archive_binding(client: TestClient) -> None:
    upload = stage_catalog(client)
    first = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("a.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    ).json()
    original = next(
        row["canonical"]["image_url"]
        for row in first["products"]
        if row["canonical"]["sku"] == "MYSA-01"
    )

    second = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("b.zip", make_zip({"MYSA-01.png": PNG}), "application/zip")},
    ).json()
    by_sku = {row["canonical"]["sku"]: row["canonical"] for row in second["products"]}
    assert by_sku["MYSA-01"]["image_url"] != original
    assert by_sku["MYSA-02"]["image_url"] is None
    assert second["images"]["kept_workbook_images"] == 0

    # The replaced file is gone, not just unreferenced.
    assert TestClient(app).get(original.removeprefix("/api")).status_code == 404


# --- archive hardening -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entries", "kept", "reason_fragment"),
    [
        ({"ok.png": PNG, "../escape.png": PNG}, ["ok.png"], "unsafe"),
        ({"ok.png": PNG, "notes.txt": b"hello"}, ["ok.png"], "extension"),
        ({"ok.png": PNG, "fake.png": b"MZ this is an executable"}, ["ok.png"], "not a known image"),
        ({"ok.png": PNG, "__MACOSX/ok.png": PNG}, ["ok.png"], "unsafe"),
        ({"ok.png": PNG, "OK.PNG": PNG}, ["ok.png"], "duplicate product name"),
    ],
)
def test_archive_refuses_unsafe_entries_and_says_why(
    entries: dict[str, bytes], kept: list[str], reason_fragment: str
) -> None:
    images, skipped = extract_image_archive(make_zip(entries), "images.zip")
    assert [image.entry_name for image in images] == kept
    assert any(reason_fragment in item["reason"] for item in skipped), skipped


def test_archive_rejects_non_zip_and_empty_archives() -> None:
    with pytest.raises(ImageArchiveError, match="valid ZIP"):
        extract_image_archive(b"not a zip at all", "images.zip")
    with pytest.raises(ImageArchiveError, match=r"\.zip archive"):
        extract_image_archive(make_zip({"ok.png": PNG}), "images.rar")
    with pytest.raises(ImageArchiveError, match="no usable image"):
        extract_image_archive(make_zip({"notes.txt": b"hello"}), "images.zip")


def test_oversized_archive_is_refused_by_the_route(client: TestClient) -> None:
    upload = stage_catalog(client)
    response = client.post(
        f"/merchant/m_mysa/catalog/uploads/{upload['upload_id']}/images",
        files={"file": ("images.zip", b"x" * (25 * 1024 * 1024 + 1), "application/zip")},
    )
    assert response.status_code == 413


# --- image_url from the workbook ---------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://cdn.example.com/a.png", "https://cdn.example.com/a.png"),
        ("/products/a.png", "/products/a.png"),
        ("", None),
    ],
)
def test_workbook_image_urls_that_are_safe_to_render(
    client: TestClient, value: str, expected: str | None
) -> None:
    headers = [*CATALOG_HEADERS, "Image URL"]
    rows = [[*CATALOG_ROWS[0], value]]
    upload = client.post(
        "/merchant/m_mysa/catalog/uploads",
        files={"file": ("catalog.xlsx", workbook_bytes(rows, headers), "application/vnd.ms-excel")},
    ).json()
    assert upload["summary"]["ready"] == 1
    assert upload["products"][0]["canonical"]["image_url"] == expected


@pytest.mark.parametrize(
    "value",
    ["javascript:alert(1)", "data:image/png;base64,AAAA", "//evil.example/a.png", "ftp://h/a.png"],
)
def test_workbook_image_urls_that_cannot_be_rendered_are_held(
    client: TestClient, value: str
) -> None:
    headers = [*CATALOG_HEADERS, "Image URL"]
    upload = client.post(
        "/merchant/m_mysa/catalog/uploads",
        files={
            "file": (
                "catalog.xlsx",
                workbook_bytes([[*CATALOG_ROWS[0], value]], headers),
                "application/vnd.ms-excel",
            )
        },
    ).json()
    assert upload["summary"]["rejected"] == 1
    assert "image_url must be an https:// link" in upload["errors"][0]["reason"]


# --- matching internals ------------------------------------------------------------------


def test_fuzzy_matching_needs_a_clear_winner() -> None:
    targets = [
        ImageTarget("row_000002", 2, "A-1", "Calm Gel Serum"),
        ImageTarget("row_000003", 3, "A-2", "Calm Gel Cream"),
    ]
    images, _ = extract_image_archive(make_zip({"calm gel serum.png": PNG}), "i.zip")
    matched, _ = asyncio.run(match_images(images, targets))
    assert matched["calm gel serum.png"]["source_record_id"] == "row_000002"

    # A name equally close to two products is left for the merchant, not guessed.
    ambiguous, _ = extract_image_archive(make_zip({"calm gel.png": PNG}), "i.zip")
    assert asyncio.run(match_images(ambiguous, targets))[0] == {}


def test_normalize_name_folds_separators_and_case() -> None:
    assert normalize_name("Calm-Gel_Serum  30ml.PNG") == "calm gel serum 30ml png"
    assert normalize_name("MYSA--01") == "mysa 01"


def test_model_image_matches_must_name_real_ids_and_stay_one_to_one() -> None:
    ids, records = {"a.png", "b.png"}, {"row_000002", "row_000003"}
    good = {
        "schema_version": "catalog-image-match.v1",
        "matches": [
            {"image_id": "a.png", "source_record_id": "row_000002", "confidence": 0.9, "reason": "same name"},
            {"image_id": "b.png", "source_record_id": "row_000003", "confidence": 0.4, "reason": "unsure"},
        ],
    }
    accepted = validate_match_payload(good, image_ids=ids, record_ids=records)
    assert [item["image_id"] for item in accepted] == ["a.png"]  # 0.4 is below the floor

    for payload, message in [
        ({"schema_version": "catalog-image-match.v1", "matches": [
            {"image_id": "ghost.png", "source_record_id": "row_000002", "confidence": 1, "reason": "x"}
        ]}, "unknown image"),
        ({"schema_version": "catalog-image-match.v1", "matches": [
            {"image_id": "a.png", "source_record_id": "row_999999", "confidence": 1, "reason": "x"}
        ]}, "unknown product row"),
        ({"schema_version": "catalog-image-match.v1", "matches": [
            {"image_id": "a.png", "source_record_id": "row_000002", "confidence": 1, "reason": "x"},
            {"image_id": "a.png", "source_record_id": "row_000003", "confidence": 1, "reason": "x"},
        ]}, "matched twice"),
        ({"schema_version": "wrong.v9", "matches": []}, "schema_version"),
    ]:
        with pytest.raises(ImageMatchValidationError, match=message):
            validate_match_payload(payload, image_ids=ids, record_ids=records)


# --- AI-assisted column mapping ----------------------------------------------------------


def rows_with(headers: list[str]) -> list[SourceRow]:
    return [
        SourceRow(
            source_record_id="row_000002",
            row_number=2,
            sheet_name="Products",
            values={header: f"value for {header}" for header in headers},
        )
    ]


def test_alias_ties_are_recorded_rather_than_raised() -> None:
    candidates = detect_mappings(rows_with(["SKU", "Price", "Unit Price", "Stock"]))
    assert candidates.resolved["sku"] == "SKU"
    assert candidates.conflicts["price"] == ["Price", "Unit Price"]


def test_a_tie_the_model_cannot_break_still_stops_the_upload(client: TestClient) -> None:
    headers = ["SKU", "Name", "Price", "Unit Price", "Ingredients", "Stock"]
    response = client.post(
        "/merchant/m_mysa/catalog/uploads",
        files={
            "file": (
                "catalog.xlsx",
                workbook_bytes([["A-1", "Serum", 10, 10, "niacinamide", 5]], headers),
                "application/vnd.ms-excel",
            )
        },
    )
    assert response.status_code == 400
    error = response.json()["detail"]["error"]
    assert error["code"] == "BAD_CATALOG"
    assert error["details"]["unresolved_fields"][0]["candidate_columns"] == ["Price", "Unit Price"]


def test_model_mappings_must_name_a_real_column_and_a_free_field() -> None:
    candidates = detect_mappings(rows_with(["SKU", "Price", "Unit Price", "What it helps with"]))
    askable = ["Price", "Unit Price", "What it helps with"]

    accepted = validate_mapping_payload(
        {
            "schema_version": "catalog-mapping.v1",
            "assignments": [
                {"column": "Unit Price", "target": "price", "confidence": 0.9, "reason": "per-unit selling price"},
                {"column": "Price", "target": "ignore", "confidence": 0.9, "reason": "list price"},
                {"column": "What it helps with", "target": "concerns", "confidence": 0.8, "reason": "skin concerns"},
            ],
        },
        candidates=candidates,
        askable=askable,
    )
    assert [item["target"] for item in accepted] == ["price", "concerns"]

    for payload, message in [
        ([{"column": "Ghost", "target": "price", "confidence": 1, "reason": "x"}], "unknown column"),
        ([{"column": "What it helps with", "target": "price", "confidence": 1, "reason": "x"}],
         "candidate columns"),
        ([{"column": "Price", "target": "sku", "confidence": 1, "reason": "x"}], "already mapped"),
        ([{"column": "Price", "target": "price", "confidence": 1, "reason": "x"},
          {"column": "Price", "target": "stock", "confidence": 1, "reason": "x"}], "assigned twice"),
    ]:
        with pytest.raises(MappingValidationError, match=message):
            validate_mapping_payload(
                {"schema_version": "catalog-mapping.v1", "assignments": payload},
                candidates=candidates,
                askable=askable,
            )


def test_low_confidence_mappings_are_discarded() -> None:
    candidates = detect_mappings(rows_with(["SKU", "Mystery column"]))
    accepted = validate_mapping_payload(
        {
            "schema_version": "catalog-mapping.v1",
            "assignments": [
                {"column": "Mystery column", "target": "benefits", "confidence": 0.3, "reason": "maybe"}
            ],
        },
        candidates=candidates,
        askable=["Mystery column"],
    )
    assert accepted == []


def test_a_renamed_column_reaches_the_classifier_but_a_locked_fact_never_does() -> None:
    row = SourceRow(
        source_record_id="row_000002",
        row_number=2,
        sheet_name=None,
        values={
            "SKU": "A-1",
            "Name": "Calm Serum",
            "Price": "30.00",
            "What it helps with": "redness",
            "Cost price": "8.00",
        },
    )
    fields = _descriptive_fields(
        row,
        {"sku": "SKU", "title": "Name", "price": "Price"},
        {"What it helps with": "concerns", "Cost price": "claims"},
    )
    assert fields == {"title": "Calm Serum", "concerns": "redness", "claims": "8.00"}

    # An oddly named column that was mapped correctly is still read as evidence. Without
    # this the classifier saw nothing for a header the allow-list does not happen to spell.
    odd = SourceRow(
        source_record_id="row_000002",
        row_number=2,
        sheet_name=None,
        values={"Article No.": "A-1", "What we call it": "Calm Serum", "Full INCI": "niacinamide",
                "RRP (S$)": "30.00", "Landed cost": "8.00"},
    )
    assert _descriptive_fields(
        odd,
        {"sku": "Article No.", "title": "What we call it", "ingredients": "Full INCI",
         "price": "RRP (S$)"},
    ) == {"title": "Calm Serum", "ingredients": "niacinamide"}

    # A column the mapping step assigned to a locked fact is excluded whatever it is renamed to.
    guarded = _descriptive_fields(
        row, {"sku": "SKU", "title": "Name", "price": "Cost price"}, {"Cost price": "claims"}
    )
    assert "claims" not in guarded


def live_model(monkeypatch, module) -> None:
    """Pretend this process has a usable model, without one being reachable."""
    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(demo_mode=False, openai_api_key="test", openai_model="test-model"),
    )


def test_the_model_fills_mapping_gaps_that_aliases_left(monkeypatch) -> None:
    live_model(monkeypatch, catalog_mapping)
    candidates = detect_mappings(rows_with(["SKU", "Price", "Unit Price", "What it helps with"]))

    async def fake_ask(_candidates, askable, missing):
        assert set(askable) == {"Price", "Unit Price", "What it helps with"}
        assert "title" in missing and "price" not in missing  # price is ambiguous, not missing
        return [
            {"column": "Unit Price", "target": "price", "confidence": 0.92, "reason": "unit price"},
            {"column": "What it helps with", "target": "concerns", "confidence": 0.8, "reason": "concerns"},
        ]

    monkeypatch.setattr(catalog_mapping, "_ask_model", fake_ask)
    resolution = asyncio.run(catalog_mapping.resolve_mappings(candidates))

    assert resolution.mappings == {"sku": "SKU", "price": "Unit Price"}
    assert resolution.descriptive_aliases == {"What it helps with": "concerns"}
    assert resolution.unresolved == []
    assert resolution.source == "hybrid_model_with_alias_guard"
    assert resolution.report()["model_assisted"] is True
    methods = {decision["target"]: decision["method"] for decision in resolution.decisions}
    assert methods == {"sku": "exact_alias", "price": "model", "concerns": "model_descriptive"}


def test_a_mapping_model_failure_falls_back_to_aliases_alone(monkeypatch) -> None:
    live_model(monkeypatch, catalog_mapping)

    async def explode(*_args):
        raise RuntimeError("synthetic mapping failure")

    monkeypatch.setattr(catalog_mapping, "_ask_model", explode)
    candidates = detect_mappings(rows_with(["SKU", "Price", "Unit Price"]))
    resolution = asyncio.run(catalog_mapping.resolve_mappings(candidates))

    assert resolution.source == "deterministic_failover"
    assert resolution.mappings == {"sku": "SKU"}
    assert resolution.unresolved[0]["target"] == "price"


def test_the_model_only_sees_images_and_rows_the_deterministic_pass_could_not_place(
    monkeypatch,
) -> None:
    live_model(monkeypatch, catalog_images)
    targets = [
        ImageTarget("row_000002", 2, "A-1", "Calm Gel Serum"),
        ImageTarget("row_000003", 3, "A-2", "Barrier Milk"),
    ]
    images, _ = extract_image_archive(
        make_zip({"A-1.png": PNG, "barrier-milk-50ml-new.png": PNG}), "i.zip"
    )

    async def fake_ask(unmatched_images, unmatched_targets):
        assert [image.entry_name for image in unmatched_images] == ["barrier-milk-50ml-new.png"]
        assert [target.sku for target in unmatched_targets] == ["A-2"]
        return [
            {
                "image_id": "barrier-milk-50ml-new.png",
                "source_record_id": "row_000003",
                "confidence": 0.88,
                "reason": "same product with a size suffix",
            }
        ]

    monkeypatch.setattr(catalog_images, "_ask_model", fake_ask)
    matched, source = asyncio.run(catalog_images.match_images(images, targets))

    assert matched["A-1.png"]["method"] == "exact_sku"
    assert matched["barrier-milk-50ml-new.png"]["method"] == "model"
    assert source == "hybrid_model_with_deterministic_guard"


def test_an_image_model_failure_keeps_the_deterministic_matches(monkeypatch) -> None:
    live_model(monkeypatch, catalog_images)

    async def explode(*_args):
        raise RuntimeError("synthetic match failure")

    monkeypatch.setattr(catalog_images, "_ask_model", explode)
    targets = [ImageTarget("row_000002", 2, "A-1", "Calm Gel Serum"),
               ImageTarget("row_000003", 3, "A-2", "Barrier Milk")]
    images, _ = extract_image_archive(make_zip({"A-1.png": PNG, "mystery.png": PNG}), "i.zip")
    matched, source = asyncio.run(catalog_images.match_images(images, targets))

    assert set(matched) == {"A-1.png"}
    assert source == "deterministic_failover"


# --- merchant-facing error summary -------------------------------------------------------


def test_upload_diagnostics_explain_every_held_row(client: TestClient) -> None:
    headers = ["SKU", "Name", "Price", "Ingredients", "Stock", "Description"]
    rows = [
        ["OK-1", "Gentle Cloud Cleanser", 29.90, "glycerin", 10, "A gentle face wash for dry skin"],
        ["BAD-1", "Broken Price Toner", "N/A", "glycerin", 3, "A toner"],
        ["BAD-2", "No Ingredients Serum", 20.00, "", 3, "A serum"],
        ["OK-1", "Duplicate Code Cream", 25.00, "ceramide", 3, "A moisturiser"],
    ]
    upload = client.post(
        "/merchant/m_mysa/catalog/uploads",
        files={"file": ("catalog.xlsx", workbook_bytes(rows, headers), "application/vnd.ms-excel")},
    ).json()

    diagnostics = upload["diagnostics"]
    assert diagnostics["source"] == "deterministic"
    assert diagnostics["headline"] == (
        "1 of 4 rows are ready to publish; 3 could not be read."
    )
    codes = {group["code"]: group for group in diagnostics["groups"]}
    assert set(codes) == {"PRICE_INVALID", "MISSING_INGREDIENTS", "DUPLICATE_SKU"}
    assert codes["DUPLICATE_SKU"]["row_count"] == 1
    assert codes["DUPLICATE_SKU"]["example_rows"] == [5]
    assert "SKU" in codes["DUPLICATE_SKU"]["fix"] or "code" in codes["DUPLICATE_SKU"]["fix"]
    assert all(group["blocking"] for group in diagnostics["groups"])


def test_a_clean_upload_says_so(client: TestClient) -> None:
    upload = stage_catalog(client)
    assert upload["diagnostics"]["groups"] == []
    assert upload["diagnostics"]["headline"] == "All 3 rows are clean and ready to publish."


@pytest.mark.parametrize(
    ("issue", "code"),
    [
        ("price must be numeric with at most two decimal places", "PRICE_INVALID"),
        ("stock is required", "STOCK_INVALID"),
        ("duplicate sku A-1; each source row must be unique", "DUPLICATE_SKU"),
        ("formula content requires review: Notes", "FORMULA_CELL"),
        ("image_url must be an https:// link or a path on this store", "IMAGE_URL_INVALID"),
        ("exactly one primary product type is required", "AMBIGUOUS_PRODUCT_TYPE"),
        ("something nobody planned for", "OTHER"),
    ],
)
def test_issues_are_grouped_under_a_stable_code(issue: str, code: str) -> None:
    assert classify_issue(issue) == code


def test_one_row_with_two_problems_is_counted_once_per_group() -> None:
    groups = build_groups(
        [
            {"row_number": 2, "status": "rejected", "issues": ["sku is required", "price is required"]},
            {"row_number": 3, "status": "rejected", "issues": ["price is required"]},
            {"row_number": 4, "status": "ready", "issues": []},
        ]
    )
    counts = {group["code"]: group["row_count"] for group in groups}
    assert counts == {"PRICE_INVALID": 2, "MISSING_SKU": 1}
    assert deterministic_headline(
        {"input_rows": 3, "ready": 1, "review_required": 0, "rejected": 2}, groups
    ) == "1 of 3 rows are ready to publish; 2 could not be read."


def test_the_model_may_reword_a_group_but_never_invent_one() -> None:
    rewritten = validate_diagnostics_payload(
        {
            "schema_version": "catalog-diagnostics.v1",
            "headline": "Most of your file is ready.",
            "groups": [
                {"code": "PRICE_INVALID", "title": "Prices we could not read",
                 "why": "The price cell was not a number.", "fix": "Write prices as 29.90."}
            ],
        },
        codes=["PRICE_INVALID"],
    )
    assert rewritten["prose"]["PRICE_INVALID"]["title"] == "Prices we could not read"

    for payload, message in [
        ({"schema_version": "catalog-diagnostics.v1", "headline": "h", "groups": [
            {"code": "MADE_UP", "title": "t", "why": "w", "fix": "f"}
        ]}, "exactly the codes"),
        ({"schema_version": "catalog-diagnostics.v1", "headline": "h", "groups": []},
         "exactly the codes"),
        ({"schema_version": "old.v0", "headline": "h", "groups": []}, "schema_version"),
    ]:
        with pytest.raises(DiagnosticsValidationError, match=message):
            validate_diagnostics_payload(payload, codes=["PRICE_INVALID"])
