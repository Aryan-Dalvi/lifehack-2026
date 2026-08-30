# Sway — conversational commerce for any skincare merchant

Sway is a plug-and-play shopping agent any skincare merchant can stand up for themselves —
self-service sign-up, no admin gatekeeping a key. A merchant brands their store (name, logo),
uploads or edits a catalog from a dashboard with real product management and sales insights, then
publishes the same grounded shopping experience as a one-line embeddable widget or a hosted
storefront. Nothing here is hard-coded to one demo merchant: catalog rows, receipts, and the
agent's own answers all name the actual shop a shopper is standing in.

**Shopper side:** discover by chat or by browsing categories, compare products in a deterministic
table, ask the agent general skincare questions (not just search), set or change a spending limit,
enter a card, preview a server-priced cart, explicitly consent, complete a bank OTP challenge, and
get a receipt on screen and by email — with a live trust rail showing each verification step.

**Trust boundary, unchanged since the first commit:** the model never sees a raw card number,
never calculates a total, and never authorizes a payment or creates an order — that path is
deterministic code only. The payer's request is signed and verified with Ed25519 using a
TAP-shaped HTTP Message Signature before a (simulated, by default) authorization can run.

## Payment adapter

Two interchangeable adapters sit behind one interface, chosen by `PAYMENT_ADAPTER`:

- **`simulator`** (default) — the reliable demo path. No real card is ever charged; the OTP is
  `492118`.
- **`visa`** — a real VisaNet Connect Acceptance Authorization call against Visa's sandbox (mTLS,
  Message Level Encryption, the Authorizations v3 envelope). It only activates once every
  credential in `.env.example`'s Visa block is present and correct; `GET /health` reports
  `payment_ready: false` otherwise, and the adapter refuses to run rather than guess.

Never flip this to `visa` for a demo you haven't verified end-to-end against the sandbox first.

## Run locally

Prerequisites: Python 3.11+, Node.js 20+.

```bash
cp .env.example .env   # then fill in OPENAI_API_KEY at minimum — see the file for every option
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
npm --prefix web install
./.venv/bin/python -m seed.reset
./.venv/bin/python scripts/dev.py
```

<details>
<summary>PowerShell</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm --prefix web install
.\.venv\Scripts\python.exe -m seed.reset
.\.venv\Scripts\python.exe -m scripts.dev
```
</details>

`seed.reset` seeds a demo merchant, a demo shopper (`demo@mysa.test` / `mysa-demo-password`), and
demo order history, then writes the demo merchant's API key to `var/merchant-key.txt` (gitignored).

Open:
- **`/`** — landing page
- **`/admin`** — merchant dashboard (sign up fresh, or open the demo store from the front door)
- **`/storefront?merchant=<id>`** — the shopper storefront for that merchant
- One-line embed for any merchant's own site: `<script src=".../widget.js" data-merchant="m_…">`

`DEMO_MODE=0` with `OPENAI_API_KEY` set runs one structured interpretation call per ambiguous
shopper turn (or one further bounded call for a routine explanation or a general question);
`DEMO_MODE=1` runs a deterministic parser and makes no model calls at all. Either way, catalog
search, cart pricing, consent, and checkout are deterministic code, never the model.

## Verify

With the app running (for the Playwright specs):

```bash
./.venv/bin/ruff check app agent merchant payments seed scripts tests
./.venv/bin/python -m pytest -q
npm --prefix web run build
npm --prefix web run test:e2e
```

See [`docs/architecture-flowchart.md`](docs/architecture-flowchart.md) for deployment and trust
boundaries, [`docs/contracts.md`](docs/contracts.md) for the API contract (draft, pending freeze),
and [`docs/testing.md`](docs/testing.md) for the dated log of every test pass run against this repo.
The implementation intentionally keeps Phase 0 to one category: skincare.
