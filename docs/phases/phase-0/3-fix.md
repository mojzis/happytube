# Phase 0 — fix

See [context.md](./context.md) and [log.md](./log.md) (QA + review reports, verbatim) — required reading.

## Task
Fix on branch `phase-0-template`, commit in logical chunks, hooks must pass, no push.

### Must fix (review findings)
All 7 review `findings` (high → low), as proposed in the report, unless you find the
proposal wrong — then say so in `deviations`.

### Also fix (orchestrator picked from preexisting / QA)
1. videos.py YTKEY bug: `Search`/`Videos.__post_init__` must call
   `super().__post_init__()` (or equivalent). Add a test proving the key lands in params.
2. `YtQuery.get`: module logger, `raise_for_status()` (or a clear logged error —
   don't silently return empty data).
3. `uv lock --upgrade` for the vulns — **separate commit**, then `poe check` +
   `happytube --help`. Report vuln count before/after.
4. Add `.python-version` = `3.12` so local matches CI.
5. CLAUDE.md "Fresh clone"/Notes: a new git worktree needs `uv sync` before the
   madoqua hook works; don't run pytest concurrently in one checkout (shared .coverage).
6. Extract `_run_stage` in `run_all` if it cleanly removes the PLR0915 noqa; skip if
   it gets awkward.

### Do NOT fix (deferred, record only)
- Web player/export reading `data/fetched/` instead of `stages/` → later phase.
- `report` requiring API keys even though it calls no API → later.
- runpy RuntimeWarning in `python -m happytube.web.*`.

## Report
Return ONLY JSON (≤400 words):
{"commit_shas": [], "fixed": [], "not_fixed": ["item + reason"], "deviations": [],
 "vulns_before_after": "", "check_output_tail": ""}
