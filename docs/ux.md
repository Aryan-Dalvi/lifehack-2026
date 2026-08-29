# UX SPEC — the two surfaces

> Authored by Claude Code / Aryan, plan revision 2. **Wireframes (rendered):**
> `docs/wireframes.html` — open it locally, or
> https://claude.ai/code/artifact/f798d544-e897-4572-8421-925f2cb32a0a
>
> The HTML file is the picture; this file is the text a Codex window can act on. If they disagree,
> the HTML wins for layout and this file wins for behaviour. **Y2 owns both after the huddle.**

Wireframes are **specification, not visual design.** Colour, imagery, type and motion in the built
product are Y2's call — what's fixed here is what appears on each screen, in what order, and why.

---

## Part 1 — the shopper's conversation (plates C1–C9)

> **Renumbered in revision 3** — two screens landed mid-flow. Consent is now **C6** (was C5),
> declined is now **C9** (was C8).

### Six rules the surface obeys

1. **The spend limit is set before anything is searched.** A cap chosen in turn one is a natural UI
   gesture *and* the Intent Mandate. Consent becomes the frame of the conversation instead of a
   modal bolted on at the end.
2. **Detail arrives when it's asked for.** Four things on a resting card, four more on hover,
   everything on Compare.
3. **Every fact on screen has a source.** Ratings, prices and attributes all come from the
   merchant's catalog row. If it isn't in the database, it does not render.
4. **Money never appears without its scope.** Any screen showing a price also shows what the agent
   may do with it.
5. **A decline is a fork, not a wall.** C9 offers two ways forward.
6. **The Trust Panel is quiet until it matters** — then a link turns red and it carries the pitch.

### Plate index

| Plate | Screen | In MVP? | Owner |
|---|---|---|---|
| **C1** | Two delivery modes — embedded widget vs demo stage with Trust Panel rail | ✅ | Y2 |
| **C2** | Greeting + spend limit control → signs the Intent Mandate | ✅ | Y2 |
| **C3** | Discovery — minimal cards: image, name, price, **5-star rating + count** | ✅ | Y2 |
| **C4** | **Hover preview** — ≤4 salient features, on hover / focus / tap | ✅ | Y2 |
| **C5** | Comparison — **the full detail**, only after clicking Compare | ✅ | Y2 |
| **C6** | **Consent sheet** — ship-to, transaction preview, scope band, Trust rail | ✅ | Y2 |
| **C7** | **Bank approval** — issuer-minted, cart-bound, single-use token | ✅ | Y2 |
| **C8** | Receipt in-thread + link to the authorisation chain | ✅ | Y2 |
| **C9** | **Declined** — over-limit, with recovery actions | ✅ | Y2 |

### Ratings (C3, C5) — where the stars come from

**Ratings are a catalog field, not a live lookup.** `rating_avg` (0–5, one decimal),
`rating_count`, `rating_source` arrive with the merchant's feed and are ingested and cached by T-40.
An enrichment hook can fill gaps **at ingest time only** — that hook is where a mentor-supplied
ratings API would land. Nothing fetches a rating while a shopper is waiting, and nothing fetches one
during judging.

- Always render the **count** beside the average. *4.1 over 3,907 ratings is a different claim from
  4.8 over 612*, and showing only the average hides that.
- **Unrated products show no stars** — not "0 stars", which is a lie about a real product.
- Stars are deliberately **not gold**. Gold is reserved for human-decision moments (the C6 scope
  band); spending it on decoration would blunt the one place it means something.
- A rating is a **fact**: read from the row, rendered by code, never phrased by a model. The
  Guardian grounds ratings exactly as it grounds prices. A recommendation may say *"the
  better-reviewed of the two"*; it may not say a number that isn't in the payload.

### Progressive disclosure (C3 → C4 → C5)

| Stage | Shows | Trigger |
|---|---|---|
| Resting card | image, name, price, stars + count | — |
| **Preview** | ≤4 attributes from the pack's `salient_dims`, + "4 of 9 · compare for the rest" | **hover, keyboard focus, or tap** |
| **Compare** | every `comparison_dimension`, ratings row included, best-in-column highlighted | select 2–3, click Compare |

