# HANDOFF — living project state

> Any window (Claude or Codex, any member's machine) reads this first at session start.
> Refresh it via the `HANDOFF` keyword (procedure in `prompts/handoff.md`): full rewrite,
> commit, push. The Decision log is the only append-only section.

## Snapshot
- **When:** **T+1:45** (Sat 29 Aug 2026, ~12:45 SGT) · **Author:** Claude Code / Aryan (KICKOFF rev 3)
- **Deadline:** Devpost locks **T+24 = 11:00 Sun**. Judging 12:00–14:30. Closing 15:00 (all must attend).

## Project one-liner
**Agent-Ready Commerce** — a plug-and-play layer that lets any merchant, SME or enterprise, drop a
category-trained shopping agent onto their site that takes a customer from discovery to a completed,
**in-conversation** Visa payment, with every purchase carrying a verifiable chain of human consent.

## Direction & why
Direction **A** in `docs/brief.md` §4 (recommended, **pending huddle confirmation**). It is the only
candidate that hits all four "Expected Submissions" head-on and splits cleanly into four parallel
modules. The wedge: ChatGPT's Instant Checkout was deprecated in Mar 2026 and the industry retreated
to *discovery + redirect* because in-conversation payment is a **trust** problem — the PS explicitly
demands "no redirects", so we ship the trust artifact that removes the need for one.

## Stack & repo map
Proposed, frozen by Y4 at the huddle. Full detail: `docs/contracts.md` (DRAFT v0.9).

- **One FastAPI process on :8000** mounting three routers + **Vite/React/Tailwind on :5173** + SQLite.
  Rationale: cold start in seconds for 2.5 h of walking-format judging.
- `payments/` **Y4** — mock Visa token vault, authorize/capture, **deterministic cart builder**,
  AP2-shaped mandate chain, TAP (RFC 9421) signature verification, trust-event stream, and a
  **mock issuer ACS (`/bank/*`) with its own store** — it has to be able to refuse us.
- `agent/` **Y3** — **orchestrator + 5 specialists** (Concierge · Discovery · Comparison · Guardian,
  with cart/payment as code in `payments/`), category packs as data, agent-side signing,
  `DEMO_MODE` fallback.
- `web/` **Y2** — chat widget (plates C1–C9: ratings, hover preview, consent sheet, bank approval,
  decline recovery), Trust Panel, 3-section merchant console (M1–M3), live agent preview.
- `merchant/` **Aryan** — catalog ingest (CSV/JSON), merchant registry, search API, embed snippet.
- `app/`, `seed/`, `demo/`, `docs/` **Aryan** — entrypoint, seed data, ops.

## State
- **Done:** KICKOFF complete — `brief.md`, `research/initial.md`, `tasks.md`, `contracts.md` (draft),
  `timeline.md`, `coverage.md`; PS + official rubric transcribed into `event.md`.
  **Revision 2** — `ux.md` + `wireframes.html` (subagent diagrams, plate set, M1–M3);
  `contracts.md` → v0.10.
  **Revision 3** — ratings, progressive disclosure, issuer authentication, shipping address;
  plates renumbered **C1–C9**; `contracts.md` → v0.11; board at **~56 h, no buffer left**.
  **`agent-workflow.md`** — the full execution spec: 22 steps across 6 phases, each with its exact
  input, output, required tools, Guardian checks, failure codes, and latency/cost budget.
- **In progress:** nothing — **no code exists yet.**
- **Blocked:** everything downstream of the huddle (T-01) and the OpenAI key (T-04).

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

## How to run & test
_Nothing to run yet._ After **T-02** (target T+2:10): `make dev` → API :8000 + web :5173 from a clean
clone; `make reset` reseeds SQLite in <5 s; `make keys` generates local signing keys.

## Env & secrets
Names in `.env.example`, values only in local `.env`, never committed:
`OPENAI_API_KEY`, `OPENAI_MODEL`, `DEMO_MODE`, `DATABASE_URL`, `AGENT_PRIVATE_KEY`, `AGENT_KID`,
`PLATFORM_PRIVATE_KEY`, `TRUST_REGISTRY_PATH`, `API_BASE_URL`, `VITE_API_BASE`, `SIGNATURE_ENFORCE`.

## API credit spend
- $0 of $50. **~$25 protected for demo day.** ≤$10 during dev (mini-tier model, prompt caching,
  capped `max_tokens`). Key not yet obtained → **T-04 is urgent**.

## Next 3 actions
1. **HUDDLE at T+0:40** — fill `docs/team.md` *first* (it is still empty; every owner below is a
   role-archetype guess), confirm direction + stack + demo category, **Y4 freezes `contracts.md` v1**,
   everyone claims and commits their first two tasks.
2. **T-04** — get the OpenAI key onto all four machines (org staff grant on-site). Blocks `agent/`.
3. **T-02 + T-03** — scaffold and seed data by T+2:10, so all four modules can start in parallel.

## Open questions
- **`docs/team.md` is empty** — highest-impact unknown in the whole plan (risk #1 in `brief.md` §6).
- Three mentor questions in `brief.md` §7 — chiefly: is any Visa sandbox reachable on-site today?
- Whether the organisers publish event-level judging criteria beyond the PS's own five lines
  (check the Telegram channel at every checkpoint).
- **Eight contract questions at freeze** (`contracts.md` §Open contract questions). Three are new in
  rev 2 (Guardian's home module, the cart builder's home module, mid-conversation pack switching) and
  two in rev 3: where the issuer ACS lives, and — **the one that isn't Y4's alone** — whether the team
  accepts landing at ~56 h with no buffer. By `team.md`, scope calls are a majority vote, tie to Y4.
- **`brief.md` §5 stretch list is now stale** in its numbering (S6 passkey is cut, S8 cross-merchant
  is cut). The authoritative list of what's in and out is `tasks.md`. Reconcile at the next `STATUS`.
