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

## 2 — review (verdict: fix)
- R1 medium: shown video whose assess lacks snapshot fields is missing from the
  queue and 404s → unreviewable, unhideable (orchestrator item confirmed).
- R2 medium: `load_yaml` catches only YAMLError; non-UTF-8 file / dir named x.yaml
  → unhandled 500 on /videos and /player/videos.json.
- R3 low: snapshot taken at POST time, not from the page seen (rescore race).
- R4 low: "rescored since" logic duplicated in template and `assess_changed`.
- R5 low: ChannelStoreError alias makes the channel handler catch video errors.
- R6 low: private helpers imported across packages; records.py depends on
  channels.models.
- R7 low: Jinja video_id test regex ≠ `is_video_id`.
- R8 low: test_bad_host_refused uses the repo's real video-reviews/.
- preexisting: undecodable channel review file crashes channel_statuses.

## 2 — QA (verified: true)
- numbers: 594 passed / 87%, poe check green.
- Q1 medium (= R2): non-UTF-8 review / dir named *.yaml → 500s on /videos,
  /player/videos.json; export traceback.
- Q2 low: `videos` CLI prints warnings twice (same root as dev's note / R1).
- Q3 low: `videos show` prints raw microsecond timestamps; UI formats them.
- all seeded scenarios, guard, bad ids, CLI JSON, missing dir, CI sim: pass.
- preexisting: header-less POST accepted (by design); reviews dir default is repo
  root while stages is cwd (same convention as channels).

## 3 — fix
- commits: da12e6e records StoreError + public helpers; f88bc9d every shown video
  queued/reviewable; ffc1aaf rescore guard (422); 65d3fb1 is_video_id in Jinja;
  f3c7603 CLI times; 3ae2f92 docs.
- tests: 607 passed, coverage 87%.
- fixed all R1–R8, Q1–Q3: `player.eligible` shared by queue + player; snapshot
  fields optional, "incomplete assess" marker; `records.read_text`; hidden
  `assessed_at` token; `rescored_since` single function; ChannelStoreError ⊂
  StoreError; helpers public in `utils`; warnings once.
- deviations: shared-helper errors are plain StoreError (tests updated); test ids
  now 11 chars; POST without `assessed_at` (curl) not checked.
- unresolved: bad flags/note in assess silently become empty.
