# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot

- **When:** **T+14:01** (Sun 30 Aug 2026, 01:01 SGT) · **Author:** Codex / Aryan
- **Baseline immediately below this handoff commit:** `7f6f860` on `main`, including the concurrent
  README cleanup fetched from `origin/main` and integrated without conflict.
- **Verified this refresh, not taken on trust:** API health 200; **115/115 pytest pass**; TypeScript
  compile passes; production Vite build passes from a normal temporary path; Ruff has one
  fixable unused-import failure. No live-model or Playwright run was made during this refresh.
- **Deployment:** local only. Repository visibility could not be independently checked on this
  host because `gh` is not installed; the prior handoff recorded it as private.

### ⏰ Deadlines — restated because `docs/timeline.md` and `docs/event.md` are absent

| When | T+ | What | From snapshot |
|---|---:|---|---:|
| **Sun 08:00** | **T+21** | **FEATURE FREEZE. Unmerged work dies.** | **6 h 59 m** |
| Sun 09:00–09:45 | T+22 | Record the backup demo video while the build is known-good | 7 h 59 m |
| Sun 09:45–10:00 | T+22:45 | Make repo public; confirm licence and secret scan | 8 h 44 m |
| **Sun 11:00** | **T+24** | **Devpost form locks** — target submission by 10:40 | **9 h 59 m** |
| Sun 12:00–14:30 | — | Walking judging, COM3 MPH; expect repeated demos | — |
| Sun 15:00–16:15 | — | Closing ceremony; attendance required to win | — |

The old timeline scheduled staggered 3-hour rest shifts from 23:00. At this snapshot they should
already be underway. These timings survive only in this handoff and git history; verify them
against the organisers' current channel before relying on them.

## Project one-liner

**Sway** is a plug-and-play skincare commerce agent for the Visa problem statement
*“Conversational Commerce Agents for Every Merchant.”* The demo merchant, **Mysa Skin**, can
download a canonical Excel template, upload CSV/XLSX/JSON catalog data and an optional image ZIP,
review deterministic cleaning diagnostics, then publish a grounded hosted storefront or widget.
A shopper can discover products, compare them deterministically, set a spend limit, preview a
**server-priced** cart, consent explicitly, complete a mock-bank OTP challenge, and receive an
auditable receipt.

Payment is clearly labelled as a simulator — **no real card is charged**; simulator OTP
`492118`. The payment request is still Ed25519-signed and checked as a TAP-shaped HTTP Message
Signature. **The model never authorizes a payment, calculates a price, or creates an order.**

## Direction & why

Direction **A** from `docs/brief.md` §4 is built: demonstrate one complete
discover → decide → pay thread. Direction B (cross-merchant concierge) was rejected because it
adds basket splitting and settlement; direction C (voice-first) was rejected because a noisy
walking-judging venue makes it fragile.

Scope is deliberately one category (**skincare**) and one polished demo merchant. The category-pack
mechanism exists at `agent/packs/skincare.json`, but no other category is populated. The core
control rule is: **facts travel through deterministic code; only phrasing travels through a model;
no model runs from cart creation downward.**

## Stack & repo map

Python 3.11+ / FastAPI / SQLite · React / Vite / TypeScript · `uv` / `pyproject.toml`.

| Path | What |
|---|---|
| `app/` | FastAPI entrypoint and settings; mounts agent, merchant, catalog, consumer, bank, pay and trust routers |
| `agent/` | Orchestration, interpreter, recommender, phraser, Guardian and skincare category pack |
| `merchant/` | Registry, consumer identity, catalog parsing/mapping/cleaning, diagnostics, image ZIP handling, template export and search |
| `payments/` | Server-priced cart, mandates, mock issuer/ACS, Ed25519 signing and verification, authorization and trust log |
| `web/src/features/` | Landing, shopper/storefront and merchant-admin surfaces |
| `web/public/` | Embeddable `widget.js` and `widget-demo.html` |
| `seed/`, `scripts/`, `tests/` | Deterministic reset/seed, local runners and regression suites |
| `outputs/01a04c55-25c7-7382-9ab7-43cc8b274ec6/` | Three tracked workbook artifacts: `skincare-catalog-template.xlsx`, `sigi-skin-unclean-catalog.xlsx`, and clean control `sigi-skin-clean-control.xlsx` |
| `var/` | Local databases, generated merchant key and Ed25519 key; gitignored |

Primary local surfaces: `/storefront?merchant=m_mysa`, `/admin`, and the widget snippet generated
in admin. There is no deployed URL recorded in the repository.

## State

### Working and freshly verified

- `GET /health` returns 200 with
  `{"status":"ok","category":"skincare","payment_mode":"simulator"}`.
