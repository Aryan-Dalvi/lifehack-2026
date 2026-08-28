# STATUS — progress & risk check protocol

Runs on the `STATUS` keyword. Keep the whole output short — it feeds a standing huddle, not a
report. Never sugar-coat: a red flag raised at T+10 is a gift; the same flag at T+20 is a
funeral.

## Procedure

1. **Clock**: run `date`, compute current T+, and say what `docs/timeline.md` expects to be
   happening right now. Time remaining to feature freeze (T+21) and form lock (T+24).
2. **Board scan** (`git pull` first): from `docs/tasks.md` + `git log` —
   - done / doing / blocked counts, and who is on what;
   - **unclaimed** tasks inside the current or next timebox;
   - **orphans**: MVP requirements whose tasks are all unstarted (re-run the coverage matrix);
   - **stale claims**: claimed >2h ago with no commits touching that module.
3. **Trajectory**: for each in-progress task, on-track / at-risk / slipped vs its timebox.
   Estimate whether the MVP lands by freeze at current pace.
4. **Risks & cuts**: top 3 risks right now. If behind, propose specific cuts **from the
   pre-agreed cut list** in `docs/brief.md` (protect the demo path above all). If ahead, name
   the next stretch goal worth pulling in.
5. **Actions**: one next action per member, plus whether a checkpoint merge or HANDOFF refresh
   is due. If a P0 from `docs/testing.md` is open, it outranks everything.

Output to screen only (no file writes) — except: if a cut is agreed at the huddle, the author
window updates `brief.md`/`tasks.md` immediately so the docs never lie.
