# Task board

> Filled by KICKOFF at T+0:30 (Claude Code / Aryan). One row per task. **Claim = put your name in
> Owner and commit immediately** (`claim: T-07 …`). Edit only your own rows. Statuses:
> todo / claimed / doing / done / blocked.
>
> Owners below are **proposals from the role archetypes in `docs/team.md`** — that roster is still
> empty, so re-allocate at the huddle before anyone starts. Y2/Y3/Y4 = placeholders for real names.
>
> Executor column follows `docs/ai-budget.md`. "own-Codex" = that member's own NUS Codex window.

## Totals

**≈53 person-hours planned** (revision 2, +3 h) against ~55–65 available. That is tight, not
comfortable: the cut list in `brief.md` §5 exists for a reason, and revision 2 adds one more item to
it — **real WebAuthn in C6 drops to a simulated sheet unless everything else is green by T+16.**
Anything further added to this board must displace something.

| Lane | Planned | Δ rev 2 |
|---|---|---|
| Shared / setup | 3.75 h | — |
| `payments/` (Y4) | 11.5 h | +0.5 (absorbs the cart builder) |
| `agent/` (Y3) | 12.0 h | +2.0 (subagent split + Guardian, minus cheaper packs) |
| `web/` (Y2) | 11.0 h | +0.5 (live preview, minus a simpler console) |
| `merchant/` (Aryan) | 5.5 h | — |
| Integration, test, demo, submission (Aryan) | 9.25 h | — |

> **Revision 2 (T+1:10)** applied the three plan changes: consumer UX specified (plates C1–C8),
> merchant onboarding simplified to three sections, and `agent/` split into an orchestrator plus
> five specialists. Surfaces: `docs/ux.md` + `docs/wireframes.html`. Contracts: `contracts.md` v0.10.

---

## Shared / setup

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-01 | **Huddle**: fill `team.md`, pick direction, confirm stack + category, freeze `contracts.md` v1, claim tasks | all 4 | 0.5 ea | 0:40 → 1:10 | brief | human-only | todo | `team.md` filled; contracts marked FROZEN v1; every T-1x/2x/3x/4x row has an owner |
| T-02 | **Repo scaffold**: single FastAPI app mounting `agent`/`merchant`/`pay` routers, Vite+React+Tailwind app, SQLite, `make dev`, `make reset`, `.env.example`, CI-free smoke script | Aryan | 1.0 | 1:10 → 2:10 | T-01 | Aryan-**Claude** (strongest model, thinking on) | todo | `make dev` boots API :8000 + web :5173 from a clean clone; `/health` green; `make reset` reseeds in <5s |
| T-03 | **Seed data**: 2 merchants in one category — "Lumen Electronics" (large, 60 SKUs JSON feed) + "Kopi & Co" or SME equivalent (12 SKUs CSV); local placeholder images | Aryan | 0.75 | 1:10 → 2:00 | T-01 | Aryan-**Codex** (med) | todo | Both files load via ingest; no network calls at runtime; prices/attributes realistic enough to compare on |
| T-04 | **Get the OpenAI key** into every member's local `.env` (org staff grant on-site) | Aryan | 0.25 | 0:40 → 1:30 | — | human-only | todo | All 4 machines can call the API; key **not** in git; name present in `.env.example` |

## `payments/` — mock Visa stack + trust layer · **Y4 (architect)**

