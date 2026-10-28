# Architecture

## Overview

A Python CLI (`happytube`, click) runs a stage-based pipeline. Each stage reads the
previous stage's markdown files and writes its own, so stages can be rerun per date.
The player shows the trusted pipeline's suitable, cleaned-up videos of currently
approved channels (decision 0010): served live by the local FastAPI app at
`/player/`, and as a static export built in CI from the committed
`stages/trusted/` and deployed to GitHub Pages. A git-tracked channel registry holds candidate channels and their human
and agent reviews; a local FastAPI + htmx review app (`happytube serve`) lets a human
decide on them. The trusted pipeline (`happytube trusted`, decision 0009) fetches
new videos only from human-approved channels, scores them with the shared rubric
and cleans the descriptions of suitable ones; it runs side by side with the legacy
search-by-category pipeline (see [plan](plan.md)).

## Components

Current (`src/happytube/`):

- `cli/` — click commands: legacy `fetch`, `assess`, `enhance`, `report`, `run-all`,
  `status`; `serve`; the `channels` subgroup (`add`, `list`, `show`, `review`,
  `resolve`, `evidence`, `vet`) and the `trusted` subgroup (`fetch`, `assess`,
  `enhance`, `run`, `status`); `--json` for agents.
- `claude.py` — the one Claude call shape shared by vet and the trusted pipeline:
  `MODEL` (Opus 5.5), effort, structured output into a pydantic type, server-side
  refusal fallback, token counting, `estimate_usd`, and the error split
  (`ClaudeStoppingError` for key/permission/credit, `ClaudeCallError` otherwise).
- `trusted/` — the trusted pipeline (decision 0009). `stages.py`: `TrustedStage`
  (dirs under `stages/trusted/`, the seen-id scan) and `status_counts`. `fetch.py`:
  approved channels → uploads + `UUSH` Shorts + `videos.list` → new long-form
  files; `FetchRun` stops on quota / bad key like `collect.py`. `assess.py`: one
  call per channel batch, `id_mismatch` check, `is_suitable` in code. `enhance.py`:
  one call per suitable video. `runs.py`: `ItemRun` / `run_items`, the shared run
  loop (stopping error, dry run, client made only when there is work) behind the
  `TrustedClient` protocol. `player.py`: the player's selection rule
  (`select_videos`, pure: suitable + enhanced + channel approved now, fields from
  assess, newest first), the forgiving file reader (`read_stage`, bad files skipped
  with a warning) and `player_videos`, shared by `/player/videos.json` and the
  export (decision 0010).
- `channels/` — channel registry: `Channel`, `Review` and `Evidence` models and
  `ChannelStore` (files under `channels/`). Status is derived from the latest human
  approve/reject; agent reviews never change it; a rejected channel is the blocklist
  entry. `evidence.py` builds snapshots from API responses; `collect.py` runs
  resolve / evidence over many channels and stops on quota or a rejected key.
  `vet.py` holds the pure vetting parts (flags, prompt, verdict rule, report);
  `vet_run.py` the vet run behind a `VetClient` protocol (on `claude.py`), which
  stops on a rejected key, missing permission or no credit.
- `review/` — local review UI (decision 0007): `create_app(store, …)` builds a
  FastAPI app over one `ChannelStore` (no global app, no cache, re-read per
  request). Queue (`queue.py`: pure `queue_sections` — channels without a human
  review first, flagged or unresolved on top, then by latest vet verdict), channel
  page (latest evidence, latest vet from its frontmatter, all reviews) and a review
  form that writes a `role: human` `Review` via `ChannelStore.add_review`, the same
  record as `channels review`. Jinja templates (autoescaped) with htmx partials
  (queue table; reviews section + out-of-band status badge), plain GET/POST
  fallbacks. A middleware refuses non-loopback `Host` headers (DNS rebinding) and
  cross-site POSTs by `Origin` / `Sec-Fetch-Site` (CSRF). htmx is vendored. The
  same app serves the player: `/player/` (static page from `web/static/`) and
  `/player/videos.json` (live selection from `--stages-dir`).
- `rubric.py` — the calm/happy rubric (`RUBRIC_VERSION`), video flags, `VideoScore`,
  `is_suitable` and `id_mismatch`, shared by channel vetting and trusted assess.
