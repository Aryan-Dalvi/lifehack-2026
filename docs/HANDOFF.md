# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot
- **When:** **T+3:47** (Sat 29 Aug 2026, 14:47 SGT) · **Author:** Claude Code / Aryan
- **Deadline:** Devpost locks **T+24 = 11:00 Sun**. Judging 12:00–14:30. Closing 15:00 (all must attend).
- **Head:** `e379802` on `main`, 1 commit ahead of `origin/main` (not yet pushed this refresh).

## Project one-liner
**Agent-Ready Commerce** — for the **Visa** PS *"Conversational Commerce Agents for Every Merchant."*
A plug-and-play layer that lets any merchant, SME or enterprise, drop a category-trained shopping
agent onto their site that takes a customer from discovery to a completed, **in-conversation** Visa
payment, with every purchase carrying a verifiable chain of human and issuer consent.

## Direction & why
Direction **A** in `docs/brief.md` §4 (unchanged, still the standing recommendation). See that
file for the full rejection notes on Direction B (cross-merchant concierge) and C (voice-first).
`docs/architecture-flowchart.md` (added T+3:04) narrows the MVP to a single skincare vertical and
is the current detailed decision-aid — it **has not yet been reconciled** into `contracts.md` or
approved at a huddle (see State, below).

## Stack & repo map
Proposed; **still unfrozen** — see State. Full detail: `docs/contracts.md` v0.11.

**One process, five routers, three modules.** `uvicorn app.main:app` mounts `agent`, `merchant`,
`consumer`, `pay`, `bank` on **:8000**; Vite/React/Tailwind on **:5173**; SQLite single file.

| Directory | Owns | Owner |
|---|---|---|
| `payments/` | mock Visa stack, cart builder, AP2 mandate chain, TAP (RFC 9421) verification, trust bus, mock issuer ACS `/bank/*` with its own store | Y4 |
| `agent/` | Concierge + Discovery + Comparison specialists, **Guardian**, packs as data, signing, `DEMO_MODE` | Y3 |
| `web/` | chat widget (plates C1–C9), Trust Panel, 3-section merchant console (M1–M3), live preview | Y2 |
| `merchant/` | catalog ingest incl. ratings, registry, search, config + snippet, consumer addresses `/consumer/*` | Aryan |
| `app/`, `seed/`, `demo/`, `docs/`, `Makefile` | entrypoint, seed data, ops | Aryan |

**No deployed URL** — local only, by design. Published wireframes:
https://claude.ai/code/artifact/f798d544-e897-4572-8421-925f2cb32a0a

### Doc map — **stale, needs a pass**
`README.md`, `AGENTS.md`, and this file's old doc map pointed to `docs/event.md`, `docs/team.md`,
`docs/tasks.md`, `docs/timeline.md`, `docs/agent-workflow.md` — **all deleted in the last hour (see
State)**. `README.md` in particular still tells a new window to read files that no longer exist.
Until the team re-establishes a doc map, read what's actually on disk: `brief.md` → `contracts.md`
→ `architecture-flowchart.md` → `ux.md` + `wireframes.html` → `coverage.md` → `ai-budget.md`.

## State

> ⚠️ **Read this before anything else.** Two things changed since the last handoff (T+2:35): a
> detailed architecture doc was added, and most of the operational tracking layer was deleted by
> teammates in real time. Neither is explained in a commit message — flag it at the next sync.

- **Done:** original KICKOFF planning (`brief.md`, `research/initial.md`, `contracts.md` v0.11,
  `coverage.md`, `ux.md`, `wireframes.html`) plus a new, detailed MVP architecture decision aid,
  `docs/architecture-flowchart.md` (added T+3:04 by Nam Nguyen), which narrows the MVP to a single
  skincare-shopper vertical with a reduced two-call LLM topology. **This is not yet reconciled with
  `contracts.md` v0.11** — §1 of that file lists explicit contract deltas it needs (decoupling
  session creation from budget entry, a `PUT /agent/session/{id}/limit` op, removing the category
  selector, etc.) that have not been ported.
- **Removed in the last hour, cause unstated:** between T+3:15 and T+3:42, two authors (Nam Nguyen,
  Aryan) deleted `docs/tasks.md` (the task board), `docs/team.md` (the roster), `docs/timeline.md`,
  `docs/event.md` (the transcribed PS + judging criteria), `docs/agent-workflow.md` (the 22-step
  spec), `.claude/skills/lifehack-kickoff/`, and `samples/`. No commit message says why. **This may
  be a deliberate pivot** (e.g. consolidating onto `architecture-flowchart.md` as the new source of
  truth) **or accidental scope creep during a cleanup pass** — the next window should get a
  human confirmation before treating it as settled. Practical effect: **the task-claim mechanism
  CLAUDE.md describes ("claim = write your name in `docs/tasks.md` and commit") has no file to
  operate on right now**, and the PS's official judging criteria (previously in `event.md`) exist
  only in `Visa Problem Statement.pdf`.
- **In progress:** nothing. No branches besides `main`. Working tree clean except this handoff.
- **NO CODE EXISTS.** The repo still contains only `docs/`, `prompts/`, `.claude/`, `.env.example`,
  and the PS PDF. There is no `app/`, `agent/`, `payments/`, `merchant/`, `web/`, `seed/` or `Makefile`.
- **Blocked / not started:**
  - **Huddle** — still no evidence it happened, and the one artifact that would prove it
    (`team.md`) is now gone rather than filled, so this can no longer even be checked from the repo.
  - **Scaffold** — not started. Blocks all four module lanes.
  - **OpenAI key** — not confirmed obtained. Blocks every `agent/` task.
  - `contracts.md` is still **v0.11 unfrozen**, and now also out of sync with
    `architecture-flowchart.md`'s recommendations.

