# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot

- **When:** **T+15:00** (Sun 30 Aug 2026, 02:00 SGT) · **Author:** Claude Code / Aryan
- **`origin/main` is at `835d1f9`.** It moved **5 commits** during this session — multi-merchant
  signup, shopper address creation, a real VisaNet Connect adapter and a `CLAUDE.md` trim all
  landed while the CRM dashboard was being built. Read "Integration state" before merging anything.
- **Verified this refresh, not taken on trust:** `origin/main` **133 pytest pass** in a clean
  worktree; `origin/main` Ruff **red** on one unused import; branch `aryan/crm-dashboard`
  **135 pytest pass**, **Ruff clean**, **TypeScript clean** under `tsconfig.app.json` options;
  the two new API routes exercised over HTTP for auth, tenancy and validation.
- **Not verified this refresh:** Vite production build, Playwright. **Node/npm is not installed on
  Aryan's Mac** (see "How to run & test") — neither can run here at all.
- **Deployment:** local only. No deployed URL exists in the repo. `gh` is not installed on this
  host, so repository visibility still could not be independently checked; the prior handoff
  recorded it as private.

### ⏰ Deadlines — restated because `docs/timeline.md` and `docs/event.md` are still absent

| When | T+ | What | From snapshot |
|---|---:|---|---:|
| **Sun 08:00** | **T+21** | **FEATURE FREEZE. Unmerged work dies.** | **6 h 00 m** |
| Sun 09:00–09:45 | T+22 | Record the backup demo video while the build is known-good | 7 h 00 m |
| Sun 09:45–10:00 | T+22:45 | Make repo public; confirm licence and secret scan | 7 h 45 m |
| **Sun 11:00** | **T+24** | **Devpost form locks** — target submission by 10:40 | **9 h 00 m** |
| Sun 12:00–14:30 | — | Walking judging, COM3 MPH; expect repeated demos | — |
| Sun 15:00–16:15 | — | Closing ceremony; attendance required to win | — |

Staggered rest shifts were scheduled from 23:00 and should be well underway. These timings
survive only in this file and in git history; verify against the organisers' channel before
relying on them.

## Project one-liner

**Sway** is a plug-and-play conversational commerce agent for the Visa problem statement
*"Conversational Commerce Agents for Every Merchant."* **Any merchant can now sign up**, download a
canonical Excel template, upload CSV/XLSX/JSON catalog data and an optional image ZIP, review
deterministic cleaning diagnostics, publish a grounded hosted storefront or widget — and then work
out of a **CRM dashboard** built from their own trading data. A shopper can discover products,
compare them deterministically, set a spend limit, add a shipping address, preview a
**server-priced** cart, consent explicitly, complete a mock-bank OTP challenge, and receive an
auditable receipt.

Payments default to a simulator and are labelled as such — **no real card is charged**; simulator
OTP `492118`. A **real VisaNet Connect sandbox adapter now exists** behind
`PAYMENT_ADAPTER=visa` and is off by default. Either way the request is Ed25519-signed and checked
as a TAP-shaped HTTP Message Signature, and **the model never authorizes a payment, calculates a
price, or creates an order.**

## Direction & why

Direction **A** from `docs/brief.md` §4: demonstrate one complete discover → decide → pay thread.
Direction B (cross-merchant concierge) was rejected because it adds basket splitting and
settlement; direction C (voice-first) was rejected because a noisy walking-judging venue makes it
fragile.

Scope is one category (**skincare**) with `agent/packs/skincare.json` as the only populated pack.
The demo merchant is Mysa Skin, but the product is no longer single-tenant: merchants self-serve.

The core control rule is unchanged and now also governs the dashboard: **facts travel through
deterministic code; only phrasing travels through a model; no model runs from cart creation
downward.**

## Stack & repo map

Python 3.11+ / FastAPI / SQLite · React 19 / Vite / TypeScript · `uv` / `pyproject.toml`.

