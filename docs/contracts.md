# Interface contracts — DRAFT until frozen by the Y4 at the first huddle

**Status: TEMPLATE (pre-event).** KICKOFF drafts this; the Y4/architect freezes v1 at the first
team huddle (~T+1). After freeze: changing anything here requires the Y4's OK + a message in
the team chat + bumping the version line. Parallel work touches other members' modules **only**
through what is written here — that is the whole point of this file.

Version: v0 (unfrozen)

## Module split & owners

| Directory | Owns | Member |
|---|---|---|
| _e.g. `api/`_ | _backend service, business logic_ | _Y3_ |
| _e.g. `frontend/`_ | _UI_ | _Y2_ |
| _e.g. `ml/` or `agent/`_ | _LLM/agent layer_ | _Y4_ |
| _e.g. `infra/` + `demo/`_ | _deploy scripts, seed data, demo script_ | _Aryan_ |

## System sketch

_One paragraph or ASCII diagram: what calls what._

## API endpoints

| Method | Path | Request (JSON) | Response (JSON) | Errors |
|---|---|---|---|---|
| _POST_ | _/api/…_ | _{...}_ | _{...}_ | _400 {error}, 500 {error}_ |

## Data models

_Shared shapes (DB rows, message formats), one fenced block each._

## Cross-cutting conventions

- **Error format:** _e.g. `{ "error": string, "detail"?: string }` with proper HTTP codes._
- **Env var names:** `OPENAI_API_KEY`, _…add all here; values only in local `.env`._
- **Ports:** _frontend :3000, api :8000, …_
- **Seed/demo data:** _where it lives, how to load it._
