# TEST — verification & feedback protocol

Runs on `TEST <target>` — target may be a feature, module, endpoint, page, script, or "the
whole demo". Any member can run this from their own window; test against `main` unless told
otherwise. Core rule: **nothing is "done" until it has been run.** Reading code is not testing.

## Procedure

1. **Derive base cases** from the task's DoD in `docs/tasks.md` and the interface in
   `docs/contracts.md`: the documented happy path(s), exactly as a judge would use them.
2. **Derive edge cases** — pick what's relevant: empty/missing input · huge input · malformed
   input (wrong types, broken JSON) · unicode/emoji · double-submit & concurrency · auth
   failure/expired key · network/API failure and timeout (kill the connection mid-call) ·
   refresh/back-button mid-flow · a second user at the same time.
3. **LLM-feature cases** (if the product calls an LLM): nonsense input, adversarial/prompt-
   injection input ("ignore your instructions…"), very long input, empty API response, rate
   limit/quota error. The product must fail *gracefully* — judges type weird things.
4. **Run them for real** — unit tests, scripted curl/HTTP calls, or driving the UI. Capture
   actual output, not expectations.
5. **Log** to `docs/testing.md` (append a dated section): target · case · expected · actual ·
   pass/fail · repro command. Commit the log.
6. **Feedback**, severity-ranked:
   - **P0 — breaks the demo path**: must fix before the next checkpoint.
   - **P1 — visible wart or wrong result** off the happy path.
   - **P2 — cosmetic/nice-to-have** (candidate for the cut list).
   End with the **top-3 fixes** in order, each with suggested owner + executor AI, and post
   P0s to the task board as new rows (author: whoever ran the test).

## Standing test duties

- Before every integration checkpoint merge: run the demo path end-to-end on `main`.
- After feature freeze (T+21): full pass of this protocol on the whole demo, then **record the
  backup video** while it's green.
- Sanity-check the deployed/demo environment (not just localhost) at least twice: once when
  first deployed, once after freeze.
