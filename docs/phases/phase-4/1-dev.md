# Phase 4 — dev

See [context.md](./context.md) — required reading; it settles the design.

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-4-review-ui` (already
checked out). First commit `docs/phases/phase-4/` and the `docs/plan.md` change
as-is.

## Task
1. Deps (`fastapi`, `uvicorn`, `python-multipart`; `httpx` dev) as one commit;
   `poe check` green.
2. Build `review/` package, `happytube serve`, tests, docs as in context.md.
   Small coherent commits; `uv run poe typecheck` before each; hooks must pass.
3. Exploratory real run on a scratch copy (context.md "Real run"). Commit nothing
   from it. Kill the server.
4. `uv run poe check` green at the end.

## Report
Return ONLY JSON (≤600 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X% (was 75%: why moved)",
 "deps": "added packages + versions; htmx version vendored + source",
 "real_run": [{"check": "", "result": ""}],
 "real_run_eyeball": "does the queue order / detail page look right? examples",
 "deviations": ["anything differing from context.md, incl. workarounds"],
 "unresolved_issues": [""]}
