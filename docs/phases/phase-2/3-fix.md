# Phase 2 — fix

See [context.md](./context.md) and [log.md](./log.md) (dev, review R1–R7, QA Q1–Q6).
Work in the main checkout on `phase-2-evidence`. Commit in logical chunks; hooks must
pass; no `--no-verify` / `MADOQUA_SKIP`; do NOT push. Never read/print/commit `.env`
or the key.

## Must fix
- **R3 (Q1) Shorts via UUSH.** Per channel, one `playlistItems` call on
  `"UUSH" + channel_id[2:]` with `maxResults = max_videos` → set of Short ids.
  404 `playlistNotFound` = channel has no Shorts (empty set, source `uush`). Any other
  non-stopping error → duration fallback, source `duration`. Quota/invalid-key
  errors still stop the run. Duration fallback improves per Q1: Short if
  `0 < d <= 60` for videos published before 2024-10-15, `0 < d <= 180` after.
  Evidence gains `shorts_source: uush | duration` with default `duration` so the 13
  committed snapshots still load unchanged. `build_evidence` takes the short-id set
  (None → duration rule). Update tests (FakeYouTube serves UUSH playlists and a 404
  case), docs: 0004 Shorts rule + quota (~3N + N/50), research note table,
  CLAUDE.md, architecture.md.
- **R1 (Q2) aborted run lists every requested channel.** Pre-fill a result per slug;
  channels never reached get an explicit status (e.g. `not_fetched`), not a message
  string compare. Same for `resolve`. Multi-slug tests for both.
- **R2 set_channel_id preserves the file.** Load the raw YAML mapping, set only
  `channel_id`, dump with key order kept (comments may be lost — note it in 0004;
  don't add ruamel). Don't invent `added_at`; validate the result with `Channel`
  before writing. Refuse an id another slug already holds. Unique temp file name
  (`tempfile` in the same dir) + `os.replace`; re-check null just before replace.
- **Q3 resolve spends units on already-resolved channels.** Default: skip channels
  with a `channel_id` (status `already`, 0 units). Keep re-verification behind
  `--verify`. Update help/docs.

## Also fix
- R4: `YouTubeSettings.youtube_api_key` → `SecretStr`.
- R5 (Q5): add `keyInvalid` / `accessNotConfigured` to stopping reasons; uploads
  playlist 404 → 0-video snapshot; tolerate missing `snippet.publishedAt` (skip
  the item, don't crash the run).
- R6: `list` reads only the latest snapshot file per channel (order by stem + collision
  index, same ordering helper), not every snapshot.
- R7: `is None` checks for subscriber count and duration in `show`.
- Preexisting: `videos.py` `YtQuery.get` — catch `requests.RequestException` and raise
  `YouTubeAPIError` without the URL (key leak). Minimal change; don't refactor the
  legacy fetch otherwise.

## Do NOT fix
- videos.py reading YTKEY via `os.getenv` (phase 5 rewrites fetch).
- Rewriting committed snapshots (append-only — a re-run adds new ones).
- Handles for ct-decko / zoo-zlin; NPS / Dvůr Králové identity (user decides).

## Real re-run (last)
After `uv run poe check` is green: `uv run happytube channels evidence --all` in the
main checkout. The key in `.env` may still have a trailing stray character. Do NOT
truncate or otherwise work around it this time: if the first call reports an invalid
key, stop, report `real_rerun: "skipped: invalid key"` and finish. Otherwise commit
the new snapshots (expect ~13 × 3 + 1 ≈ 40 units).

## Report
Return ONLY JSON (≤450 words):
{"commit_shas": [], "fixed": ["R1 (Q2): how"], "deviations": [], "real_rerun": "",
 "shorts_after": "per-channel uush counts vs old duration counts, if re-run",
 "unresolved_issues": [], "check_output_tail": ""}
