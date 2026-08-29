# Interface contracts — DRAFT until frozen by the Y4 at the first huddle

**Status: DRAFT v0.11** — proposed by KICKOFF (Claude Code / Aryan, T+0:35), revised T+1:10
(subagent split, simplified console) and T+1:40 (ratings, progressive disclosure, issuer
authentication, shipping address). The Y4/architect freezes v1 at the first huddle. After freeze:
changing anything here requires the Y4's OK + a message in the team chat + a bump of the version
line. Parallel work touches other members' modules **only** through what is written here — that is
the whole point of this file.

Version: **v0.11 (unfrozen)** · Project: *Agent-Ready Commerce* (working name)

**Proposed v0.12 — shipped in code, awaiting the Y4's OK (Aryan/Claude, T+~17).** The shopper UX
pass added three things that cross module lines, so they are written here rather than left to be
discovered: the shopper now enters a **card** (`PUT /agent/session/{id}/card`), names an address
for an **emailed receipt** (`PUT /agent/session/{id}/receipt-email`, or `receipt_email` on
`/agent/confirm`), and a merchant can upload a **logo** (`POST|DELETE|GET /merchant/{id}/logo`).
The admin gate also gained a deliberate public route, `GET /merchant/demo-store`, so the demo
can be opened without finding a key — read its row below before deploying anywhere real.
`create_cart` refuses with **`CARD_REQUIRED`** until a card is on the session, exactly as it
already refuses with `ADDRESS_REQUIRED`. See the module tables below for the full shapes. Y4:
please confirm or push back — nothing above the tables was changed.

**Changes from v0.10:** `Product` gains rating fields · new `Address` model and
`/consumer/{id}/addresses` · **new mock issuer ACS at `/bank/*`, and `/pay/authorize` now requires
a valid issuer token** · cart hash now covers the shipping address · four new bank decline codes ·
category packs gain `salient_dims` · plates renumbered **C1–C9**.

**Changes from v0.9:** `agent/` is now an orchestrator plus five specialists (see §Subagents) ·
new internal `AgentMessage` envelope and Guardian validator · the cart builder moves from `agent/`
to `payments/` · UI surfaces are specified in `docs/ux.md` and `docs/wireframes.html`.

---

## Module split & owners

| Directory | Owns | Member |
|---|---|---|
| `payments/` | mock Visa stack: token vault, authorize/capture, cart builder, mandate chain, TAP verification, trust events, **mock issuer ACS (`/bank/*`, own store)** | **Y4** |
| `agent/` | orchestrator + specialists, Guardian, category packs, agent-side signing, demo-mode fallback | **Y3** |
| `web/` | chat widget, trust panel, merchant console (Vite + React + Tailwind) | **Y2** |
| `merchant/` | catalog ingest, merchant registry, discovery/search API, merchant config + embed snippet, **consumer addresses (`/consumer/*`)** | **Aryan** |
| `app/` | FastAPI entrypoint, router mounting, middleware wiring, DB session, settings | **Aryan** (shared — PRs, not direct pushes, after freeze) |
| `seed/`, `demo/`, `docs/`, `Makefile` | seed catalogs, demo script, ops | **Aryan** |

**One process, five routers.** `uvicorn app.main:app` mounts `agent`, `merchant`, `consumer`, `pay`
and `bank` on **:8000**; the web app runs on **:5173**. Router count is not module count — `consumer`
is Aryan's code inside `merchant/`, and `bank` is Y4's inside `payments/` (with its own store). Rationale: walking-format judging needs a cold start in
seconds, and one process cannot half-die. Signature verification is still honest — the agent calls
the merchant/payment routes over real HTTP to `http://localhost:8000`, so requests really are signed
and really are verified at the edge.

## System sketch

