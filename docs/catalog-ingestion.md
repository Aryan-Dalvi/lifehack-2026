# Catalog ingestion contract

Status: approved recommendation for the Phase 0 skincare merchant workflow.

## Format decision

Use a constrained `.xlsx` workbook as the primary merchant-facing upload. It is familiar to SME
operators, supports typed cells and validation lists, and can carry instructions without mixing them
into product rows. The importer retains the exact uploaded bytes and stages every source row before
any live catalog change.

The canonical application representation is versioned JSON stored in the database. UTF-8 CSV and
`catalog-source.v1` JSON are supported as fallbacks. Product images arrive one of exactly two ways -
an `image_url` column, or a ZIP archive matched to live products by file name (see "Product
images"); images embedded in the workbook, macros, and external workbook links are not accepted as
catalog facts.
Formula-like cell content is retained as raw evidence but quarantined for merchant review.

## XLSX workbook contract

The distributable template is `skincare-catalog-template.xlsx`. The importer automatically selects
the single worksheet whose header row best matches catalog fields; the recommended sheet name is
`Products`. Row 1 is the header row and each following non-empty row is one product.

Required fields:

| Field | Type | Rule |
|---|---|---|
| `sku` | text | Unique, stable merchant identifier |
| `title` | text | Product-facing name |
| `description` | text | Merchant-provided factual copy |
| `price` | decimal | Major currency units, non-negative |
| `currency` | text | Three-letter currency code, for example `SGD` |
| `stock` | integer | Non-negative available quantity |

Recommended evidence fields:

| Field | Type | Purpose |
|---|---|---|
| `ingredients` | text | Merchant ingredient/INCI evidence |
| `product_type` | text | Existing merchant classification; cleaner may normalize it |
| `skin_types` | text | Delimited merchant claims |
| `concerns` | text | Delimited merchant claims |
| `fragrance_free` | boolean/text | Explicit merchant claim only |
| `excludes` | text | Explicit free-from claims |
| `texture` | text | Formulation or texture evidence |
| `usage_time` | text | Explicit morning/evening guidance |
| `image_url` | URL | SKU-linked product image |
| `rating_avg` | decimal | Optional merchant/source rating |
| `rating_count` | integer | Optional rating sample size |
| `size_ml` | decimal | Optional volume |
| `source_url` | URL | Audit source for collected or enriched rows |

Do not put instructions to the agent in any product cell. Catalog text is always untrusted data.
Unknown values should be blank rather than guessed.

## Column mapping

Mapping is deterministic and costs nothing. Headers are matched against a fixed alias table,
and the downloadable template ships exactly those headers - so a file filled in from the
template maps perfectly, every time, with no model call and no latency.

- A header the table does not know is **ignored and reported**, never guessed at. Merchants
  keep their own internal columns (cost, supplier, notes) in the file without consequence,
  and `mapping_report.ignored_columns` tells them what had no effect.
- Two headers competing for one field **stop the upload** for correction.
- Every decision appears in `mapping_report.decisions` with its method (`exact_alias`).

There is deliberately no model in this path. Naming columns is a job a template solves better
than a model does: cheaper, instant, and the same answer every time.

## The catalog template

`GET /catalog/template` returns `skincare-catalog-template.xlsx`. It is public - it holds the
shape of a catalog, never a merchant's data. Two sheets:

- **Products** - the header row, styled so required columns stand out, plus two greyed example
  rows to delete, and a yes/no validation list on `fragrance_free`.
- **How to fill this in** - every column, whether it is required, and what to put in it.

Five columns are required: `sku`, `title`, `price`, `stock`, `ingredients`. Everything else is
optional - evidence the assistant uses when present and skips when blank. A blank cell is
always preferred to a guess.

Every template header is either a mapped field or recognised evidence; a test asserts this, so
a column cannot be added to the template that the importer would silently ignore.

## Product images

Two routes, and neither overrules the other:

1. **`image_url` column** in the workbook. Accepted only as an `https://` address or a path on
   this store. A `javascript:`, `data:`, protocol-relative or other scheme is a row-level
   rejection with a merchant-facing message, because the value is rendered in an `<img src>`
   on every shopper's page.
2. **ZIP archive** posted to `POST /merchant/{merchant_id}/catalog/images`, matched to the
   **live catalog** by file name and applied immediately.

Photos deliberately do not go through staged review. They only ever set `image_url` - never a
price, title or stock - so the worst a wrong match can do is show the wrong picture, which the
merchant can see in the report and correct by uploading a corrected archive. Requiring a
catalog upload first made the feature unreachable for any merchant who already had a catalog,
which is precisely when photos get added.

Archive limits: 25 MB uploaded, 100 MB expanded, 500 files, 5 MB per image, PNG/JPEG/WebP/GIF
decided by magic bytes rather than by extension. Path traversal, absolute paths, symlinks,
hidden entries and `__MACOSX/` are refused per entry, with the reason reported back.

Matching is deterministic first - exact SKU, then exact product name, then a fuzzy name match
that requires a clear winner - and only leftover files and products are shown to the model,
whose answer must name real ids, stay one photo to one product, and clear 0.6 confidence. In
practice a well-named archive costs zero model calls. An unmatched file is a safe outcome: it
is reported, and its bytes are not stored at all.

A replaced photo's bytes are swept once nothing references them. Images are served from
`GET /catalog/images/{image_id}`, public only once the photo is on a live product in a
published store, and merchant-authenticated before that.

## Upload diagnostics

Every preview carries a `diagnostics` block explaining why rows did not make it through. Rows
are grouped, counted and coded deterministically; the model is only allowed to rewrite the
prose of a group it was handed, and must return exactly the codes it was given. Counts and row
numbers never come from the model. If the model is unavailable the deterministic wording
stands. Unrecognised columns are surfaced here too, as a note.

## Limits and deterministic parsing

- Maximum uploaded file size: 5 MB.
- Maximum expanded XLSX size: 50 MB.
- Maximum 10,000 product rows and 200 columns.
- CSV delimiter and encoding are detected; malformed rows are reported rather than silently dropped.
- XLSX macros and external links are rejected. Formula-like cells are held for review rather than
  evaluated. SKUs formatted with leading zeroes remain text when the worksheet number format makes
  that intent explicit.
- An ambiguous worksheet or field mapping stops the upload for explicit correction.
- SKU, price, currency, stock, ratings, and image URLs are locked deterministic facts and are never
  supplied to or generated by the categorization model.

## Staged publication

1. Upload `.xlsx`, `.csv`, or JSON to `POST /merchant/{merchant_id}/catalog/uploads` (the legacy
   `/catalog` path is an alias). The response is a staged preview; it does not change live products.
2. Review every page with `GET /merchant/{merchant_id}/catalog/uploads/{upload_id}` using `offset`
   and `limit`.
3. Choose the preview's `replace` or `upsert` plan. Replace is blocked while any row is held for
   review because it could otherwise delete products unintentionally.
4. Publish through `POST /merchant/{merchant_id}/catalog/uploads/{upload_id}/approve` with the exact
   plan `approval_token`, its required reviewed-row count, and the selected mode.

Approval tokens bind the preview, base catalog, mode, and removal plan. A changed live catalog or
stale preview must be reviewed again. The original upload, parsed rows, classifications, evidence,
taxonomy version, model/prompt provenance, and publication result remain auditable.
