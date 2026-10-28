# Architecture

## Overview

A Python CLI (`happytube`, click) runs a stage-based pipeline. Each stage reads the
previous stage's markdown files and writes its own, so stages can be rerun per date.
A Flask app serves a player for the curated videos; a static export of it deploys to
GitHub Pages. Planned: a channel registry and review layer in front of fetch, so
videos come only from human-approved channels (see [plan](plan.md)).

## Components

Current (`src/happytube/`):

- `cli/` — click commands: `fetch`, `assess`, `enhance`, `report`, `run-all`, `status`.
- `stages/` — `fetch` (YouTube Data API search), `assess` (Claude happiness score
  1–5), `enhance` (Claude rewrites descriptions of videos scoring ≥ threshold),
  `report` (HTML report + parquet exports).
- `models/` — `MarkdownFile` (YAML frontmatter + body), `Video` (pydantic).
- `config/` — pydantic settings from `.env`; YAML config from `config/base/`.
- `web/` — Flask player (`server.py`) and static export (`export.py`).
- `videos.py`, `prompts.py`, `utils/` — YouTube query helpers, prompt texts, helpers.

Planned:

- **Channel registry** — channel files (`candidate` / `approved` / `rejected`) with
  ids, kind, language.
- **Evidence** — per-channel stats and recent uploads, cached.
- **Review records** — who (human or agent), verdict, notes, when; one shape for both.
- **Agent vetting** — Claude reads evidence with the calm/happy rubric and writes a
  vet report plus an agent review record.
- **Web review UI** — channel queue, detail and approve/reject form in the Flask app.

## Data

- `stages/<stage>/YYYY-MM-DD/video_<id>.md` — one markdown file per video per stage.
- `stages/report/YYYY-MM-DD.html`, `parquet/<stage>/by-run-date/*.parquet`.
- `config/base/*.yaml` — app, prompts, YouTube search settings.
- `data/fetched/` (git-ignored) — legacy raw API JSON the web player still reads.
- Planned: channel, evidence and review files in git (see decision 0002).

## Flows

- **Daily:** `happytube run-all` → fetch → assess → enhance → report.
- **Player:** `python -m happytube.web.server` locally, or
  `python -m happytube.web.export` → GitHub Pages.
- **Planned review:** add candidate channel → collect evidence → agent vets → human
  approves in the web UI or CLI → fetch reads only approved channels.
