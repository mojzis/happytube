# Phase 5b — fix

See [context.md](./context.md) and findings in [log.md](./log.md) (R = review,
Q = QA). Main checkout, branch `phase-5b-trusted-player`. Small commits, tests for
each behaviour change, `uv run poe typecheck` before each, hooks must pass,
`uv run poe check` green at the end.

## Must fix
- **Q1** daily_run.sh: with `HAPPYTUBE_PUSH=1`, push whenever the branch is ahead of
  its upstream, not only after a new commit (a failed push is retried next run).
  Simplest: always `git push` after the commit step; "nothing to commit" is not an
  error, a failed push still is.
- **R2** `trusted status | tee` failure must not skip the push (log a warning).
- **R3/Q2** no `stages/trusted` dir → skip commit/push with a log line, not an error.
- **R1/Q6** deploy.yml `paths:` add `src/happytube/channels/**`,
  `src/happytube/trusted/**`, `src/happytube/models/**`, `pyproject.toml`, `uv.lock`.
- **R4/Q3** `happytube serve` warns (stderr, at start) when `<stages-dir>/trusted`
  is missing; the live route logs a warning too (once is fine).
- **Q4** `/player/videos.json` answers HEAD from the live route too (no fallthrough
  to the static mount).

## Also fix
- **R5** help text + CLAUDE.md: `--stages-dir` / `HAPPYTUBE_STAGES_DIR` is where the
  player and export *read*; the `trusted` commands write `stages/` in the cwd.
- **Q5** non-`YYYY-MM-DD` dir under a trusted stage → warning naming it (still skipped).
- `logs/` into `.gitignore`.
- Remove daily_run.sh's stale commented legacy export/commit block.

## Do NOT fix
- player.js waiting for the YouTube iframe API before listing videos (UI work; backlog).
- daily_run pushing the current branch (documented).
- First stages/trusted commit (user's call).

## Report
Return ONLY JSON (≤400 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X%",
 "fixed": {"Q1": "", "R2": "", "R3": "", "R1": "", "R4": "", "Q4": "", "R5": "", "Q5": "", "other": ""},
 "deviations": [""], "unresolved_issues": [""]}
