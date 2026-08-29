# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot
- **When:** **T+12:15** (Sat 29 Aug 2026, 23:15 SGT) · **Author:** Claude Code / Aryan
- **Head:** `59def0a` on `main`, pushed, working tree clean, in sync with origin.
- **Verified this refresh:** app imports, API boots, `/health` 200. Not taken on trust.

### ⏰ Deadlines — restated here because `timeline.md` and `event.md` were deleted from main

| When | T+ | What | From now |
|---|---|---|---|
| **Sun 08:00** | T+21 | **FEATURE FREEZE.** Unmerged work dies | **8 h 45 m** |
| Sun 09:00–09:45 | T+22 | **Record the backup demo video while everything works** | 9 h 45 m |
| Sun 09:45–10:00 | T+22:45 | **Flip repo to PUBLIC** + licence + secret scan | 10 h 30 m |
| **Sun 11:00** | **T+24** | **DEVPOST FORM LOCKS** — submit by 10:40, never touch it after | **11 h 45 m** |
| Sun 12:00–14:30 | | Judging — walking format, COM3 MPH, demo runs many times | |
| Sun 15:00–16:15 | | Closing ceremony — **attendance required to win** | |

**Rest shifts were scheduled to start at 23:00 (staggered pairs, 3 h each). It is 23:15.**

## Project one-liner
**Sway** (renamed from "Agent-Ready Commerce") — for the **Visa** PS *"Conversational Commerce
Agents for Every Merchant."* A plug-and-play **skincare** commerce agent for the demo merchant
**Mysa Skin**. A merchant uploads a CSV/XLSX/JSON catalog and publishes the same grounded shopping
experience as either an embedded widget or a hosted storefront. Shoppers discover, deterministically
compare, set a spending limit, preview a **server-priced** transaction, consent explicitly, clear a
**bank OTP challenge**, and get an auditable receipt.

Payment is a clearly-labelled simulator — **no real card is charged**, simulator OTP `492118` — but
the payer request is still Ed25519-signed and verified as a TAP-shaped HTTP Message Signature before
the simulated authorization runs. **The model never authorizes payments or creates orders.**

## Direction & why
Direction **A** in `docs/brief.md` §4, built. Rejected: B (cross-merchant concierge — needs basket
splitting and settlement) and C (voice-first — a liability in a loud MPH during walking judging).

**Scope narrowed since planning:** Phase 0 is **one category, skincare**, one demo merchant. The
multi-category pack machinery exists (`agent/packs/skincare.json`) but only skincare is populated.

## Stack & repo map
Python 3.11+ / FastAPI / SQLite · React + Vite + TypeScript · `uv` + `pyproject.toml`.

| Path | What |
|---|---|
| `app/` | FastAPI entrypoint. Includes 7 routers: `agent`, `merchant`, `catalog`, `consumer`, `bank`, `pay`, `trust` |
| `agent/` | `router.py`, interpreter / recommender / phraser / guardian, `packs/skincare.json` |
| `merchant/` | catalog ingest (CSV/XLSX/JSON), staged cleaning workflow, registry, search |
| `payments/` | mock Visa stack, issuer ACS, Ed25519 TAP signing/verification, trust log |
| `web/src/features/` | `landing/` · `shopper/` (ShopperApp, ProductCard, CartSidebar, ComparisonDrawer, CheckoutSheets, **TrustRail**, RoutinePlan) · `merchant/MerchantAdmin` |
| `web/public/` | `widget.js`, `widget-demo.html` — the embed path |
| `seed/`, `scripts/`, `tests/`, `outputs/`, `var/` | reset + seed, dev runner, test suite, generated artifacts, local DBs and keys (gitignored) |

**Surfaces:** `/storefront?merchant=m_mysa` · `/admin` · widget snippet (generated in admin).
**No deployed URL** — local only, by design.

## State

### Working and verified
- **API boots and serves.** `/health` → `{"status":"ok","category":"skincare","payment_mode":"simulator"}`.
- **`signature_enforce: True`** — TAP signature verification is on, not bypassed.
- Full shopper path built: discovery → deterministic compare → spending limit → server-priced
  preview → explicit consent → bank OTP → receipt.
- Merchant path built: catalog upload with staged cleaning → publish → widget snippet.
- **Four security passes logged** in `docs/testing.md` (T+9:05 tenant isolation, T+9:40 UI
  verification, T+10:20 route authorization audit, T+10:55 objects/credentials/exposure), with
  fixes landed in `c58bede`, `2d5ac3a`, `3e9cf2f`. Route auth is now **enforced in CI**.

### Open defects — from the T+7:42 agent pass, 56 cases, **51 pass / 5 fail**
- **P1 — medical safety boundary is bypassable**, and fails into a confusing message. On a
  *skincare* agent in front of judges this is the worst thing on the list. Later commits
  (`f1f0c78`, `121962b`, `90b642f`) changed how the agent answers, so this **may** be closed —
  **nobody has re-run the case.** Treat as open until re-tested.
- **P2 — contract drift:** `agent/router.py` `ConfirmRequest` requires `cart_id`, while the
  contract and clients say `cart_mandate_id`. Also unverified since.
- Three further LLM adversarial/safety failures in the same pass.

### Blocked / at risk
- **`.env` missing on Aryan's machine** → `demo_mode: True`, no OpenAI calls. `var/sway.db`,
  `var/issuer.db` and `var/agent-ed25519.pem` survive from 17:34; only the key is gone.
- **No task board.** `tasks.md` was deleted, so nothing tracks the submission lane — Devpost
  fields, README, backup recording, repo-flip-to-public. This is how teams lose at T+22.
- **Repo is still private.** Must be public before 11:00 Sun.