- The preview data **ships with the card** in the same `product_cards` event — no fetch, so it's
  instant and works with the network off.
- **Hover alone is not enough.** A judge on a trackpad in a crowded hall is exactly the person who
  fails to trigger a hover. Open on `mouseenter`, `focusin` and tap; close on Esc, blur, or a second
  tap. Screen readers get the attributes as a description, not a hover-only surface.
- Compare is a two-step (select, then compare) so it reads as deliberate rather than as a wall of
  specs nobody asked for.

### C6 — consent sheet (the screen that wins Trust & Safety)

Everything needed to say yes, above the fold, no scrolling. Ordered the way every checkout page
orders it — **ship-to first**:

- **Ship to:** recipient + one-line address, truncated, with `Change`. Sourced from
  `GET /consumer/{id}/addresses` (`is_default`).
- **Slip:** Merchant · Item × qty · Delivery estimate · Card `Visa •••• 4821` · **Total** (bold, rule above)
- **Scope band** (the only gold in the product):
  > *Charge this card **once**, for **this cart**, at **this merchant**, shipping to **this address**.
  > Nothing else. This permission expires in **4:52**.*
- **Buttons:** `Cancel` (ghost) · `Confirm & pay S$149.00` (primary — **the amount is on the button**)
- **Warning before the handoff:** "Your bank will ask you to approve this next." An unannounced bank
  prompt reads as a phishing attempt.
- **Trust rail** (7 steps): Spend limit ✓ · Agent identity ✓ `tag=agent-payer-auth` ·
  Cart + address signed ✓ · Within limit ✓ · **You — waiting** · Bank approval — not yet issued ·
  Authorise — not yet requested

**The address is inside the signed cart hash.** `cart_hash` covers
`{items, total, currency, merchant_id, shipping_address_id, shipping_address_fingerprint}`, so an
agent that redirects the goods after consent produces a different hash and the issuer token stops
matching. The ship-to line is not decoration — it is tamper-evident.

### C7 — bank approval (new in revision 3)

The **issuer**, not the merchant and not us, authenticates the cardholder for this one transaction.
Modelled on Visa Secure / EMV 3-D Secure; implemented as a mock ACS in `payments/` (T-14).

- Visually **the bank's surface**, not the merchant's: issuer chip (`◆ Meridian Bank · Visa Secure`),
  its own framing.
- Amount + merchant restated, 6-digit code entry, `Code sent to •••• 8821 · expires in 4:41`,
  and an "approve in the app instead" alternate path.
- "Lumen never sees this code. Neither does the agent."
- The token is **single-use, 5-minute TTL, and bound to cart hash + amount + merchant**.
  `/pay/authorize` refuses without a valid one.

Two things to say out loud: real 3-D Secure runs this as an **embedded challenge frame, not a page
redirect**, which is how "no redirects" survives contact with a bank — and this **replaces the device
passkey**, because a passkey proves the *device* is present while an issuer token proves the *bank*
authenticated the cardholder for this amount.

### C9 — declined (the demo's money shot)

Triggered by asking for something above the cap. Nothing is faked: the constraint check in
`payments/` genuinely refuses.

- Red banner: **"Not authorised — S$39 over your limit"** / "You set a S$150 limit for this chat.
  The Kestrel Studio 60 is S$189."
- Machine code beside it, small: `AMOUNT_EXCEEDS_MANDATE`
- Recovery: `Raise limit to S$189` · `Show options under S$150`
- Footnote: "Raising the limit re-signs your permission — you'll confirm again."
- Trust rail: first four ✓, **Within limit ✕ "189 > 150 — stopped here"**, then three dead steps —
  *You: never asked* · *Bank approval: never requested* · *Authorise: never called*.

> **The line to say out loud to a Visa judge:** the shopper was never asked, the bank was never
> troubled, and the network was never called. The refusal happened before any of them.

### Three refusals worth rehearsing

