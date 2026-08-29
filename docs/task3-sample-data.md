# Task 3 sample catalog provenance

Retrieved: 2026-08-29 (Singapore time)

## Company selection

The matched raw/control sample uses eight single products from Sigi Skin. The company's own About
page describes it as a local skincare brand and says it is entirely self-funded, making it a useful
real SME-shaped catalog rather than a synthetic brand.

- Company evidence: https://sigiskin.com/pages/about-us
- Scope: skincare products only; bundles, lip products, accessories, and discontinued listings are
  excluded.

## Matched outputs

- `sigi-skin-unclean-catalog.xlsx` contains source-faithful but deliberately inconsistent headers,
  separators, casing, whitespace, units, and category terms.
- `sigi-skin-clean-control.xlsx` contains the same eight products and source facts, manually
  normalized into the Phase 0 schema and taxonomy. It is the comparison control, not output from the
  catalog cleaner.

Both workbooks use the same `source_record_id` and `sku` keys. The cleaner is intentionally not run
against either workbook as part of Task 3.

## Provenance and fixture boundaries

Official product pages provide names, SGD prices, sizes, merchant SKUs where exposed, descriptions,
directions, key/full ingredients, and displayed review totals. The source URL is repeated on every
product row and in each workbook's Sources sheet.

The public pages expose only an availability flag rather than stock quantities. Integer stock values
are therefore deterministic test-fixture values and are marked `synthetic_test_fixture` in both
workbooks. Four products expose no merchant SKU; stable sample-only SKUs are marked
`dataset_assigned_missing_merchant_sku`. These fields must never be described as Sigi Skin facts.

No average rating is created from review counts. No medical or safety claim is added by inference.
The clean control only normalizes claims supported by the cited product copy or directions; unknown
fields remain blank.

## Product sources

| Source record | Product | Official page |
|---|---|---|
| `row_000002` | Kaleanser Face Wash, 100 ml | https://sigiskin.com/products/kaleanser |
| `row_000003` | Morning Glow Physical Sunscreen | https://sigiskin.com/products/sunscreen |
| `row_000004` | Dew Potion Essence Mist | https://sigiskin.com/products/dew-potion |
| `row_000005` | Idyllic Fields Daytime Moisturiser | https://sigiskin.com/products/idyllic-fields |
| `row_000006` | Dream Capsule Daily Overnight Sleeping Mask | https://sigiskin.com/products/dream-capsule |
| `row_000007` | Youth Beam Anti-Ageing Night Serum | https://sigiskin.com/products/youth-beam |
| `row_000008` | Bright Skies Peeling Gel Exfoliator | https://sigiskin.com/products/bright-skies |
| `row_000009` | Garden Party Deep Cleansing Clay Mask | https://sigiskin.com/products/garden-party |

