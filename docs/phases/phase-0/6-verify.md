# Phase 0 — final verify (review + QA, report only)

See [context.md](./context.md) and [log.md](./log.md) — required reading.

## Task
1. Review `18d0ed6..HEAD` (fix round 2) with the `python-review` skill. For each
   Step 4a finding/suggestion: resolved / partial / not. Any new issues?
2. QA: `uv sync`; `uv run poe check`; `uv run poe dead-code` (expect exactly the 8
   known hits); `uv run happytube --help`; `uv run pytest tests/test_cli.py -v`.
3. Coverage puzzle: earlier runs reported 70% with 42 tests, now 51% with 46 tests
   (fix agent says 18d0ed6 also gives 51% now). Find out why — e.g. is `src/` measured
   via the installed package vs source path, does a stale `.coverage` / parallel run
   matter, is `--cov=src` vs `--cov=happytube` the issue? Measure at 18d0ed6 (use a
   worktree in /tmp/claude-1000/, `uv sync` there first) and HEAD. Recommend a fix if
   config is wrong; don't change anything.
4. `git status` clean apart from docs/phases/*.

## Constraints
Read-only on the branch.

## Report
Return ONLY JSON (≤350 words):
{"round2": [{"finding": "", "status": ""}], "new_findings": [], "qa_ok": true,
 "qa_evidence": "", "coverage_explanation": "", "coverage_fix": "", "verdict": "ship|fix-first"}
