# BRIEF — Visa: Conversational Commerce Agents for Every Merchant

> Authored by **Claude Code / Aryan** at **T+0:25** (T0 = 11:00 Sat 29 Aug 2026).
> These are **recommendations**. Y4 + the team decide at the huddle; changes get written back here.
> Source PS: `Visa Problem Statement.pdf` (also transcribed into `docs/event.md`).

---

## 1. The problem in two sentences

Shopping today is split across browse / compare / decide / pay surfaces, and SMEs can't afford to
build AI commerce experiences of their own. Visa wants a **plug-and-play layer that lets any
merchant — corner shop or big retailer — drop in a category-trained AI agent that carries a
customer from discovery all the way to a completed, trusted payment inside one conversation.**

## 2. What the sponsor actually cares about

Visa is a **network and a trust broker**, not a shop. They do not make money from our chatbot; they
make money when a transaction flows over rails people trust. Their public 2025–26 agentic push is
exactly this thesis:

- **Visa Intelligent Commerce** — agent-bound tokenized credentials, passkey authentication of the
  user's instruction, and controls that bind an agent's spending to what the human actually
  authorised.
- **Trusted Agent Protocol (TAP)** — an open spec (with Cloudflare) that cryptographically signs an
  agent's identity, intent and consumer recognition into HTTP headers so a merchant can answer
  "is this agent legitimate, and did a human authorise it?"
- **Visa Intelligent Commerce Connect / MCP server / Acceptance Agent Toolkit** — the on-ramp story:
  one integration, any merchant, low-code.

**Read: the judges from Visa will reward the trust, consent and merchant-onboarding layers at least
as much as the chatbot.** Anyone can ship a shopping chatbot in 24h. Almost nobody will ship one
that can *prove* the agent was authorised. That is our wedge. (Full sourcing: `docs/research/initial.md`.)

## 3. Explicit requirements — checklist

From the PS, verbatim where wording matters. Every line here maps to task IDs in `docs/coverage.md`.

**Must deliver ("Expected Submissions"):**

- [ ] **R1 — AI Agent Layer.** "A chatbot or voice assistant **trained for a specific category**
      (e.g., food ordering, fashion, electronics, travel bookings etc.)"
- [ ] **R2** — agent "Handles product discovery, recommendations, **comparison** and decision to buy"
- [ ] **R3 — Merchant Integration.** "A simple way for merchants to become ready for agents to shop
      (e.g., upload catalog, connect APIs, **no-code/low-code setup**)"
- [ ] **R4** — "**Customizable for different merchant types / sizes (SMEs vs large retailers)**"
- [ ] **R5 — Seamless Payment Flow.** "Integrate a **mock or simulated Visa payment flow**"
- [ ] **R6** — "frictionless checkout within the conversation (**no redirects**)"
- [ ] **R7 — Trust, Consent & Transparency.** "Show how users **authorize** agent-driven actions
      (e.g., confirming purchases)"
- [ ] **R8** — "safeguards like **transaction previews, identity verification, confirmation before
      agent transacts**"

**Must produce ("Expected Output"):**

- [ ] **R9** — a working prototype (web/app/chat interface)
- [ ] **R10** — demo/video of the end-to-end flow: **discover → decide → pay**
- [ ] **R11** — brief written explanation of (a) architecture (AI + payments integration),
      (b) merchant onboarding flow, (c) how trust and security are handled

**Plus event-level requirements** (`docs/event.md`): public repo by 11:00 Sun, Devpost submission,
demo restartable and drivable by all 4 members through 2.5h of walking-format judging.

**Judging rubric — official, from the PS itself** (this supersedes the proxy criteria in `event.md`):

| Rubric | What it rewards | Our answer |
|---|---|---|
| **Innovation** | novelty of the agentic commerce experience | in-conversation completion with a verifiable authorisation chain — the thing the market retreated from (see §4) |
| **User Experience** | simplicity + intuitiveness of the conversation | one thread, zero redirects, ≤4 turns to a paid order |
| **Technical Feasibility** | realistic AI + payment integration | we mirror the *real* shapes: RFC 9421 signatures, AP2-style mandates, network tokens with constraints |
| **Scalability** | applicability across merchant sizes | two live merchants in the demo — an SME (CSV upload) and a large retailer (API feed) — same agent, same rails |
| **Trust & Safety** | consent, security, transparency | the Trust Panel + a **live declined over-budget purchase** on stage |

