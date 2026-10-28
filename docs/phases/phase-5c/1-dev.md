# Phase 5c — dev

See [context.md](./context.md) — required reading; it settles the design.

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-5c-video-spot-checks`
(checked out; context.md committed). Baseline: 498 passed, coverage 85%, `poe check`
green.

## Task
1. Model + store + derived verdict + agreement stats first (small commit), with
   tests. Shared file-naming helper extracted from `channels/store.py`.
2. Selection rule 4 in `select_videos`, route + export wiring, `video-reviews/`
   option and README, deploy paths.
3. Review UI routes + templates, `videos` CLI group.
4. Decision 0011 (+ amend notes in 0008/0010), CLAUDE.md, DEPLOYMENT.md,
   architecture. Small coherent commits; `uv run poe typecheck` before each; hooks
   must pass.
5. Real data probe (context.md "Real data"): no paid calls; commit nothing from
   scratch.
6. `uv run poe check` green at the end.

## Report
Return ONLY JSON (≤600 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X% (was 85%: why moved)",
 "design": "where store / rule 4 / stats live; how route, export, CLI share them",
 "real_run": [{"check": "", "result": ""}],
 "real_run_eyeball": "queue section counts, one stored review file, player count before/after",
 "deviations": ["anything differing from context.md, incl. workarounds"],
 "unresolved_issues": [""]}
