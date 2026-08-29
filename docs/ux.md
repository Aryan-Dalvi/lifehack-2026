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

## Part 1 — the shopper's conversation (plates C1–C8)

### Four rules the surface obeys

1. **The spend limit is set before anything is searched.** A cap chosen in turn one is a natural UI
   gesture *and* the Intent Mandate. Consent becomes the frame of the conversation instead of a
   modal bolted on at the end.
2. **Money never appears without its scope.** Any screen showing a price also shows what the agent
   may do with it.
3. **A decline is a fork, not a wall.** C8 offers two ways forward.
4. **The Trust Panel is quiet until it matters** — then a link turns red and it carries the pitch.

### Plate index

| Plate | Screen | In MVP? | Owner |
|---|---|---|---|
| **C1** | Two delivery modes — embedded widget vs demo stage with Trust Panel rail | ✅ | Y2 |
| **C2** | Greeting + spend limit control → signs the Intent Mandate | ✅ | Y2 |
| **C3** | Discovery — 3 product cards, limit applied as a filter | ✅ | Y2 |
| **C4** | Comparison — table on the category pack's dimensions + one recommendation | ✅ | Y2 |
| **C5** | **Consent sheet** — transaction preview, scope band, Trust rail | ✅ | Y2 |
| **C6** | Identity check — passkey sheet | stretch → simulated | Y2 |
| **C7** | Receipt in-thread + link to the authorisation chain | ✅ | Y2 |
| **C8** | **Declined** — over-limit, with recovery actions | ✅ | Y2 |

### C5 — consent sheet (the screen that wins Trust & Safety)

Everything needed to say yes, above the fold, no scrolling:

- **Slip:** Merchant · Item × qty · Card `Visa •••• 4821` · **Total** (rule above it, bold)
- **Scope band** (the only gold element in the whole product):
  > *Charge this card **once**, for **this cart**, at **this merchant**. Nothing else.
  > This permission expires in **4:52**.*
- **Buttons:** `Cancel` (ghost) · `Confirm & pay S$149.00` (primary — **the amount is on the button**)
- **Links:** "Why am I seeing this?" · "What can this agent do?"
- **Trust rail** (6 steps): Spend limit set ✓ · Agent identity ✓ `tag=agent-payer-auth` ·
  Cart signed ✓ · Within limit ✓ · **You — waiting** · Authorise — not yet requested

The shopper *is* the missing link, and the rail says so before anyone explains it.

### C8 — declined (the demo's money shot)

Triggered by asking for something above the cap. Nothing is faked: the constraint check in
`payments/` genuinely refuses.

- Red banner: **"Not authorised — S$39 over your limit"** / "You set a S$150 limit for this chat.
  The Kestrel Studio 60 is S$189."
- Machine code beside it, small: `AMOUNT_EXCEEDS_MANDATE`
- Recovery: `Raise limit to S$189` · `Show options under S$150`
- Footnote: "Raising the limit re-signs your permission — you'll confirm again."
- Trust rail: first three ✓, **Within limit ✕ "189 > 150 — stopped here"**, then two dead steps —
  *You: never asked* · *Authorise: never called*.

> **The line to say out loud to a Visa judge:** the shopper was never asked, and the network was
> never called. The refusal happened before either.

### Copy rules

- The word **"mandate" never appears in shopper-facing UI.** It's "spend limit", "your permission",
  "what the agent may do".
- Errors say what happened and how to move forward. No apologies.
- Prices are always `S$` + two decimals, tabular figures. Money is integer cents everywhere below
  the UI (`contracts.md`).

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

Rationale, diagrams and the roster table are in `docs/wireframes.html` Part 3. The contract-level
detail (message types, Guardian checks, ownership) lives in `docs/contracts.md` §Subagents.

**One-line summary:** facts travel through code, only phrasing travels through a model, and there is
no model at all from the cart downward — so "what if the AI hallucinates a price?" has the answer
*the AI never touches one*.