```
                 ┌─────────────── web/ (:5173) ───────────────┐
                 │  Chat widget   │  Trust Panel  │  Merchant │
                 │                │   (SSE)       │  console  │
                 └────┬───────────┴──────┬────────┴─────┬─────┘
                      │ POST /agent/*    │ GET /trust/  │ /merchant/*
                      ▼                  │  events      ▼
              ┌───────────────┐          │      ┌──────────────────┐
              │   agent/      │          │      │   merchant/      │
              │ LLM + tools   │          │      │ catalog, search, │
              │ signs TAP reqs│          │      │ config, snippet  │
              └───┬───────┬───┘          │      └────────▲─────────┘
   tag=agent-     │       │ tag=agent-   │               │
   browser-auth   │       │ payer-auth   │               │
                  │       ▼              │               │
                  │  ┌──────────────────────────┐        │
                  └─►│  TAP verify middleware   │────────┘
                     │  (RFC 9421, agent reg.)  │
                     └────────────┬─────────────┘
                                  ▼
                        ┌────────────────────┐
                        │    payments/       │
                        │ token vault ·      │
                        │ mandate chain ·    │
                        │ authorize/capture ·│
                        │ trust event bus    │
                        └────────────────────┘
                                  │
                             SQLite (single file, `make reset` reseeds)
```

## Data models

```jsonc
// Product — merchant/
{
  "sku": "LUM-TV-55X",
  "merchant_id": "m_lumen",
  "merchant_name": "Lumen Electronics",
  "merchant_size": "enterprise",          // "sme" | "enterprise"
  "title": "Lumen 55\" 4K OLED",
  "description": "…",
  "price_cents": 129900,
  "currency": "SGD",
  "image_url": "/static/products/lum-tv-55x.png",   // always local
  "category": "electronics",
  "attributes": { "screen_in": 55, "panel": "OLED", "hdr": true },
  "stock": 12,

  // ratings — v0.11. A rating is a FACT: read from this row, rendered by code,
  // never phrased by a model. Guardian check #2 grounds them like prices.
  "rating_avg": 4.8,           // 0.0–5.0, one decimal, null if unrated
  "rating_count": 612,         // always shown beside the average
  "rating_source": "merchant_feed"   // merchant_feed | enrichment | none
}
```

```jsonc
// Address — v0.11. One consumer may have several; exactly one is `is_default`.
{
  "address_id": "adr_01J…",
  "consumer_id": "usr_demo",
  "recipient": "Aryan D.",
  "lines": ["14 Prince George's Park", "#05-21"],
  "postal_code": "118420",
  "country": "SG",
  "is_default": true
}
```

```jsonc
// IssuerToken — v0.11, minted by the mock ACS in payments/, NOT by the agent
{
  "bank_token": "btk_01J…",     // opaque; stands in for a 3-DS CAVV
  "issuer": "Meridian Bank",
  "eci": "05",                  // authenticated
  "bound": {                    // the binding is the whole point
    "cart_hash": "sha256:…",    // covers items, total AND shipping address
    "amount_cents": 14900,
    "merchant_id": "m_lumen"
  },
  "single_use": true,
  "expires_at": "2026-08-29T12:08:11Z",   // 5 minutes
  "status": "issued"            // issued | consumed | expired | revoked
}
```

```jsonc
// Mandate — payments/ (AP2-shaped). type ∈ intent | cart | payment
{
  "mandate_id": "mnd_01J…",
  "type": "cart",
  "parent_id": "mnd_01J…",                // intent for cart, cart for payment
  "session_id": "ses_01J…",
  "issued_at": "2026-08-29T12:03:11Z",
  "expires_at": "2026-08-29T12:18:11Z",
  "payload": {
    // intent:  { "category": "electronics", "max_amount_cents": 150000,
    //            "currency": "SGD", "merchant_scope": ["m_lumen"] }
    // cart:    { "merchant_id": "m_lumen", "items": [{ "sku": …, "qty": 1,
    //            "unit_price_cents": … }], "total_cents": 129900, "currency": "SGD" }
    // payment: { "cart_hash": "sha256:…", "token_id": "tok_…",
    //            "human_confirmation": { "method": "passkey|click",
    //                                    "at": "…", "assertion": "…" } }
  },
  "cart_hash": "sha256:…",                // present on cart + payment
  "signatures": [ { "signer": "agent|platform", "kid": "agent-key-1",
                    "alg": "ed25519", "sig": "base64url…" } ]
}
```

