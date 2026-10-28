# Phase 5b — log

Loop (planned): dev → review ‖ QA → fix → combined verify → orchestrator probe →
learnings.

Decisions taken with the user before dev (2026-10-28): deployed data = committed
`stages/trusted/`; show all suitable newest first; hide until enhanced. Orchestrator
defaults in context.md "Settled by the orchestrator" (channel-status filter, one
app, JSON shape, export fails on missing dir, push opt-in in daily_run.sh).

Orchestrator pre-checks: baseline 456 passed / 82%; GitHub Pages not enabled on the
repo (API 404); `stages/` untracked, not ignored; `static/videos.json` tracked (empty).

Orchestrator (user request): enabled GitHub Pages via `gh api -X POST repos/mojzis/happytube/pages -f build_type=workflow` → https://mojzis.github.io/happytube/. Dev told to document it as enabled.

## 1 — dev
- commits: 42b3003 selection; f4cc144 player in FastAPI app; 9d65273 export from
  stages/trusted, Flask + legacy loader gone; b28604f deploy on push, daily_run push;
  717ee70 docs (0010, deployment, architecture, CLAUDE.md); 6ba33af drop None branch.
- tests: 495 passed, coverage 85% (was 82%: new modules covered, old Flask/export gone).
- selection: `trusted/player.py` (`select_videos` pure, `read_stage`,
  `channel_statuses`, `player_videos`, `videos_json`); route + export share it.
- real run: fetch 42 new / 33 units; assess cincinnati-zoo 4/6, explore-org 3/3;
  enhance 7/7; export 7; serve /player/ 200, JSON 7; Host guard 400; unsuitable,
  not-enhanced, rejected-channel all hidden live. Cost ≈ $0.073.
- deviations: export exits 1 on missing registry too; latest date copy wins even if
  broken (hidden); strict file validation (StrictBool, tz, id/filename match);
  unreadable reviews → channel hidden; `--stages-dir`/`HAPPYTUBE_STAGES_DIR` on serve
  + export; `TrustedStage.days()`; deploy_web.sh and web/DEPLOYMENT.md deleted;
  LEGACY_FETCHED_DIR kept (videos.py); no-store caching; empty message text.
- unresolved: push deploys fail until first stages/trusted commit on main;
  daily_run pushes current branch; plan.md runpy backlog item now fixed.

## 2 — review (verdict: ship)
- R1 low: deploy `paths:` misses channels/**, trusted/**, models/**, pyproject/uv.lock.
- R2 low: daily_run `status | tee` failure under set -e skips the push.
- R3 low: `git add stages/trusted` fails if dir missing → misleading push error.
- R4 low: live `/player/videos.json` returns `[]` silently on wrong stages dir.
- R5 low: `HAPPYTUBE_STAGES_DIR` applies to player only, name suggests everywhere.
- preexisting: legacy commented git block in daily_run.sh contradicts 0010.
- Answers: all scenarios handled; no path shows non-approved channel; guard covers
  mount; traversal 404; flask fully gone.

## 2 — QA (verified)
- 495 / 85%; seeded 31 cases: export == live, exactly 8 shown; routes, traversal,
  guard, exit codes, daily_run commit scope, CI fresh clone exit 1 — all pass.
- Q1 medium: failed push leaves commit local; next run with nothing new never pushes.
- Q2 low (= R3), Q3 low (= R4), Q6 low (= R1).
- Q4 low: HEAD /player/videos.json falls to the static mount (404 / stale file).
- Q5 low: non-date stage dir skipped silently.
- preexisting: logs/ not git-ignored; player.js loads list only after YT iframe API
  (no error if YouTube unreachable); daily_run pushes current branch.

## 3 — fix
- commits: 4badca8 daily_run push every run, tolerate status failure / no dir;
  1d62dc5 deploy paths; d2b9179 serve/route missing-dir warning, HEAD live;
  b61fb54 non-date dir warning; 273f133 --stages-dir help (read side only).
- tests: 498 passed, 85%, poe check green.
- all must/also-fix done (Q1, R2, R3, R1, R4, Q4, R5, Q5, logs/ ignore, stale block).
- deviations: compact names like `20261028` now warned + skipped (were read as
  dates; closes 5a V2); route warning once per app instance.
