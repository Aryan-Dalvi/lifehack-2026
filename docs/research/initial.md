# RESEARCH — agentic commerce, Visa's stack, and prior art

> Compiled by Claude Code / Aryan at T+0:25, 29 Aug 2026. Every claim carries a source.
> Red-team windows: append corrections in `docs/kickoff-review-<member>.md`, don't edit this file.

## 1. What Visa has actually shipped (this is what the judges work on)

### Visa Intelligent Commerce (VIC)
Visa's agent-payments product. Three API families, per the developer portal:

1. **Tokenization APIs** — provision **agent-specific tokens** for a user, verify card details at
   setup, manage token lifecycle.
2. **Authentication iFrame** — checks for / establishes a **Passkey** on the user's device and
   authenticates the user's *instruction* to purchase.
3. **Payment Instructions & Signals APIs** — enrol tokens, set/update/cancel **user instructions**,
   retrieve payment credentials for the merchant transaction, deliver transaction event
   notifications.

Positioning: agents get "tokenized credentials **bound to agents**", user authentication is
mandatory for purchases, and controls "align the agent's payment actions with the user's original
authenticated instructions."

- https://developer.visa.com/use-cases/visa-intelligent-commerce-for-agents
- https://corporate.visa.com/en/products/intelligent-commerce.html
- https://developer.visa.com/capabilities/visa-intelligent-commerce

**Sandbox reality check:** the portal has no self-serve mock we can reach in 24h; it routes you to
"Register/Sign In" and project approval, and the product is flagged "in the process of development
and deployment." → **Assumption A1 holds: we simulate.** Ask mentors (brief §7 Q1) in case they can
hand us keys on-site.

### Trusted Agent Protocol (TAP) — **the most useful thing we found**
Open spec from Visa + Cloudflare, announced Oct 2025, aligned with IETF / OpenID Foundation / EMVCo,
explicitly designed to **complement** ACP rather than compete. It answers, cryptographically:
*is this agent legitimate, and is a real consumer behind it?*

Built on **HTTP Message Signatures (RFC 9421)**. Concrete, implementable surface:

| Element | Detail |
|---|---|
| Headers | **`Signature-Input`** (dictionary structured field, signature metadata) and **`Signature`** (the signature itself) |
| Minimum covered components | `@authority`, `@path`, `created`, `keyid`, `expires`, `alg`, `nonce`, `tag` |
| `tag` values | **`agent-browser-auth`** (browsing / product info) · **`agent-payer-auth`** (payment / checkout) |
| Agentic Consumer Recognition Object | `nonce`, `idToken` (JWT from the payment scheme), `contextualData` (device/location), `kid`, `alg`, `signature` |
| Agentic Payment Container | `nonce`, `kid`, `alg`, `paymentCredentialsHash`, `cardMetadata` (e.g. last four), `payload` (encrypted payment object), `browsingIOU` (invoice object for HTTP 402 responses) |
| Architecture in the reference impl | TAP Agent → CDN proxy (verifies signature) → merchant backend; plus an **Agent Registry** holding public keys + metadata |
| Reference code | Python (FastAPI backend + agent registry), Node.js (CDN proxy), React frontend, Streamlit agent — in the public repo |

- Spec: https://developer.visa.com/capabilities/trusted-agent-protocol/trusted-agent-protocol-specifications
- Repo: https://github.com/visa/trusted-agent-protocol
- Announcement: https://usa.visa.com/about-visa/newsroom/press-releases.releaseId.21716.html
- Explainer: https://eco.com/support/en/articles/14845482-visa-trusted-agent-protocol-tap-explained

**→ Direct action for us:** our `payments/` module implements this *shape* — same two headers, same
covered components, same two `tag` values, an agent registry of public keys, and a verifying
middleware standing in for the CDN proxy. Saying "we implemented Visa's own TAP shape" to a Visa
judge is worth more than any amount of UI polish. **Check the repo's LICENSE before copying any code
— read it, don't vendor it blind.** Reimplement from the spec; cite the repo.

### Visa Intelligent Commerce Connect / MCP server / Agent Toolkit (2026)
- **Connect**: a "network, protocol and token-vault-agnostic on-ramp to agentic commerce… via a
  single integration" through the Visa Acceptance Platform — piloting Apr 2026 with AWS, Diddo,
  Highnote, Mesh, Payabli, Sumvin.
- **MCP Server for VIC**: lets developers reach VIC APIs over Model Context Protocol.
- **Visa Acceptance Agent Toolkit**: plain-language, no-code agent setup, in pilot.

- https://corporate.visa.com/en/sites/visa-perspectives/innovation/visa-mcp-server-agent-acceptance-toolkit.html
- https://www.pymnts.com/artificial-intelligence-2/2026/visa-aims-to-give-businesses-agentic-commerce-on-ramp/
- https://usa.visa.com/about-visa/newsroom/press-releases.releaseId.22276.html

**→ Narrative gift:** "on-ramp", "single integration", "no-code" is *Visa's own language for our
merchant-onboarding module*. Use their words in the pitch and the README.

## 2. The competing / stacking protocols (know these; a judge will ask)

