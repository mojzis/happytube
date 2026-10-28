# Phase 0 — fix round 2

See [context.md](./context.md) and [log.md](./log.md) (Step 4a review round 2, 4b QA round 2) — required reading.

## Task
On `phase-0-template`, fix and commit (hooks pass, no push, don't commit docs/phases/*):
1. All 5 `should-fix` findings from Step 4a, as proposed (fetch/run-all exit non-zero
   on `YouTubeAPIError` with a CliRunner test; API error message in the exception
   without URL/key, no double logging; config message after the stage header;
   replace/delete tautological `test_today_local`; tmp_path test for
   `df_from_stage_dir` skip/warn path + parquet round-trip).
2. Both `suggestion`s (log %s args + log missing dir once/at debug; no hard-coded `/4`).
3. QA nits: `deploy_web.sh` use `uv run python` and drop dead `$?` check; add a
   vulture whitelist (e.g. `vulture_whitelist.py` or `[tool.vulture] ignore_names` /
   `ignore_decorators`) so `poe dead-code` is quiet on the 29 false positives —
   only silence true false positives.
Keep it small; no restructuring of FetchStage beyond what (1) needs.

## Report
Return ONLY JSON (≤300 words):
{"commit_shas": [], "fixed": [], "not_fixed": [], "deviations": [], "check_output_tail": ""}