| Path | What |
|---|---|
| `app/` | FastAPI entrypoint and settings; mounts agent, merchant, catalog, consumer, bank, pay and trust routers |
| `agent/` | Orchestration, interpreter, recommender, adviser, Guardian and the skincare category pack |
| `merchant/` | Registry, consumer identity, catalog parsing/mapping/cleaning, diagnostics, image ZIP handling, template export, search, **and `insights.py` / `insights_summary.py` (the CRM)** |
| `payments/` | Server-priced cart, mandates, mock issuer/ACS, **`visa_client.py` (real VisaNet Connect adapter)**, Ed25519 signing, authorization and trust log |
| `web/src/features/` | Landing, shopper/storefront and merchant surfaces (`MerchantAdmin` = onboarding, `MerchantDashboard` = CRM) |
| `web/public/` | Embeddable `widget.js` and `widget-demo.html` |
| `seed/`, `scripts/`, `tests/` | Deterministic reset/seed, **`demo_history.py`**, local runners and regression suites |
| `outputs/01a04c55-.../` | Three tracked workbooks: `skincare-catalog-template.xlsx`, `sigi-skin-unclean-catalog.xlsx`, clean control `sigi-skin-clean-control.xlsx` |
| `var/` | Local databases, generated merchant key and Ed25519 key; gitignored |

Primary local surfaces: `/storefront?merchant=<id>`, `/admin` (CRM dashboard), `/admin/setup`
(onboarding), and the widget snippet generated in setup.

## State

### Done and verified on `origin/main` (`835d1f9`)

- `GET /health` → 200 `{"status":"ok","category":"skincare","payment_mode":"simulator"}`.
- **133 pytest pass** in a clean worktree (after installing the new `joserfc` dependency).
- **Multi-merchant is live** (`5934226`): `GET /merchant/me` resolves the caller from their key,
  the admin page serves any merchant rather than a hardcoded one, and `catalog_search` now
  **requires** a `merchant_id` instead of defaulting to `m_mysa`.
- **Shoppers can add a shipping address** (`d2f3759`) — `POST /consumer/{id}/addresses` plus an
  `AddressPrompt` surface. This closed a real dead end in checkout.
- **Real VisaNet Connect authorization adapter** (`c4a270c`, `payments/visa_client.py`): mutual
  TLS, Basic auth, JWE message-level encryption, authorization only. `PAYMENT_ADAPTER` defaults to
  `simulator` and the module's own docstring says the request body shape is best-effort against
  Visa's schema rather than built from a verified OpenAPI spec. `tests/conftest.py` now forces
  `PAYMENT_ADAPTER=simulator` so the suite can never reach the network.
- Shopper flow end to end: discovery, deterministic comparison, spending limit, server-priced cart,
  explicit consent, OTP, authorization, receipt.
- Tenant/session boundaries, unpublished-catalog isolation, credential throttling, 12-hour sessions
  and route-authorization coverage — see `docs/security.md`, `docs/testing.md`.
- Catalog ingestion: canonical workbook download, deterministic versioned column mapping (no AI
  column mapping), staged cleaning with grouped diagnostics, validated image ZIPs.

### Done on branch `aryan/crm-dashboard` (`7ca79b8`, pushed, **not merged**)

The merchant CRM dashboard. Full write-up in **`docs/merchant-dashboard.md`**, which lives
**on that branch, not on `main`** — read it with `git show aryan/crm-dashboard:docs/merchant-dashboard.md`.

- `/admin` is the CRM dashboard, `/admin/setup` is onboarding; publishing navigates to the
  dashboard and a still-draft store is sent back to setup.
- `merchant/insights.py` computes every figure from that merchant's own `orders`, `carts`,
  `sessions`, `trust_events` and `products`. Nothing cached — a live checkout moves the numbers.
  Layout follows the CRM conventions NetSuite documents: three compared KPIs, one revenue trend
  with a labelled trailing-7-day forecast, a task list derived from live state, a customer table,
  and a performance panel. Every derived figure carries the denominator it was taken over.
