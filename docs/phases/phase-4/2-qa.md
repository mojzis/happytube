# Phase 4 — QA (runtime + browser, report only)

See [context.md](./context.md) — required reading. Also [log.md](./log.md).

## Scope
Branch `phase-4-review-ui`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p4-qa phase-4-review-ui`, cd there,
`uv sync`. Remove + prune at the end. Logic review is done by another agent —
check behaviour by running things. Work on a scratch copy of `channels/`
(`/tmp/claude-1000/p4-qa-channels`), never the repo's.

## Checks
1. `uv run poe check` green; test count, coverage.
2. **Browser** (the dev run was curl only). If `mcp__claude-in-chrome__*` tools are
   available (load via ToolSearch, skill `claude-in-chrome` first; new tab only,
   don't touch the user's tabs), serve on a free port and check by eye: queue
   readable and ordered, filter form swaps the table and updates the URL, back
   button, detail page (thumbnails, resolved-to line, vet table), htmx review
   POST updates reviews + status badge without reload, 422 error shows in the
   form, reviewer prefilled after reload (cookie), no console errors, htmx loads
   from `/static` (no external JS). Screenshot key states. If browser tools are
   unavailable, say so and skip — don't fake it.
3. Packaging: `uv build`; the wheel contains templates + static (htmx, css);
   install it in a throwaway venv, run `happytube serve` from another cwd
   (e.g. `/tmp`) with `--channels-dir` → pages render.
4. `serve` with no keys, missing registry dir (empty queue), port in use (clear
   error?), `--host 0.0.0.0` warning, `HAPPYTUBE_REVIEWER` / `HAPPYTUBE_CHANNELS_DIR`.
5. Concurrent writes: CLI `channels review` and web POST on the same channel at
   once → both files present, no overwrite; CLI `list`/`show` see web reviews.
6. Old commands (`channels list/show/review`, `--help`) still work.
7. Number issues Q1, Q2…

## Constraints
Read-only on the branch: no edits, no commits. Kill every server you start.

## Report
Return ONLY JSON (≤500 words):
{"verified": [{"check": "", "how": "", "result": ""}],
 "issues": [{"id": "Q1", "severity": "high|medium|low", "issue": "", "repro": ""}],
 "screenshots": ["path"], "verdict": "ship|fix-first"}
