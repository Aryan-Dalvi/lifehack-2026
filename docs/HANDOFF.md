# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot

- **When:** **T+27:30** (Sun 30 Aug 2026, 14:30 SGT) · **Author:** Aryan / Codex desktop
- **Git:** `main` and `origin/main` are both at **`ae6b781`** after a five-commit fast-forward.
  Tracked files are clean. The only local residue is untracked **`.agents/`**, which was not
  inspected, staged or altered by this refresh.
- **Verified now, not inherited:** **210 pytest pass** in 11.87 s; Ruff clean; TypeScript clean;
  Vite production build clean (1,604 modules, 662 ms); `git diff --check` clean. The unauthenticated
  GitHub URL returned **HTTP 200**, so the repository is publicly reachable.
- **Not verified now:** the full Playwright suite, a live OpenAI turn, a live Visa sandbox
  authorization, SMTP delivery, any hosted deployment, the Devpost submission, or the actual demo
  video URL. These are not implied by code or screenshots.
- **Local runtime posture:** `.env` exists on Aryan's Mac with `DEMO_MODE=0`, an OpenAI key
  configured, model `gpt-4.1`, `PAYMENT_ADAPTER=simulator`, incomplete Visa sandbox configuration,
  and no SMTP host. The pytest suite remained hermetic because `tests/conftest.py` forces demo mode
  and the simulator.

### Event clock — reconstructed because `docs/timeline.md` and `docs/event.md` remain absent

| When | T+ | Recorded event | Status at this snapshot |
|---|---:|---|---|
| Sun 08:00 | T+21 | Feature freeze | passed by 6 h 30 m |
| Sun 09:00–09:45 | T+22 | Backup recording window | passed; only a thumbnail is in the repo |
| Sun 09:45–10:00 | T+22:45 | Public repo / licence / secret scan | repo public; licence and scan evidence absent |
| Sun 11:00 | T+24 | Devpost lock | passed by 3 h 30 m; submission status not recorded |
| Sun 12:00–14:30 | — | Walking judging, COM3 MPH | ending at snapshot time |
| Sun 15:00–16:15 | — | Closing ceremony; attendance required to win | begins in 30 minutes |

The schedule above survives from earlier handoffs, not a current organiser feed. Confirm it in the
organisers' channel before acting on any remaining event timing.

## Project one-liner

**Sway** is a self-service conversational commerce platform for Visa's *“Conversational Commerce
Agents for Every Merchant”* problem statement. Any skincare merchant can register, turn a
CSV/XLSX/JSON catalog plus optional product images into a grounded hosted storefront or one-line
widget, and operate the result through a tenant-scoped CRM. Shoppers discover, compare, set a
spending limit, review a server-priced cart, consent, complete issuer-style OTP verification, and
receive an auditable receipt without leaving the experience.

Payments default to a clearly labelled simulator—**no real card is charged**; OTP `492118`. An
optional VisaNet Connect sandbox adapter exists behind `PAYMENT_ADAPTER=visa` but is not configured
or live-verified on this machine. The payment path is deterministic, Ed25519-signed and TAP-shaped;
the model never calculates prices, authorizes payments or creates orders.

## Direction & why

Direction **A** from `docs/brief.md` §4 remains shipped: one complete discover → decide → pay
thread, plus merchant self-service and post-launch CRM. Cross-merchant concierge was rejected to
avoid basket splitting and settlement; voice-first was rejected as fragile in a noisy venue.

Scope remains one category (**skincare**) with `agent/packs/skincare.json` as the only populated
pack. Mysa Skin is the seeded demonstration merchant, not a hardcoded tenant.

The governing rule remains: **facts travel through deterministic code; only phrasing travels
through a model; no model runs from cart creation downward.** The CRM extends the same rule by
rejecting model rewrites that introduce any figure not present in the deterministic report.

## Stack & repo map