- `merchant/insights_summary.py` answers "summarise any business content": deterministic keyword
  routing to one of seven reports, prose built from the computed figures, and a model rewrite that
  is **rejected unless every number in it is one it was handed** (`3,552.00` and `3552` normalise
  to the same figure).
- `seed/demo_history.py` gives the demo merchant 60 days of trading: deterministic, inert
  (historic sessions carry no token hash so none can be resumed), written once.
- 20 new tests in `tests/test_insights.py`. Also cleared the long-standing `F401` and replaced
  three `COUNT(*) FROM orders == 0` proxies in `test_api_flow.py` with session-scoped assertions.
- **135 pytest pass, Ruff clean, TypeScript clean.**

### Integration state — read before merging

`aryan/crm-dashboard` branched from `1e3ee54`, **before** the five commits above. A dry-run merge
(`git merge-tree origin/main aryan/crm-dashboard`) reports:

- **One conflicted file: `web/src/features/merchant/MerchantAdmin.tsx`.** Both sides edited it —
  main rewrote it for signup and `/merchant/me`, the branch added a Dashboard nav link and a
  post-publish redirect. Small, but it must be hand-resolved.
- `merchant/router.py` and `tests/test_api_flow.py` **auto-merge cleanly.**

Two things will be **silently wrong after a clean merge** — no conflict marker will point at them:

1. **`MerchantDashboard.tsx` hardcodes `/merchant/m_mysa/insights`.** With multi-merchant signup
   that is now the wrong store for everyone but Mysa. Fix: call `GET /merchant/me` first (as the
   rewritten `MerchantAdmin` does) and use the returned `merchant_id`. The backend is already
   correct — the routes are `assert_merchant`-guarded and tenant-scoped, and a test proves a new
   merchant sees zeroes rather than Mysa's trade.
2. **The dashboard footer asserts every authorization is simulated.** With `PAYMENT_ADAPTER=visa`
   that becomes false. Fix: render from the adapter setting / the `simulated` column, which the
   Visa path now writes as a bound parameter rather than a hardcoded `1`.

Neither is hard; both are about 20 minutes. Nothing else in the branch depends on tenancy.

### Open defects and release risks

- **P1 — the branch is unmerged with 6 hours to freeze.** It is the largest single piece of
  unlanded work. Decide to merge or drop it deliberately, not by running out of time.
- **P2 — new dependency breaks existing checkouts silently:** `joserfc>=1.0.0` was added to
  `pyproject.toml` for the Visa adapter. Without it **the entire pytest suite fails to collect**
  (9 collection errors, not a clear message). Anyone who pulls `main` must reinstall deps. It has
  been installed into Aryan's `.venv` on this machine.
- **P2 — Ruff is red on `origin/main`:** `tests/test_catalog_images.py:48` F401. Already fixed on
  `aryan/crm-dashboard`; merging clears it.
- **P2 — contract drift, now one-sided:** `docs/contracts.md:279` documents `/agent/confirm` with
  `cart_mandate_id`; the code (`ConfirmRequest`) has settled on `cart_id`. This is no longer a
  choice, just a stale doc line. `contracts.md` is Y4's file.
- **Playwright is unverified against everything since the catalog UI work**, and there are now two
  more specs (`multi-merchant.spec.ts`, plus the dashboard test added on the branch).
- **No local `.env`:** this machine runs deterministic `DEMO_MODE=1`; no live-model path was
  exercised. Code defaults to `gpt-5-mini`, `.env.example` says `gpt-4.1`; **the demo model is
  still not frozen.**
- **Local-path build trap:** this checkout's parent directory contains a literal `?`, which
  esbuild/Vite refuses. Use a checkout without `?` for any release rehearsal.
- **Release coordination is still missing:** `docs/tasks.md`, `docs/timeline.md`, `docs/event.md`,
  `docs/team.md` and `docs/agent-workflow.md` remain absent. There is still **no task board and no
  Devpost/README/licence/recording/secret-scan checklist**, and `AGENTS.md` still references
  deleted files.