The hardest and highest-scoring module. Two of five rubric lines live here.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-10 | **Mock Visa token vault + authorize/capture + cart builder**: agent-bound network tokens with constraints (max amount, merchant lock, single-use, expiry); `/pay/authorize`, `/pay/capture`, `/pay/receipt`; **deterministic cart builder — totals re-read from the DB, never carried over from the model** (moved here from `agent/` in rev 2) | Y4 | 3.5 | 2:10 → 6:00 | T-02 | own-Codex (high) | todo | Base: valid cart → `approved` + auth code + receipt. Edge: expired token, wrong merchant, reused single-use token, amount over cap, unknown token → correct decline code each, never a 500. Cart total must disagree with a tampered client total and win |
| T-11 | **Mandate chain** (AP2-shaped): Intent → Cart → Payment, ed25519-signed, canonical JSON, parent linkage, `/pay/mandates`, `/pay/mandates/{id}/chain` with per-link verification status | Y4 | 3.0 | 5:00 → 9:00 | T-10 | own-Codex (high) | todo | Base: 3-link chain verifies. Edge: tampered cart total → `CART_HASH_MISMATCH`; orphan payment mandate → rejected; expired intent → `MANDATE_EXPIRED`; chain endpoint reports *which* link failed |
| T-12 | **TAP-shaped HTTP signatures**: RFC 9421 `Signature` / `Signature-Input` over `@authority @path created keyid expires alg nonce tag`; `tag` ∈ `agent-browser-auth` \| `agent-payer-auth`; agent registry of public keys; verifying middleware on `/merchant/*` and `/pay/*`; nonce replay cache | Y4 | 3.0 | 9:00 → 14:00 | T-11 | own-Codex (high) → escalate to Aryan-Claude if stuck >45 min | todo | Base: signed request passes, unsigned rejected 401. Edge: replayed nonce, expired `created`/`expires`, wrong `tag` for a payment route, unknown `keyid`, tampered path → distinct errors. **Hard timebox — fall back to HMAC envelopes with identical field shape rather than overrun** |
| T-13 | **Safeguard rules + `/trust/events` SSE**: emit a verification event per step (signature ok, mandate link verified, constraint checked, decision) for the Trust Panel; assemble the scripted decline scenario | Y4 | 2.0 | 14:00 → 17:00 | T-12, T-31 | own-Codex (med) | todo | Base: a normal purchase emits ≥6 ordered events. Edge: the over-cap purchase emits a `declined` event with `AMOUNT_EXCEEDS_MANDATE` and the panel shows exactly where the chain broke. Reconnect after refresh works |

## `agent/` — orchestrator + specialists · **Y3 (backend/core)**

Restructured in rev 2. Contracts: `contracts.md` §Subagents. Diagrams: `wireframes.html` Part 3.
**The rule that makes it work:** facts travel through code, only phrasing travels through a model,
and there is no model at all from the cart downward.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-20a | **Concierge + session + SSE**: orchestrator that routes a turn and holds the transcript — **never sees product rows, prices or the card**; `/agent/session`, `/agent/message` streaming | Y3 | 2.0 | 2:10 → 5:00 | T-02, T-04 | own-Codex (high) | todo | Base: a turn routes to the right specialist and streams back. Edge: off-topic turn, empty message, mid-stream disconnect, two turns in flight → no crash, no leaked internals |
| T-20b | **Discovery specialist + catalog tool**: scoped brief in, **`CatalogQuery` object out and nothing else**; binds to `/catalog/search` | Y3 | 1.5 | 5:00 → 7:00 | T-20a, T-41 | own-Codex (high) | todo | Base: "good ANC for flights" → 3 grounded cards ≤3 turns. Edge: no results, budget of $0, ambiguous query, model emits prose instead of a query → schema rejects, one repair, then a keyword fallback. **Never a hallucinated SKU** |
| T-20c | **Comparison specialist**: ≤5 rows injected verbatim + the pack's dimensions → comparison table + one recommendation, every claim citing a `sku` | Y3 | 1.5 | 7:00 → 9:00 | T-20b | own-Codex (high) | todo | Base: plate C4 renders from real rows. Edge: 1 product only, products missing an attribute, a claim citing an attribute not in the payload → Guardian rejects → deterministic table |
| T-25 | **Guardian validator** (new in rev 2): schema · grounding vs DB to the cent · scope strip · mandate cap; repair-once then deterministic fallback; emits `TrustEvent` on Y4's bus | Y3 | 2.0 | 9:00 → 12:00 | T-20c, T-13 | own-Codex (high) | todo | **The whole anti-hallucination claim rests here — not cuttable.** Base: a clean turn passes all four checks. Edge: invented SKU, price off by one cent, wrong-category product, cart above the cap → each refused with the right code (`UNGROUNDED_CLAIM`, `OUT_OF_SCOPE_PRODUCT`, `SCHEMA_REJECTED`) and a trust event |
| T-21 | **`DEMO_MODE=1` deterministic fallback**: scripted run covering the full demo script with zero API calls; automatic failover on API error/timeout | Y3 | 1.5 | 12:00 → 14:00 | T-20a | own-Codex (med) | todo | Judging-critical. With the network **off**, the whole demo script still runs end to end. Failover from live mode is invisible to the audience |
| T-22 | **Agent-side signing**: build + sign the Intent Mandate when the shopper sets the spend limit (plate C2), sign every outbound call per TAP with the right `tag` | Y3 | 2.0 | 12:00 → 15:00 | T-12 | own-Codex (high) | todo | Base: browse calls carry `agent-browser-auth`, pay calls `agent-payer-auth`, all verify. Edge: payment attempted with no intent mandate → blocked client-side *and* server-side |
| T-23 | **Category packs as data**: `agent/packs/<category>.json` — system prompt, attribute schema, comparison dimensions, guardrails, few-shot. 2 packs minimum | Y3 | 1.0 | 15:00 → 16:00 | T-20c, T-42 | own-Codex (med) | todo | Was 2.5 h — the architecture pays for itself here. Base: switching a merchant's category visibly changes the comparison dimensions. Edge: unknown category → generic pack, no error. **A third pack must cost only a file** |
| T-24 | **Cost control**: cheapest viable model per specialist (concierge nano, discovery/comparison mini), prompt caching, `max_tokens` caps, running spend log | Y3 | 0.5 | 16:00 → 17:00 | T-20c | own-Codex (low) | todo | A full demo run costs **<$0.05** — verify with the real meter, not an estimate; spend appears in `STATUS`; a runaway loop is capped |

