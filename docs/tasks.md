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

**≈56 person-hours planned** (revision 3) against ~55–65 available. **The buffer is gone.** Revision
3 added 3.75 h and paid for 2.75 h of it by cutting real WebAuthn and cross-merchant search. Nothing
further goes on this board without something coming off it — and that is now a team vote, not an
owner's call.

| Lane | Planned | Δ rev 3 |
|---|---|---|
| Shared / setup | 3.75 h | — |
| `payments/` (Y4) | 13.5 h | **+2.0** (mock issuer ACS, T-14) |
| `agent/` (Y3) | 12.0 h | — |
| `web/` (Y2) | 10.5 h | +1.0 bank sheet & ship-to (T-35), −1.5 WebAuthn cut |
| `merchant/` (Aryan) | 6.25 h | +0.5 addresses (T-43), +0.25 rating ingest |
| Integration, test, demo, submission (Aryan) | 9.25 h | — |
| *(cut)* cross-merchant search | −1.25 h | stretch S8, third on the cut list |

> **Revision 3 (T+1:40)** — star ratings from catalog data · progressive disclosure (minimal card →
> hover preview → full compare) · **issuer-minted authentication token required for every purchase**
> · default shipping address on the confirmation, folded into the signed cart hash.
> Plates renumbered **C1–C9**. Contracts: `contracts.md` v0.11.
>
> **Revision 2 (T+1:10)** — consumer UX specified as a plate set, merchant onboarding simplified to
> three sections, `agent/` split into an orchestrator plus five specialists.
> Surfaces: `docs/ux.md` + `docs/wireframes.html`.

---

## Shared / setup

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-01 | **Huddle**: fill `team.md`, pick direction, confirm stack + category, freeze `contracts.md` v1, claim tasks | all 4 | 0.5 ea | 0:40 → 1:10 | brief | human-only | todo | `team.md` filled; contracts marked FROZEN v1; every T-1x/2x/3x/4x row has an owner |
| T-02 | **Repo scaffold**: single FastAPI app mounting `agent`/`merchant`/`pay` routers, Vite+React+Tailwind app, SQLite, `make dev`, `make reset`, `.env.example`, CI-free smoke script | Aryan | 1.0 | 1:10 → 2:10 | T-01 | Aryan-**Claude** (strongest model, thinking on) | todo | `make dev` boots API :8000 + web :5173 from a clean clone; `/health` green; `make reset` reseeds in <5s |
| T-03 | **Seed data**: 2 merchants in one category — "Lumen Electronics" (large, 60 SKUs JSON feed) + an SME equivalent (12 SKUs CSV); local placeholder images; **plausible `rating_avg` + `rating_count` on every SKU**; one demo consumer with a default address | Aryan | 0.75 | 1:10 → 2:00 | T-01 | Aryan-**Codex** (med) | todo | Both files load via ingest; no network calls at runtime; prices/attributes realistic enough to compare on. **Ratings must vary believably — a 4.1 with 3,907 ratings next to a 4.8 with 612 is the point.** Leave 2 SKUs unrated to exercise the empty state |
| T-04 | **Get the OpenAI key** into every member's local `.env` (org staff grant on-site) | Aryan | 0.25 | 0:40 → 1:30 | — | human-only | todo | All 4 machines can call the API; key **not** in git; name present in `.env.example` |

## `payments/` — mock Visa stack + trust layer · **Y4 (architect)**

