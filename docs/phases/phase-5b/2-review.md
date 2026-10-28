# Phase 5b — review

See [context.md](./context.md) and the dev report in [log.md](./log.md). Read-only:
report, don't fix. Use the `python-review` skill.

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5b-review
phase-5b-trusted-player`, `uv sync` there; remove + `git worktree prune` at the end.
Diff: `git diff 326b098..HEAD`. No real API calls.

## Check
Design vs context.md, logic, tests, naming. Trace multi-day and partial-failure
scenarios against the rules (5a lesson). Added after dev (logic — yours only):
1. Selection rule in `trusted/player.py`: every context.md failure scenario
   handled? Scores only from assess, description only from enhance? Join across
   date dirs correct? "Latest date copy wins even if broken" — sound, or can it hide
   a good video forever (e.g. assess under one date, enhance under another)?
2. Channel filter: `derive_status` == approved only; unreadable reviews → hidden.
   Any path that shows a rejected / candidate / unknown channel's video?
3. Route ordering: `/player/videos.json` before the `/player` static mount; Host /
   Origin guard covers both; no path traversal via the static mount; caching headers.
4. Export: missing stages or registry dir → exit ≠ 0; empty → exit 0 + warning;
   CI path (repo root cwd) right? Workflow `paths:` filter complete (would a change
   that alters output skip the deploy)?
5. `daily_run.sh` push block: never `git add -A`; behaviour on run failure, nothing
   changed, push failure; `set -e`/`pipefail` interplay; pushes current branch.
6. Deletions: deploy_web.sh, web/DEPLOYMENT.md, server.py, templates — anything
   still referencing them (docs, workflow, pyproject scripts)? flask fully gone from
   pyproject/uv.lock?
7. `--stages-dir` / `HAPPYTUBE_STAGES_DIR`: consistent with `--channels-dir`; does
   it conflict with the trusted commands' fixed `stages/`?

## Report
Return ONLY JSON (≤600 words):
{"verdict": "ship | fix", "findings": [{"id": "R1", "severity": "high|medium|low",
 "where": "file:line", "what": "", "fix": ""}], "preexisting": [""],
 "answers": {"1": "", "2": "", "3": "", "4": "", "5": "", "6": "", "7": ""}}
