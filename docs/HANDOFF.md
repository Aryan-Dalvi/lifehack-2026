# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot
- **When:** **T+2:35** (Sat 29 Aug 2026, 13:35 SGT) · **Author:** Claude Code / Aryan
- **Deadline:** Devpost locks **T+24 = 11:00 Sun**. Judging 12:00–14:30. Closing 15:00 (all must attend).
- **Head:** `71bbff2` on `main`, pushed, working tree clean. No other branches.

## Project one-liner
**Agent-Ready Commerce** — for the **Visa** PS *"Conversational Commerce Agents for Every Merchant."*
A plug-and-play layer that lets any merchant, SME or enterprise, drop a category-trained shopping
agent onto their site that takes a customer from discovery to a completed, **in-conversation** Visa
payment, with every purchase carrying a verifiable chain of human and issuer consent.

## Direction & why
Direction **A** in `docs/brief.md` §4 — *recommended by KICKOFF, still pending huddle confirmation.*
The only candidate that hits all four "Expected Submissions" head-on and splits into four clean
parallel modules.

**Rejected:** Direction B, a cross-merchant category concierge (higher ceiling, needs basket
splitting and multi-merchant settlement — absorbed the cheap 80% into A instead, then cut it in
rev 3); Direction C, voice-first for hawker SMEs (charming, thin, and voice in a loud MPH during
walking judging is a liability).

**The wedge:** ChatGPT deprecated Instant Checkout in March 2026 and the industry fell back to
*discovery + redirect*, because in-conversation payment is a **trust** problem. The PS explicitly
demands "no redirects" — so we ship the trust artifact that removes the need for one.

## Stack & repo map
Proposed; **Y4 freezes at the huddle.** Full detail: `docs/contracts.md` **v0.11 (unfrozen)**.

**One process, five routers, three modules.** `uvicorn app.main:app` mounts `agent`, `merchant`,
`consumer`, `pay`, `bank` on **:8000**; Vite/React/Tailwind on **:5173**; SQLite single file.
Chosen so a cold start takes seconds across 2.5 h of walking-format judging.

| Directory | Owns | Owner |
|---|---|---|
| `payments/` | mock Visa stack, cart builder, AP2 mandate chain, TAP (RFC 9421) verification, trust bus, **mock issuer ACS `/bank/*` with its own store** | Y4 |
| `agent/` | Concierge + Discovery + Comparison specialists, **Guardian**, packs as data, signing, `DEMO_MODE` | Y3 |
| `web/` | chat widget (plates C1–C9), Trust Panel, 3-section merchant console (M1–M3), live preview | Y2 |
| `merchant/` | catalog ingest incl. ratings, registry, search, config + snippet, **consumer addresses `/consumer/*`** | Aryan |
| `app/`, `seed/`, `demo/`, `docs/`, `Makefile` | entrypoint, seed data, ops | Aryan |

**No deployed URL** — local only, by design. Published wireframes:
https://claude.ai/code/artifact/f798d544-e897-4572-8421-925f2cb32a0a

### Doc map — read in this order
`event.md` (PS + rubric) → `brief.md` (direction, MVP, cut list) → `ux.md` + `wireframes.html`
(the two surfaces) → `contracts.md` (types and endpoints — **authoritative**) →
`agent-workflow.md` (22 steps, inputs/outputs/tools) → `tasks.md` (the board) →
`timeline.md` (checkpoints and slip rules) → `coverage.md` (requirement → task).

## State

> ⚠️ **Read this before anything else.** The documentation is far ahead of the code. Do not mistake
> one for the other.

- **Done:** planning only. KICKOFF + revisions 2 and 3 — `brief.md`, `research/initial.md`,
  `tasks.md`, `contracts.md` v0.11, `timeline.md`, `coverage.md`, `ux.md`, `wireframes.html`,
  `agent-workflow.md`. PS and the official 5-line rubric transcribed into `event.md`.
- **In progress:** *nothing.* No branches besides `main`. Working tree clean, everything pushed.
- **NO CODE EXISTS.** The repo contains `docs/`, `prompts/`, `samples/`, `.env.example` and the
  PS PDF. There is no `app/`, `agent/`, `payments/`, `merchant/`, `web/`, `seed/` or `Makefile`.
- **Blocked / not started:**
  - **T-01 huddle** — no evidence it happened. `team.md` has 4 unfilled rows; the board has 0 claims.
    By the team's own protocol ("claiming = write your name and commit immediately"), no commit
    means no claim. *If the huddle did happen offline, the board is lying to every other window and
    must be updated now.*
  - **T-02 scaffold** — not started. **Blocks all four module lanes.**
  - **T-04 OpenAI key** — not obtained. Blocks every `agent/` task.
  - `contracts.md` is still **v0.11 unfrozen**. Eight open questions await the huddle.

### Schedule reality at T+2:35

| Timeline said | Actual |
|---|---|
| T+0:40–1:10 huddle, contracts frozen | not evidenced |
| T+1:10–2:10 scaffold + seed data | not started |
| **T+2:10 all four modules building in parallel** | **nothing building** |
| T+4:00 checkpoint 1, `main` runs | at risk |
| T+8:00 walking skeleton | at risk but recoverable |