The hardest and highest-scoring module. Two of five rubric lines live here.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-10 | **Mock Visa token vault + authorize/capture + cart builder**: agent-bound network tokens with constraints (max amount, merchant lock, single-use, expiry); `/pay/authorize`, `/pay/capture`, `/pay/receipt`; **deterministic cart builder — totals re-read from the DB, never carried over from the model** (moved here from `agent/` in rev 2) | Y4 | 3.5 | 2:10 → 6:00 | T-02 | own-Codex (high) | todo | Base: valid cart → `approved` + auth code + receipt. Edge: expired token, wrong merchant, reused single-use token, amount over cap, unknown token → correct decline code each, never a 500. Cart total must disagree with a tampered client total and win |
| T-11 | **Mandate chain** (AP2-shaped): Intent → Cart → Payment, ed25519-signed, canonical JSON, parent linkage, `/pay/mandates`, `/pay/mandates/{id}/chain` with per-link verification status | Y4 | 3.0 | 5:00 → 9:00 | T-10 | own-Codex (high) | todo | Base: 3-link chain verifies. Edge: tampered cart total → `CART_HASH_MISMATCH`; orphan payment mandate → rejected; expired intent → `MANDATE_EXPIRED`; chain endpoint reports *which* link failed |
| T-12 | **TAP-shaped HTTP signatures**: RFC 9421 `Signature` / `Signature-Input` over `@authority @path created keyid expires alg nonce tag`; `tag` ∈ `agent-browser-auth` \| `agent-payer-auth`; agent registry of public keys; verifying middleware on `/merchant/*` and `/pay/*`; nonce replay cache | Y4 | 3.0 | 9:00 → 14:00 | T-11 | own-Codex (high) → escalate to Aryan-Claude if stuck >45 min | todo | Base: signed request passes, unsigned rejected 401. Edge: replayed nonce, expired `created`/`expires`, wrong `tag` for a payment route, unknown `keyid`, tampered path → distinct errors. **Hard timebox — fall back to HMAC envelopes with identical field shape rather than overrun** |
| T-14 | **Mock issuer ACS** (new in rev 3): `/bank/challenge`, `/bank/verify`, `/bank/token/{id}` — mints a **single-use token bound to cart hash + amount + merchant**, 5-min TTL. `/pay/authorize` rejects without a valid one. **Own store, separate from the authoriser — it has to be able to refuse us** | Y4 | 2.0 | 6:00 → 9:00 | T-10 | own-Codex (high) | todo | Base: challenge → correct code → token → authorize approves, `eci` and issuer on the receipt. Edge: **each of these must produce its own decline** — no token (`BANK_TOKEN_MISSING`), expired (`BANK_TOKEN_EXPIRED`), replayed on a second purchase (`BANK_TOKEN_REUSED`), cart edited after issue (`BANK_TOKEN_CART_MISMATCH`), address swapped after issue (`SHIPPING_ADDRESS_MISMATCH`), 3 wrong codes → 429. **In `DEMO_MODE` the code is fixed but every binding rule still runs for real** |
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
| T-23 | **Category packs as data**: `agent/packs/<category>.json` — system prompt, attribute schema, **`salient_dims` (max 4, for the hover preview)**, comparison dimensions, guardrails, few-shot. 2 packs minimum | Y3 | 1.0 | 15:00 → 16:00 | T-20c, T-42 | own-Codex (med) | todo | Was 2.5 h — the architecture pays for itself here. Base: switching a merchant's category visibly changes both the hover preview and the comparison dimensions. Edge: unknown category → generic pack, no error; `salient_dims` naming a missing attribute → skipped, not blank. **A third pack must cost only a file** |
| T-24 | **Cost control**: cheapest viable model per specialist (concierge nano, discovery/comparison mini), prompt caching, `max_tokens` caps, running spend log | Y3 | 0.5 | 16:00 → 17:00 | T-20c | own-Codex (low) | todo | A full demo run costs **<$0.05** — verify with the real meter, not an estimate; spend appears in `STATUS`; a runaway loop is capped |

## `web/` — chat widget, trust panel, merchant console · **Y2 (frontend/UX)**

