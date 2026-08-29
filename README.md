# LifeHack 2026 — Team Repo

## Sway prototype

Sway is a plug-and-play skincare commerce agent for **Mysa Skin**. A merchant can upload a
CSV/XLSX/JSON catalog, then publish the same grounded shopping experience as either an isolated
website widget or a hosted storefront. Shoppers can discover and deterministically compare
products, optionally set or change a spending limit, preview a server-priced transaction,
explicitly consent, complete a bank OTP challenge, and receive an auditable receipt.

The demo uses a clearly labelled payment simulator: **no real card is charged**. The simulator
OTP is `492118`. The payer request is nevertheless signed and verified with Ed25519 using a
TAP-shaped HTTP Message Signature before the simulated authorization can run. The AI model never
authorizes payments or creates orders.

### Run locally (PowerShell)

Prerequisites: Python 3.11+ and Node.js 20+.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm --prefix web install
.\.venv\Scripts\python.exe -m seed.reset
.\.venv\Scripts\python.exe -m scripts.dev
```

Open `http://localhost:5173/storefront?merchant=m_mysa` for the hosted storefront or
`http://localhost:5173/admin` for merchant setup. The generated one-line widget snippet is shown
in the admin surface. Demo mode is deterministic by default; set `DEMO_MODE=0` and provide an
`OPENAI_API_KEY` to enable one structured Responses API interpretation call per ambiguous shopper
turn, with deterministic catalog and checkout tools remaining authoritative.

### Verify

With the app running for the browser tests:

```powershell
.\.venv\Scripts\ruff.exe check app agent merchant payments seed scripts tests
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix web run build
npm --prefix web run test:e2e
```

See [the architecture decision aid](docs/architecture-flowchart.md) for deployment and trust
boundaries. The implementation intentionally keeps Phase 0 to one category: skincare.