### Branches
| Branch | State |
|---|---|
| `main` @ `59def0a` | current, clean, pushed |
| `codex/catalog-cleaner-agent` @ `8ccd879` | **1 unmerged commit** — two skincare test fixtures (`sigi-skin-clean-control.xlsx`, `sigi-skin-unclean-catalog.xlsx`) + `docs/task3-sample-data.md`. Pushed, safe. Decide: merge or abandon before freeze |
| `codex/t-02-walking-skeleton` @ `33b234b` | fully merged into main — safe to delete |

**Contributors today:** Nam Nguyen 14 commits · Glen Han 8 · Aryan 3.

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

## How to run & test

**Verified working at T+12:15 on macOS** (README documents PowerShell; the POSIX equivalents below
are what was actually run).

```bash
# one-time
python3 -m venv .venv && ./.venv/bin/python -m pip install -e ".[dev]"
npm --prefix web install

# reset data, then run
./.venv/bin/python -m seed.reset
./.venv/bin/python -m scripts.dev
```

Or the Makefile: `make dev` · `make api` · `make web` · `make reset` · `make keys` · `make test` · `make build`.

**Known-good demo path** — storefront `http://localhost:5173/storefront?merchant=m_mysa`,
admin `http://localhost:5173/admin`:
discover → compare two → set/confirm spending limit → server-priced preview → consent →
**bank OTP `492118`** → receipt. Then the refusals.

**Smoke test in one line:**
```bash
curl -s http://127.0.0.1:8000/health
```
Expect `{"status":"ok","category":"skincare","payment_mode":"simulator"}`.

**Verify suite:**
```bash
./.venv/bin/ruff check app agent merchant payments seed scripts tests
./.venv/bin/python -m pytest -q
npm --prefix web run build
npm --prefix web run test:e2e     # needs the app running
```

⚠️ Without `.env` the app runs `demo_mode: True` — deterministic parser, **zero model calls**. The
demo works; the LLM path does not. Restore `.env` from the team group chat to exercise it.

## Env & secrets
Names only. Values live in each machine's local `.env` (gitignored), mirrored by name into
`.env.example`. **Never committed, never printed into docs, never logged.**

`OPENAI_API_KEY` (the $50 grant — value via the team group chat) · `OPENAI_MODEL` ·
`DEMO_MODE` (`1` = deterministic, no model calls; `0` = live) · `DEMO_MERCHANT_KEY` (unset →
`make reset` generates one into `var/merchant-key.txt`, gitignored) · `DEMO_CONSUMER_PASSWORD`
(demo shopper `demo@mysa.test`, defaults to `mysa-demo-password`).

Signing key: `var/agent-ed25519.pem`, kid `sway-demo-agent-1`, generated by `make keys`, gitignored.

**Before the repo goes public (T+22:45): scan history for the key.** `.env` was never tracked, but
verify — `git log -p | grep -iE 'sk-|api[_-]?key'`.

## API credit spend
- **Estimated well under $5 of $50. Not verified against the provider dashboard — someone with
  the account should check before the overnight shift.**
- Known usage: the T+7:42 pass ran 56 cases live on `gpt-4.1`, plus development turns. Design keeps
  it cheap — one structured interpretation call per ambiguous turn, deterministic catalog and
  checkout tools remain authoritative, and `DEMO_MODE=1` is the default.
- **Demo-day reserve (~$25): not at risk from spend.** The real risk is the opposite — Aryan's
  machine has no key at all, so the live path cannot be demoed or re-tested here.

## Next 3 actions

1. **Start the rest shifts — they were due at 23:00 and it is 23:15.** Owner: **Aryan**,
   human-only. Two staggered pairs, 3 h each. Whoever is awake owns `main`. This is on the timeline
   for a reason: a team that slept demos better than one that didn't, and judging is 2.5 h of
   repeated live demos. Protect it even though the build feels unfinished.
2. **Re-test and close P1 (medical safety) and P2 (`cart_id` / `cart_mandate_id` drift).**
   Owner: **Aryan**, executor **Aryan-Claude** (`TEST agent`). P1 is a skincare agent giving
   medical advice in front of judges — the single highest-severity open item. The later agent
   commits may already have fixed it; **run the case, don't assume.** Restore `.env` first or the
   live path can't be exercised.
3. **Stand the submission lane back up, tonight, not at T+21.** Owner: **Aryan**, executor
   **Aryan-Codex** (med). With `tasks.md` deleted nothing is tracking: Devpost field drafts, README
   polish, the PS-required written explanation (architecture / merchant onboarding / trust +
   security), **the backup screen recording**, and **flipping the repo public**. Recreate a minimal
   checklist — `git checkout 29e1c20^ -- docs/tasks.md` gets the old board back as a starting point.

## Open questions
- **Were P1 and P2 fixed by `f1f0c78` / `121962b` / `90b642f`?** Nobody has re-run the cases. This
  blocks knowing whether the agent is judge-safe.
- **Which model do we demo on** — `gpt-5-mini` (settings default) or `gpt-4.1` (what was tested)?
  The 56-case pass does not transfer between models; whichever we pick needs a re-run.
- **Was deleting `tasks.md`, `timeline.md`, `event.md`, `team.md` and `agent-workflow.md`
  deliberate pre-public cleanup, or accidental?** If deliberate, fine — but the deadlines and the
  board need to live somewhere, and right now that somewhere is only this file.
- **`codex/catalog-cleaner-agent`** — merge the two test fixtures before freeze, or abandon?
- **Who holds the OpenAI account** and can read the actual spend?
- Three mentor questions in `brief.md` §7 remain unanswered — chiefly whether any real Visa
  sandbox was reachable on-site.
- Whether the organisers published event-level judging criteria beyond the PS's five lines —
  check the official Telegram channel.
