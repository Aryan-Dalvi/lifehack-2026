# LifeHack 2026 — verified event facts

Sources: lifehack2026.nuscomputing.com (+ its official timeline PDF, "Transmission 002",
indicative), lifehack-2026.devpost.com, and the organisers' pre-event email. Compiled 28–29 Aug
2026. **Announcements land in the official Telegram channel — check it at every checkpoint.**

## Logistics

- **Dates/venue:** Sat 29 – Sun 30 Aug 2026, COM3, NUS School of Computing, 11 Research Link,
  S(119391). Main venue **COM3 MPH**; overflow SR1 & LT38. All timings SGT.
- **Reporting: 09:00 Sat**, MPH Foyer. QR-code check-in from registration. All members must be
  physically present to register.
- Team: 4 members (Y1 Aryan, Y2, Y3, Y4 — see `team.md`). Main Hackathon only.

## Schedule (from the official timeline PDF — marked indicative)

**Day 1 — Sat 29 Aug**
| Time | What |
|---|---|
| 09:00 | Arrival & registration (30 min), MPH Foyer |
| 09:30 | Opening ceremony & sponsor talks (90 min), COM3 MPH |
| **11:00** | **Problem statements released = T0. Hacking begins.** |
| 12:00 | Lunch (60 min), MPH & SR1 foyers |
| 13:00→ | Hacking continues (overnight) |

**Day 2 — Sun 30 Aug**
| Time | What |
|---|---|
| 09:00 | All three venues open for hacking |
| **11:00** | **T+24:00 — SUBMISSIONS DUE. The Devpost form locks.** |
| 11:00 | Lunch (45 min) |
| 12:00–14:30 | **Judging — walking format, COM3 MPH only.** Judges circulate to each station for live demos + technical Q&A; finalists then reviewed by panel (industry, NUS faculty, alumni) |
| 15:00–16:15 | Main Hackathon closing ceremony — **attendance required to win** |

⚠️ Discrepancy note: the org email says PSes are "uploaded to the website at 1:00 PM" while the
PDF says released 11:00 at the ceremony. Treat **11:00 as T0**; 13:00 website upload is the
backup copy. Also: each team receives an **allocated theme + company PS by email** — paste that
email into the "Allocated PS" section below the moment it arrives.

## Submission & judging

- **Deliverables: working prototype + PUBLIC repository + demo.** Submitted via **Devpost**
  (lifehack-2026.devpost.com); the exact form link is posted in the Telegram channel. Form
  fields/criteria "confirmed before the event".
- The repo must be **public by submission time** (it may stay private during the build — flip
  visibility before 11:00 Sun; this is a task on the board).
- **Judging criteria: NOT yet published.** Devpost placeholder mentions "Creativity". Until the
  official criteria are announced, plan against the proxy: creativity · impact · technical
  depth · demo quality. **→ PASTE OFFICIAL CRITERIA HERE at the ceremony and re-prioritise.**
- Walking format means the demo runs **many times over 2.5 h** at your own station: it must be
  restartable in seconds, resilient to repeated use, and every member must be able to drive it.

## Partners & prizes

- Partners / brief domains (5 briefs total; final lineup at ceremony): **Visa** — digital
  payments & agentic commerce · **Ecovolt** — AI, IoT & sustainable buildings · **CSIT** —
  cybersecurity, AI & secure systems · **Rezolve AI** — AI commerce, search & checkout
  (Devpost also lists ViSenze — AI product discovery/visual search).
- Prizes (Main): 1st S$3,000 · 2nd S$2,000 · 3rd S$1,000 · 3 special awards S$600 each.

## OpenAI credits

Each team gets **US$50 OpenAI API credits**; org staff on-site grant access (form was emailed —
one member's OpenAI-account email per the form). Budget policy in `ai-budget.md`.

## Allocated PS — **VISA** (received T0, 29 Aug 2026)

**"Conversational Commerce Agents for Every Merchant"** · source file: `Visa Problem Statement.pdf`
(repo root) · full breakdown in `docs/brief.md`.

**Challenge (verbatim):** "How might we enable merchants of any size to deploy pre-built,
category-trained AI commerce agents on their platforms, allowing customers to discover, decide, and
pay through a single conversation—powered by Visa's payment stack?"

**Expected submissions:** (1) AI agent layer — category-trained chatbot or voice assistant handling
discovery, recommendations, comparison, decision · (2) Merchant integration — upload catalog /
connect APIs / no-code setup, customisable for SMEs vs large retailers · (3) Seamless payment flow —
mock or simulated Visa payment, frictionless checkout **within the conversation (no redirects)** ·
(4) Trust, consent & transparency — user authorisation of agent actions, transaction previews,
identity verification, confirmation before the agent transacts.

**Expected output:** working prototype (web/app/chat) · demo/video of discover → decide → pay ·
brief written explanation of architecture, merchant onboarding flow, and trust/security handling.

## Official judging criteria — **from the Visa PS itself** (supersedes the proxy below)

1. **Innovation** — novelty of the agentic commerce experience
2. **User Experience** — simplicity and intuitiveness of the conversation flow
3. **Technical Feasibility** — realistic integration of AI + payment concepts
4. **Scalability** — applicability across merchants of different sizes
5. **Trust & Safety** — clear handling of consent, security, and transparency

> These five are the PS's own rubric. If the organisers publish separate event-level criteria in the
> Telegram channel, paste them here too and re-run `STATUS` to re-prioritise.
