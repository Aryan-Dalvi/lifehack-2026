# HANDOFF — project-state refresh protocol

Runs on the `HANDOFF` keyword, before any AI switch, when a rate limit hits, and at every
integration checkpoint (Aryan's window is the checkpoint scribe). Purpose: any other window —
Claude or Codex, any member's machine — can pick up the project cold from `docs/HANDOFF.md`.

## Procedure

1. Gather truth first: `git log -20`, `git status`, `docs/tasks.md`, and the diff of anything
   uncommitted. Don't write from memory alone.
2. Rewrite `docs/HANDOFF.md` in full (it is a snapshot, not a journal) with the sections below.
3. Commit (`handoff: <short summary> [<member>/<AI>]`) and push. If the push fails, say so
   loudly — an unpushed handoff is invisible to every other machine.
4. If work is being handed off mid-task, also leave the working branch pushed and name it in
   the file.

## docs/HANDOFF.md sections (all required)

- **Snapshot** — timestamp, current T+, author (member + AI window).
- **Project one-liner** — what we're building, for which sponsor PS.
- **Direction & why** — the chosen approach and the one-line rationale (and what we rejected).
- **Stack & repo map** — languages/frameworks, what lives in which directory, deployed URLs.
- **State** — done / in-progress (who, which branch) / blocked (on what).
- **Decision log** — dated one-liners; append-only across handoffs (the only journal section).
- **How to run & test** — exact commands from a fresh clone; known-good demo path.
- **Env & secrets** — variable *names* only and where to get values (never values themselves).
- **API credit spend** — running estimate against the US$50 (from provider dashboard or call
  counts); flag if the demo-day reserve (~$25) is at risk.
- **Next 3 actions** — concrete, ordered, each with suggested owner + executor AI.
- **Open questions** — for mentors, sponsor reps, or the team huddle.

## Receiving end (any window picking up after a handoff)

`git pull` → read `docs/HANDOFF.md` → read `git log -15` and `docs/tasks.md` → verify the
"how to run" path actually runs **before** building on top of it. Treat uncommitted local
state as suspect. Then claim your task on the board and go.
