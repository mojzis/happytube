# HappyTube Web Player

A simple, controlled web player for the videos the trusted pipeline found
suitable (decision 0010). Deployment: [DEPLOYMENT.md](../../../DEPLOYMENT.md).

## Two ways to run it

1. **Local:** `uv run happytube serve` → http://127.0.0.1:8000/player/ — the
   FastAPI app serves this page and `videos.json` live from `stages/trusted/`, the
   channel registry and `video-reviews/` (same app as the review UI at `/channels`
   and `/videos`).
2. **GitHub Pages:** CI runs `python -m happytube.web.export`, which writes
   `static/videos.json` (a git-ignored build product), and deploys `static/`.

Both use the same selection (`happytube.trusted.player.select_videos`): assessed
`suitable: true`, enhanced (non-empty cleaned description), channel currently
approved, not hidden by a human spot-check (decision 0011); newest first. `player.js` fetches `videos.json` relative to the page,
so it is one code path in both places.

## Features

- **Controlled playback:** YouTube embed with recommendations and related
  videos disabled
- **Curated playlist:** only the selected videos
- **Search:** filter by title, description or channel
- **Keyboard navigation:** arrow keys or n/p
- **Auto-play next** (optional) and fullscreen

## YouTube embed restrictions

- `rel=0` — no related videos from other channels
- `modestbranding=1` — minimal YouTube branding
- `iv_load_policy=3` — no annotations
- `disablekb=1` — keyboard controls that could navigate to YouTube disabled
- `showinfo=0` — no video information overlay

## `videos.json`

A list of records, newest `published_at` first:

```json
{
  "video_id": "MBkj5UGA_Xw",
  "title": "…",
  "channel_name": "explore.org",
  "channel_slug": "explore-org",
  "published_at": "2026-10-23T18:13:43Z",
  "duration_s": 163,
  "description": "the cleaned description (enhance step)"
}
```

## Layout

```
src/happytube/web/
├── export.py           # python -m happytube.web.export → static/videos.json
└── static/
    ├── index.html      # the player page (served at /player/ and on Pages)
    ├── player.js       # player logic, loads videos.json next to the page
    ├── styles.css
    └── videos.json     # build product (git-ignored)
```
