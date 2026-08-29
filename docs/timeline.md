# TIMELINE — T0 = 11:00 Sat 29 Aug 2026

**Hard deadline: the Devpost form locks at T+24 = 11:00 Sun.** Judging 12:00–14:30 Sun (walking
format, COM3 MPH). Closing 15:00–16:15 — **attendance required to win.**

Wall-clock column is SGT. Anything marked 🔒 is immovable.

| T+ | Clock | What must be true / what's happening |
|---|---|---|
| 0:00 | Sat 11:00 🔒 | PS released. Kickoff protocol runs (this document set). |
| 0:35 | 11:35 | Kickoff artifacts on `main`: brief, research, tasks, contracts draft, timeline, coverage. |
| **0:40–1:10** | **11:40–12:10** | **HUDDLE.** Fill `team.md` first. Pick direction (recommend A). Confirm stack + demo category. **Y4 freezes `contracts.md` v1.** Everyone claims their first two tasks and commits the claim. Aryan chases the OpenAI key (T-04). |
| 1:00 | 12:00 🔒 | Lunch (60 min, MPH/SR1 foyers) — **stagger it**, half the team eats while half starts T-02/T-03. Don't lose an hour here. |
| 1:10–2:10 | 12:10–13:10 | T-02 scaffold (Aryan-Claude) + T-03 seed data in parallel. Everyone else reads the frozen contracts and stubs their module against them. |
| 2:10 | 13:10 | **All four modules start in parallel.** T-10, T-20, T-30, T-40. |
| **4:00** | **15:00** | **CHECKPOINT 1 — merge party.** `main` must run. Stubs are fine, red is not. HANDOFF refresh. First mentor walkaround: ask the three questions in `brief.md` §7. |
| 5:00–8:00 | 16:00–19:00 | T-11 mandates · T-21 demo-mode fallback · T-30 finishes · T-41 search. |
| **8:00** | **19:00** | 🎯 **WALKING SKELETON DUE.** discover → decide → pay works end to end on `main`. **T-51 TEST pass 1** runs against it. If the skeleton isn't up by T+9, invoke the cut list — don't negotiate with it. |
| **9:00** | **20:00** | **CHECKPOINT 2 — merge party.** HANDOFF refresh. Dinner, staggered. Re-prioritise stretch goals against what actually landed. |
| 9:00–14:00 | 20:00–01:00 | T-12 TAP signatures · T-22 agent signing · T-31 Trust Panel. The trust layer is the highest-value block of the night — protect it. |
| **12:00–18:00** | **23:00–05:00** | 🛏 **REST SHIFTS — on the timeline, not optional.** Two staggered pairs, 3h each: pair A 23:00–02:00, pair B 02:00–05:00. Whoever is awake owns `main`. A team that slept demos better than one that didn't. |
| 14:00–17:00 | 01:00–04:00 | T-13 safeguards + trust events. The **decline scenario** must exist by T+17. |
| **15:00** | **02:00** | **CHECKPOINT 3 — merge party** (whoever is awake). HANDOFF refresh. |
| 13:00–18:00 | 00:00–05:00 | T-32 merchant console · T-42 config/snippet · T-23 category packs. |
| 16:00–18:00 | 03:00–05:00 | T-24 cost control · T-33 demo polish. |
| **18:00** | **05:00** | **T-51 TEST pass 2** — full build, base + edge. Top-3 fixes become board rows with owners. |
| 18:00–21:00 | 05:00–08:00 | Fix only. No new features. Breakfast. |
| **20:00** | **07:00** | **CHECKPOINT 4 — final merge party.** HANDOFF refresh. Everything that isn't merged now is cut. |
| **21:00** | **08:00** 🔒 | **FEATURE FREEZE.** Anything unmerged dies here. Bugfix + demo block begins. |
| 21:00–22:00 | 08:00–09:00 | T-55 demo script + **rehearsal — all four members drive it once**. T-52 README, T-53 the PS explanation doc. |
| 22:00–22:45 | 09:00–09:45 | **T-56 backup recording — record it while everything works.** This is insurance against a laptop dying mid-judging. |
| 22:45–23:00 | 09:45–10:00 | T-57 repo → **public**, licence, secret scan. |
| **23:00–23:40** | **10:00–10:40** | **T-54 Devpost submission.** Paste the drafted fields, attach links, submit. |
| 23:40–24:00 | 10:40–11:00 🔒 | **Hands off the form.** Set up the demo station, charge everything, `make reset`, run the happy path twice. |
| **24:00** | **Sun 11:00** 🔒 | **SUBMISSIONS LOCK.** Lunch (45 min). |
| 25:00–27:30 | 12:00–14:30 🔒 | **JUDGING — walking format.** Judges circulate; demo runs many times. Rotate who presents so nobody burns out. `make reset` between judges. Keep the backup video open in a tab. |
| 28:00–29:15 | 15:00–16:15 🔒 | **Closing ceremony — all four present.** |

## Standing rules for the night

- **`main` always runs.** It is the demo. Never merge red; never leave red overnight.
- Branch `<name>/<task-id>`, small commits, pull --rebase before push.
- At every checkpoint: merge, verify a clean clone runs, refresh `docs/HANDOFF.md`, push.
- **Check the official Telegram channel at every checkpoint** — announcements land there, and the
  official judging criteria / Devpost fields may still change (`docs/event.md`).
- If Aryan's Claude window hits its rate limit: run `HANDOFF` immediately and continue in Codex
  (`docs/ai-budget.md`).
- Spend check at each checkpoint: the $50 OpenAI grant needs **~$25 left at T+24** for judging.

## Slip rules — decide fast, don't debate

| If, at… | …this isn't true | Then |
|---|---|---|
| T+9 | walking skeleton runs end to end | Cut items 1–3 of the cut list immediately. Whole team converges on the skeleton. |
| T+14 | Trust Panel renders *something* live | Drop RFC 9421 (T-12) to HMAC envelopes; keep the mandate chain and the panel. |
| T+17 | the decline scenario works | Hard-script it in demo mode. It is never cut — it is the pitch. |
| T+20 | merchant console onboarding works | Fall back to a pre-recorded 20-second onboarding clip inside the live demo; keep the CSV upload API real. |
| T+21 | anything is unmerged | It's cut. No exceptions, no "five more minutes". |
