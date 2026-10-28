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