- Backend regression suite: **115 passed in 4.06 s** using temporary SQLite databases and
  `DEMO_MODE=1`.
- Frontend TypeScript compile passes. The production Vite build passes from a clean temporary path:
  1,594 modules, 63.84 kB CSS and 286.78 kB JS, built in 591 ms.
- Shopper flow exists end to end: discovery, deterministic comparison, spending limit,
  server-priced cart, explicit consent, OTP, authorization and receipt.
- Tenant and session boundaries, unpublished-catalog isolation, credential throttling, 12-hour
  sessions and route-authorization coverage are implemented and documented in
  `docs/security.md` and `docs/testing.md`.
- The earlier medical-safety P1 is **closed**: the Guardian uses a shared word-boundary policy;
  matcher/API cases and the scripted demo safety boundary were later recorded green.
- The earlier no-results/jargon issue is **closed** by adviser regression coverage.

### Catalog ingestion and task-3 artifacts

- Merchant can download the canonical workbook from `GET /catalog/template`.
- Column mapping is deterministic and versioned: known aliases map; ignored columns are reported;
  ambiguous collisions stop the import. **There is no AI column-mapping call.**
- Cleaning is staged. The merchant reviews normalized rows and deterministic grouped diagnostics
  before approval/publish; a model may rewrite the explanation, but the deterministic report is
  the fallback and source of truth.
- Image ZIPs are validated for type, size, traversal, symlinks and junk files; filenames are matched
  deterministically first, with a bounded optional model pass only for unmatched images. Uploaded
  images enter the live catalog immediately and become public only when used by a published product.
- The requested template, unclean sample and cleaned control are all tracked on `main` in the
  output directory above via `834a8c7`. The clean control's actual filename is
  `sigi-skin-clean-control.xlsx`, not `sigi-skin-clean-catalog.xlsx`.

### Open defects and release risks

- **P2 — Ruff is red:** `tests/test_catalog_images.py:48` imports `build_template` without using
  it. This is an isolated `F401` and Ruff reports it as auto-fixable; pytest remains green.
- **P2 — contract drift:** `docs/contracts.md` describes `/agent/confirm` with
  `cart_mandate_id`; `ConfirmRequest` and current tests require `cart_id`. Choose one and align
  docs/clients before freeze.
- **Current catalog UI E2E is unverified:** the last recorded Playwright result was 5/5 before the
  latest template/image/catalog UI changes. It was not rerun in this handoff.
- **Local-path build trap:** this saved checkout's parent directory contains a literal `?`.
  esbuild/Vite refuses to load the config from that path. The same tree builds from a normal temp
  path, so use a fresh checkout without `?` for release rehearsal rather than debugging app code.
- **No local `.env`:** this machine runs deterministic `DEMO_MODE=1`; no live OpenAI path was
  exercised in this refresh. Code defaults to `gpt-5-mini`, while `.env.example` says
  `gpt-4.1`; the demo model is not frozen.
- **Release coordination is missing:** `docs/tasks.md`, `docs/timeline.md`,
  `docs/event.md`, `docs/team.md` and `docs/agent-workflow.md` are absent. `7f6f860` removed the
  stale event/AI setup sections from `README.md`, but `AGENTS.md` still references deleted files.
  There is no current task board for Devpost, README/licence, recording, secret scan or visibility.
- Security trade-offs remain: broad demo CORS, in-process throttles, 7-day non-rotating consumer
  tokens, no merchant-key rotation, email-existence disclosure at registration, and a redundant
  gated `POST /pay/consent`. See `docs/security.md`.

### Branches

| Branch | State |
|---|---|
| `main` baseline @ `7f6f860` before this handoff commit | contains all three workbooks plus the concurrent README cleanup from `origin/main` |
| `codex/catalog-cleaner-agent` @ `8ccd879` | pushed; its commit still appears unmerged because main received the workbooks through `834a8c7`. It uniquely carries `docs/task3-sample-data.md`, a stale handoff delta and an earlier tiny template export. Confirm whether the provenance doc is wanted, then abandon or selectively recover it |
| `origin/codex/t-02-walking-skeleton` @ `33b234b` | remote-only and fully merged; safe to delete |

Baseline commit identities, excluding this handoff: Nam Nguyen 20; Aryan 16 across two email
identities; Glen Han 8 across two identities.

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

## How to run & test

Use a checkout whose path does not contain `?` for the Vite production build.

```bash
# one-time
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
npm --prefix web install

# deterministic local data and app
./.venv/bin/python -m seed.reset
./.venv/bin/python -m scripts.dev
```

Or use the Makefile: `make dev`, `make api`, `make web`, `make reset`, `make keys`,
`make test`, `make build`.

