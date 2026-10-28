# Phase 0 — QA round 2 (report only)

See [context.md](./context.md) and [log.md](./log.md) — required reading.

## Task
Rerun the round-1 QA checks from [2-qa.md](./2-qa.md) (steps 2–14; skip step 9's
worktree hook test unless hooks/ or pyproject madoqua config changed since `4b4f31e`),
plus:
15. `.python-version` honoured: `uv run python --version` → 3.12.x.
16. `uv run poe check-all` — report each tool's result (vulture/deptry may warn).
17. `uv run happytube enhance --threshold 9` and `run-all --threshold 0` are rejected
    by click with a range error (set dummy YTKEY/ANTHROPIC_API_KEY env vars if config
    loading comes first; make no real API calls beyond what the CLI does on its own
    before failing — prefer commands that fail at argument parsing).
18. `YtQuery.get` error path: confirm with the test suite (tests/test_videos.py) that
    a non-200 raises `YouTubeAPIError` without the key in the message.
19. `scripts/deploy_web.sh`: read it, confirm paths are consistent from repo root
    (don't run the interactive parts).
20. Parquet round-trip via `Video` models still works on pyarrow 26 (small fixture in
    /tmp/claude-1000/).

## Constraints
Don't modify tracked files or commit. Restore anything touched.

## Report
Return ONLY JSON (≤400 words):
{"verified": true, "checks": [{"step": 0, "ok": true, "evidence": ""}], "issues": []}