```jsonc
// PaymentToken — payments/ (agent-bound network token, simulated)
{
  "token_id": "tok_01J…",
  "network_token_last4": "4821",          // never a real PAN, anywhere
  "consumer_id": "usr_demo",
  "bound_agent_kid": "agent-key-1",
  "constraints": {
    "max_amount_cents": 150000,
    "merchant_id": "m_lumen",             // null = any merchant in scope
    "single_use": true,
    "expires_at": "2026-08-29T12:18:11Z"
  },
  "status": "active"                      // active | used | revoked | expired
}
```

```jsonc
// TrustEvent — payments/ → SSE → web/ Trust Panel
{
  "seq": 4,
  "session_id": "ses_01J…",
  "at": "2026-08-29T12:03:12.114Z",
  "stage": "signature|mandate|constraint|decision",
  "label": "Cart mandate verified",
  "status": "ok|warn|fail",
  "detail": { "mandate_id": "mnd_…", "check": "cart_hash", "expected": "…", "got": "…" }
}
```

## API endpoints

All JSON. All timestamps RFC 3339 UTC. All money as integer **cents** + explicit `currency` —
never floats, never a bare number.

### `merchant/` — owner Aryan

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| POST | `/merchant/onboard` | `{name, size, category, currency}` | `{merchant_id, api_key, embed_snippet}` | 400 `VALIDATION` |
| GET | `/merchant/demo-store` | — | `{available, merchant_id, name, api_key}` — **public and deliberate**: the seeded demo store's key, for one-click sign-in. Only `settings.demo_merchant_id`, only where the seed wrote the key file, only while `DEMO_LOGIN_ENABLED` is on. `available:false` is a normal answer | — |
| POST | `/merchant/{id}/catalog/uploads` (`/catalog` alias) | multipart `.xlsx`/CSV (`file`, optional `sheet_name`) **or** versioned JSON | staged review preview with `upload_id`, mappings, row statuses, taxonomy, pagination, and mode-bound approval plans; live catalog unchanged | 400 `BAD_CATALOG`, 404 `NO_MERCHANT`, 413 `TOO_LARGE` |
| GET | `/merchant/{id}/catalog/uploads/{upload_id}` | query: `offset=0, limit=100` | paginated staged preview and `replace`/`upsert` approval plans | 400 `BAD_PAGINATION`, 404 `NO_CATALOG_UPLOAD`, 409 |
| POST | `/merchant/{id}/catalog/uploads/{upload_id}/approve` | `{approval_token, reviewed_row_count, mode:"replace"|"upsert"}` | `{status:"published", mode, published, removed, skipped, idempotent_replay}` | 400, 404, 409 stale/incomplete/unsafe plan |
| GET | `/merchant/{id}/config` | — | `{merchant_id,name,size,category,currency,accent_color,logo_url,persona,policies}` | 404 |
| PUT | `/merchant/{id}/config` | partial config | updated config | 400, 404 |
| GET | `/merchant/{id}/snippet` | — | `{snippet:"<script src=…></script>"}` | 404 |
| POST | `/merchant/{id}/logo` | multipart image (`file`) — PNG/JPEG/GIF, ≤512 KB, **type decided by the file's own bytes** | `{merchant_id, logo_url, content_type}` | 400 `BAD_IMAGE`, 401, 413 `TOO_LARGE` |
| DELETE | `/merchant/{id}/logo` | — | `{merchant_id, logo_url:null}` | 401, 404 |
| GET | `/merchant/{id}/logo` | — | the image bytes, `nosniff`, immutable cache | 404 `NO_IMAGE` |
| GET | `/catalog/search` | query: `q, merchant_id?, category?, max_price_cents?, attrs?, limit=10` | `{results:[Product], facets:{…}, total:int}` | 400 |
| GET | `/catalog/product/{sku}` | — | `Product` | 404 |