### Schedule reality at T+3:47

| Timeline said (original plan) | Actual |
|---|---|
| T+0:40–1:10 huddle, contracts frozen | not evidenced |
| T+1:10–2:10 scaffold + seed data | not started |
| T+2:10 all four modules building in parallel | nothing building |
| T+4:00 checkpoint 1, `main` runs | at risk — 15 min away with zero code |

The build is now **~2.5 h behind** a plan that had no buffer to begin with. The last 70 minutes
were spent adding a detailed architecture doc and deleting the tracking layer, not writing code or
running a huddle. This is the second consecutive handoff to record this gap — escalate verbally,
not just in this file.

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

## How to run & test

**Nothing runs yet.** There is no `Makefile`, no `app/`, no dependency manifest. Any window that
tries to verify a "known-good demo path" right now will find none — that is expected, not a
broken clone.

Once a scaffold lands, this section must be replaced with the real commands. The intended DoD
(from the now-deleted task board, still valid as a target) was for these three to work from a
clean clone:

```bash
make dev      # uvicorn app.main:app on :8000  +  vite on :5173
make reset    # drop + reseed SQLite in under 5 s
make keys     # generate local ed25519 signing keys (gitignored)
```

Known-good demo path once the skeleton exists: set a spend limit → describe a skincare need →
compare two → confirm → issuer/bank challenge in `DEMO_MODE` → receipt. Then the rehearsed
refusals (over-cap, replayed bank token, cart/address edited after approval).

## Env & secrets
Names only; values live in each machine's local `.env`, mirrored by name into `.env.example`, and
are **never committed, never printed into docs, never logged**.

`.env.example` currently declares only `OPENAI_API_KEY` (team's $50 grant — value via the team
group chat only). The earlier plan also called for `OPENAI_MODEL`, `DEMO_MODE`, `DATABASE_URL`,
`AGENT_PRIVATE_KEY`, `AGENT_KID`, `PLATFORM_PRIVATE_KEY`, `TRUST_REGISTRY_PATH`, `API_BASE_URL`,
`VITE_API_BASE`, `SIGNATURE_ENFORCE` — none of these have been added back to `.env.example` yet;
add them as the scaffold lands.

Signing keys are intended to be generated locally by `make keys` and gitignored (not yet built).

## API credit spend
- **$0 of $50 spent.** No API calls have been made — the key's current status is unconfirmed in
  the repo (the file that would have tracked this, `docs/team.md`/`tasks.md`, is deleted).
- **Demo-day reserve (~$25): not at risk from spend.** It is at risk from *never getting the key
  onto all four machines* — this is still on the critical path for the whole `agent/` lane.
- Budget once building: ≤$10 dev, ~$25 held for judging, ~$15 buffer (from the original plan).
  A full demo run was estimated at **≈$0.004** (per the now-deleted `agent-workflow.md`); verify
  against the real meter once building starts.

## Next 3 actions

Ordered. Nothing below item 1 can start until item 1 finishes.

1. **Get a human sync on what just happened to the docs — before anything else.** Owner: **Aryan**,
   human-only. Confirm with Nam Nguyen (and the rest of the team) whether deleting the task board,
   team roster, event transcript, and agent-workflow spec was deliberate, and if so what replaces
   them (is `architecture-flowchart.md` now the single source of truth? is task-claiming moving off
   `docs/tasks.md` entirely?). Without this, every other window is guessing.
2. **Run the huddle** — confirm Direction A, reconcile `architecture-flowchart.md`'s deltas into
   `contracts.md`, have the architect (Y4) freeze contracts v1, and re-establish however the team
   wants to track task ownership now that `tasks.md`/`team.md` are gone. Owner: **Aryan**,
   human-only, no AI.
3. **Scaffold** — single FastAPI app mounting the five routers, Vite/React/Tailwind, SQLite,
   `make dev` / `make reset` / `make keys`, restore/extend `.env.example`. Owner: **Aryan**,
   executor **Aryan-Claude**. Still ~1 h. Blocks all four module lanes — start the moment the
   huddle produces a frozen contract to build against.

Immediately after: all four members start their module lanes in parallel, and Aryan sets a timer
for **checkpoint 1**.

## Open questions

- **Why was the tracking layer deleted, and what (if anything) replaces it?** Highest-impact
  unknown right now — see State and Decision log above. Resolve verbally before the huddle.
- **Has the huddle happened offline?** The repo can no longer answer this on its own now that
  `team.md` is gone — ask directly rather than inferring from git history.
- **`architecture-flowchart.md` vs `contracts.md` v0.11**: the flowchart doc lists its own contract
  deltas (§1, §16 freeze checklist) that haven't been ported. Someone (Y4) needs to either port them
  or explicitly reject them at the huddle.
- **README.md and AGENTS.md are stale** — both still point to `docs/event.md`, `docs/team.md`,
  `samples/`, and the `docs/tasks.md` claim-by-commit workflow, all of which no longer exist.
  Needs a pass once the team confirms the new doc structure.
- Whether a **Visa sandbox, TAP endpoint, or ratings API** is reachable on-site today — still
  unanswered; check with mentors.
- Whether the organisers have published **event-level judging criteria** beyond the PS's own text —
  previously tracked in the now-deleted `docs/event.md`; the source PDF (`Visa Problem
  Statement.pdf`) is the only copy left in-repo. Re-transcribe if the team wants it back.
