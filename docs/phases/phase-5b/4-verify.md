# Phase 5b — verify (combined review + QA)

See [context.md](./context.md) and [log.md](./log.md). Read-only. Own worktree
`/tmp/claude-1000/p5b-verify` (`git worktree add --detach … phase-5b-trusted-player`,
`uv sync`; remove + prune after). Diff of the fix: `git diff 430bd65..HEAD`.

## Check
1. Every R/Q id resolved or justified; re-trace each fix end to end (script exit
   code, served response), not just the changed function.
2. daily_run.sh with a stub `uv` + bare remote: failed push retried next run;
   status failure still pushes; no stages dir → exit 0; run failure → files pushed,
   exit ≠ 0; only stages/trusted committed.
3. Q5 deviation: does treating `20261028` as non-date break any trusted command
   (`load_until`, `pending`, `status_counts`)?
4. `uv run poe check` green; numbers.
5. Any new issue from the fix.

## Report
Return ONLY JSON (≤400 words):
{"verdict": "ship | fix", "ids": {"Q1": "resolved|partial|open: why", "...": ""},
 "new_findings": [{"id": "V1", "severity": "", "what": "", "fix": ""}], "numbers": ""}