Known demo path: open `http://localhost:5173/storefront?merchant=m_mysa` and
`http://localhost:5173/admin`; discover → compare → set/confirm spend limit → server-priced
preview → consent → bank OTP **`492118`** → receipt. Rehearse the refusal paths too.

```bash
curl -s http://127.0.0.1:8000/health
./.venv/bin/ruff check app agent merchant payments seed scripts tests
./.venv/bin/python -m pytest -q
npm --prefix web run build
npm --prefix web run test:e2e  # app must be running
```

Current expectations:

- health: 200 with skincare/simulator payload;
- pytest: 115 pass;
- Ruff: currently fails only `tests/test_catalog_images.py:48 F401`;
- frontend build: passes in a normal path;
- Playwright: must be rerun after the latest catalog UI work.

This host does not expose a system `npm`; the bundled workspace Node runtime was used for the
fresh TypeScript/Vite checks. A normal Node/npm installation is still the documented developer path.

## Env & secrets

Names only. Values belong in a local, gitignored `.env`; never commit or print them.

Named in `.env.example`: `OPENAI_API_KEY`, `OPENAI_MODEL`, `DEMO_MODE`,
`DEMO_MERCHANT_KEY`, `DEMO_CONSUMER_PASSWORD`.

Also accepted by the code but not currently mirrored in `.env.example`: `DATABASE_PATH`,
`ISSUER_DATABASE_PATH`, `AGENT_PRIVATE_KEY_PATH`, `AGENT_KID`, `SIGNATURE_ENFORCE`,
`API_BASE_URL`, `CATALOG_IMAGE_BASE_URL`, `WEB_BASE_URL`,
`MERCHANT_HARD_CEILING_CENTS`.

The shared OpenAI key comes from the team group chat. Signing material defaults to the gitignored
`var/agent-ed25519.pem`; `make reset` can emit a demo merchant key into the gitignored
`var/merchant-key.txt`.

Before making the repo public, scan the current tree and full history for credentials and inspect
the actual visibility setting. Do not paste any matched value into issues, docs or chat.

## API credit spend

- **No new API spend in this handoff:** `.env` is absent and verification ran with
  `DEMO_MODE=1`.
- Previous estimate: **well under $5 of the $50 grant**, including a 56-case live `gpt-4.1` pass
  plus development turns. This is not verified against the provider dashboard.
- The demo model remains unresolved: code default `gpt-5-mini`, example env `gpt-4.1`.
  Freeze one model, restore the local key from the team channel, then run only the highest-value
  live regression/rehearsal so the spend stays bounded.
- A human with access to the OpenAI account must check the real spend and record it here.

## Next 3 actions

At **T+14:01**, the feature-freeze window is 6 h 59 m and rest shifts should already be active.
These are recommendations; the team/Y4 decides ownership.

1. **Make the release gate green by T+14:40 (about 40 min, awake engineer).** Remove the single unused
   test import, resolve `cart_id` versus `cart_mandate_id`, then rerun Ruff, 115 pytest, the
   clean-path frontend build and Playwright. Include one medical-boundary turn and the complete
   OTP purchase/refusal rehearsal. Commit and push the working increment.
2. **Stand up the submission/release lane by T+15:25 (45 min, team lead + one awake owner).** Create
   a minimal live checklist for Devpost fields, PS explanation, README/licence, secret/history scan,
   repo-public check, backup video and a normal-path release checkout. Assign a human owner and a
   hard completion time to every line; do not wait for T+21.
3. **Protect staggered rest through T+19 and lock scope by 07:30 (human-only).** Keep exactly one
   integration owner awake, stop new features, merge only green increments, rehearse/record at
   09:00, make the repo public by 09:45 and submit Devpost by 10:40.

## Open questions

- Which identifier is canonical for `/agent/confirm`: `cart_id` or `cart_mandate_id`?
- Which model will be demoed: `gpt-5-mini` or `gpt-4.1`? The selected live path still needs one
  bounded, current safety/journey run.
- Were the task board, timeline, event facts, roster and agent workflow deleted deliberately?
  If yes, where is the live submission checklist now?
- Is the GitHub repository currently private or public, who owns the visibility flip, and has the
  full-history secret scan been completed?
- Does the unique `docs/task3-sample-data.md` on `codex/catalog-cleaner-agent` contain provenance
  worth selectively recovering, or should that branch be abandoned?
- Who can inspect the OpenAI account and record the real spend?
- Was a real Visa sandbox made available on site? The current build deliberately uses a simulator.
- Did the organisers publish event-level judging criteria beyond the problem statement? Check the
  official event channel; `docs/event.md` is absent.
