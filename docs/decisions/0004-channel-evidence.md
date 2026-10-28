# 0004 Channel evidence: append-only API snapshots

Date: 2026-10-28
Status: accepted

## Context

Phase 3 (agent vetting) and phase 4 (web review) need something to judge a channel
by: who it really is, how big, and what it has uploaded lately. Registry channels
start as a name and maybe a handle (decision 0003). Fetching must fit the YouTube
Data API budget of 10 000 units a day. Research and quota math:
[channel-fetch-methods](../research/channel-fetch-methods.md).

## Decision

- **Snapshots, append-only** — `channels/<slug>/evidence/<UTC YYYYMMDDTHHMMSSZ>.yaml`,
  created exclusively, `-2`, `-3`… on a name collision, never overwritten (the same
  rules as reviews in 0003). The latest snapshot is the one with the newest
  `fetched_at`, ties broken like reviews.
- **Snapshot fields** — `fetched_at`, `method` (`api`; `rss` reserved), the resolved
  channel's `channel_id`, `title`, `custom_url`, `description` (≤1000 chars),
  `country`, `published_at`, `subscriber_count` (null if hidden), `view_count`,
  `video_count`, `uploads_playlist_id`, `shorts_source` (`uush` | `duration`,
  default `duration` so the first snapshots still load), and `videos` newest first (default 50): id,
  title, `published_at`, `duration_s`, `is_short`, `description` (≤300 chars),
  `default_language`, `made_for_kids`. Strict model, unknown keys are errors.
- **Method: official API** — `channels.list?forHandle` to resolve (1 unit, once),
  `channels.list?id=` (1 unit per 50 channels), `playlistItems.list` on the `UU…`
  uploads playlist (1 unit per 50 uploads), `playlistItems.list` on the `UUSH…`
  Shorts playlist (1 unit), `videos.list` for durations (1 unit per 50 videos).
  About 3 units per channel per refresh (`3N + N/50`). A 404 on the uploads
  playlist is a channel with no uploads (0-video snapshot). `search.list`
  (100 units) is not used.
- **Shorts: `UUSH` playlist membership** — a video is a Short if it is in the
  channel's `UUSH` + `channel_id[2:]` playlist; one page of `--max-videos` items is
  enough (the Shorts among the newest N uploads are the newest Shorts). A 404
  `playlistNotFound` means the channel has no Shorts (`shorts_source: uush`, none
  flagged). Any other non-stopping error on that call falls back to the duration
  rule (`shorts_source: duration`): `0 < duration_s ≤ 60` for videos published
  before 2024-10-15, `≤ 180` since (Shorts got 3 minutes then). `duration_s` is
  stored either way.
- **channel_id write-back** — amends 0003's "written once by `channels add`;
  afterwards only humans edit it": `channels resolve` / `evidence` may fill
  `channel_id` in `channel.yaml` **only when it is null**, and only with an id no
  other channel holds. It changes just that key: the rest of the mapping is kept
  in its key order, but **YAML comments are lost** (no round-trip YAML library). The
  write is atomic (temp file + replace, null re-checked just before). `resolve`
  skips channels that already have an id (0 units); `resolve --verify` re-checks
  them, and a different id is a `mismatch` error, never overwritten.
- **Human check of resolution** — a handle can resolve to the wrong channel, so the
  snapshot records the resolved `title` and `custom_url` and `channels show` prints
  them ("resolved to: …") next to the registry name.
- **Run safety** — the API key is never logged: request errors carry no URL, and the
  key is a `SecretStr` in settings. A used-up quota or a rejected key stops the run;
  snapshots already written stay, and every requested channel is still reported
  (`not_fetched` for those never reached).
- **RSS deferred** — researched, not implemented; recommended for phase 5 daily
  polling (0 units, 15 latest entries, no durations).
- Code: `happytube/youtube.py` (`YouTubeClient`), `channels/evidence.py` (pure
  builder), `channels/collect.py` (resolve / collect runs), `ChannelStore.add_evidence`
  / `evidence` / `latest_evidence` / `set_channel_id`, CLI `channels resolve` and
  `channels evidence`.

## Consequences

- Evidence history accumulates in git; nothing is lost when a channel changes, and a
  reviewer can see what the vetter saw.
- A full refresh of 500 channels costs ~1 510 units (15 % of the daily budget).
- Agent-proposed handles need the human check: in the first real run one handle
  resolved to an unofficial look-alike channel, caught only by its snapshot.
- The first 13 snapshots (before the fix) used the plain ≤ 180 s rule, which flagged
  many regular short clips (Zoo Praha: 33 of 50 uploads, none of them Shorts). They
  stay as written (append-only, `shorts_source` defaults to `duration`); later
  snapshots use `UUSH`. `UUSH` is undocumented — if YouTube drops it, the duration
  fallback takes over and `shorts_source` says so.
- Snapshots grow the repo (~20–30 kB per channel per refresh); fine for weekly
  refreshes of hundreds of channels, worth revisiting for daily ones.
