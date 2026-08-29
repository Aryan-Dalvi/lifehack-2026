# COVERAGE MATRIX — every PS requirement → the tasks that deliver it

> Built by KICKOFF at T+0:40. **`STATUS` re-checks this every run.** A requirement with no task, or
> a task with no owner or no timebox, is a defect — fix it the moment it appears.

## Requirements → tasks

| # | Requirement (from `brief.md` §3) | Delivered by | MVP? | Risk |
|---|---|---|---|---|
| **R1** | Category-trained chatbot/voice assistant | T-20 (agent loop), **T-23 (category packs)**, T-03 (category seed data) | partial — one category at MVP | med — T-23 lands late (T+16); if cut, R1 rests on a single hard-coded pack. **Keep at least 2 packs.** |
| **R2** | Discovery, recommendations, **comparison**, decision | T-20, T-41 (search), T-30 (product cards + comparison view) | ✅ yes | low |
| **R3** | Simple merchant onboarding (upload catalog / connect API / no-code) | **T-32 (console wizard)**, T-40 (ingest), T-42 (config + embed snippet) | no — MVP uses seeded catalogs | **high** — console is the latest-starting rubric-critical task (T+13). Ingest API (T-40) is early and real, so the capability exists even if the UI slips; slip rule at T+20 covers it. |
| **R4** | Customisable for merchant types/sizes (SME vs large) | T-03 (two merchants, two sizes), T-40 (`size` field), T-32 (size preset), T-41 (cross-merchant) | ✅ yes — cheap, high rubric value | low |
| **R5** | Mock/simulated **Visa** payment flow | **T-10 (token vault, authorize/capture)** | ✅ yes | low |
| **R6** | Frictionless checkout **in the conversation, no redirects** | T-30 (confirm sheet + receipt in-thread), T-20 (`execute_payment` tool) | ✅ yes — this is the MVP's defining property | low |
| **R7** | Users **authorize** agent-driven actions | T-30 (transaction preview + Confirm), **T-11 (mandate chain)**, T-22 (intent mandate), S6 passkey (stretch) | ✅ yes | low |
| **R8** | Safeguards: transaction previews, identity verification, confirmation before transacting | T-30 (preview), **T-13 (safeguard rules + decline)**, T-12 (agent identity via TAP), T-31 (Trust Panel) | partial at MVP (preview + confirm); full by T+17 | med — T-12/T-13 are the crypto-risk block. Slip rules in `timeline.md` degrade them without losing the story. |
| **R9** | Working prototype (web/app/chat) | T-02, T-30, T-33 | ✅ yes | low |
| **R10** | Demo/video of discover → decide → pay | **T-55 (script + rehearsal)**, **T-56 (backup recording)** | ✅ yes | low — but only if T+21 freeze holds |
| **R11a** | Written explanation: architecture (AI + payments) | T-52 (README + diagram), T-53 | ✅ yes | low |
| **R11b** | Written explanation: merchant onboarding flow | T-53 | ✅ yes | low |
| **R11c** | Written explanation: trust & security handling | T-53 | ✅ yes | low |
| **E1** | Public repo by 11:00 Sun | T-57 | ✅ yes | low — but it's a 15-min task that has sunk teams. It's on the timeline at T+22:45. |
| **E2** | Devpost submitted before T+24 | T-54 (draft T+19, submit T+23) | ✅ yes | low |
| **E3** | Demo restartable + drivable by all 4 through 2.5 h | T-33 (reset), T-21 (demo mode), T-55 (all four rehearse) | ✅ yes | med — needs the rehearsal to actually happen, not get squeezed |

**No requirement has zero tasks. No task lacks an owner or a timebox.** ✅

## Rubric → evidence the judge will actually see

| Rubric line | The 20 seconds of demo that earns it | Tasks |
|---|---|---|
| **Innovation** | Payment completes *inside the thread* — no redirect, no new tab — and the Trust Panel shows why that's now safe | T-30, T-31, T-11 |
| **User Experience** | Four turns from "I need X" to a receipt. No forms. | T-30, T-20, T-33 |
| **Technical Feasibility** | "These are Visa's own TAP headers, and an AP2-shaped mandate chain" — real spec shapes, named | T-12, T-11, T-10 |
| **Scalability** | Two merchants of different sizes, same agent, same rails; a CSV upload makes a third one live in 90 s | T-03, T-40, T-32, T-04 |
| **Trust & Safety** | The agent tries to overspend and is **declined**, live, with the broken link highlighted | **T-13, T-31** |

## Gaps and honest weaknesses (say these before a judge finds them)

1. **No real Visa integration.** Stated assumption A1; the PS says "mock or simulated". Put it in the
   README and say it out loud — being straight about it reads as engineering maturity, being caught
   hiding it reads as the opposite.
2. **"Category-trained" is prompt-and-schema, not fine-tuning.** Assumption A2. Defensible in 24h;
   have the honest answer ready ("here's what fine-tuning would add, and what data we'd need").
3. **Voice is not built.** The PS says "chatbot **or** voice assistant". Fine. Don't apologise for it.
4. **Search is keyword + filters, not semantic.** Acceptable at 200 SKUs; name it as the first thing
   we'd upgrade.
5. **Single-currency, single-region, no settlement/refunds.** Scope, stated.

## Re-check log

| When | By | Result |
|---|---|---|
| T+0:40 | Claude Code / Aryan | Initial matrix — full coverage, no orphans. R3 and R8 flagged as the two at-risk requirements. |
