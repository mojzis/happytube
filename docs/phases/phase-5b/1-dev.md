# Phase 5b — dev

See [context.md](./context.md) — required reading; it settles the design.

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-5b-trusted-player` (checked
out; context.md committed). Baseline: 456 passed, coverage 82%, `poe check` green.

## Task
1. Pure selection + loader first (small commit), with its table test.
2. Player routes in the FastAPI app, player.js/index.html on one code path, export
   rewritten, Flask + legacy loader removed, `.gitignore`, daily_run.sh push opt-in,
   deploy workflow, decision 0010, CLAUDE.md, DEPLOYMENT.md, architecture — as in
   context.md. Small coherent commits; `uv run poe typecheck` before each; hooks
   must pass.
3. Real data run (context.md "Real data"): scratch under `/tmp/claude-1000/p5b-real`,
   keys from the repo `.env`, never printed. Probe first; credential failure → stop
   and report. Commit nothing from scratch.
4. `uv run poe check` green at the end.

## Report
Return ONLY JSON (≤600 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X% (was 82%: why moved)",
 "selection": "where the rule lives, how live route + export share it",
 "real_run": [{"check": "", "result": ""}],
 "cost_ledger": {"youtube_units": "", "anthropic": "tokens + USD"},
 "real_run_eyeball": "videos shown per channel, hidden cases checked, two records",
 "deviations": ["anything differing from context.md, incl. workarounds"],
 "unresolved_issues": [""]}