UX is a whole rubric line. This module *is* the demo surface.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
Surfaces are now specified plate by plate in `docs/ux.md` + `docs/wireframes.html`. Build to the
plates; layout is fixed, visual design (colour, type, imagery, motion) is Y2's call.

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-30 | **Chat widget — plates C1–C6, C8**: greeting + **spend-limit control**, product cards with **5-star ratings + count**, **hover/focus/tap preview (≤4 salient features)**, full comparison table, **consent sheet with ship-to + scope band**, receipt | Y2 | 3.5 | 2:10 → 7:00 | T-02 | own-Codex (high) | todo | Base: full happy path clickable against a mocked API, matching plates C2–C6, C8. Edge: long titles, 0 results, unrated product (no stars, not "0 stars"), network error, **double-click Confirm must not double-charge**, mid-stream disconnect. **Preview must open on hover AND keyboard focus AND tap, and close on Esc** — hover-only fails a judge on a trackpad. Amount on the Confirm button |
| T-35 | **Bank approval sheet — plate C7** (new in rev 3) + the ship-to block on C6 | Y2 | 1.0 | 7:00 → 8:30 | T-30, T-14 | own-Codex (med) | todo | Replaces the cut WebAuthn UI. Base: challenge sheet → code entry → approved, visibly the *bank's* surface not the merchant's. Edge: wrong code ×3 → locked with a clear message, expiry countdown reaching zero, "approve in app" alternate path. Warn on C6 before the handoff — an unannounced bank prompt reads as phishing |
| T-31 | **Trust Panel + plate C9** (decline recovery): live chain (now 7 links incl. bank approval), verification badges, constraint checks, the broken-link state and its recovery actions | Y2 | 2.5 | 9:00 → 13:00 | T-30, T-13 | own-Codex (high) | todo | Base: a purchase renders the chain step by step in real time. Edge: the declined run makes the broken link **obvious without narration**, and shows the three dead steps below it (*never asked* / *never troubled* / *never called*). Readable at 1.5 m by a standing judge |
| T-32 | **Merchant console — plates M1–M3, simplified**: one page, three sections (shop / catalog / go live). Auto-mapped columns as chips, per-row error list, copy-snippet button, SME-vs-large toggle. **No wizard state, no mapping screen, no persona screen** | Y2 | 2.5 | 13:00 → 17:00 | T-40, T-42 | own-Codex (high) | todo | Base: CSV upload → agent live on that merchant in **<90 s**, on stage, no code. Edge: malformed CSV → per-row errors and **partial success**, not a stack trace; empty catalog; duplicate SKUs |
| T-34 | **Live agent preview in the console** (new in rev 2): the real widget against the just-uploaded catalog, running from section one | Y2 | 1.0 | 17:00 → 18:00 | T-30, T-32 | own-Codex (med) | todo | Reuses T-30's widget — no second implementation. Base: preview re-renders as the shop is configured. The "90 seconds" claim is not credible without this |
| T-33 | **Demo-day polish**: Reset button, keyboard-driveable, responsive, ≤5 s cold start, no console errors, favicon/title | Y2 | 1.5 | 18:00 → 20:00 | all web | own-Codex (med) | todo | Ten consecutive demo runs with no reload-and-pray. Reset returns to a pristine state in one click |

## `merchant/` — catalog + discovery service · **Aryan (Y1)**

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-40 | **Catalog ingest**: CSV + JSON → normalised `Product` rows in SQLite; merchant registry with `size` (sme\|enterprise); per-row error reporting. **Rev 3: `rating_avg` / `rating_count` / `rating_source` columns, plus an enrichment hook that runs at ingest and caches** | Aryan | 2.25 | 2:10 → 5:00 | T-02, T-03 | own-Codex (med) | todo | Base: both seed catalogs ingest clean, ratings included. Edge: missing column, bad price, duplicate SKU, non-UTF8, 5 MB file, empty file → clear errors, partial success allowed. **Rating out of range or non-numeric → `rating_source: "none"`, never a guessed value. No network call at query time — ever** |
| T-43 | **Consumer addresses** (new in rev 3): `Address` model, default flag, `GET /consumer/{id}/addresses`, `PUT …/default`; **shipping address folded into the signed `cart_hash`** | Aryan | 0.5 | 5:00 → 5:30 | T-02 | own-Codex (med) | todo | Base: default address renders on plate C6 and on the receipt. Edge: no address on file → the agent asks for one before proposing a cart; address changed after the cart is signed → hash differs → `SHIPPING_ADDRESS_MISMATCH` at authorize. Coordinate the hash definition with Y4 (T-11) |
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

## Cut in revision 3 (do not restart these without a team vote)

- **Real WebAuthn passkey** (−1.5 h) — redundant now that the issuer authenticates the cardholder.
  An issuer token is a strictly stronger claim than device presence.
- **Cross-merchant search** (−1.25 h) — stretch S8, third on the cut list. The multi-merchant data
  model stays, so it's a config flag if we somehow finish early.

## Parking lot (do not start without displacing something)

Voice input · cross-merchant basket splitting · refunds/disputes · embeddings search · merchant
analytics · live URL catalog scraping · multi-currency · live ratings APIs at query time (ratings
are ingest-time only, by design — see `ux.md`).
