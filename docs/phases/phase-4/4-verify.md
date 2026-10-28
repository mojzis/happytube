# Phase 4 — verify (combined review + QA, report only)

See [context.md](./context.md) and [log.md](./log.md) (R1–R7, Q1–Q4, fix report).

## Scope
Fix range `8170100..phase-4-review-ui`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p4-verify phase-4-review-ui`, `uv sync`
there; remove + prune at the end. Scratch registry copy only.

## Task
1. `uv run poe check` green; count, coverage.
2. Each of R1–R7, Q1, Q2, Q4: resolved / partial / not — with evidence. Re-trace end
   to end (HTTP status + what the user sees; CLI exit code), not just the function.
3. Judge each fix `deviation` (accept or finding): probe race, plain-text htmx
   errors, `[]` stripping, stubbed probe in tests.
4. Safety re-check after the Host-check rewrite: `ipaddress` parsing can't be
   tricked (Host with userinfo, trailing dot, `0x7f.1`, `127.1`, decimal IPs,
   `[::ffff:127.0.0.1]`, bad ports); Origin check still exact; R1 alert uses
   textContent only.
5. **Browser** (Chrome tools via ToolSearch, `claude-in-chrome` skill, new tab only):
   trigger an htmx error (e.g. break a channel.yaml in the scratch copy, then post a
   review; and an unknown filter value) → alert visible, readable; normal approve
   still works; no console errors. Screenshot to
   `/tmp/claude-1000/-home-matous-git-happytube/1e0067df-5509-4e53-97d3-ebdd0dff0265/scratchpad/p4-verify-shots/`.
   If browser tools are unavailable, say so.
6. New findings V1, V2…

## Constraints
Read-only: no edits, no commits. Kill every server.

## Report
Return ONLY JSON (≤500 words):
{"checks": [{"id": "R1", "status": "resolved|partial|not", "evidence": ""}],
 "deviations_judged": [{"deviation": "", "ruling": ""}],
 "findings": [{"id": "V1", "severity": "", "issue": "", "fix": ""}],
 "screenshots": [""], "verdict": "ship|fix-first"}