Python 3.11+ / FastAPI / SQLite · React 19 / Vite / TypeScript · `uv` / `pyproject.toml`.

| Path | What |
|---|---|
| `app/` | FastAPI entrypoint and settings; mounts agent, merchant, catalog, consumer, bank, pay and trust routers |
| `agent/` | Orchestration, interpreter, recommender, adviser, Guardian and the skincare category pack |
| `merchant/` | Registry, consumer identity, catalog parsing/mapping/cleaning, diagnostics, image ZIP handling, template export, search, **and `insights.py` / `insights_summary.py` (the CRM)** |
| `payments/` | Server-priced cart, mandates, mock issuer/ACS, **`visa_client.py` (real VisaNet Connect adapter)**, Ed25519 signing, authorization and trust log |
| `web/src/features/` | Landing, shopper/storefront and merchant surfaces (`MerchantAdmin` = onboarding, `MerchantDashboard` = CRM) |
| `web/public/` | Embeddable `widget.js`, widget demo, product media and the official local Visa Brand Mark |
| `seed/`, `scripts/`, `tests/` | Deterministic reset/seed, **`demo_history.py`**, local runners and regression suites |
| `demo-site/` | Standalone mock merchant website with the live Sway widget tag; still targets local port 5173 |
| `docs/screenshots/` | Three live product captures embedded by README |
| `outputs/` | Submission/video assets, including `sway-video-thumbnail.png` |
| `outputs/01a04c55-.../` | Three tracked workbooks: `skincare-catalog-template.xlsx`, `sigi-skin-unclean-catalog.xlsx`, clean control `sigi-skin-clean-control.xlsx` |
| `var/` | Local databases, generated merchant key and Ed25519 key; gitignored |

Primary local surfaces: `/storefront?merchant=<id>`, `/admin` (CRM dashboard), `/admin/setup`
(onboarding), `/widget-demo.html`, and the widget snippet generated in setup. No hosted product URL
is recorded. Public source: `https://github.com/Aryan-Dalvi/lifehack-2026`.

## State

### Done and verified on `origin/main` (`ae6b781`)

- **Merchant platform:** self-service registration, remembered-store gate, tenant-scoped setup,
  canonical workbook download, CSV/XLSX/JSON staging, deterministic mappings and diagnostics,
  optional image ZIPs, publishing, branding, hosted storefront and one-line widget.
- **Merchant CRM:** `/admin` is the live dashboard; `/admin/setup` is onboarding. Revenue,
  customers, orders, conversion, forecast, tasks and product management are computed from that
  merchant's live rows. Numeric model rewrites are rejected if they introduce a new figure.
- **Shopper journey:** anonymous browsing and category tables, general questions, grounded
  recommendations, routines, details and comparison; persistent cart; optional spend limit; real
  card entry with only brand/last-four metadata retained; address creation; exact consent; OTP;
  authorization; receipt and optional SMTP/demo-outbox delivery.
- **Trust and payment:** server pricing, AP2-shaped signed mandates, cart/address binding,
  issuer-style single-use token, TAP-shaped HTTP signature verification, idempotency/replay
  protection, persistent Trust Rail, safe simulator by default and optional VisaNet Connect adapter.
- **Isolation and security:** merchant, consumer and session credentials are separate; catalog,
  products, carts, receipts and dashboard data are tenant/session scoped; route authorization,
  unpublished-catalog isolation, credential throttling and 12-hour sessions are regression-tested.
- **Widget:** cross-origin branded launcher, lazy iframe, backdrop and keyboard closing, duplicate
  protection, mobile full-bleed layout and failure fallback. `demo-site/index.html` is a standalone
  merchant host for it.
- **Release presentation:** expanded product README, three live screenshots, video thumbnail,
  standalone demo site, official Visa Brand Mark, and corrected `/agent/confirm` contract.
- **Verification at this handoff:** 210 pytest, Ruff, TypeScript and Vite production build all green.

### In progress / working tree

