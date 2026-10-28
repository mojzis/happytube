# Phase 1 — review (report only)

See [context.md](./context.md) — required reading. Also [log.md](./log.md) (dev report).

## Scope
Commit range `ce54e00..phase-1-channels`. Work in your own worktree
(`git worktree add /tmp/claude-1000/p1-review phase-1-channels && cd` there,
`uv sync`), so you don't collide with QA's pytest. Remove + prune it at the end.

## Task
1. Invoke the `python-review` skill (Skill tool) over that range.
2. Phase-specific judgement:
   - Status derivation: correct for all cases (no reviews, agent-only, human
     unsure after approve, approve then reject, same-second ties)? Ordering by
     `created_at` or filename — robust?
   - Append-only guarantee: can any path overwrite or rewrite an existing file?
   - Store API fit for phase 4 (Flask) — no click/rich in the store.
   - Validation: bad kind/language/role/verdict, malformed YAML on disk, missing
     channel — clear errors, non-zero exit, no tracebacks.
   - JSON output: stdout only, parseable, stable; errors on stderr.
   - Path traversal via slug / reviewer name in filenames.
   - Tests: meaningful assertions, not implementation-pinned.
   - Docs (decision 0003, CLAUDE.md, architecture.md) match the code.
3. Number findings R1, R2… Pre-existing issues in untouched code → `preexisting`.

## Constraints
Read-only. Do NOT edit or commit on the branch.

## Report
Return ONLY JSON (≤500 words):
{"findings": [{"id": "R1", "severity": "high|medium|low", "file": "", "issue": "", "fix": ""}],
 "preexisting": [""], "verdict": "ship|fix-first"}

## Dev deviations to cover (added by orchestrator)
- Tie-break: dev says identical `created_at` sorts `-2` before the base filename
  (wrong order). Real risk? Propose a robust ordering (e.g. parse suffix numerically).
- Hand-edited `channel.yaml` (null optional fields kept): does load tolerate a human
  deleting a null key, adding unknown keys, or editing `slug` so it no longer matches
  the directory name?
- vulture ignores (`added_at`, `obj`, decorators): narrow enough?
