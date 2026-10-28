# Phase 3 — QA (runtime only, report only)

See [context.md](./context.md) — required reading. Also [log.md](./log.md).

## Scope
Branch `phase-3-vetting`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p3-qa phase-3-vetting`, cd there,
`uv sync`. Remove + prune at the end. No `.env`: never the real API. Logic review is
done by another agent — check behaviour by running things.

## Checks
1. `uv run poe check` green; test count, coverage.
2. Legacy stages after the SDK 1.17 upgrade: `happytube --help`, `assess --help`,
   import of assess/enhance/claude_response; `report`/`status` on an empty dir.
3. CLI vet with a temp copy of `channels/` and a fake client (scratch script that
   injects it, or monkeypatch at the documented seam):
   - `--dry-run --all` without any key: statuses, flags, exit 0, nothing written.
   - no key, no dry-run: clear error, exit ≠ 0, nothing written.
   - happy path: report .md + review written; frontmatter loads; unicode literal
     (Czech channel); `show`/`list --json` show the vet; second run →
     `skipped_current`; `--force` → new files, old ones intact.
   - refusal, auth error mid-run (later channels `not_vetted`, earlier files kept,
     exit ≠ 0), parse error, missing/extra video id → no files for that channel.
   - `--json` stdout parseable, errors on stderr.
4. Other commands (`list`, `show`, `add`, `review`) still work with no keys.
5. Secret grep: `git grep -E 'sk-ant-[A-Za-z0-9_-]{20,}'` + over `git log -p
   0bbad42..`.
6. Number issues Q1, Q2…

## Constraints
Read-only on the branch: no edits, no commits.

## Report
Return ONLY JSON (≤500 words):
{"verified": [{"check": "", "how": "", "result": ""}],
 "issues": [{"id": "Q1", "severity": "high|medium|low", "issue": "", "repro": ""}],
 "verdict": "ship|fix-first"}
