# Architecture

## Overview

A Python CLI (`happytube`, click) runs a stage-based pipeline. Each stage reads the
previous stage's markdown files and writes its own, so stages can be rerun per date.
A Flask app serves a player for the curated videos; a static export of it deploys to
GitHub Pages. A git-tracked channel registry holds candidate channels and their human
and agent reviews; planned: put it in front of fetch, so videos come only from
human-approved channels (see [plan](plan.md)).

## Components

Current (`src/happytube/`):

- `cli/` — click commands: `fetch`, `assess`, `enhance`, `report`, `run-all`, `status`,
  and the `channels` subgroup (`add`, `list`, `show`, `review`, `resolve`,
  `evidence`, `vet`; `--json` for agents).
- `channels/` — channel registry: `Channel`, `Review` and `Evidence` models and
  `ChannelStore` (files under `channels/`). Status is derived from the latest human
  approve/reject; agent reviews never change it; a rejected channel is the blocklist
  entry. `evidence.py` builds snapshots from API responses; `collect.py` runs
  resolve / evidence over many channels and stops on quota or a rejected key.
  `vet.py` holds the pure vetting parts (flags, prompt, verdict rule, report);
  `vet_run.py` the Claude call behind a `VetClient` protocol and the vet run, which
  stops on a rejected key, missing permission or no credit.
- `rubric.py` — the calm/happy rubric, video flags, `VideoScore` and `is_suitable`,
  shared by channel vetting and (phase 5) video assessment.
- `youtube.py` — small YouTube Data API client (handle resolve, channels,
  playlistItems, videos): injectable HTTP getter, 50-id batching, quota count,
  errors that never contain the key.
- `stages/` — `fetch` (YouTube Data API search), `assess` (Claude happiness score
  1–5), `enhance` (Claude rewrites descriptions of videos scoring ≥ threshold),
  `report` (HTML report + parquet exports).
- `models/` — `MarkdownFile` (YAML frontmatter + body), `Video` (pydantic).
- `config/` — pydantic settings from `.env`; YAML config from `config/base/`.
- `web/` — Flask player (`server.py`) and static export (`export.py`).
- `videos.py`, `prompts.py`, `utils/` — legacy YouTube search for fetch, prompt
  texts, helpers.

Planned:

- **Web review UI** — channel queue, detail and approve/reject form in a FastAPI +
  htmx app (decision 0006); the Flask player moves there in phase 5.

## Data

- `stages/<stage>/YYYY-MM-DD/video_<id>.md` — one markdown file per video per stage.
- `stages/report/YYYY-MM-DD.html`, `parquet/<stage>/by-run-date/*.parquet`.
- `config/base/*.yaml` — app, prompts, YouTube search settings.
- `data/fetched/` (git-ignored) — legacy raw API JSON the web player still reads.
- `channels/<slug>/channel.yaml` and `channels/<slug>/reviews/<UTC stamp>-<reviewer>.yaml`
  — registry and append-only review records in git (decisions 0002, 0003).
- `channels/<slug>/evidence/<UTC stamp>.yaml` — append-only evidence snapshots:
  resolved channel, stats, recent uploads with durations and Shorts flag (`UUSH`
  playlist membership, duration fallback; 0004).
- `channels/<slug>/vet/<UTC stamp>.md` — append-only vet reports: YAML frontmatter
  (verdict, flags, channel and per-video calm/happy scores, tokens) and a markdown
  body for people (0005).

## Flows

- **Daily:** `happytube run-all` → fetch → assess → enhance → report.
- **Player:** `python -m happytube.web.server` locally, or
  `python -m happytube.web.export` → GitHub Pages.
- **Evidence:** `channels resolve` (handle → channel id, once) → `channels evidence`
  (stats + latest 50 uploads + `UUSH` Shorts ids, ~3 API units per channel) →
  snapshot in git.
- **Vetting:** `channels vet` → Claude Opus 5.5 judges the latest snapshot (identity,
  long-form videos only) → vet report + agent review (status unchanged). Skipped
  when the latest vet already used the latest snapshot.
- **Planned review:** add candidate channel → collect evidence → agent vets → human
  approves in the web UI or CLI → fetch reads only approved channels.