*Requires a valid TAP signature with `tag=agent-browser-auth` when called by the agent (enforced
from T-12 onward; before that the middleware runs in log-only mode so nobody is blocked).*

### `payments/` — owner Y4

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| POST | `/pay/tokens` | `{consumer_id, mandate_id, constraints{…}}` | `PaymentToken` | 400, 409 `MANDATE_NOT_VERIFIED` |
| POST | `/pay/mandates` | `{type, parent_id?, session_id, payload, expires_at, signatures[]}` | `Mandate` | 400 `SIGNATURE_INVALID`, 409 `PARENT_MISMATCH` |
| GET | `/pay/mandates/{id}/chain` | — | `{links:[{mandate_id,type,verified:bool,failed_check?}], verified:bool}` | 404 |
| POST | `/pay/authorize` | `{token_id, payment_mandate_id, amount_cents, currency, merchant_id, `**`bank_token`**`}` | `{status:"approved", transaction_id, auth_code, eci, issuer, amount_cents}` **or** `{status:"declined", decline_code, reason}` | 400 · **never 5xx for a business decline** |
| POST | `/pay/capture` | `{transaction_id}` | `{status:"captured", captured_at}` | 404, 409 `NOT_AUTHORIZED` |
| GET | `/pay/receipt/{transaction_id}` | — | `{transaction_id, merchant, items[], total_cents, currency, card_brand, last4, auth_code, at, email_delivery{recipient,status,channel}}` | 404 |
| GET | `/trust/events?session_id=` | SSE | stream of `TrustEvent` | 404 |

*Payment routes require `tag=agent-payer-auth`. A payer-auth route presented with a browser-auth
signature is a hard reject — that distinction is part of the pitch.*

`merchant` and `last4` on a cart preview and a receipt are now read from the merchant row and
from the card the shopper entered. They were the constants `"Mysa Skin"` and `"4821"`, which were
wrong for every merchant who signed up after the seed and for every shopper who ever existed.

`email_delivery.status` is one of `sent` (a real message over SMTP) · `simulated` (rendered to
`var/outbox/` because no `SMTP_HOST` is configured) · `failed` (delivery raised; **the order is
still approved**) · `skipped` (no address on file). Never render `simulated` as "sent".