**The build is ~1.5 h behind.** If the team has genuinely been idle since T0, roughly **8
person-hours** of the budget are already gone, taking available capacity from 55–65 h to about
**47–57 h against a ~56 h plan**. The revision-3 scope question stops being theoretical here: the
team should expect to cut, and `brief.md` §5 already names what goes first. Recoverable — the
critical path is one 1-hour scaffold task — but only if the huddle happens immediately.

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

## How to run & test

**Nothing runs yet.** There is no `Makefile`, no `app/`, no dependency manifest. Any window that
tries to verify a "known-good demo path" right now will find none — that is expected, not a
broken clone.

After **T-02** lands (target: 1 h from whenever it starts), this section must be replaced with the
real commands. The scaffold's own DoD is that these three work from a clean clone:

```bash
make dev      # uvicorn app.main:app on :8000  +  vite on :5173
make reset    # drop + reseed SQLite in under 5 s
make keys     # generate local ed25519 signing keys (gitignored)
```

Known-good demo path once the skeleton exists (`docs/agent-workflow.md` has the step detail):
set a spend limit → "good ANC for flights" → compare two → confirm → bank code `492118` in
`DEMO_MODE` → receipt. Then the three rehearsed refusals.

## Env & secrets
Names only; values live in each machine's local `.env`, mirrored by name into `.env.example`, and
are **never committed, never printed into docs, never logged**.

`OPENAI_API_KEY` (team's $50 grant — value via the team group chat only) · `OPENAI_MODEL` ·
`DEMO_MODE` · `DATABASE_URL` · `AGENT_PRIVATE_KEY` · `AGENT_KID` · `PLATFORM_PRIVATE_KEY` ·
`TRUST_REGISTRY_PATH` · `API_BASE_URL` · `VITE_API_BASE` · `SIGNATURE_ENFORCE`.

Signing keys are generated locally by `make keys` and gitignored.

## API credit spend
- **$0 of $50 spent.** No API calls have been made — **the key has not been obtained yet (T-04).**
- **Demo-day reserve (~$25): not at risk from spend.** It is at risk from *never getting the key* —
  T-04 is now on the critical path for the whole `agent/` lane.
- Budget once building: ≤$10 dev, ~$25 held for judging, ~$15 buffer. Per `agent-workflow.md`, a
  full demo run should cost **≈$0.004** (3 model calls; cart and payment make none), against the
  <$0.05 target in T-24 — roughly 10× headroom. Verify against the real meter at T-24.

## Next 3 actions

Ordered. Nothing below item 1 can start until item 1 finishes.

1. **RUN THE HUDDLE — now, 20 minutes, not 30.** Owner: **Aryan**, human-only, no AI.
   Fill `docs/team.md` *first* (it is still blank and it is risk #1 — every owner on the board is a
   role-archetype guess). Then: confirm Direction A, confirm the stack, pick the demo category,
   have **Y4 freeze `contracts.md` v1** against the eight open questions, and get every member to
   write their name on two rows and **commit the claim**. One of those eight questions is a *team
   vote, not Y4's call*: whether to accept ~56 h with no buffer, or cut now.
2. **T-02 scaffold** — Owner: **Aryan**, executor **Aryan-Claude** (strongest model, thinking on).
   1 h. Single FastAPI app mounting five routers, Vite/React/Tailwind, SQLite, `make dev` /
   `make reset` / `make keys`, `.env.example`. **This blocks all four module lanes** — start it the
   moment the huddle ends, and run T-03 seed data (Aryan-Codex) in parallel.
3. **T-04 OpenAI key onto all four machines** — Owner: **Aryan**, human-only. Chase the on-site org
   staff. Blocks every `agent/` task. Can be done *during* the huddle by whoever is least needed.

Immediately after: all four members start T-10 / T-20a / T-30 / T-40 in parallel, and Aryan sets a
timer for **checkpoint 1**.

## Open questions

- **`docs/team.md` is still empty.** Highest-impact unknown in the whole plan (`brief.md` §6 risk 1).
  Fill it in the first five minutes of the huddle and re-allocate the board on the spot.
- **Eight contract questions** await freeze (`contracts.md` §Open contract questions). Rev 2 added
  three (Guardian's home module, cart builder's home, mid-conversation pack switching), rev 3 added
  two (where the issuer ACS lives; **whether the team accepts ~56 h with no buffer** — a scope call,
  so by `team.md` it is a majority vote with the tie to Y4).
- **Three mentor questions** in `brief.md` §7 — chiefly: is any Visa sandbox, TAP endpoint or MCP
  server reachable on-site today? If yes, T-10/T-12/T-14 change from "mock" to "integrate".
- Whether a **ratings source** is available from the Visa mentors. It plugs into the ingest-time
  enrichment hook (assumption A6) without touching anything downstream.
- Whether the organisers publish **event-level judging criteria** beyond the PS's own five lines —
  check the official Telegram channel at every checkpoint.
- **`brief.md` §5 stretch numbering is stale** (S6 passkey cut, S8 cross-merchant cut).
  `tasks.md` is authoritative. Reconcile at the next `STATUS`.