- `youtube.py` — small YouTube Data API client (handle resolve, channels,
  playlistItems, videos): injectable HTTP getter, 50-id batching, quota count,
  errors that never contain the key.
- `stages/` — legacy: `fetch` (YouTube Data API search), `assess` (Claude happiness score
  1–5), `enhance` (Claude rewrites descriptions of videos scoring ≥ threshold),
  `report` (HTML report + parquet exports).
- `models/` — `MarkdownFile` (YAML frontmatter + body), `Video` (pydantic).
- `config/` — pydantic settings from `.env`; YAML config from `config/base/`.
- `web/` — the player page (`static/`) and `export.py` (`videos.json` for Pages;
  exits ≠ 0 when `stages/trusted/` or the registry is missing).
- `videos.py`, `prompts.py`, `utils/` — legacy YouTube search for fetch, prompt
  texts, helpers.

## Data

- `stages/<stage>/YYYY-MM-DD/video_<id>.md` — legacy: one markdown file per video
  per stage.
- `stages/trusted/{fetch,assess,enhance}/YYYY-MM-DD/<id>.md` — trusted pipeline:
  fetch frontmatter (channel, published, duration, `shorts_source`), assess adds
  calm/happy/flags/note/`suitable`/model/`rubric_version`, enhance adds
  `enhanced_description` (suitable videos only). Tracked in git: it is the
  player's deployed data (0010); other `stages/` dirs are git-ignored.
- `stages/report/YYYY-MM-DD.html`, `parquet/<stage>/by-run-date/*.parquet`.
- `config/base/*.yaml` — app, prompts, YouTube search settings.
- `data/fetched/` (git-ignored) — legacy raw search JSON (`videos.py` still writes
  it; nothing reads it).
- `channels/<slug>/channel.yaml` and `channels/<slug>/reviews/<UTC stamp>-<reviewer>.yaml`
  — registry and append-only review records in git (decisions 0002, 0003).
- `channels/<slug>/evidence/<UTC stamp>.yaml` — append-only evidence snapshots:
  resolved channel, stats, recent uploads with durations and Shorts flag (`UUSH`
  playlist membership, duration fallback; 0004).
- `channels/<slug>/vet/<UTC stamp>.md` — append-only vet reports: YAML frontmatter
  (verdict, flags, channel and per-video calm/happy scores, tokens) and a markdown
  body for people (0005).

## Flows

- **Daily (legacy, default of `scripts/daily_run.sh`):** `happytube run-all` →
  fetch → assess → enhance → report.
- **Daily (trusted, `HAPPYTUBE_PIPELINE=trusted scripts/daily_run.sh`):**
  `happytube trusted run` → fetch approved channels' new long-form videos (~3
  units per channel, skip any seen before) → assess per channel batch with the
  rubric (Opus 5.5) → enhance suitable ones. Assess and enhance take everything
  still pending up to the date, so a failed day's videos are picked up the next
  day. A per-channel / per-batch failure exits ≠ 0 after the chain finishes; a
  quota or key stop ends the chain; rerun is idempotent.
- **Player:** `happytube serve` → `/player/` (live), or a push of
  `stages/trusted/` / `channels/` to `main` → CI `python -m happytube.web.export`
  → GitHub Pages. With `HAPPYTUBE_PUSH=1` the trusted daily run commits and pushes
  `stages/trusted/` itself.
- **Evidence:** `channels resolve` (handle → channel id, once) → `channels evidence`
  (stats + latest 50 uploads + `UUSH` Shorts ids, ~3 API units per channel) →
  snapshot in git.
- **Vetting:** `channels vet` → Claude Opus 5.5 judges the latest snapshot (identity,
  long-form videos only) → vet report + agent review (status unchanged). Skipped
  when the latest vet already used the latest snapshot.
- **Review:** `happytube serve` → queue → channel page → approve / reject / unsure →
  review file in `channels/<slug>/reviews/` (status derived as for the CLI) → the
  user commits and pushes.
- **Channel to video:** add candidate channel → collect evidence → agent vets →
  human approves in the web UI or CLI → `trusted fetch` reads only approved
  channels → the agent gates each video (decision 0008).
- **Planned:** video spot-checks (5c).
