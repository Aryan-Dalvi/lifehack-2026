# COVERAGE MATRIX — every PS requirement → the tasks that deliver it

> Built by KICKOFF at T+0:40. **`STATUS` re-checks this every run.** A requirement with no task, or
> a task with no owner or no timebox, is a defect — fix it the moment it appears.

## Requirements → tasks

| # | Requirement (from `brief.md` §3) | Delivered by | MVP? | Risk |
|---|---|---|---|---|
| **R1** | Category-trained chatbot/voice assistant | T-20b/T-20c (per-category specialists), **T-23 (packs as data)**, T-03 (category seed data) | partial — one category at MVP | **low, improved in rev 2** — packs are now data files and the specialists are instantiated per category, so a second pack is a file, not a rewrite. Category isolation is now a structural guarantee, not a prompt instruction. |
| **R2** | Discovery, recommendations, **comparison**, decision | T-20b, T-20c, T-41 (search), T-30 (cards with ratings, hover preview, full compare — plates C3–C5) | ✅ yes | low — **strengthened in rev 3**: star ratings give the comparison a decision axis judges recognise instantly, and progressive disclosure makes "comparison" a deliberate act rather than a spec dump |
| **R3** | Simple merchant onboarding (upload catalog / connect API / no-code) | **T-32 (3-section console)**, T-34 (live preview), T-40 (ingest), T-42 (config + embed snippet) | no — MVP uses seeded catalogs | **med, improved in rev 2** — was high. The console dropped from 5 screens to 3 sections (3.0 h → 2.5 h) and starts at the same time, so it now has slack. Ingest API (T-40) is early and real; slip rule at T+20 still covers it. |
| **R4** | Customisable for merchant types/sizes (SME vs large) | T-03 (two merchants, two sizes), T-40 (`size` field), T-32 (size toggle, plate M1), T-41 (cross-merchant) | ✅ yes — cheap, high rubric value | low |
| **R5** | Mock/simulated **Visa** payment flow | **T-10 (token vault, authorize/capture)** | ✅ yes | low |
| **R6** | Frictionless checkout **in the conversation, no redirects** | T-30 (confirm sheet + receipt in-thread), T-20 (`execute_payment` tool) | ✅ yes — this is the MVP's defining property | low |
| **R7** | Users **authorize** agent-driven actions | T-30 (plate C6 consent sheet + scope band), **T-11 (mandate chain)**, T-22 (intent mandate signed at the spend-limit control, plate C2), **T-14 + T-35 (issuer approval, plate C7)** | ✅ yes | low — **rev 3 makes this the strongest requirement on the board.** Authorisation is now two-party: the shopper consents *and* the bank authenticates. |
| **R8** | Safeguards: transaction previews, **identity verification**, confirmation before transacting | T-30 (preview + ship-to), **T-14 (issuer ACS — new in rev 3)**, T-43 (address in the signed hash), **T-13 (safeguard rules + decline)**, **T-25 (Guardian)**, T-12 (agent identity via TAP), T-31 (Trust Panel + plate C9) | partial at MVP (preview + confirm); full by T+17 | low — **was med.** The PS names "identity verification" explicitly and rev 3 finally answers it with an issuer, not a device. R8 now has **three independent layers** — Guardian (pure code), issuer token (pure code), TAP signatures (crypto). If T-12 slips entirely, two of three still demo. |
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
| **User Experience** | Four turns from "I need X" to a receipt. No forms. Ratings and hover previews mean the shopper decides without ever leaving the thread | T-30, T-20a, T-33 |
| **Technical Feasibility** | "These are Visa's own TAP headers, and an AP2-shaped mandate chain" — real spec shapes, named. Plus: **no language model anywhere in the payment path** | T-12, T-11, T-10, T-25 |
| **Scalability** | Two merchants of different sizes, same agent, same rails; a CSV upload makes a third one live in 90 s; a fourth category costs a JSON file | T-03, T-40, T-32, T-34, T-23 |
| **Trust & Safety** | The agent tries to overspend and is **declined**, live, with the broken link highlighted and three dead steps below it — then, for a judge who probes, a replayed bank token and a cart edited after approval, both refused | **T-13, T-31, T-25, T-14** |

## Gaps and honest weaknesses (say these before a judge finds them)

1. **No real Visa integration.** Stated assumption A1; the PS says "mock or simulated". Put it in the
   README and say it out loud — being straight about it reads as engineering maturity, being caught
   hiding it reads as the opposite. **This now includes the issuer:** "Meridian Bank" is a mock ACS
   we wrote, modelling the EMV 3-D Secure step-up. The *binding rules* it enforces are real logic;
   the bank is not.
1b. **Ratings come from the merchant's feed, not from a live review corpus.** Assumption A6 (new in
   rev 3). Ingest-time only, cached, with an enrichment hook where a real ratings source would plug
   in. Deliberate: a demo that depends on venue wifi at 12:30 on Sunday is a demo that fails.
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
| T+1:10 | Claude Code / Aryan | **Revision 2** re-check. Still full coverage, no orphans. R3 risk high → med (console simplified, now has slack). R8 gains a crypto-independent second layer (T-25 Guardian). R1 risk med → low (packs are data). New task T-34 mapped to R3; new task T-25 mapped to R8. |
| T+1:40 | Claude Code / Aryan | **Revision 3** re-check. Still full coverage, no orphans. R7 and R8 both strengthen materially — "identity verification", named explicitly in the PS, is now answered by an issuer rather than a device, and R8 has three independent layers. R2 strengthens (ratings + progressive disclosure). New tasks T-14 → R7/R8, T-35 → R7/R8, T-43 → R8. **New weakness logged (1b): ratings are merchant-feed, not live.** Plan now ~56 h with no buffer — that is the live risk, not coverage. |
