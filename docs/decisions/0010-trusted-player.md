# 0010 The trusted player

Date: 2026-10-28
Status: accepted (amended by 0011: selection rule 4, not hidden by a human
spot-check)

## Context

The trusted pipeline (decision 0009) writes suitable, cleaned-up videos of approved
channels to `stages/trusted/`, but the player and its GitHub Pages export still read
legacy raw JSON from `data/fetched/`, which nothing writes any more: the export
yielded 0 videos and the deploy was paused. The player ran on Flask, while the
user's web stack is FastAPI + htmx (decision 0006). The player is what a
grandmother with early dementia watches, so what it shows must follow the rules
exactly and fail loudly rather than show the wrong thing.

## Decision

- **Deployed data = committed `stages/trusted/`.** The trusted stage files are
  tracked in git (public repo; public YouTube metadata only, no keys, no personal
  data). Other stage dirs stay ignored (`/stages/*` except `trusted/`). The Pages
  workflow builds `videos.json` from `stages/trusted/` + `channels/` in CI and
  deploys again on a push to `main` touching them or the player; `videos.json` is a
  build product, untracked and git-ignored. GitHub Pages is enabled with the GitHub
  Actions source (https://mojzis.github.io/happytube/).
- **Selection rule** — one pure function, `trusted.player.select_videos`, used by
  the live route and the export. A video is shown iff
  1. its assess file says `suitable: true` (a real boolean),
  2. it has an enhance file with a non-empty `enhanced_description` (**hidden until
     enhanced**), and
  3. its channel is **currently `approved`** (`derive_status`). A channel rejected
     later disappears from the player — safety beats history. An unknown slug, or a
     channel whose reviews can't be read, is not shown.
- **Every suitable video ever assessed, newest `published_at` first** (then by id).
  No window, no grouping.
- **Fields from assess, only the description from enhance**: an enhance file can
  carry stale scores after a re-score. Joined by video id across date dirs.
- **Duplicates and bad files:** per video id the copy in the latest date dir counts,
  even if broken (an older copy may be stale). A file that can't be read, lacks a
  field, has a timestamp without zone or a `video_id` not matching its file name is
  skipped with a warning naming the path — never shown, never a crash.
- **Public JSON is minimal:** `video_id`, `title`, `channel_name`, `channel_slug`,
  `published_at`, `duration_s`, `description` (a pydantic `PlayerVideo`). No scores.
- **One app:** the player joins the local FastAPI app served by `happytube serve`:
  `GET /player/` is the static page (`web/static/`), `GET /player/videos.json` the
  selection read live per request (`--stages-dir`, default `stages/` in the cwd as
  the `trusted` commands). The Host / Origin guard covers it. `player.js` has one
  code path: it fetches `videos.json` relative to the page, locally and on Pages.
- **Export fails loudly:** `python -m happytube.web.export` exits non-zero when
  `stages/trusted/` or the registry dir is missing (a wrong CI path must not deploy
  an empty player); an empty selection is a warning and exit 0.
- **Flask dropped:** `web/server.py`, its template and the `data/fetched/` loader
  are gone, and `flask` with them.
- **Daily push is opt-in:** `HAPPYTUBE_PIPELINE=trusted HAPPYTUBE_PUSH=1
  scripts/daily_run.sh` commits only `stages/trusted/` ("trusted run DATE") and
  pushes, also after a failed run that wrote files; off by default.

## Consequences

- A merge of stage files to `main` is a deploy: what is committed is what she sees.
  The first real `stages/trusted/` commit is the user's call; until then the
  deploy workflow fails at the export (no `stages/trusted/`), which is intended.
- Rejecting a channel removes its videos on the next page load (local) or the next
  deploy (Pages; `channels/**` is in the push trigger).
- A suitable video appears only after its enhance step succeeds; an enhance failure
  delays it, never shows a raw description.
- The repo grows by one small markdown file per stage per video; fine at the
  expected tens of videos a day.
- The local player and review UI share one server, one guard and one port.
