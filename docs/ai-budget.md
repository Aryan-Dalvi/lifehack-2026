# AI budget & assignment policy

Who has what, what each resource is *for*, and how KICKOFF/TEST fill the "Executor" column on
the task board. Principle: **spend the scarce resources where they're uniquely good; parallelise
on the plentiful ones.**

## The resource map

| Resource | Who | Limits | Reserve it for |
|---|---|---|---|
| **Claude Code (Pro)** | Aryan only — the team's single premium Claude seat, personally paid | ~5-hour rolling usage windows + a weekly cap; hitting it mid-build is the #1 risk | Architecture decisions, cross-module integration, gnarly debugging, repo-wide edits, authoring `docs/` planning artifacts |
| **Codex (NUS enterprise)** | All 4 members — **four separate limit pools** | Workspace-policy limits per account; `xhigh` effort drains them fastest | The parallel workhorses: one window per member, each on their own module; research via browser plugin; demo assets via documents/presentations plugins |
| **US$50 OpenAI API credits** | Team-shared (one key) | Hard dollar cap; needed **during judging** | **Primarily the product's own runtime** — sponsors hand out credits expecting the prototype to call the API |
| **Free claude.ai** | Teammates | Small daily message caps | Throwaway questions, prose polish. Never repo work |

## Model & effort ladder (fill the Executor column with these)

| Task type | First choice | Setting | Note |
|---|---|---|---|
| Architecture, contracts, hard bugs | Aryan-Claude | strongest model available (check `/model`), thinking on | Short, high-stakes sessions; hand the output to Codex windows to execute |
| Module implementation | Owner's own Codex | default model, **medium/high effort** | The bulk of all work. Don't default to xhigh |
| Truly stuck problem | Owner's Codex at `xhigh`, or escalate to Aryan-Claude | one shot, then huddle | If two AIs disagree, a human decides |
| Boilerplate, renames, config, tests scaffolding | Any Codex | low/medium effort | Cheapest thing that works |
| Research memos | Aryan-Claude (WebSearch) or any Codex (browser) | medium | Always with source links |
| Demo assets: slides, script, README polish | Aryan-Codex (presentations/documents plugins) | medium | End-of-build lane |
| Product's own LLM calls | OpenAI API ($50 key) | **mini/nano-tier models** where possible, prompt caching, low max_tokens | See spend plan below |

## Claude Pro survival rules (Aryan's window)

- Batch premium work into deliberate sessions; don't idle-chat in it.
- Default Sonnet-tier for ordinary edits; the biggest model only for the ladder's top row.
- If a limit hits: run `HANDOFF` immediately (it's designed for exactly this), continue the
  task in Aryan-Codex or the owner's Codex, and note when the window resets.

## $50 credit spend plan (product runtime)

- **≤ $10 during development** — use the cheapest model that passes the DoD; cache prompts;
  cap max_tokens; stub/mock LLM calls in unit tests instead of hitting the API.
- **~$25 protected for demo day** — judging is 2.5 h of repeated live demos; running dry
  mid-judging is fatal. `STATUS`/`HANDOFF` track the running spend estimate.
- **~$15 buffer.**
- Key handling: one member's OpenAI account holds the grant (per the organisers' form). The key
  is shared via the team group chat only, lives in each machine's local `.env`, is named in
  `.env.example`, and is **never committed**. If the product doesn't need OpenAI at runtime,
  credits may back Codex-via-API as overflow — but enterprise Codex pools come first.

## If a resource dies

Claude capped → Codex continues via HANDOFF. A member's Codex pool dry → that member pairs
with another member's window or uses the API-key overflow. Credits burning too fast → drop the
product to a cheaper model / cache harder / trim prompt sizes (this is a P0 task).