All three are real checks, not scripted branches. Lead with the first; keep the others for a judge
who asks "but what if…".

| Provoke it by | Decline code | What it proves |
|---|---|---|
| Asking for something over the limit | `AMOUNT_EXCEEDS_MANDATE` | The cap is enforced by the payment layer, not by the model's good manners |
| Approving once, then paying again with the same code | `BANK_TOKEN_REUSED` | Issuer approval is single-use and cart-bound; a stolen token buys nothing |
| Editing the cart or the address after approval | `BANK_TOKEN_CART_MISMATCH` / `SHIPPING_ADDRESS_MISMATCH` | What the shopper approved is what gets bought, and where they said to send it |

### Copy rules

- The word **"mandate" never appears in shopper-facing UI.** It's "spend limit", "your permission",
  "what the agent may do".
- Errors say what happened and how to move forward. No apologies.
- Prices are always `S$` + two decimals, tabular figures. Money is integer cents everywhere below
  the UI (`contracts.md`).
- The bank is named on C7 **and** on the receipt — naming the issuer is what a shopper checks when
  something looks wrong.

---

## Part 2 — merchant onboarding, simplified (plates M1–M3)

**One page, three sections, live preview from the first keystroke.** The claim on stage is
"ninety seconds from CSV to a live agent" — a five-screen wizard cannot make that claim.

### What was cut from contracts v0.9, and why it's safe

| Was | Now | Why |
|---|---|---|
| Five-screen wizard with back/next state | One page, three sections | No wizard state machine to build or break (~0.5 h saved) |
| Column-mapping screen | Auto-map on header names + editable chips | Real CSVs use `title`, `price`, `sku`. Show the guess, allow a correction |
| Agent persona config screen | Collapsed "Advanced" disclosure | Nobody tunes a persona in 90 s; the category pack sets the voice |
| "Connect API" as a separate path | One "Feed URL" field beside the file picker | Same ingest code, a third of the UI |
| Preview after publishing | Preview live from section one | The preview *is* the pitch |

### M1 — Your shop (~20 s)
Shop name · **category as 4 tiles** (Food / Fashion / Electronics / Travel — highest-consequence
choice, it loads the whole subagent pack) · **size toggle** (Small business / Large retailer — the
literal answer to the Scalability rubric line, so it must be visible) · one collapsed
`▸ Advanced` row, closed by default.

### M2 — Your catalog (~40 s)
Tabs: `Upload a file` · `Feed URL` · `Use sample`. Dropzone. Then:
- Result banner: **"48 products read · 2 rows need attention"** — **partial success is the default.**
  46 good rows beat a rejected file.
- Mapping shown as a *result*, not asked as a question: chips `title ← Product Name`,
  `price ← Price (SGD)`, `sku ← Item Code`, plus one `change` chip.
- Error list naming rows: `row 17  price "N/A" → skipped` / `row 33  duplicate sku KS-40 → kept first`.
  This is exactly the payload `POST /merchant/{id}/catalog` already returns — the UI just renders it.

### M3 — Go live (~10 s)
The snippet, one `Copy snippet` button, "Paste it before `</body>`. That's the whole integration."
Then three green checks: Catalog ✓ 46 products · Agent ✓ electronics pack · Payments ✓ Visa test mode.
Right rail: the **live preview**, running since M1, real widget against the real uploaded catalog.

### Fallback if the console slips past T+20
The ingest API is real and early (T-40), so we upload the CSV with `curl` on screen and show the
agent going live. The capability is what the rubric scores; the wizard is how we make it pretty.

---

## Part 3 — one agent becomes six

Rationale, diagrams and the roster table are in `docs/wireframes.html` Part 3. **Every step of the
run, with its exact input, output and required tools, is in `docs/agent-workflow.md`** — that is the
file to implement against. The contract-level
detail (message types, Guardian checks, ownership) lives in `docs/contracts.md` §Subagents.

**One-line summary:** facts travel through code, only phrasing travels through a model, and there is
no model at all from the cart downward — so "what if the AI hallucinates a price?" has the answer
*the AI never touches one*.