| Protocol | Who | Answers | Mechanism |
|---|---|---|---|
| **ACP** (Agentic Commerce Protocol) | OpenAI + Stripe | *how* checkout executes inside an AI surface | Stripe **Shared Payment Token**; agents transact without seeing buyer credentials. Stable spec `2026-04-17`. PayPal joined Oct 2025; Stripe Agentic Commerce Suite shipped Dec 2025 |
| **AP2** (Agent Payments Protocol) | Google + 60 partners | *who authorised* the purchase | Three **W3C Verifiable Credential** mandates — **Intent → Cart → Payment** — a tamper-proof signed chain. v0.2 donated to the **FIDO Alliance**, 28 Apr 2026 |
| **TAP** | Visa + Cloudflare | *is this agent legitimate* at the merchant edge | RFC 9421 HTTP message signatures (above) |
| **x402** | Coinbase-origin | machine-native payment over HTTP **402** | per-request settlement |

They **stack**, they don't replace each other.

- https://www.crossmint.com/learn/agentic-payments-protocols-compared
- https://wetheflywheel.com/en/agentic-commerce/acp-vs-ap2/
- https://orium.com/blog/agentic-payments-acp-ap2-x402
- https://agenticplug.ai/current-state-of-agentic-commerce

**→ Design decision this drives:** our trust layer = **TAP shape at the transport edge** +
**AP2-shaped Intent/Cart/Payment mandate chain** as the consent artifact. Two real standards,
one coherent story, both cheap to mock convincingly. When a judge asks "why not ACP?", the answer is:
*ACP is the checkout execution layer and it assumes a hosted AI surface; our merchant hosts the
agent themselves, so we need identity (TAP) and authorisation (AP2), not a marketplace protocol.*

## 3. Prior art — what will make a judge say "seen it"

- **ChatGPT Instant Checkout was deprecated in March 2026.** The current ACP-era pattern is
  *product discovery + redirect to the merchant's site* — the agent recommends, the shopper
  completes on the merchant's own checkout.
  https://www.hypotenuse.ai/blog/chatgpts-instant-checkout-the-next-phase-of-agentic-commerce
- **Perplexity** — conversational discovery, product cards, instant checkout via PayPal.
- **Google** — agentic checkout in Search AI Mode and Gemini; "Buy for me" executes on merchant sites.
- **Shopify-ecosystem chatbots** — live catalog, in-conversation recommendations, order status.
  https://commercetools.com/blog/ai-trends-shaping-agentic-commerce ·
  https://www.yotpo.com/commerce-gpt/ai-conversational-commerce-guide/

**Seen-it list (avoid framing our work as any of these):** "a chatbot that recommends products",
"AI product search", "an ecommerce copilot", "RAG over a catalog".

**The gap we aim at:** everyone retreated to *redirect* because in-conversation payment is a trust
problem, not a UI problem. The PS demands **"no redirects."** So we ship the trust artifact — a
verifiable chain of consent — and the redirect becomes unnecessary. Two of the five rubric lines
(Innovation, Trust & Safety) are won by exactly this argument.

## 4. Build inputs — libraries, data, licences

| Need | Pick | Note |
|---|---|---|
| Signatures / JWS / ed25519 | Python **`cryptography`** (BSD/Apache dual) | ed25519 keygen+sign+verify is ~10 lines; avoid heavyweight JOSE libs |
| RFC 9421 | **hand-roll from the spec** | ~80 lines for the subset we need; third-party libs are immature and would cost more than they save |
| Backend | **FastAPI + uvicorn + SQLite** (MIT/BSD) | one process, three routers, zero infra — critical for "restartable in seconds" |
| Frontend | **Vite + React + Tailwind** (MIT) | fastest path to a polished chat widget |
| LLM | OpenAI API, **mini/nano tier**, tool calling + streaming | `docs/ai-budget.md`: ≤$10 dev, ~$25 held for judging |
| Passkeys | **`@simplewebauthn/browser` + `py_webauthn`** (MIT) | localhost is a valid WebAuthn RP origin; still a stretch goal — simulated sheet is the fallback |
| Catalog seed data | hand-authored JSON/CSV + placeholder images | **Do not scrape a real retailer.** Invent merchants; keeps licensing clean and the demo stable offline |
| Product images | local `/static` files or CSS-generated cards | Never hotlink — venue wifi will betray us during judging |

### Needs sign-up / lead time — decide in the first hour
- **OpenAI API key** — the team's $50 grant; org staff grant on-site. **Get this before T+2**; the
  agent module is blocked without it. (T-03 dependency.)
- **Visa Developer portal** — needs project approval; *not* obtainable in 24h. Don't start the
  application; ask a mentor instead (brief §7 Q1).
- **Devpost** — every member should already have an account (pre-event checklist).
- Nothing else requires an account. No cloud deploy, no Docker registry, no domain.

## 5. Open questions this research could not settle

1. Whether any Visa sandbox is reachable on-site today → mentor question Q1.
2. Whether the judges weight the five rubric lines equally → mentor question Q2.
3. Exact TAP `browsingIOU` semantics for HTTP 402 flows — under-documented publicly; we don't need
   it for the MVP, so we note it as "future work" in the README rather than guessing.