- Security trade-offs unchanged: broad demo CORS, in-process throttles, 7-day non-rotating consumer
  tokens, no merchant-key rotation, email-existence disclosure at registration, a redundant gated
  `POST /pay/consent`. See `docs/security.md`.

### Branches

| Branch | State |
|---|---|
| `origin/main` @ `835d1f9` | green (133 pass), Ruff red on one import. **The demo.** |
| `origin/aryan/crm-dashboard` @ `7ca79b8` | pushed, green on its own base. One conflict + two tenancy fixes to land. See "Integration state". |
| `origin/codex/catalog-cleaner-agent` @ `8ccd879` | still unmerged. Uniquely carries `docs/task3-sample-data.md` and a stale handoff delta. Decide: recover the provenance doc, or abandon. |
| `origin/codex/t-02-walking-skeleton` | **deleted** since the last handoff — that open question is closed. |

Commit identities on `origin/main`: Nam Nguyen 22 · Aryan 17 · Glen Han 9 (+1 as "GlenHan").

## Decision log
- 2026-08-29 · Workspace created; dual-AI protocol (CLAUDE.md/AGENTS.md + prompts/) adopted.
- 2026-08-29 T+0:45 · **PS allocated: Visa — Conversational Commerce Agents for Every Merchant.**
- 2026-08-29 T+0:45 · KICKOFF recommends **Direction A**; MVP = discover→decide→pay in one thread by
  T+8; differentiator = TAP-shaped signatures + AP2-shaped mandate chain + a live declined
  over-budget purchase. *Recommendation only — the huddle decides.*
- 2026-08-29 T+0:45 · **Assumption A1: no real Visa sandbox** (portal needs project approval); we
  simulate and say so openly. Mentor question filed to check for on-site keys.
- 2026-08-29 T+0:45 · Architecture: single process / three routers, not three services — demo
  restartability beats microservice purity here.
