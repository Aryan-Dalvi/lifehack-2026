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

NUS LifeHack 2026 Main Hackathon · 29–30 Aug 2026 · COM3 MPH. Four-person team, working with a
dual-AI setup: **Claude Code** (Aryan) + **Codex** (every member, NUS enterprise). Until T0
(~11:00 Sat) this repo contains only the team's operating protocol — no product code.

## How the AI setup works (30-second version)

- Clone this repo, open the folder in **Codex** → it reads `AGENTS.md` and follows the team
  protocol automatically. Aryan's **Claude Code** reads `CLAUDE.md` — same protocol.
- **Drop the problem statement into a window → it runs KICKOFF** (breakdown → per-member tasks
  → timeboxes → AI/model assignments → research → coverage check). Aryan's Claude authors the
  plan docs; every Codex red-teams it.
- Keywords in any window: `KICKOFF` · `RESEARCH <topic>` · `TEST <target>` · `STATUS` · `HANDOFF`.
- `docs/HANDOFF.md` + git = the shared brain: `HANDOFF` in one window, `git pull` in another,
  and work continues there. Works across AIs and across machines.
- Deconfliction: module-per-member (interfaces frozen in `docs/contracts.md`), personal
  branches merged to an always-runnable `main` at checkpoints, and claim-by-commit on
  `docs/tasks.md` (edit only your own rows).

## Map

`CLAUDE.md`/`AGENTS.md` — the protocol · `prompts/` — KICKOFF/TEST/STATUS/HANDOFF behaviours ·
`docs/event.md` — verified schedule/rules (T0 11:00 Sat, **Devpost form locks 11:00 Sun**,
walking-format judging 12:00–14:30 Sun) · `docs/team.md` — roster (fill!) · `docs/ai-budget.md`
— who uses which AI/model and the $50 credit plan · `samples/` — a fictional PS for dry runs.

## Pre-event checklist

**Aryan**
- [ ] Org email: OpenAI account ready + credits form submitted (with the OpenAI-account email).
- [ ] Create the **private** GitHub repo + invite the other 3 as collaborators, push this repo
      (commands below). It flips **public before the 11:00 Sun submission** — requirement.
- [ ] Toolchain on the Mac (admin password needed): install Homebrew, then
      `brew install node gh` (or use installers from nodejs.org / cli.github.com);
      `gh auth login`. (Git identity is already configured on this machine.)
- [ ] Fill `docs/team.md` (ask the group for strengths/stack/OS) — allocation quality depends on it.
- [ ] Dry run: fresh `claude` session here → drop `samples/sample-ps.md` → confirm KICKOFF fires.
      Then open this folder in the Codex app (trust it) → same drop → confirm the red-team flow.
      Delete any docs the dry run generated before committing.

**Everyone (all 4)**
- [ ] Devpost account + register on lifehack-2026.devpost.com; join the official **Telegram**
      channel (submission link appears there). Agree who owns the Devpost form.
- [ ] Verify Codex access with your NUS enterprise account on your own laptop
      (Mac → Codex app; Windows → ChatGPT web Codex or CLI/WSL).
- [ ] Clone the repo, open it in Codex, make a one-line hello-commit to prove push access.
- [ ] Logistics: chargers + one extension cord, water, sleep. Report **09:00, MPH Foyer**.

### GitHub setup (Aryan, once)

```bash
cd "/Users/aryan/What will you have after 500 years?/Aryan/Personal Projects/LifeHack 2026" && gh repo create lifehack-2026 --private --source . --push
```

(No `gh` yet? Create an empty private repo named `lifehack-2026` on github.com, then
`git remote add origin <url> && git push -u origin main`. Invite collaborators under
Settings → Collaborators.)

## Day-of rhythm

1. **Ceremony:** paste the allocated-PS email + official judging criteria into `docs/event.md`.
2. **T0:** drop the PS into Aryan-Claude → KICKOFF (authors the plan). Each member drops it
   into their Codex → independent analysis + `docs/kickoff-review-<name>.md`.
3. **T+1 huddle:** pick direction, freeze `contracts.md` v1, claim first tasks. Build.
4. **Checkpoints ~T+4/9/15/20:** merge to `main`, run the demo path, refresh HANDOFF.
5. **T+21 freeze → demo block:** Devpost fields, README, demo script, **backup recording**,
   flip repo public. **Submit by T+23:40 — the form locks at 11:00 sharp.**
6. Judging 12:00–14:30 at the station (everyone can drive the demo) · closing 15:00 (attend!).