- No tracked implementation is in progress and no working branch needs rescue.
- Untracked `.agents/` is local tooling/configuration and was deliberately left out of Git.
- `origin/aryan/crm-dashboard` is fully merged into `main`; the remote branch is now historical.
- `origin/codex/catalog-cleaner-agent` remains unmerged and uniquely carries
  `docs/task3-sample-data.md`; decide whether that provenance is worth recovering before deleting it.

### Open defects and release risks

- **P0 — submission evidence absent after the lock.** No Devpost URL/status or actual video URL is
  recorded. `outputs/sway-video-thumbnail.png` proves only that a thumbnail exists. A human must
  confirm the submission was accepted and archive the links.
- **P1 — current Playwright suite not rerun.** There are 27 specs. The last recorded complete run
  was 27/27 before the header and Visa-logo edits; those edits were checked directly in the in-app
  browser. The shell runner on this Mac is blocked because `playwright.config.ts` hardcodes the
  absent Microsoft Edge channel.
- **P1 — release hygiene incomplete.** The repository is public, but no `LICENSE`/`LICENCE` file or
  evidence of a current-tree plus full-history secret scan exists. No release tag exists either.
- **P1 — demo-site broken media.** `demo-site/index.html` references Unsplash image
  `photo-1608248597359-00f72f88320e`, confirmed **HTTP 404** in this refresh. The page also depends
  on network fonts/images and points its widget at local port 5173; it is a local fixture, not a
  deployable offline backup.
- **P2 — live integrations remain unproved.** Local OpenAI mode is enabled with `gpt-4.1`, but was
  not exercised in this refresh. Visa configuration is incomplete and the adapter has only
  unit/mock coverage. SMTP is unconfigured; receipts go to the demo outbox.
- **P2 — no hosted product deployment.** Only local URLs and the public source repository are
  recorded. The committed app has broad demo CORS and one-click demo-store access enabled by
  default; do not treat it as production-safe.
- **P2 — coordination documents remain absent.** `docs/tasks.md`, `docs/timeline.md`,
  `docs/event.md`, `docs/team.md` and `docs/agent-workflow.md` were deleted earlier. The handoff is
  the only live coordination record and organiser facts are not independently transcribed.
- **Known prototype trade-offs:** in-process throttles, seven-day non-rotating consumer tokens,
  no merchant-key rotation, registration email-existence disclosure, wide CORS, SQLite, and a
  redundant gated `POST /pay/consent`. See `docs/security.md`.

### Branches and authorship

| Branch | State |
|---|---|
| `origin/main` @ `ae6b781` | current demo; 210 pytest, Ruff/TypeScript/Vite clean |
| `origin/aryan/crm-dashboard` | merged into `main`; safe to archive after team confirmation |
| `origin/codex/catalog-cleaner-agent` @ `8ccd879` | unmerged; provenance doc may still be unique |

`git shortlog` on `origin/main`: Nam Nguyen 38 · Aryan 30 across two identities · Glen Han 11
across two identities.

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
- 2026-08-30 T+15:28 · The CRM dashboard was integrated into `main` (`9abc155`) and its live,
  tenant-scoped routes became the canonical `/admin` experience.
- 2026-08-30 T+15:58–16:17 · Tenant-scoped product management, table controls and their regression
  tests landed (`a30ec21`…`954ca9a`).
- 2026-08-30 T+17:04 · Shopper checkout expanded (`8830278`) with real card entry while retaining
  only brand/last-four metadata, emailed or demo-outbox receipts, a browsable catalog and merchant
  logo support.
- 2026-08-30 T+17:40 · One-click demo/remembered-store access was added to the admin gate
  (`3a6fa81`). It is a demo convenience and must be disabled before serving real merchant data.
- 2026-08-30 T+18:26 · The embeddable widget gained cross-origin, mobile and merchant-brand fixes
  (`717d7be`).
