# Example KICKOFF output shapes (format reference — content is illustrative, from the
# fictional sample PS; real outputs replace these entirely)

## docs/brief.md — shape

- Problem restated (2 sentences) + what the sponsor cares about.
- Requirements checklist: R1 ingest/simulate data · R2 actionable insights for a named user ·
  R3 intelligent component · R4 3-min live demo · C1 no proprietary hardware · C2 open data ·
  C3 declare AI-generated code.
- Ambiguities: "actionable" undefined → assume concrete ££/kWh recommendation per room.
- Directions considered:
  | Direction | Wow | Feasibility | PS fit | Demo-ability | Verdict |
  |---|---|---|---|---|---|
  | A. Facilities dashboard + anomaly alerts | 3 | 5 | 4 | 4 | |
  | B. Student-facing "energy coach" chat + gamified leaderboard | 4 | 4 | 4 | 5 | ✅ recommended |
  | C. RL-based HVAC scheduler | 5 | 2 | 3 | 2 | too risky in 24h |
- MVP (walking skeleton by ~T+8): synthetic data generator → API serving room stats →
  one-page UI with live leaderboard → LLM coach answering "how do I save energy in COM3-01?"
- Stretch (priority order): anomaly detection, weekly digest, QR per room. 
- Cut list (dies first): gamification polish → digest → anomaly detection.
- Mentor questions (≤3): Is simulated data acceptable for scoring? … 

## docs/tasks.md — example rows

| ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor | Status | DoD |
|---|---|---|---|---|---|---|---|---|
| T-01 | Freeze contracts v1 (API + data shapes) | Y4 | 1 | T+1→2 | brief | human + Aryan-Claude (strongest model, thinking) | todo | contracts.md v1 committed; team ack in chat |
| T-04 | Synthetic occupancy/energy generator | Y3 | 2 | T+2→4 | T-01 | own-Codex, med effort | todo | CSV+API seed; base: 3 rooms 7 days; edge: empty day, spike day |
| T-07 | Frontend shell + leaderboard page | Y2 | 3 | T+2→5 | T-01 | own-Codex, med effort | todo | renders from live API; base: 3 rooms; edge: API down → friendly error |
| T-10 | LLM coach endpoint ($50 key, mini-tier model, cached system prompt) | Y4 | 3 | T+4→8 | T-01 | own-Codex xhigh (1 shot) then med | todo | base: 3 canned Qs; edge: nonsense input, injection attempt, API timeout → graceful |
| T-13 | Demo script + backup recording | Aryan | 2 | T+21→23 | freeze | Aryan-Codex (presentations plugin) | todo | 3-min script; video file saved off-machine |

## docs/timeline.md — shape

T-anchored table from T0 to T+24 with: huddle (T+1), skeleton (T+8), checkpoints
(T+4/9/15/20 — merge + demo-path run + HANDOFF refresh), rest shifts (2×3h pairs overnight),
freeze (T+21), demo block (T+21→23), submit (≤T+23:40), then judging/closing wall-clock times.

## Coverage matrix — shape

| Requirement | Tasks |
|---|---|
| R1 data | T-04 |
| R2 insights | T-07, T-11 |
| R3 intelligent component | T-10 |
| R4 3-min demo | T-13, T-14 |
| C3 declare AI code | T-15 (README section) |
(any empty right-hand cell = defect in the kickoff — fix before the huddle)
