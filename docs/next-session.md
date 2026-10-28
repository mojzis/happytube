# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–5 + backlog).
- Phases 0, 1, 2 merged (PRs #6, #7, #9). **Phase 2 done** (channel evidence);
  merged with full history — commit 6a89bb6 alone is inconsistent (V6, bisect only).
  - `happytube channels resolve` (handle → channel id, written to channel.yaml only
    when null; `--verify` re-checks) and `channels evidence` (stats + recent
    uploads + durations, append-only snapshots in `channels/<slug>/evidence/`).
  - Shorts = membership of the channel's `UUSH…` playlist (404 = none); duration
    rule only as fallback. Quota ≈ 3N + N/50 per full refresh (500 ch ≈ 1510).
  - Decision 0004, research note `docs/research/channel-fetch-methods.md`
    (RSS deferred to phase 5 polling).
  - 13/15 channels resolved, snapshots committed — but taken **before** the UUSH
    switch, so their Shorts flags use the old ≤180 s rule (`shorts_source: duration`).
  - Tests 122 → 212, coverage 59% → 69%.
  - Record: `docs/phases/phase-2/` (log.md, learnings.md).
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **User:** fix `YTKEY` in `.env` (stray trailing character; YouTube says
   `API_KEY_INVALID`). Then `uv run happytube channels evidence --all` (~42 units),
   check UUSH Shorts counts look sane, commit the new snapshots.
2. **Content questions (deferred by user):** agent `unsure` reviews on ct-decko,
   zoo-zlin (handles unknown), national-park-service (identity),
   zoo-dvur-kralove (inactive since 2024-08). `channels show <slug>`.
3. Start **phase 3 — agent vetting**: write `docs/phases/phase-3/context.md`
   (rubric for calm/happy from the constitution, vet report format under
   `channels/<slug>/vet/`, agent review record, `channels vet <slug>`, Claude model
   choice — load the `claude-api` skill), then run the loop. Fold in the backlog
   item "auto-flag unresolved / inactive / look-alike channels".

## Open decisions (settle in phase 3 context.md)

- Vet input: latest snapshot only, or also fetch transcripts/thumbnails?
- Vet output: verdict scale (approve/reject/unsure as agent review) + per-video
  calm/happy scores reused later by video assessment?
- Re-vet policy when a newer snapshot appears.

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence = append-only snapshots, API method, UUSH Shorts,
  channel_id write-back only when null (0004).