## `web/` — chat widget, trust panel, merchant console · **Y2 (frontend/UX)**

UX is a whole rubric line. This module *is* the demo surface.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
Surfaces are now specified plate by plate in `docs/ux.md` + `docs/wireframes.html`. Build to the
plates; layout is fixed, visual design (colour, type, imagery, motion) is Y2's call.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-30 | **Chat widget — plates C1–C5, C7**: greeting + **spend-limit control**, product cards, comparison table, **consent sheet with scope band**, receipt in-thread | Y2 | 3.5 | 2:10 → 7:00 | T-02 | own-Codex (high) | todo | Base: full happy path clickable against a mocked API, matching plates C2–C5, C7. Edge: long titles, 0 results, network error, **double-click Confirm must not double-charge**, mid-stream disconnect. Amount must appear on the Confirm button |
| T-31 | **Trust Panel + plate C8** (decline recovery): live chain, verification badges, constraint checks, the broken-link state and its two recovery actions | Y2 | 2.5 | 9:00 → 13:00 | T-30, T-13 | own-Codex (high) | todo | Base: a purchase renders the chain step by step in real time. Edge: the declined run makes the broken link **obvious without narration**, and shows the two dead steps below it (*never asked* / *never called*). Readable at 1.5 m by a standing judge |
| T-32 | **Merchant console — plates M1–M3, simplified**: one page, three sections (shop / catalog / go live). Auto-mapped columns as chips, per-row error list, copy-snippet button, SME-vs-large toggle. **No wizard state, no mapping screen, no persona screen** | Y2 | 2.5 | 13:00 → 17:00 | T-40, T-42 | own-Codex (high) | todo | Base: CSV upload → agent live on that merchant in **<90 s**, on stage, no code. Edge: malformed CSV → per-row errors and **partial success**, not a stack trace; empty catalog; duplicate SKUs |
| T-34 | **Live agent preview in the console** (new in rev 2): the real widget against the just-uploaded catalog, running from section one | Y2 | 1.0 | 17:00 → 18:00 | T-30, T-32 | own-Codex (med) | todo | Reuses T-30's widget — no second implementation. Base: preview re-renders as the shop is configured. The "90 seconds" claim is not credible without this |
| T-33 | **Demo-day polish**: Reset button, keyboard-driveable, responsive, ≤5 s cold start, no console errors, favicon/title | Y2 | 1.5 | 18:00 → 20:00 | all web | own-Codex (med) | todo | Ten consecutive demo runs with no reload-and-pray. Reset returns to a pristine state in one click |

