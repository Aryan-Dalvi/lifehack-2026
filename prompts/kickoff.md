# KICKOFF — problem-statement intake protocol

Runs when a problem statement (PS) is pasted/dropped, or on the `KICKOFF` keyword. Before
starting: read `docs/event.md`, `docs/team.md`, `docs/ai-budget.md`, and `docs/HANDOFF.md`.
State the current T+ time. Total budget for this protocol: **≤ 60 minutes** — a good plan now
beats a perfect plan at T+3.

## Which role are you?

- **Author** (Aryan's Claude Code window — or, fallback, the first Codex window if no
  `docs/brief.md` exists ~20 min after T0): produce steps 1–6 below.
- **Red team** (every other window given the PS): do step 1 as an *independent* analysis but
  write it only to `docs/kickoff-review-<member>.md`, plus any research to `docs/research/`.
  Then read the author's `docs/brief.md`/`tasks.md` and append a critique: missed requirements,
  over/under-scoped tasks, risky assumptions, a better direction if you see one, and the three
  changes you'd make. Do **not** edit the author's files.

## Step 1 — Break down the PS → `docs/brief.md`

- Restate the problem in two sentences. Name the sponsor and what *they* actually care about
  (their business, their tech, why they set this PS — use sponsor context in `docs/event.md`).
- Extract **explicit requirements, constraints, and deliverables** as a checklist. Quote the PS
  where exact wording matters. List what is *ambiguous* separately.
- Map to judging criteria: use the official criteria in `docs/event.md` if announced; otherwise
  proxy on creativity / impact / technical depth / demo quality.
- Propose **2–3 candidate directions**, each scored (1–5) on: wow-factor for judges, feasibility
  for a 4-person 24h team, fit to the PS, demo-ability in a 3-minute walking-format pitch.
  **Recommend one** and say why.
- Define the **MVP** (the walking skeleton — an end-to-end thin slice demoable by ~T+8),
  **stretch goals** in priority order, and a **pre-agreed cut list** (what dies first when late).
- End with **≤3 clarifying questions** to ask the on-site mentors/sponsor reps. Don't block on
  answers — plan on stated assumptions and mark them.

## Step 2 — Research (≤45 min) → `docs/research/initial.md`

Sponsor's domain, products and public APIs; prior art and existing solutions (what would make
judges say "seen it"); candidate libraries/APIs/datasets/starter patterns with licence notes;
anything the PS names that the team doesn't know. Every claim gets a source link. Claude: use
WebSearch/WebFetch. Codex: use the browser plugin. Flag anything that needs sign-ups/keys NOW —
those have lead time.

## Step 3 — Task board → `docs/tasks.md`

One row per task:

`ID | Task | Owner | Est (h) | Timebox (T+) | Depends on | Executor (member + AI, model, effort) | Status | DoD (incl. base + edge tests)`

- Owners come from the `docs/team.md` roster — match strengths and seniority (Y4 → architecture
  + hardest module; Y1 → well-scoped, well-specified tasks + demo/ops is a sensible default,
  but follow the actual roster).
- Executor column follows `docs/ai-budget.md`: own-Codex for module work, Aryan-Claude for
  architecture/integration/debug, Aryan-Codex for research/demo assets, human-only where AI
  doesn't help. Include model + reasoning effort + a limit note (e.g. "Codex med — save xhigh").
- Reality check the math: 4 people × ~14–16 productive hours each over 24h (minus sleep shifts,
  meals, demo prep) ≈ **55–65 person-hours total**. If estimates exceed ~45h, cut scope now.
- Include the non-code lanes as first-class tasks: integration checkpoints, Devpost form
  fields, README for the public repo, demo script + rehearsal, backup screen-recording,
  repo-flip-to-public.
- Statuses: todo / claimed / doing / done / blocked.

## Step 4 — Module split + contracts draft → `docs/contracts.md`

Propose the directory-per-member module split and draft the interfaces between them: API
endpoints (method, path, request/response JSON), data models, env var names, ports, error
format. Mark it DRAFT — the Y4 freezes it at the first team huddle. This is the team's main
defence against merge conflicts: parallel work only touches other modules through these
contracts.

## Step 5 — Timeline → `docs/timeline.md`

Anchor to the real clock (T0 ≈ 11:00 Sat; **Devpost form locks T+24 = 11:00 Sun**; judging
12:00–14:30 Sun; everyone must attend the 15:00 closing):

- T0→T+1: kickoff, huddle, decide direction, freeze contracts v1, claim first tasks.
- T+1→T+8: walking skeleton — end-to-end thin slice on `main`.
- Integration checkpoints at ~T+4 / T+9 / T+15 / T+20 — merge parties; `main` must run;
  Aryan's window refreshes HANDOFF at each.
- T+9→T+21: features by priority; meal breaks; overnight **rest shifts** (2×3h staggered pairs
  — a team that slept demos better than one that didn't).
- **T+21: feature freeze.** T+21→23: bugfix + demo block (Devpost fields, README, demo script,
  slides if wanted, **record the backup demo video while everything works**).
- T+23→23:40: submit. Never touch the form in the final 20 minutes.

## Step 6 — Coverage matrix + huddle summary

- Matrix: every MVP requirement (from step 1) → the task IDs that deliver it. Any requirement
  with zero tasks, or any task with no owner/timebox, is a defect in this kickoff — fix it now.
- Print an on-screen summary for the team huddle: recommended direction, the module split,
  each member's first two tasks, the three biggest risks, and the mentor questions.
- Update `docs/HANDOFF.md`, commit everything, push. These outputs are **recommendations** —
  the team decides at the huddle; capture any changes back into the docs immediately after.