- 2026-08-30 T+22:11–22:20 · Shopper UX merges and an honest empty-store state removed the last
  hardcoded Mysa presentation (`d3b24da`, `51f90ab`, `462cf0d`).
- 2026-08-30 T+23:08–23:41 · The `/agent/confirm` `cart_id` contract was corrected, the header's
  switch-store control was aligned, and the placeholder card mark was replaced with the official
  local Visa Brand Mark (`6eeb841`, `cd254a7`, `65a4188`).
- 2026-08-30 T+24:03–24:28 · Submission presentation assets landed: video thumbnail, expanded
  README, standalone demo site and three live screenshots (`f3e0922`…`ae6b781`). No Devpost or
  actual video URL was recorded with them.
- 2026-08-30 T+27:30 · Handoff truth gate: 210 pytest, Ruff, TypeScript and Vite production build
  are green; public repository access is independently verified. Current E2E, live integrations,
  hosted deployment and submission acceptance remain unverified.

## How to run & test

```bash
git clone git@github.com:Aryan-Dalvi/lifehack-2026.git
cd lifehack-2026
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
npm --prefix web ci

# Safest deterministic demo posture: omit .env, or set DEMO_MODE=1 and
# PAYMENT_ADAPTER=simulator before starting.
./.venv/bin/python -m seed.reset
./.venv/bin/python -m scripts.dev
```

Primary surfaces are `http://localhost:5173/`, `/storefront?merchant=m_mysa`, `/admin`,
`/admin/setup`, `/widget-demo.html`, and API docs at `http://127.0.0.1:8000/docs`. The seeded
issuer OTP is **`492118`**. `demo-site/index.html` may be served from a second origin to exercise the
widget, but it still requires the Vite/API stack and its hero image is currently broken.

```bash
# Fast local gate
./.venv/bin/python -m ruff check app agent merchant payments seed scripts tests
./.venv/bin/python -m pytest -q
npm --prefix web run build

# Full browser gate: start the app first, then run in a second shell.
npm --prefix web run test:e2e
```

Current gate: **210 pytest pass**; Ruff, TypeScript and Vite production build are clean. The 27
Playwright specs were not rerun at this snapshot: `playwright.config.ts` hardcodes Microsoft Edge,
which is absent on this Mac. Either run them on a machine with Edge or make the browser channel
portable and rerun the entire suite before claiming E2E green.

The interactive shell on Aryan's Mac does not expose `node` or `npm`. Codex desktop's bundled
runtime can still type-check and build:

```bash
/Users/aryan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  web/node_modules/typescript/bin/tsc -b web
/Users/aryan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  web/node_modules/vite/bin/vite.js build web
```

## Env & secrets

Names only. Values belong in a local, gitignored `.env`; never commit or print them.