## `merchant/` — catalog + discovery service · **Aryan (Y1)**

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-40 | **Catalog ingest**: CSV + JSON → normalised `Product` rows in SQLite; merchant registry with `size` (sme\|enterprise); per-row error reporting | Aryan | 2.0 | 2:10 → 5:00 | T-02, T-03 | own-Codex (med) | todo | Base: both seed catalogs ingest clean. Edge: missing column, bad price, duplicate SKU, non-UTF8, 5 MB file, empty file → clear errors, partial success allowed |
| T-41 | **Discovery API**: `/catalog/search` keyword + price/attribute filters + facets, single- or cross-merchant, deterministic ranking | Aryan | 2.0 | 5:00 → 8:00 | T-40 | own-Codex (med) | todo | Base: "shoes under $150" returns sensible, stable ordering. Edge: empty query, no matches, price filter excluding everything, injection-ish input, `limit` abuse |
| T-42 | **Merchant config + embed snippet API**: `GET/PUT /merchant/{id}/config`, snippet endpoint returning a real one-line `<script>` | Aryan | 1.5 | 13:00 → 15:00 | T-40 | own-Codex (med) | todo | Base: snippet pasted into a blank HTML file boots the widget against that merchant. Edge: unknown merchant, config with an unknown category |

## Integration, testing, demo, submission · **Aryan (Y1)**

Non-code lanes are first-class. These are the tasks teams lose on.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-50 | **Integration checkpoints** ×4 — merge party, `main` must run, HANDOFF refresh at each | Aryan | 0.5 ×4 | 4:00 / 9:00 / 15:00 / 20:00 | — | Aryan-**Claude** (integration/debug) | todo | After each: clean clone → `make dev` → happy path passes. Red `main` is never left overnight |
| T-51 | **TEST passes** ×2 (`prompts/test.md`): pass 1 on the skeleton, pass 2 on the full build | Aryan | 1.0 ×2 | 8:00 / 18:00 | T-30 / all | Aryan-**Claude** | todo | `docs/testing.md` written with base + edge results, severity-ranked, top-3 fixes assigned as rows on this board |
| T-52 | **README + architecture diagram** for the public repo (also satisfies PS R11a) | Aryan | 1.0 | 20:00 → 21:00 | — | Aryan-Codex (med) | todo | A stranger clones and runs it in <5 min; diagram shows agent / merchant / payments / trust boundaries; simulation assumption stated plainly |
| T-53 | **PS "brief explanation" doc** (R11): architecture, merchant onboarding flow, trust & security | Aryan | 1.0 | 20:00 → 21:30 | T-52 | Aryan-Codex (med) | todo | Covers all three required sub-points; ≤2 pages; reusable verbatim in the Devpost long description |
| T-54 | **Devpost submission**: draft all fields early, paste at the end | Aryan | 1.0 | draft 19:00 · **submit 23:00** | T-52, T-53, T-56 | Aryan-Codex (med) | todo | Draft complete by T+20 with only links pending. **Submitted by T+23:40. Never touch the form after T+23:40** |
| T-55 | **Demo script + rehearsal** — all four members can drive it unaided | all 4 | 1.0 | 21:00 → 22:00 | feature freeze | human-only | todo | 3-minute script incl. the decline beat; each member has run it once end to end; Q&A answers agreed for the top 5 likely judge questions |
| T-56 | **Backup screen recording** of the full flow — **recorded while everything works** | Aryan | 0.75 | 22:00 → 22:45 | T-55 | human-only | todo | ≤3 min, shows discover → decide → pay **and** the decline; uploaded and linked; playable offline |
| T-57 | **Flip repo to public** + licence + secret scan | Aryan | 0.25 | 22:45 → 23:00 | — | human-only | todo | Public before 11:00 Sun; `git log -p \| grep -i` finds no key; `.env` never committed |

## Parking lot (do not start without displacing something)

Voice input · real WebAuthn passkeys · cross-merchant basket splitting · refunds/disputes ·
embeddings search · merchant analytics · live URL catalog scraping · multi-currency.
