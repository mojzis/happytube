# Phase 0 — QA (functional verification, report only)

See [context.md](./context.md) — required reading, esp. "Verification baseline".

## Task
Independently verify the repo works after phase 0. Run from a clean state:
1. `git status` clean; `git log --oneline a336adc..HEAD`.
2. `rm -rf .venv && uv sync` succeeds.
3. `uv run poe check` — paste tail; each sub-tool result.
4. `uv run pytest -q` — count ≥ 30 passed.
5. `uv run happytube --help` and `--help` for every subcommand.
6. `uv run happytube status` (should not crash without data / API keys, or fail
   with a clear message — report which).
7. `uv run python -m happytube.web.export` and confirm output path is
   `src/happytube/web/static/videos.json`; `git checkout` it afterwards if modified.
8. Start `uv run python -m happytube.web.server` in background, `curl` `/` and an
   API route if any, then kill it.
9. `git config core.hooksPath` == `hooks`; make a throwaway `.py` change in a
   scratch git worktree (`git worktree add /tmp/claude-1000/qa-wt HEAD`), stage and
   `git commit` there to prove the hook runs; then remove the worktree.
10. Grep the repo (excl. .venv, uv.lock, docs/phases) for references to deleted
    modules/paths: `happytube.main`, `mq`, `tmq`, `ip.sh`, `yt_api_pipeline`,
    `dlt`, `poetry`, old `happytube/web/static` paths.
11. `.github/workflows/deploy.yml` paths match the new layout.
12. Confirm template files present: hooks/pre-commit, .github/dependabot.yml,
    src/happytube/py.typed, tests/__init__.py, docs/{constitution,architecture,naming}.md,
    docs/decisions/0001*, 0002*.

## Constraints
Do NOT modify tracked files or commit on the branch. Restore anything a command touches.

## Report
Return ONLY JSON (≤500 words):
{"verified": true, "checks": [{"step": 1, "ok": true, "evidence": ""}], "issues": [""]}
