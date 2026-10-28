# Channel fetch methods: API vs RSS vs search.list

Date: 2026-10-28 · phase 2 · real runs against 13 seed channels (decision 0004)

## Question

How should HappyTube read a trusted channel's recent uploads — once, as evidence for
vetting (phase 2–4), and daily, to find new videos (phase 5) — within the YouTube Data
API budget of 10 000 units a day?

## Methods

| | Official API (implemented) | RSS feed | `search.list` |
|---|---|---|---|
| Calls | `channels.list?forHandle` (resolve, once), `channels.list?id=` (≤50 ids), `playlistItems.list` on `UU…`, `videos.list` (≤50 ids) | `youtube.com/feeds/videos.xml?channel_id=UC…` (or `?playlist_id=`) | `search.list?channelId=…&order=date` |
| Cost | 1 unit per call | 0 units, no key | **100 units per call** |
| Items | up to 50 per page, any depth | latest **15** only | 50 per page |
| Duration | yes (`contentDetails.duration`) | **no** | no (needs `videos.list`) |
| Shorts | duration only (see below); `UUSH…` playlist | link is `/shorts/<id>` for Shorts | no |
| made_for_kids | yes (`status.madeForKids`) | no | no |
| Language | `defaultAudioLanguage` / `defaultLanguage` | no | no |
| Channel stats | subscribers, views, video count, country | title only | no |
| Views per video | with `part=statistics` | yes (`media:statistics views`) | no |
| Stability | documented, versioned | undocumented, has worked for years | documented |

**`search.list` is ruled out**: 100 units per channel per refresh means 100 channels
use the whole daily budget; it also returns no durations.

## Quota per refresh

API path, one page (50 uploads) per channel, durations for all of them:
`ceil(N/50)` channels + `N` playlistItems + `N` videos (one call per channel's ≤50
ids). Resolving handles costs `N` once, never again (the id is stored).

| channels N | resolve (once) | full evidence refresh | daily poll, API only¹ | daily poll, RSS + API² | share of 10 000 (full / API poll) |
|---:|---:|---:|---:|---:|---|
| 50 | 50 | 101 | ~52 | ~1 | 1 % / 0.5 % |
| 200 | 200 | 404 | ~205 | ~4 | 4 % / 2 % |
| 500 | 500 | 1 010 | ~510 | ~10 | 10 % / 5 % |

¹ `N` playlistItems (first page only, `maxResults` small) + `videos.list` only for ids
not seen before, batched 50 across channels (`ceil(new/50)`, assuming ~1 new upload
per channel per day).
² RSS to spot new ids (0 units), then `videos.list` for those ids only.

Measured: the phase 2 real run used **31 units** for 13 channels (2 resolves, 2
not-found resolves, 1 `channels.list`, 13 × (playlistItems + videos)) plus 15 for the
initial `resolve --all`, 4 for a re-run of one channel and 6 for the UUSH/UULF test
below. Formula check: 13 channels → 1 + 26 = 27 + 4 resolves = 31. ✓

## Shorts

The phase rule is `is_short = 0 < duration_s ≤ 180` (Shorts may be up to 3 min since
October 2024; `0` is a live or upcoming stream, reported as `P0D`). Real data shows
**the duration rule over-counts heavily** — zoos post many regular 1–3 min clips:

- **Zoo Praha**: 33 of its last 50 uploads are ≤ 180 s, but **none** is a Short — all
  50 are in its `UULF` (long-form) playlist, and its 34 Shorts are older.
- **Monterey Bay Aquarium**: 33 rule-Shorts; 25 are in `UUSH` (real Shorts), 7 are
  regular videos in `UULF`; every `UUSH` video in the snapshot is ≤ 180 s.
- **RSS** agrees with `UUSH`: of Monterey's 15 RSS entries, 6 link to `/shorts/<id>`;
  4 `watch?v=` entries are ≤ 180 s (incl. two 0 s streams). BBC Earth's Shorts in RSS
  are 60–113 s, and Zoo Praha's nine 84–177 s RSS entries are all `watch?v=`.

**The `UUSH…` / `UULF…` / `UULV…` playlist trick works** (replace `UC` in the channel id
with `UUSH` = Shorts, `UULF` = long-form, `UULV` = live streams). It works via the API
(1 unit per page) and as RSS (`feeds/videos.xml?playlist_id=UUSH…`, 0 units). It is
undocumented, so we don't depend on it yet: snapshots keep the duration rule and store
`duration_s`, so a better flag can be recomputed later.

## RSS observations (real fetches, no key)

- 3 channels (Monterey Bay Aquarium, Zoo Praha, BBC Earth): HTTP 200, 25–36 kB,
  50–200 ms each, exactly **15 entries**, newest first, all among the API's
  latest 50 uploads.
- Per entry: video id, title, `published`, `updated`, description (full, not
  truncated), thumbnail, views, star rating; the link reveals Shorts. No duration, no
  made_for_kids, no language, no channel stats.
- Fifteen entries cover ~7 weeks for Zoo Praha (Jul 30 – Sep 15), far less for busy
  channels — enough for a daily poll, not for vetting evidence.

## Other findings from the real run

- **Agent-proposed handles are unreliable**: 4 of 13 did not resolve (`@ctdecko`,
  `@exploreorg`, `@zoodvurkralove`, `@zoozlin`), and one resolved to the **wrong
  channel**: `@NatureonPBS` is an unofficial 454-subscriber channel from Pakistan;
  PBS's own is `@naturepbs`. Only the snapshot's title / country / subscribers showed
  it — the human check in `show` is needed. `explore.org` is
  `@ExploreLiveNatureCams`, ZOO Dvůr Králové renamed itself
  `@safariparkdvurkralove`; ČT Déčko and Zoo Zlín are still unknown.
- `made_for_kids` is all-true on kids broadcasters (BBC Earth Kids, Nat Geo Kids) and
  mostly false elsewhere — usable as a signal, not a filter.
- `defaultAudioLanguage` is set on nearly every video (`cs`, `en`, `en-GB`, `en-US`).

## Recommendation

- **Evidence (phase 2–4)**: keep the official API path as implemented.
- **Shorts**: in phase 3, mark Shorts by `UUSH` membership (1 extra unit per channel,
  or 0 via RSS) instead of the 180 s rule, which flags most short zoo clips wrongly.
- **Daily polling (phase 5)**: RSS to detect new uploads (0 units, 15 entries), then
  one `videos.list` per 50 new ids for durations / made_for_kids / language. Fall back
  to `playlistItems` (1 unit per channel) when a feed fails or more than 15 uploads
  are new. Even the API-only fallback for 500 channels is ~5 % of the budget.
