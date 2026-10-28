# Phase 5c — log

Loop (planned): dev → review ‖ QA → fix → combined verify → orchestrator probe →
learnings.

Decisions taken with the user before dev (2026-10-28, one question call, all four
recommended options): `video-reviews/<id>/` top-level; verdict + flags + watched +
note; queue = all assessed, shown-in-player unreviewed first; latest human
`unsuitable` hides from the player (amends 0008/0010). Orchestrator defaults in
context.md "Settled by the orchestrator" (snapshot of agent call in the record,
derived status, dir must exist, unreadable review hides, `videos` CLI group).

Orchestrator pre-checks: baseline 498 passed / 85%.

## 1 — dev
- commits: 94a04cb model/store/verdict/agreement; d7e1c28 player rule 4; 51a1f64
  review UI queue/detail/form; 98fbe21 `videos` CLI; a83f189 docs (0011 etc.).
- tests: 594 passed, coverage 87% (was 498 / 85%).
- design: `records.py` shared file helpers (ChannelStoreError = alias of StoreError);
  `trusted/video_reviews.py` (VideoReview, store, ReviewState, hidden_ids,
  Agreement); rule 4 in `select_videos(…, hidden)`; `trusted/spot_checks.py` queue
  (shown from select_videos); `review/videos.py` routes, `review/pages.py` helpers;
  `cli/videos.py` thin.
- real run: 42 assessed, 14 shown; unsuitable → 13, later suitable → 14; bad ids
  404; cross-site POST 403; export missing dir exit 1; serve missing dir warns +
  500s.
- deviations: `--watched` required in CLI; StageRecord.body; queue skips assess
  files lacking snapshot fields; plain iframe embed; DEPLOYMENT.md paths fixed.
- unresolved: bad assess file warned twice in queue (cosmetic).
