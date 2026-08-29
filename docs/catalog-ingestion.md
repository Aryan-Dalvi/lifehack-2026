# Catalog ingestion contract

Status: approved recommendation for the Phase 0 skincare merchant workflow.

## Format decision

Use a constrained `.xlsx` workbook as the primary merchant-facing upload. It is familiar to SME
operators, supports typed cells and validation lists, and can carry instructions without mixing them
into product rows. The importer retains the exact uploaded bytes and stages every source row before
any live catalog change.

The canonical application representation is versioned JSON stored in the database. UTF-8 CSV and
`catalog-source.v1` JSON are supported as fallbacks. Product images arrive one of exactly two ways -
an `image_url` column, or a separate ZIP archive matched by file name (see "Product images"); images
embedded in the workbook, macros, and external workbook links are not accepted as catalog facts.
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

Headers are matched to fields by an alias table first, and that result always wins. The model is
asked only about what the aliases could not settle - a header the table has never seen, or two
headers competing for one field - and it is given the header wording plus at most three short sample
values per column. Its answer is validated back against the real headers before anything is applied:
the column must exist, the field must still be free, an ambiguous field must be resolved to one of
its own candidate columns, no column may be used twice, and anything below 0.55 confidence is
discarded. A tie the model cannot break still stops the upload for explicit correction.

The model names columns; it never reads or authors values. Every mapped value goes through the same
deterministic normalisation, so a mapping mistake can misfile a column but cannot invent a price.
The model may also rename an unrecognised descriptive column to a canonical name (for example
`Who it's for` to `skin_types`) so it reaches the classifier as evidence. Columns mapped to locked
facts are excluded from classifier input whatever they are renamed to.

Every mapping decision is returned in `mapping_report` with its method (`exact_alias`, `model`,
`model_descriptive`), confidence and reason, and is shown to the merchant before publication.

## Product images

Two supported routes, and neither overrules the other:

1. **`image_url` column.** Accepted only as an `https://` address or a path on this store. A
   `javascript:`, `data:`, protocol-relative or other scheme is a row-level rejection with a
   merchant-facing message, because the value is rendered in an `<img src>` on every shopper's page.
2. **ZIP archive**, uploaded to `POST /merchant/{merchant_id}/catalog/uploads/{upload_id}/images`
   while the upload is awaiting review. Each file is named after the product or its SKU.

Archive limits: 25 MB uploaded, 100 MB expanded, 500 files, 5 MB per image, PNG/JPEG/WebP/GIF
decided by magic bytes rather than by extension. Path traversal, absolute paths, symlinks, hidden
entries and `__MACOSX/` are refused per entry, with the reason reported back.

Matching is deterministic first - exact SKU, then exact product name, then a fuzzy name match that
requires a clear winner - and only leftover files and product rows are shown to the model, whose
answer must name real ids, stay one image to one product, and clear 0.6 confidence. An unmatched
file is a safe outcome and is reported rather than guessed at.

A ZIP may replace a binding from a previous ZIP but never an `image_url` the merchant typed into the
workbook. Attaching images rewrites staged rows, so it recomputes the preview hash and invalidates
any approval token already issued: the preview a merchant approves is always the one they last saw.

Bytes are stored with the upload and served from `GET /catalog/images/{image_id}`, public only once
the image is on a live product in a published store and merchant-authenticated before that.

## Upload diagnostics

Every preview carries a `diagnostics` block explaining why rows did not make it through. Rows are
grouped, counted and coded deterministically; the model is only allowed to rewrite the prose of a
group it was handed, and must return exactly the codes it was given. Counts and row numbers never
come from the model. If the model is unavailable the deterministic wording stands.

## Limits and deterministic parsing

- Maximum uploaded file size: 5 MB.
- Maximum expanded XLSX size: 50 MB.
- Maximum 10,000 product rows and 200 columns.
- CSV delimiter and encoding are detected; malformed rows are reported rather than silently dropped.
- XLSX macros and external links are rejected. Formula-like cells are held for review rather than
  evaluated. SKUs formatted with leading zeroes remain text when the worksheet number format makes
  that intent explicit.
- An ambiguous worksheet stops the upload for explicit correction. An ambiguous field mapping is
  offered to the model first, and stops the upload only if the model cannot settle it either.
- SKU, price, currency, stock, ratings, and image URLs are locked deterministic facts and are never
  supplied to or generated by the categorization model.

## Staged publication

1. Upload `.xlsx`, `.csv`, or JSON to `POST /merchant/{merchant_id}/catalog/uploads` (the legacy
   `/catalog` path is an alias). The response is a staged preview; it does not change live products.
1a. Optionally attach product photos with `POST .../uploads/{upload_id}/images`. This reissues the
   preview and its approval tokens.
2. Review every page with `GET /merchant/{merchant_id}/catalog/uploads/{upload_id}` using `offset`
   and `limit`.
3. Choose the preview's `replace` or `upsert` plan. Replace is blocked while any row is held for
   review because it could otherwise delete products unintentionally.
4. Publish through `POST /merchant/{merchant_id}/catalog/uploads/{upload_id}/approve` with the exact
   plan `approval_token`, its required reviewed-row count, and the selected mode.

Approval tokens bind the preview, base catalog, mode, and removal plan. A changed live catalog or
stale preview must be reviewed again. The original upload, parsed rows, classifications, evidence,
taxonomy version, model/prompt provenance, and publication result remain auditable.