### Ambiguous / unstated (assumptions we're planning on)

| # | Ambiguity | Our stated assumption |
|---|---|---|
| A1 | "mock or simulated Visa payment flow" — how real? | Fully simulated in-repo. **No real Visa sandbox credentials** (Visa Developer access has application lead time we don't have). We model the real API *shapes* and say so openly. |
| A2 | "category-trained" — fine-tuned model, or category-specialised agent? | **Not** fine-tuning (no time, no data). Category = a swappable pack: system prompt + attribute schema + comparison dimensions + guardrails. We ship 2–3 packs to prove the pattern. |
| A3 | Voice assistant — required or an "or"? | PS says "chatbot **or** voice assistant". We ship chat; voice input is a stretch (Web Speech API, ~1h) and is **first on the cut list**. |
| A4 | "a seller **or a category of sellers**" | Multi-merchant discovery is in scope. We make `merchant_id` a first-class field from hour one so cross-seller search is a config flag, not a rewrite. |
| A5 | Who is the customer of the *product* — merchant or shopper? | Both, and the demo must show both surfaces: merchant console (onboarding) + shopper chat. |

## 4. Candidate directions

Scored 1–5. Wow = judge reaction; Feas = 4 people / 24h; Fit = to the PS; Demo = in a 3-min walking pitch.

### A — "Agent-Ready in 90 Seconds": merchant onboarding platform + category agent + in-chat Visa checkout ✅ **RECOMMENDED**
A merchant signs up, uploads a catalog (CSV) or points at a feed, picks a category pack, and copies
an embed snippet. That snippet drops a chat agent onto their site that discovers, compares,
recommends and **pays in-thread** over a simulated Visa stack, with every agent action carrying a
verifiable authorisation chain shown live in a Trust Panel.

| Wow | Feas | Fit | Demo |
|---|---|---|---|
| 4 | 4 | **5** | 5 |

**Why this one:** it is the *only* option that hits all four "Expected Submissions" head-on rather
than 2 of 4. It is separable into four clean parallel modules with a thin end-to-end slice reachable
by T+8. And the demo has a genuine dramatic beat (§5).

### B — Cross-merchant "category concierge": one agent shops across many SMEs, one basket, one payment
Higher ceiling on Innovation and Scalability; needs basket splitting, multi-merchant settlement and
much more catalog normalisation.

| Wow | Feas | Fit | Demo |
|---|---|---|---|
| 5 | 2 | 4 | 4 |

**Verdict: don't build as the spine — absorb the cheap 80%.** Direction A's data model is
multi-merchant anyway, so we demo "search across the whole category" as a *feature of A* (~1.5h)
and skip split settlement entirely.

### C — Voice-first agent for hawker / food SMEs (local angle)
Charming, locally resonant, low technical depth; voice in a loud MPH during walking judging is a
liability, not an asset.

| Wow | Feas | Fit | Demo |
|---|---|---|---|
| 3 | 3 | 3 | 2 |

**Verdict: no.** Keep the food category pack; drop the voice-first framing.

### The one-line pitch (direction A)

> **Stripe-style "paste one snippet" onboarding, but what you're installing is a shopping agent that
> can be trusted with a card — because every purchase carries a cryptographic chain proving a human
> authorised exactly this cart, this amount, this merchant.**

### Why this isn't "seen it"

ChatGPT's Instant Checkout was **deprecated in March 2026**; the mainstream ACP pattern collapsed
back to *discovery + redirect to the merchant's site*. Perplexity/PayPal and Google's "Buy for me"
also lean on the merchant's own checkout. The PS explicitly asks for **"no redirects."** So the
honest framing for the judges is: *the industry retreated from in-conversation payment because trust
wasn't solvable — here's the trust layer that makes it solvable, built on Visa's own TAP shape.*
That's a real argument, not a demo trick.

## 5. MVP, stretch, cut list

### MVP — the walking skeleton, on `main` and demoable by **T+8**

One category (electronics or fashion — team picks at huddle), one seeded merchant, happy path only:

> Shopper types *"I need running shoes under $150 for flat feet"* → agent searches the catalog →
> returns 3 product cards with a comparison → shopper picks one → agent shows a **transaction
> preview** (item, price, merchant, total) → shopper hits **Confirm** → simulated Visa authorisation
> → receipt appears in the same thread. **No redirect, no new tab, no form.**

Merchant console shows the seeded catalog and the embed snippet (can be static at this stage).

### Stretch goals, in build order

1. **S1 — Trust Panel** (live): mandate chain + signature verification badges rendering beside the chat. *Highest rubric value per hour.*
2. **S2 — The decline demo**: agent instructed to buy something over the authorised cap → payment **declined** with `AMOUNT_EXCEEDS_MANDATE`, shown in the panel. *This is the money shot.*
3. **S3 — Real merchant onboarding**: CSV upload → normalised catalog → agent live, in under 90s, on stage.
4. **S4 — Second merchant of a different size** (SME CSV vs large-retailer JSON feed) → rubric item "Scalability" answered literally.
5. **S5 — TAP-shaped HTTP signatures** (RFC 9421 `Signature` / `Signature-Input`, `tag=agent-browser-auth|agent-payer-auth`) verified at the merchant edge.
6. **S6 — Passkey (WebAuthn) confirmation** instead of a plain button.
7. **S7 — Category packs** (2–3) swappable from the merchant console.
8. **S8 — Cross-merchant search** across the category.
9. **S9 — Voice input.**

### Pre-agreed cut list — what dies first, in order

1. Voice input (S9)
2. Real WebAuthn passkey → **simulated** passkey sheet (S6 degrades, doesn't vanish)
3. Cross-merchant search (S8)
4. Third category pack (S7 → keep 2)
5. Embedding-based semantic search → keyword + attribute filters
6. Refunds / disputes / order history
7. Live URL-scrape catalog ingest → CSV + JSON only
8. Merchant analytics dashboard

**Never cut:** the decline demo (S2), the Trust Panel (S1), demo-mode fallback, the backup recording.

## 6. Biggest risks

| # | Risk | Mitigation | Owner |
|---|---|---|---|
| **1** | **`docs/team.md` is still empty** — every allocation below is from role archetypes, not real strengths. A bad module fit costs more than any technical risk here. | Fill it in the first 5 minutes of the huddle; re-allocate on the spot. | Aryan |
| **2** | LLM API dies / rate-limits / $50 runs dry **during 2.5h of judging** | `DEMO_MODE=1` deterministic scripted agent, built at T+6 not T+20 (T-21). Cheap model + prompt caching + capped `max_tokens`. ~$25 protected for demo day. | Y3 |
| 3 | Crypto rabbit hole — RFC 9421 / JWS eats a whole day | Timebox T-12 hard. Fallback: HMAC-signed JSON envelopes with the same *field shape*; the narrative survives, the mandate chain still verifies. | Y4 |
| 4 | Demo fragility across 2.5h of repeated runs | One process, one `make dev`, a **Reset** button, seeded DB, and all 4 members rehearsed (T-54). | Aryan |
| 5 | Scope creep into a real payments integration | A1 is a stated assumption, printed in the README and said out loud in the pitch. Simulation is *correct*, per the PS wording. | Y4 |
| 6 | Merge conflicts across 4 people + 5 AI windows | Directory-per-owner + frozen `contracts.md` + checkpoints at T+4/9/15/20. | Y3/Y4 |

## 7. Questions for the Visa mentors / sponsor reps

Ask these at the first mentor walkaround. **Do not block on answers** — we build on the A1–A5
assumptions above and adjust.

1. **Is there any sandbox we can actually reach today** — a Visa Intelligent Commerce or Trusted
   Agent Protocol test endpoint, an MCP server, or sample keys — or do you expect a self-contained
   simulation? (Changes T-10/T-12 from "mock" to "integrate".)
2. **Which layer do you most want to see done well: the merchant on-ramp, or the trust/consent
   layer?** If we can only make one excellent in 24h, which earns more?
3. **For agent-initiated payments, what does Visa consider the minimum acceptable consent artifact** —
   is a signed cart mandate + explicit human confirmation per transaction enough, or do you expect
   standing/delegated mandates with spend caps as the primary model?