Named in `.env.example`: `OPENAI_API_KEY`, `OPENAI_MODEL`, `DEMO_MODE`, `DEMO_MERCHANT_KEY`,
`DEMO_CONSUMER_PASSWORD`, `PAYMENT_ADAPTER`, `VISA_API_BASE_URL`, `VISA_ENDPOINT_PATH`,
`VISA_SSL_CERT_PATH`, `VISA_SSL_PRIVATE_KEY_PATH`, `VISA_CA_BUNDLE_PATH`, `VISA_API_USERNAME`,
`VISA_API_PASSWORD`, `VISA_MLE_KEY_ID`, `VISA_MLE_PRIVATE_KEY_PATH`,
`VISA_MLE_ENCRYPT_CERT_PATH`, `VISA_CLIENT_ID`, `DEMO_LOGIN_ENABLED`, `DEMO_MERCHANT_ID`,
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`,
`RECEIPT_FROM_EMAIL`, and `RECEIPT_FROM_NAME`.

Also accepted by the app or development tooling: `DATABASE_PATH`, `ISSUER_DATABASE_PATH`,
`AGENT_PRIVATE_KEY_PATH`, `AGENT_KID`, `SIGNATURE_ENFORCE`, `API_BASE_URL`,
`CATALOG_IMAGE_BASE_URL`, `WEB_BASE_URL`, `MERCHANT_HARD_CEILING_CENTS`,
`RECEIPT_OUTBOX_PATH`, `VITE_API_BASE`, `API_PROXY_TARGET`, `WEB_PORT`, and
`PLAYWRIGHT_BASE_URL`.

The shared OpenAI key comes from the team group chat. Visa sandbox credentials and certificates are
secrets of the same class; obtain them from the Visa portal and keep certificate/key files outside
Git. SMTP credentials come from the selected mail provider. Signing material defaults to
gitignored `var/agent-ed25519.pem`; reset emits a demo merchant key into gitignored
`var/merchant-key.txt`.

Safe local inspection at this snapshot found `.env` with an OpenAI key configured, `gpt-4.1`,
`DEMO_MODE=0`, simulator payments, incomplete Visa settings and no SMTP configuration. No values
were printed. Pytest overrides this with deterministic demo/simulator settings. Starting the app
with the current local `.env` can make paid OpenAI calls. A hosted instance must set
`DEMO_LOGIN_ENABLED=0`, narrow CORS and rotate any credential that may ever have appeared in Git;
public visibility makes a full-history secret scan mandatory.

## API credit spend

- **No model API calls were made during this handoff refresh.** Tests were hermetic.
- The previous estimate of **well under $5 of the $50 grant** is stale and unverified against the
  provider dashboard. Actual spend and remaining demo reserve are unknown.
- The local app is configured for `DEMO_MODE=0` and `gpt-4.1`; starting it can spend credit. A human
  with account access must check the dashboard and record the actual total before another live run.

## Next 3 actions

At **T+27:30**, the recorded judging window has just ended and the recorded closing ceremony begins
in 30 minutes. These are recommendations; the team and Y4 decide.

1. **By 14:40 (10 min) — archive submission proof** *(owner: team lead; human-only)*. Confirm the
   Devpost entry is accepted, copy its public URL, actual video URL and submission timestamp into
   this handoff, and verify the registered team. If anything is absent, escalate to the organisers
   immediately; the recorded lock was 3 h 30 m ago.
2. **By 15:00 (20 min) — freeze the demo artifact and attend closing** *(owner: Y4 + one member)*.
   Preserve `ae6b781`, the public repository URL and the working local demo; do not make risky
   release changes before the ceremony. Confirm the organiser schedule/channel and get the required
   team members to the 15:00 closing.
3. **After closing, time-box 60 min — close release evidence and harden** *(owner: infra/test)*.
   Run the 27 E2E specs on a clean clone with Edge or a portable Playwright channel; archive a
   current-tree plus full-history secret-scan result; decide and add a licence if appropriate; fix
   the demo-site 404/local-only dependency; and disable demo login/narrow CORS on any hosted copy.

## Open questions

- Was the Devpost entry accepted? What are its public URL, actual video URL and submission time?
- Has the full-history secret scan been completed, and did the team intentionally ship without a
  `LICENSE` file or release tag?
- Has anyone run the Visa adapter against the real sandbox, or only its unit/mock coverage? Will
  any further demo use the proven simulator or attempt the unproved live path?
- What is the actual OpenAI spend and remaining reserve? Is `gpt-4.1` the frozen demo model?
- Is there a hosted product URL, or is the deliverable intentionally local plus public source?
- Should Playwright keep requiring Microsoft Edge, or use bundled Chromium for portable release
  verification?
- Were the task board, timeline, event facts, roster and agent workflow deleted deliberately? If
  yes, where does the live submission checklist live now?
- Does `docs/task3-sample-data.md` on `origin/codex/catalog-cleaner-agent` hold provenance worth
  recovering before that branch is retired?
- Should local `.agents/` remain untracked, or is any part of it intended as team-owned workflow?
