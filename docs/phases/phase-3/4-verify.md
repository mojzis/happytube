# Phase 3 — verify (combined review + QA, report only)

See [context.md](./context.md), [log.md](./log.md) (all findings + fix report),
[3-fix.md](./3-fix.md).

## Scope
Fix commits `4a88cba..phase-3-vetting`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p3-verify phase-3-vetting`, `uv sync`,
remove + prune after. No `.env`: fakes only, never real APIs.

## Task
1. `uv run poe check` green; count, coverage.
2. Each R1–R6, Q1, Q2: resolved end to end (trace to CLI exit code + JSON), or not.
3. Judge each fix `deviation` (accept / finding).
4. R1 specifically: load the `claude-api` skill and check the `create` +
   `output_config.format` json_schema shape, fallbacks + beta header, reading text
   after fallback blocks, stop_reason order — against the skill docs and the
   installed SDK 1.17 types. Exercise via httpx2 MockTransport.
5. New issues introduced by the fix (V1, V2…). Pre-existing → `preexisting`.

## Constraints
Read-only on the branch.

## Report
Return ONLY JSON (≤400 words):
{"resolved": [{"id": "R1", "status": "resolved|partial|not", "note": ""}],
 "deviations_judged": [{"deviation": "", "ruling": ""}],
 "findings": [{"id": "V1", "severity": "", "file": "", "issue": "", "fix": ""}],
 "preexisting": [""], "verdict": "ship|fix-first"}
