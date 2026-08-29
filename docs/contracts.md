# Interface contracts — DRAFT until frozen by the Y4 at the first huddle

**Status: DRAFT v0.9** — proposed by KICKOFF (Claude Code / Aryan, T+0:35). The Y4/architect
freezes v1 at the first huddle (~T+1). After freeze: changing anything here requires the Y4's OK +
a message in the team chat + a bump of the version line. Parallel work touches other members'
modules **only** through what is written here — that is the whole point of this file.

Version: **v0.9 (unfrozen)** · Project: *Agent-Ready Commerce* (working name)

---

## Module split & owners

| Directory | Owns | Member |
|---|---|---|
| `payments/` | mock Visa stack: token vault, authorize/capture, mandate chain, TAP signature verification, trust events | **Y4** |
| `agent/` | LLM orchestration, tools, category packs, agent-side signing, demo-mode fallback | **Y3** |
| `web/` | chat widget, trust panel, merchant console (Vite + React + Tailwind) | **Y2** |
| `merchant/` | catalog ingest, merchant registry, discovery/search API, merchant config + embed snippet | **Aryan** |
| `app/` | FastAPI entrypoint, router mounting, middleware wiring, DB session, settings | **Aryan** (shared — PRs, not direct pushes, after freeze) |
| `seed/`, `demo/`, `docs/`, `Makefile` | seed catalogs, demo script, ops | **Aryan** |

**One process, three routers.** `uvicorn app.main:app` mounts `agent`, `merchant` and `pay` routers
on **:8000**; the web app runs on **:5173**. Rationale: walking-format judging needs a cold start in
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
  "stock": 12
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
| POST | `/merchant/{id}/catalog` | multipart CSV **or** `{products:[Product]}` | `{ingested:int, skipped:int, errors:[{row,reason}]}` | 400 `BAD_CATALOG`, 404 `NO_MERCHANT`, 413 `TOO_LARGE` |
| GET | `/merchant/{id}/config` | — | `{merchant_id,name,size,category,currency,persona,policies}` | 404 |
| PUT | `/merchant/{id}/config` | partial config | updated config | 400, 404 |
| GET | `/merchant/{id}/snippet` | — | `{snippet:"<script src=…></script>"}` | 404 |
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
| POST | `/pay/authorize` | `{token_id, payment_mandate_id, amount_cents, currency, merchant_id}` | `{status:"approved", transaction_id, auth_code, amount_cents}` **or** `{status:"declined", decline_code, reason}` | 400 · **never 5xx for a business decline** |
| POST | `/pay/capture` | `{transaction_id}` | `{status:"captured", captured_at}` | 404, 409 `NOT_AUTHORIZED` |
| GET | `/pay/receipt/{transaction_id}` | — | `{transaction_id, merchant, items[], total_cents, currency, last4, auth_code, at}` | 404 |
| GET | `/trust/events?session_id=` | SSE | stream of `TrustEvent` | 404 |

*Payment routes require `tag=agent-payer-auth`. A payer-auth route presented with a browser-auth
signature is a hard reject — that distinction is part of the pitch.*

**Decline codes (closed set — Y2 renders these, Y3 handles them, don't invent new ones):**
`AMOUNT_EXCEEDS_MANDATE` · `MANDATE_EXPIRED` · `MERCHANT_MISMATCH` · `CART_HASH_MISMATCH` ·
`TOKEN_REUSED` · `TOKEN_REVOKED` · `SIGNATURE_INVALID` · `NONCE_REPLAY` · `HUMAN_NOT_PRESENT` ·
`INSUFFICIENT_FUNDS` (simulated, for realism).

### `agent/` — owner Y3

| Method | Path | Request | Response | Errors |
|---|---|---|---|---|
| POST | `/agent/session` | `{merchant_id?, category?, consumer_id, budget_cents?}` | `{session_id, intent_mandate_id, greeting}` | 400, 404 |
| POST | `/agent/message` | `{session_id, text}` | **SSE** stream of `{type, data}` | 400, 404, 429 |
| POST | `/agent/confirm` | `{session_id, cart_mandate_id, confirmation:{method,assertion?}}` | `{status, transaction_id?, receipt?, decline_code?}` | 400, 404, 409 |

**SSE event types from `/agent/message`** (Y2 must handle every one, including unknown types —
ignore gracefully):
`token` (text delta) · `product_cards` `{products:[Product]}` · `comparison` `{dimensions[], rows[]}` ·
`cart` `{cart_mandate_id, items[], total_cents, currency}` · `confirm_request`
`{cart_mandate_id, preview:{merchant, items[], total_cents, currency, last4}}` ·
`receipt` `{…}` · `declined` `{decline_code, reason}` · `error` `{code, message}` · `done`.

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
3. Do we keep `/pay/capture` separate, or auto-capture on authorize for demo simplicity?
   (Draft keeps it separate — it's 15 minutes and it looks like a real payment stack.)