- 2026-08-29 T+1:15 · **Revision 2, three changes** (Aryan's call, pending huddle):
  (a) consumer UX specified as plates C1–C8, with the spend-limit control in the greeting doubling
  as the Intent Mandate; (b) merchant onboarding cut from a 5-screen wizard to 3 sections on one
  page with a live preview; (c) `agent/` split into an orchestrator + 5 specialists with typed hops
  and a **Guardian** validator, packs instantiated per session so the wrong category's vocabulary is
  never in the context window. Net **+3 person-hours** (~50 → ~53 h).
- 2026-08-29 T+1:15 · Design rule adopted: **facts travel through code, only phrasing travels
  through a model; no model at all from the cart downward.** This is also the answer to "what if the
  AI hallucinates a price?" — it never touches one.
- 2026-08-29 T+1:15 · Cart builder moves from `agent/` to `payments/`; Guardian stays in `agent/`
  (one owner, one interface) and emits through Y4's existing trust bus — no contract change to
  `/trust/events`.
- 2026-08-29 T+1:45 · **Revision 3, four changes** (Aryan's call, pending huddle):
  (a) **5-star ratings** on every option, with the count beside the average;
  (b) **progressive disclosure** — minimal card → hover/focus/tap preview (≤4 salient features) →
  full spec table only on Compare; (c) **the issuer authenticates every purchase** — a mock ACS
  mints a single-use token bound to cart hash + amount + merchant, and `/pay/authorize` refuses
  without one; (d) **default shipping address** on the confirmation, ordered ship-to-first like a
  real checkout. Plates renumbered **C1–C9** (consent C5→C6, declined C8→C9).
- 2026-08-29 T+1:45 · **Assumption A6: ratings are a catalog field**, ingested from the merchant's
  feed and cached, with an enrichment hook that runs **at ingest only**. No rating is ever fetched
  at query time — a demo that needs venue wifi at 12:30 Sunday is a demo that fails. If a mentor
  offers a ratings API, it plugs into the hook.
- 2026-08-29 T+1:45 · **Real WebAuthn is cut** (−1.5 h) and replaced by the issuer token: a passkey
  proves the *device* is present, an issuer token proves the *bank* authenticated the cardholder for
  this amount. **Cross-merchant search also cut** (−1.25 h). Net +1 h → ~56 h, **buffer exhausted**.
- 2026-08-29 T+1:45 · The **shipping address is inside the signed `cart_hash`**, so an agent cannot
  redirect goods after consent — `SHIPPING_ADDRESS_MISMATCH`. Three refusals are now rehearsable:
  over-limit, replayed bank token, cart-or-address edited after approval.
- 2026-08-29 T+2:35 · **`docs/agent-workflow.md` added** — the flow as 22 steps across 6 phases,
  each with exact input, output, typed tool list, Guardian checks, failure codes and budgets.
  Pins two things that were only implied: Discovery/Comparison use **forced tool choice with strict
  schemas** (so "may emit only a query" is a mechanism, not an instruction), and **DEMO_MODE may
  stub language but never enforcement** — all four Guardian checks and all twelve authorize checks
  run with the network unplugged.
- 2026-08-29 T+2:35 · Module ownership closed: `/consumer/*` is Aryan's code in
  `merchant/consumer.py`; `/bank/*` is Y4's in `payments/` **with its own store** — the ACS has to
  be able to refuse us, or refusals R2/R3 are self-inflicted and prove nothing. Five routers, three
  modules.
- 2026-08-29 T+2:35 · ⚠️ **HANDOFF truth-check: the repo shows no huddle and no code at T+2:35.**
  All 35 tasks `todo`, `team.md` still has 4 `_fill_` placeholders, only branch is `main`. Planning
  is ~2 h ahead of the build; the build is ~1.5 h behind the timeline. Recorded here because the
  next window must not mistake a well-documented plan for progress.
- 2026-08-29 T+3:04 (Nam Nguyen) · **`docs/architecture-flowchart.md` added** — a detailed MVP
  decision aid narrowing the visible category to skincare-only, reducing the LLM topology to one
  required + one optional call, and formalizing the optional/versioned session spending-limit as a
  superseding Intent Mandate. Explicitly marked as a draft team decision aid, not a frozen contract;
  lists its own contract deltas still owed to `contracts.md` and a huddle freeze checklist (§16).
- 2026-08-29 T+3:15–3:42 (Aryan, Nam Nguyen) · **Cleanup pass deleted `samples/`,
  `docs/timeline.md`, `.claude/skills/lifehack-kickoff/`, `docs/agent-workflow.md`,
  `docs/event.md`, `docs/tasks.md`, `docs/team.md`.** No commit message states a reason. Net effect:
  the repo now has no task board, no team roster, no transcribed judging criteria, and no
  step-by-step agent spec. `README.md`/`AGENTS.md` still reference several of these paths and are
  now stale. **Flagged, not reversed** — this may be intentional; get it confirmed verbally before
  the next huddle so the next window isn't rebuilding files someone meant to retire.
- 2026-08-29 T+3:47 (Claude Code / Aryan) · Removed redundant `docs/research/.gitkeep` (dir was
  already non-empty). Refreshed this handoff to record the architecture doc and the deletions above.
- 2026-08-29 T+12:15 · **Handoff truth-check against real code** (previous refresh was T+3:47 and
  nine hours stale). Verified by running, not reading: API boots, `GET /health` → 200
  `{"status":"ok","category":"skincare","payment_mode":"simulator"}`; seven routers mounted
  (agent, merchant, catalog, consumer, bank, pay, trust).
- 2026-08-29 T+12:15 · ⚠️ **`.env` is missing on Aryan's machine**, so settings resolve to
  `demo_mode: True` — the live-LLM path is inert here and the agent runs deterministic-only.
  `var/` still holds `sway.db`, `issuer.db` and `agent-ed25519.pem` from 17:34, so only the key
  is absent. Restore before any live-model demo or test.
- 2026-08-29 T+12:15 · Model discrepancy logged: `app/settings` defaults to **`gpt-5-mini`**,
  `.env.example` says **`gpt-4.1`**, and the T+7:42 test pass ran **`gpt-4.1`**. Whichever we demo
  on is the one that must be re-tested — the 56-case pass does not transfer between models.
- 2026-08-29 T+12:15 · ⚠️ **Five docs were deleted from `main`** — `tasks.md`, `event.md` and
  `agent-workflow.md` in `29e1c20 "Clean up files"`, `timeline.md` in `c61c640`, `team.md` in
  `aecd5d2`. That removed the task board, the timeline with its checkpoints and slip rules, and the
  verified event facts. **The deadlines are restated in this file because it is now the only place
  they live.** Recover with `git checkout 29e1c20^ -- docs/tasks.md docs/event.md docs/agent-workflow.md`.
- 2026-08-30 T+13:37 · `80bc6ac` replaced AI column mapping with a canonical Excel template and
  deterministic aliases; image ZIP uploads now enter the live catalog immediately and are only
  public when attached to a published product.
- 2026-08-30 T+13:47 · `834a8c7` placed the template, unclean SIGI Skin sample and cleaned control
  workbook on `main` and pushed them to `origin/main`.
- 2026-08-30 T+13:52 · Fresh handoff gate: health 200, **115 pytest pass**, TypeScript and clean-path
  Vite production build pass; Ruff is red on one unused test import. `.env` remains absent, so no
  model call or API-credit spend occurred. Repo visibility could not be independently verified.
- 2026-08-30 T+14:01 · Concurrent `7f6f860` removed obsolete pre-event and AI-setup material from
  `README.md`. The handoff commit was rebased onto it without conflict; no teammate work was lost.
- 2026-08-30 T+14:20 (Nam Nguyen) · **`5934226` makes Sway genuinely multi-tenant**: any merchant
  can sign up, `GET /merchant/me` resolves a store from its API key, and `catalog_search` now
  *requires* a `merchant_id` instead of defaulting to `m_mysa`. The single-merchant assumption is
  formally dead — new code must resolve the caller, never assume Mysa.
- 2026-08-30 T+14:30 · **`c4a270c` adds a real VisaNet Connect authorization adapter**, superseding
  Assumption A1. Authorization only (no capture/refund/void — those need acquirer pre-approval we
  do not have), mutual TLS + Basic auth + JWE. **`PAYMENT_ADAPTER` defaults to `simulator` on
  purpose**: an unreachable or misconfigured sandbox must never silently become the demo's payment
  path. The request body is best-effort against Visa's schema; `_build_body` is the one place to
  correct if a live call is schema-rejected rather than declined.
- 2026-08-30 T+14:35 · `835d1f9` trimmed `CLAUDE.md`: the session-start ritual no longer asks a
  window to state its T+ time or announce which window it is, and the `KICKOFF` row is gone (the
  skill was deleted at T+3:15). `git pull` + read HANDOFF/log/tasks remains step 1.
- 2026-08-30 T+15:00 (Claude Code / Aryan) · **Merchant CRM dashboard built on
  `aryan/crm-dashboard`** (`7ca79b8`, pushed, unmerged). `/admin` is the dashboard, `/admin/setup`
  is onboarding. Design decision: **the dashboard reads live rows and computes on every request** —
  no metrics table, no cache — so a checkout completed during judging visibly moves the merchant's
  numbers, and there is no second copy of the truth to drift. The summary panel extends the
  facts-through-code rule with a numeric guardrail: a model rewrite is rejected unless every figure
  in it is one it was handed.
- 2026-08-30 T+15:00 · `seed/demo_history.py` adopted: a fresh database has no trading history, so
  the demo merchant would open on a wall of zeroes. The history is deterministic (same numbers in
  rehearsal and on stage), **inert** (historic sessions carry no token hash, so none can be resumed
  or spent against), and written once. Shaped so customers grow 10→14 while revenue slips ~9% —
  the pattern a dashboard exists to make visible.
- 2026-08-30 T+15:00 · Three assertions in `test_api_flow.py` used a global `COUNT(*) FROM orders
  == 0` as a proxy for "this flow created no order". Seeded history broke the shortcut; they now
  assert the real claim, scoped to the session under test. The pre-existing `F401` was also cleared.
- 2026-08-30 T+15:00 · ⚠️ **`joserfc` is a new hard dependency** (Visa adapter). Without it the
  whole pytest suite fails at *collection* with 9 import errors, which reads like a broken repo
  rather than a missing package. Anyone pulling `main` must reinstall dependencies.

## How to run & test

**Use a checkout whose path does not contain `?`** for anything involving Vite.

```bash
# one-time, and again after pulling main (joserfc is new)
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
npm --prefix web install

# deterministic local data and app
./.venv/bin/python -m seed.reset
./.venv/bin/python -m scripts.dev
```

Or the Makefile: `make dev`, `make api`, `make web`, `make reset`, `make keys`, `make test`,
`make build`.

**Known demo path.** Open `http://localhost:5173/storefront?merchant=m_mysa` and
`http://localhost:5173/admin`. Shopper: discover → compare → set/confirm spend limit →
server-priced preview → consent → bank OTP **`492118`** → receipt. Rehearse the three refusals too
(over-limit, replayed bank token, cart/address edited after approval). Merchant: sign up or paste
the key from `var/merchant-key.txt`, then setup → publish → dashboard.

```bash
curl -s http://127.0.0.1:8000/health
./.venv/bin/python -m ruff check .
./.venv/bin/python -m pytest -q
npm --prefix web run build
npm --prefix web run test:e2e   # app must be running; MERCHANT_KEY must be set
```

Current expectations:

- health: 200 with skincare/simulator payload;
- pytest: **133 pass on `origin/main`**, 135 on `aryan/crm-dashboard`;
- Ruff: **fails on `main`** at `tests/test_catalog_images.py:48 F401`; clean on the branch;
- frontend build and Playwright: **unverified since the catalog UI work** — see below.

> ⚠️ **Node and npm are not installed on Aryan's Mac.** `web/node_modules/` is populated, which is
> misleading: every binary in `.bin/` fails with `exec: node: not found`. So `npm run build`,
> `tsc -b` and `playwright test` **cannot run in that window at all** — they need a teammate's
> machine. TypeScript was instead type-checked there by driving the bundled compiler
> (`web/node_modules/typescript/lib/typescript.js`) from macOS's built-in JXA engine with a
> hand-built compiler host and the options from `web/tsconfig.app.json`; the harness was validated
> against a deliberate error before its clean result was trusted. **That is a type check, not a
> build** — the bundle and the e2e specs still need a real Node run before freeze.

## Env & secrets

Names only. Values belong in a local, gitignored `.env`; never commit or print them.

Named in `.env.example`: `OPENAI_API_KEY`, `OPENAI_MODEL`, `DEMO_MODE`, `DEMO_MERCHANT_KEY`,
`DEMO_CONSUMER_PASSWORD`.

**New and not yet mirrored in `.env.example`** (Visa adapter): `PAYMENT_ADAPTER`,
`VISA_API_BASE_URL`, `VISA_ENDPOINT_PATH`, `VISA_SSL_CERT_PATH`, `VISA_SSL_PRIVATE_KEY_PATH`,
`VISA_CA_BUNDLE_PATH`, `VISA_API_USERNAME`, `VISA_API_PASSWORD`, `VISA_MLE_KEY_ID`,
`VISA_MLE_PRIVATE_KEY_PATH`, `VISA_MLE_ENCRYPT_CERT_PATH`. **`.env.example` should be updated** —
that file's owner is the infra owner.

Also accepted by the code: `DATABASE_PATH`, `ISSUER_DATABASE_PATH`, `AGENT_PRIVATE_KEY_PATH`,
`AGENT_KID`, `SIGNATURE_ENFORCE`, `API_BASE_URL`, `CATALOG_IMAGE_BASE_URL`, `WEB_BASE_URL`,
`MERCHANT_HARD_CEILING_CENTS`.

The shared OpenAI key comes from the team group chat. Visa sandbox credentials and certificates are
secrets of the same class — **certificate and key *paths* may be configured, but no certificate,
key or password may enter the repo**. Signing material defaults to the gitignored
`var/agent-ed25519.pem`; `make reset` emits a demo merchant key into gitignored
`var/merchant-key.txt`.

Before making the repo public, scan the current tree **and full history** for credentials — now
including Visa material — and inspect the actual visibility setting. Do not paste any matched value
into issues, docs or chat.

## API credit spend

- **No new API spend in this handoff.** `.env` is absent on this machine and everything ran under
  `DEMO_MODE=1`; the CRM summary path was exercised on its deterministic branch only.
- Previous estimate: **well under $5 of the $50 grant**. Still not verified against the provider
  dashboard — nobody has checked the real number yet.
- The demo model remains unresolved: code default `gpt-5-mini`, example env `gpt-4.1`. Freeze one,
  restore the key, then run only the highest-value live regression so spend stays bounded.
- **New cost class:** the Visa sandbox is not OpenAI spend, but it is a live external dependency
  with its own failure modes. Budget rehearsal time, not dollars.
- A human with account access must check the real spend and record it here.

## Next 3 actions

At **T+15:00** the feature-freeze window is **6 h 00 m**. Recommendations; the team and Y4 decide.

1. **Land or drop `aryan/crm-dashboard` by T+16:30** *(owner: Aryan; executor: Aryan-Codex or this
   window)*. Merge `origin/main` into the branch, resolve the single `MerchantAdmin.tsx` conflict,
   then apply the two tenancy fixes named in "Integration state" (resolve the merchant via
   `GET /merchant/me`; stop hardcoding "simulated" in the footer). Rerun Ruff + pytest, and get a
   real `npm run build` on a machine with Node. Merge only if green.
2. **Stand up the submission/release lane by T+16:00** *(owner: team lead + one awake member;
   human-only)*. There is still no checklist. One file, one owner and a hard time per line:
   Devpost fields, PS explanation, README/licence, secret + history scan (now including Visa
   material), repo-public flip, backup video, and a release checkout on a path without `?`.
   Do not wait for T+21.
3. **Full-stack verification pass on a Node machine by T+18:00** *(owner: whoever has Node;
   executor: their Codex)*. `npm --prefix web install` (deps moved), production build, and all
   Playwright specs including the two new ones. Then rehearse the whole demo — shopper thread, the
   three refusals, merchant signup → setup → publish → dashboard — and record what actually passed
   in `docs/testing.md`. **This is the only remaining unverified layer.**

## Open questions

- **Merge or drop the CRM dashboard?** It is 6 hours from freeze, green on its own base, and needs
  roughly 20 minutes of tenancy fixes plus one conflict resolution.
- Has anyone actually run the **Visa sandbox adapter against Visa**, or only its unit tests? Are
  real sandbox credentials in hand, and does the demo intend to use `PAYMENT_ADAPTER=visa` on
  stage or stay on the simulator? *(A1 is superseded but the live path is unproven.)*
- Which model will be demoed: `gpt-5-mini` or `gpt-4.1`? The chosen path still needs one bounded
  live safety/journey run.
- Who owns updating `.env.example` with the eleven new Visa variables?
- `docs/contracts.md:279` still documents `/agent/confirm` with `cart_mandate_id` while the code
  uses `cart_id`. Y4 owns that file — one-line fix.
- Were the task board, timeline, event facts, roster and agent workflow deleted deliberately? If
  yes, where does the live submission checklist live now?
- Is the GitHub repository private or public, who owns the visibility flip, and has the
  full-history secret scan been done?
- Does `docs/task3-sample-data.md` on `codex/catalog-cleaner-agent` hold provenance worth
  recovering, or should that branch be abandoned?
- Who can inspect the OpenAI account and record the real spend?
- Did the organisers publish judging criteria beyond the problem statement? `docs/event.md` is
  still absent, so nothing is transcribed.
