# Phase 2 — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-2-evidence`, base commit
`2a22ea7` (main after PR #8). Plan: `docs/plan.md` (phase 2 row). Principles:
`docs/constitution.md`. Registry layout: `docs/decisions/0003-channel-registry-layout.md`.
Phase 1 record: `docs/phases/phase-1/`. Process lessons: `docs/process-learnings.md`.

## Goal

For every channel in the registry: resolve its YouTube channel id, collect stats and
recent uploads with durations (Shorts flagged), and store that as **evidence** next to
the channel, so phase 3 (agent vetting) and phase 4 (web review) have something to
judge. Plus a research note + decision record comparing fetch methods with quota math.

## Decisions settled for this phase (orchestrator + user, 2026-10-28)

Record them in `docs/decisions/0004-channel-evidence.md` (accepted), with the quota
math from the research note.

- **Real API key is available** in `/home/matous/git/happytube/.env` as `YTKEY`
  (git-ignored). **Never print, log, cat, echo or commit it.** Don't `cat .env`.
  Worktrees don't have `.env` — real runs happen only in the main checkout.
- **Evidence storage: append-only snapshots**, same rules as reviews:
  `channels/<slug>/evidence/<UTC compact ts>.yaml` (e.g. `20261028T190000Z.yaml`),
  created with `open("x")`, `-2` suffix on collision, never overwritten. Latest
  snapshot = the one with the newest `fetched_at` (reuse the review ordering logic,
  don't duplicate it).
- **Fetch method (implemented): official API.**
  1. Resolve: `channels.list?forHandle=@x&part=id` (1 unit, one handle per call).
  2. Stats: `channels.list?id=<≤50 ids>&part=snippet,statistics,contentDetails`
     (1 unit per 50 channels) — `contentDetails.relatedPlaylists.uploads` is the
     `UU…` uploads playlist.
  3. Recent uploads: `playlistItems.list?playlistId=UU…&part=snippet,contentDetails&maxResults=50`
     (1 unit per page; one page by default).
  4. Durations: `videos.list?id=<≤50 ids>&part=contentDetails,snippet,status`
     (1 unit per 50 videos) — ISO-8601 duration → seconds.
  RSS (`https://www.youtube.com/feeds/videos.xml?channel_id=UC…`, 0 units, ~15
  entries, no duration) is **researched, not implemented**: the research note
  compares it (try it on 2–3 real channels — no key needed) and says whether phase 5's
  daily polling should use it. If research shows the API path is wrong, flag it in
  `deviations`, don't silently switch.
- **Shorts**: `duration_s` stored per video; `is_short = duration_s <= 180` (Shorts
  can be up to 3 min since Oct 2024). Research note: does the `UUSH…` / `UULF…`
  playlist trick (shorts / long-form uploads playlists) work on a real channel? Report;
  don't depend on it.
- **Handles: agent proposes, offline.** Dev fills `handle` in the 13 seed
  `channel.yaml` files where reasonably confident (knowledge only, no `search.list`).
  `resolve` verifies: forHandle returning no item = wrong handle → report it, leave
  `channel_id` null. This is a one-off metadata edit of seed files; commit it
  separately ("agent-proposed handles, verified by forHandle").
- **channel_id write-back**: `resolve` fills `channel_id` in `channel.yaml` **only
  when it is null**. If it's set and differs from what the handle resolves to →
  error, don't overwrite. Amend decision 0003's "channel.yaml written once by add"
  sentence to allow this one machine write (in 0004, reference it).
- **Human check of resolution**: the evidence snapshot records the resolved
  channel's `title` and `custom_url`, so `show` lets a human see "handle @x → channel
  'Zoo Praha'" and spot a wrong match.

## Evidence snapshot (pydantic `Evidence`, `extra="forbid"`)

```yaml
fetched_at: '2026-10-28T19:00:00Z'
method: api            # api | rss (rss unused for now)
channel_id: UC…
title: BBC Earth
custom_url: '@bbcearth'
description: …         # truncated to 1000 chars
country: GB            # nullable
published_at: '2009-…Z'
subscriber_count: 13000000   # null if hidden
view_count: …
video_count: …
uploads_playlist_id: UU…
videos:                # newest first, up to --max-videos (default 50)
- video_id: abc
  title: …
  published_at: …
  duration_s: 612
  is_short: false
  description: …       # truncated to 300 chars
  default_language: en  # nullable (snippet.defaultAudioLanguage or defaultLanguage)
  made_for_kids: false  # status.madeForKids, nullable
```

Keep YAML human-readable (`allow_unicode=True`, `sort_keys=False`, same dump helper as
the store).

## Code shape

- **YouTube client**: new module `happytube/youtube.py` (or `happytube/youtube/`
  package) — a small `YouTubeClient(api_key, get=requests.get)` with methods
  `resolve_handle`, `channels`, `playlist_items`, `videos`. The `get` callable is
  injectable so tests pass a fake; **no network in tests**. Reuse/move
  `YouTubeAPIError` + `_api_error_detail` from `videos.py` (don't duplicate). Batch
  ids in 50s. Parse ISO durations (`PT1H2M3S`, `P1DT…`, `PT0S`).
- **Key leak**: `requests` exceptions (`ConnectionError`, `Timeout`) carry the URL
  with `key=…`. Wrap every request: catch `requests.RequestException`, raise
  `YouTubeAPIError`/own error **without** the URL or the original message. Test that
  an exception message never contains the key.
- **Quota**: client counts units used (1 per call) and the CLI reports it at the end
  (`quota_units` in JSON). 403 `quotaExceeded` → clear error, stop, exit ≠ 0, keep
  already-written snapshots.
- **Key loading without Anthropic key**: `Settings` requires `ANTHROPIC_API_KEY`. Add a
  minimal settings class (e.g. `YouTubeSettings(BaseSettings)` with only `YTKEY`,
  same `.env`) or equivalent; missing key → clear error, exit ≠ 0. Commands that don't
  call the API (`list`, `show`, `add`, `review`) must keep working with no keys.
- **Evidence building** (API responses → `Evidence`) as a pure function, tested with
  fixture dicts shaped like real API responses (use the real run's shapes, but
  hand-trimmed; no keys/PII in fixtures).
- **Store**: `ChannelStore.add_evidence(slug, evidence)`, `evidence(slug)` (sorted),
  `latest_evidence(slug)`, `set_channel_id(slug, channel_id)` (null-only rule).
  Store stays click/rich-free (phase 4 Flask reuses it).

## CLI

- `happytube channels resolve [SLUG…] [--all] [--json]` — resolves handles with
  null `channel_id`; per channel: `resolved` / `already` / `not_found` / `no_handle`
  / `mismatch`. Exit 0 if no errors other than `not_found`/`no_handle` (those are
  reported, not failures); exit ≠ 0 on API errors/mismatch.
- `happytube channels evidence [SLUG…] [--all] [--max-videos 50] [--json]` —
  resolves first where needed, then fetches and writes one snapshot per channel.
  Reports per channel: path, video count, shorts count, or the error. Quota total.
- `show` gains a latest-evidence summary (fetched_at, title, subs, video count,
  N recent videos, shorts count; full list with `--json`). `list` gains an
  `evidence_at` (latest fetched_at or null) field/column.
- JSON: stdout only, errors on stderr, exit ≠ 0 — same contract as phase 1.

## Real run (dev, last step, main checkout only)

After mocks/tests are green: `uv run happytube channels evidence --all` with the real
key. Commit the 15 (or fewer) snapshots + resolved `channel_id`s. Expected quota:
~15 resolve + 1 channels + 15 playlistItems + ~15 videos ≈ 50 units. Report every
`not_found` handle; fix the handle if the right one is obvious and rerun only that
one, otherwise leave it for the user. Check one snapshot by eye: titles sane, shorts
flagged, unicode literal (Czech).

## Research + decision docs

- `docs/research/channel-fetch-methods.md`: API (channels/playlistItems/videos) vs
  RSS vs `search.list` (100 units, why not); quota table per refresh for 50 / 200 /
  500 channels (resolve once, then refresh), daily budget 10 000 units; what each
  method gives (durations, count, made_for_kids, language); UUSH/UULF finding;
  RSS observations from real fetches; recommendation for phase 5.
- `docs/decisions/0004-channel-evidence.md` (accepted): snapshot layout, API method,
  shorts rule, channel_id write-back rule, RSS deferred.
- Update CLAUDE.md (channels CLI section + storage tree `evidence/`) and
  `docs/architecture.md`. Don't touch `docs/plan.md`, `docs/next-session.md`,
  `docs/phases/` (except committing `docs/phases/phase-2/` as-is first).

## Existing code to know

- `channels/models.py` (`Channel`, `Review`, `_iso_z`, UTC validators),
  `channels/store.py` (`ChannelStore`, `_collision_index`, `_dump_yaml`,
  `_load_model`, `ChannelStoreError`), `cli/channels.py` (subgroup, `--json`,
  `_store_errors_as_click`).
- `videos.py` — legacy `YtQuery`/`Search` used by the fetch stage; has
  `YouTubeAPIError`. Don't break `stages/fetch.py`.
- `config/settings.py` — `Settings` needs both keys.

## Verification baseline

Before: 122 tests pass, `poe check` green, coverage 59%. After: `uv run poe check`
green; new tests for duration parsing, evidence building, batching (>50 ids), client
error paths (non-200, quotaExceeded, RequestException without key in message),
store evidence (append-only, latest, channel_id null-only rule, mismatch), CLI
resolve/evidence with a fake client (statuses, exit codes, `--json` parseable, no
network), list/show still work with no keys.

## Tooling gotchas

- Parallel agents: own worktree via `git worktree add --detach <path> phase-2-evidence`
  (plain add fails — branch is checked out), `uv sync` there, remove + prune after.
  Worktrees have no `.env`: read-only agents use fakes, never the real API.
- Don't run pytest concurrently in one checkout (shared `.coverage`).
- madoqua hook runs on staged .py only; never `--no-verify` / `MADOQUA_SKIP`.
- `tyf` index stale after hook reformat: `uv run tyf daemon restart`.
- Inject the HTTP getter; don't monkeypatch `requests` globally.