**Decline codes (closed set — Y2 renders these, Y3 handles them, don't invent new ones):**
`AMOUNT_EXCEEDS_MANDATE` · `MANDATE_EXPIRED` · `MERCHANT_MISMATCH` · `CART_HASH_MISMATCH` ·
`TOKEN_REUSED` · `TOKEN_REVOKED` · `SIGNATURE_INVALID` · `NONCE_REPLAY` · `HUMAN_NOT_PRESENT` ·
`INSUFFICIENT_FUNDS` (simulated, for realism) · **v0.11:** `BANK_TOKEN_MISSING` ·
`BANK_TOKEN_EXPIRED` · `BANK_TOKEN_REUSED` · `BANK_TOKEN_CART_MISMATCH` · `BANK_AUTH_DECLINED` ·
`SHIPPING_ADDRESS_MISMATCH`.

### `bank/` — mock issuer ACS (new in v0.11) — owner Y4

Stands in for the card issuer's Access Control Server. Models the **Visa Secure / EMV 3-D Secure**
step-up: the bank, not the merchant and not the agent, authenticates the cardholder for one specific
transaction and mints a token bound to it.

> **Keep this router's state separate from the authoriser's.** The ACS must be able to refuse *us* —
> if it shares a store with `/pay/authorize`, the demo's most interesting refusals become
> self-inflicted and stop proving anything.

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| POST | `/bank/challenge` | `{consumer_id, cart_hash, amount_cents, currency, merchant_id}` | `{challenge_id, method:"otp"\|"app", masked_target:"•••• 8821", expires_at}` | 400, 404 |
| POST | `/bank/verify` | `{challenge_id, code}` | `{status:"approved", bank_token, eci, issuer, expires_at}` **or** `{status:"declined", decline_code}` | 400, 404, 429 (after 3 wrong codes) |
| GET | `/bank/token/{bank_token}` | — | `IssuerToken` (status only; never the binding secrets) | 404 |

**Rules `/pay/authorize` enforces on the token** — each one is a rehearsable demo refusal:

| Condition | Decline code |
|---|---|
| No `bank_token` supplied | `BANK_TOKEN_MISSING` |
| Past `expires_at` (5 min TTL) | `BANK_TOKEN_EXPIRED` |
| `status == consumed` — replayed on a second purchase | `BANK_TOKEN_REUSED` |
| `bound.cart_hash` ≠ the cart being authorised | `BANK_TOKEN_CART_MISMATCH` |
| `bound.amount_cents` or `bound.merchant_id` differ | `BANK_TOKEN_CART_MISMATCH` |
| Shipping address in the cart ≠ the one in the signed hash | `SHIPPING_ADDRESS_MISMATCH` |

**Demo mode:** with `DEMO_MODE=1` the ACS accepts a fixed code (`492 118`) and still enforces every
binding rule above. The refusals must be real even when the network is off.

### `/consumer/*` — profile + addresses (new in v0.11) — owner Aryan

Routes live at `/consumer/*` but the code sits in **`merchant/consumer.py`**, inside Aryan's module —
a fourth top-level package for two endpoints isn't worth the ownership boundary.

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| GET | `/consumer/{id}/addresses` | — | `{addresses:[Address], default_address_id}` | 404 |
| PUT | `/consumer/{id}/addresses/{aid}/default` | — | `{default_address_id}` | 404 |

**The shipping address is part of the signed cart.** `cart_hash` is computed over
`{items, total_cents, currency, merchant_id, shipping_address_id, shipping_address_fingerprint}`.
An agent that changes where the goods go after the shopper consented produces a different hash, and
the issuer token no longer matches it. That is the property, and it is worth saying out loud.

### `agent/` — owner Y3

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| POST | `/agent/session` | `{merchant_id?, category?, consumer_id, budget_cents?}` | `{session_id, intent_mandate_id, greeting, merchant:{name, accent_color, logo_url}}` | 400, 404 |
| POST | `/agent/message` | `{session_id, text}` | **SSE** stream of `{type, data}` | 400, 404, 429 |
| PUT | `/agent/session/{id}/card` | `{number, expiry_month, expiry_year, cvc, holder}` | `{brand, last4, expiry, holder}` — **the number is validated and dropped; only these four fields are stored** | 400 `CARD_INVALID` / `CARD_EXPIRED`, 404 |
| PUT | `/agent/session/{id}/receipt-email` | `{email}` (null clears) | `{session_id, receipt_email}` | 400, 404 |
| POST | `/agent/confirm` | `{session_id, cart_mandate_id, confirmation:{method,assertion?}, receipt_email?}` | `{status, transaction_id?, receipt?, decline_code?}` | 400, 404, 409 |

**SSE event types from `/agent/message`** (Y2 must handle every one, including unknown types —
ignore gracefully):
`token` (text delta) · `product_cards` `{products:[Product], inline?:bool}` — `inline` means the
agent's own sentence named these products, so the UI attaches their cards to that message and
bolds the names · `category_table` `{categories:[{key,label,description,product_count,from_price_cents,currency}]}` ·
`comparison` `{dimensions[], rows[]}` ·
`cart` `{cart_mandate_id, items[], total_cents, currency}` · `confirm_request`
`{cart_mandate_id, preview:{merchant, items[], total_cents, currency, last4}}` ·
`receipt` `{…}` · `declined` `{decline_code, reason}` · `error` `{code, message}` · `done`.

## Subagents — internal structure of `agent/` (new in v0.10)

Diagrams: `docs/wireframes.html` Part 3. **Step-by-step execution spec (inputs, outputs, tools per
step): `docs/agent-workflow.md`.** This is internal to `agent/` — no other module sees
these types, so Y3 may refactor freely below this line as long as the HTTP surface above holds.

### The roster

| Subagent | Sees | May emit | Model |
|---|---|---|---|
| **Concierge** (orchestrator) | The transcript. **No product rows, no prices, no card.** | User-facing text, or a routing decision | nano |
| **Discovery** (per category) | A scoped brief: this turn, the category schema, the spend cap | A `CatalogQuery` object — prose is rejected by schema | mini |
| **Comparison** (per category) | ≤5 product rows injected verbatim + the pack's dimensions | A comparison table + one recommendation, every claim citing a `sku` | mini |
| **Cart builder** | SKUs and quantities | A Cart Mandate; totals re-read from the DB, never carried over | **code** (lives in `payments/`) |
| **Payment executor** | A signed cart mandate + a human confirmation | One call to `/pay/authorize` | **code** |
| **Guardian** (validator) | Every message between every pair of agents | Pass / repair-once / refuse, plus a `TrustEvent` either way | **code** |

### Inter-agent envelope

Every hop is this shape. The Guardian validates it before the receiving agent is invoked.

```jsonc
{
  "hop_id": "hop_01J…",
  "session_id": "ses_01J…",
  "from": "concierge", "to": "discovery",
  "type": "scoped_brief",       // scoped_brief | catalog_query | product_rows
                                // | comparison | cart_request | confirmation
  "scope": {                    // the isolation boundary — never widened downstream
    "category": "electronics",
    "merchant_ids": ["m_lumen"],
    "max_amount_cents": 15000,
    "intent_mandate_id": "mnd_4kz"
  },
  "payload": { }                // typed per `type`
}
```

```jsonc
// CatalogQuery — the ONLY thing Discovery may emit
{ "q": "noise cancelling over-ear",
  "max_price_cents": 15000, "attrs": { "anc": true }, "limit": 5 }
```

### Category isolation — the rule that does the work

Each specialist is **constructed per session** from the merchant's configured pack and handed a
`scoped_brief` — **never the running transcript**. The other categories' packs are not loaded into
the context at all. Instructing one agent to "stay in category" is a request; not loading the other
categories is a guarantee.

- Packs are **data files**: `agent/packs/<category>.json` → `{ system, attribute_schema,
  salient_dims, comparison_dimensions, guardrails, few_shot }`. A fourth category costs a JSON file.
- **`salient_dims`** (new in v0.11) — **max 4** attribute keys, the ones shown in the hover preview
  (plate C4). `comparison_dimensions` is the full set, shown only on Compare (plate C5). Electronics
  might surface battery / ANC / weight / fit; fashion, fit / fabric / care / origin.
- **A category switch is a new session**, not a re-prompt (proposed — Y4 to confirm). This keeps
  the isolation guarantee absolute and costs nothing.

### Guardian checks — run on every hop, in this order

1. **Schema** — the message parses into its declared type, or it never leaves.
2. **Grounding** — every `sku` mentioned exists in this merchant's catalog; every price, attribute
   **and star rating** matches the DB row to the cent and to the decimal. One repair attempt, then a
   deterministic fallback (a plain table built from the rows, in code).
   *A model may say "the better-reviewed of the two"; it may not say a number that isn't in the
   payload.*
3. **Scope** — products outside the session's category or merchant scope are stripped.
4. **Mandate** — nothing proposes a cart above the Intent Mandate's cap; nothing reaches the payment
   executor without a cart mandate, a human confirmation **and a valid issuer token**.

Every check emits a `TrustEvent` on the existing bus — **no change to `/trust/events`**, only more
event sources. Failures use the existing decline-code set where one fits, plus:
`UNGROUNDED_CLAIM` · `OUT_OF_SCOPE_PRODUCT` · `SCHEMA_REJECTED`.

### Ownership (Y4 to settle at freeze)

Guardian lives in `agent/guardian.py`, owned by **Y3** — one owner, one interface — and emits
through Y4's trust bus. The **cart builder moves to `payments/`** (Y4): cart totals belong next to
the money, not next to the model. Alternative considered: Guardian in `payments/` beside the other
trust code; rejected because it would make Y3 wait on Y4 for every agent test.

## Cross-cutting conventions

- **Error format** (every non-2xx, every module):
  ```json
  { "error": { "code": "MANDATE_EXPIRED", "message": "human readable", "details": {} } }
  ```
  A *business decline* is **200 with `status:"declined"`**, not an HTTP error. Only malformed or
  unauthorised requests get 4xx.
- **IDs:** prefixed ULIDs — `m_` merchant · `ses_` session · `mnd_` mandate · `tok_` token ·
  `txn_` transaction · `usr_` consumer.
- **Money:** integer cents + `currency` (`"SGD"`). No floats anywhere near a price.
- **Ports:** API **:8000** · web **:5173**. Nothing else listens.
- **Env vars** (names only here; values only in each machine's local `.env`, mirrored into
  `.env.example`): `OPENAI_API_KEY`, `OPENAI_MODEL`, `DEMO_MODE` (`0|1`), `DATABASE_URL`,
  `AGENT_PRIVATE_KEY`, `AGENT_KID`, `PLATFORM_PRIVATE_KEY`, `TRUST_REGISTRY_PATH`,
  `API_BASE_URL`, `VITE_API_BASE`, `SIGNATURE_ENFORCE` (`log|enforce`).
- **Seed/demo data:** `seed/merchants.json`, `seed/lumen_catalog.json`,
  `seed/sme_catalog.csv`, images in `web/public/static/products/`. `make reset` drops the SQLite
  file and reseeds in <5 s. **No runtime network calls except the LLM** — venue wifi is not a
  dependency.
- **Secrets:** never committed, never printed into docs, never logged. Keys for signing are
  generated locally by `make keys` and gitignored.
- **Every module ships with the API stub-able**: if a dependency isn't ready, mock its responses
  behind a flag rather than blocking. Nobody waits on anybody before T+4.

## Open contract questions for the Y4 to settle at freeze

1. Does the **platform** co-sign mandates, or does only the agent sign and the platform verify?
   (Draft assumes agent signs, platform verifies and records — simpler, one keypair.)
2. Is the **intent mandate** created at session start (assumed) or at first add-to-cart?
   **Revised in v0.10:** created when the shopper sets the spend limit in plate C2 — which is the
   first interaction of the session, so this is settled unless Y4 objects.
3. Do we keep `/pay/capture` separate, or auto-capture on authorize for demo simplicity?
   (Draft keeps it separate — it's 15 minutes and it looks like a real payment stack.)
4. **New in v0.10:** Guardian in `agent/` (proposed) or in `payments/`?
5. **New in v0.10:** cart builder — Y4's `payments/` (proposed) or Y3's `agent/`?
6. **New in v0.10:** may the concierge switch category packs mid-conversation?
   (Proposed: **no** — a switch is a new session.)
7. **New in v0.11:** does the mock issuer ACS live in `payments/` as its own router with its own
   store (proposed — it must be able to refuse *us*), or as a separate top-level module?
8. **New in v0.11:** do we accept landing at **~56 h with no buffer**, or drop something further?
   This is a scope call, so by `team.md` it's a majority vote, tie to Y4 — not Y4's alone.
