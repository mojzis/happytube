# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HappyTube finds calm, happy YouTube videos for vulnerable viewers (first audience: a
grandmother with early dementia). Today it fetches videos from the YouTube Data API,
scores happiness with Claude, improves descriptions of the happy ones and plays them
in a recommendation-free player. Next it moves to a human-approved allowlist of
trusted channels (see Project plan).

## Project plan

- `docs/plan.md` — goal and phases 0–5 (trusted-channels revival).
- `docs/next-session.md` — where we are and the next step. Read it first.
- `docs/constitution.md`, `docs/architecture.md`, `docs/decisions/` — purpose,
  structure and decision records. `docs/research/` holds notes, incl. the historical
  `modernization-plan.md`.

## Commands

- `uv run poe check` — run lint (incl. ruff `S` security rules), typecheck, vulns, test-lint, clones, then tests
- `uv run poe fix` — auto-format and fix lint issues
- `uv run poe test` — run tests only
- `uv run poe check-all` — run all checks including dead-code and unused-deps

CI (`.github/workflows/ci.yml`) runs format, lint, ty, zorilla, biston and pytest on
every PR and push to `main`; pysentry is advisory.

### HappyTube CLI

```bash
happytube run-all --category Music --max-videos 50     # full pipeline
happytube fetch --category Music --max-videos 50 --date 2025-11-16
happytube assess --date 2025-11-16
happytube enhance --threshold 3 --date 2025-11-16
happytube report --date 2025-11-16 --days-back 7
happytube status --date 2025-11-16
happytube --help                                       # or <command> --help
```

Run via `uv run happytube …`. Daily automation: `./scripts/daily_run.sh` (cron-ready).

### Channel registry

```bash
happytube channels list [--status candidate|approved|rejected] [--kind zoo] \
    [--language cs] [--needs-human-review] [--json]
happytube channels show bbc-earth [--json]
happytube channels add "Zoo Zlín" --kind zoo --language cs [--handle @…] \
    [--channel-id UC…] [--url …] [--slug …] [--notes …] --added-by matous [--json]
happytube channels review bbc-earth --reviewer matous --role human \
    --verdict approve|reject|unsure [--notes …] [--json]
happytube channels resolve [SLUG…] [--all] [--verify] [--json]  # needs YTKEY
happytube channels evidence [SLUG…] [--all] [--max-videos 50] [--json]  # needs YTKEY
happytube channels vet [SLUG…] [--all] [--force] [--dry-run] [--json]  # needs ANTHROPIC_API_KEY
```

Only `resolve` and `evidence` call YouTube (`YTKEY` only, no Anthropic key); the rest
except `vet` need no keys. `resolve` fills a null `channel_id` from the handle (`forHandle`, 1
unit) and skips channels that have one; `--verify` re-checks those, and a different
id is a `mismatch`, never overwritten. `evidence` resolves where needed, then writes
an append-only snapshot per channel (~3 units each; Shorts = membership of the
channel's `UUSH…` playlist, duration fallback, `shorts_source` says which); both
report `quota_units`. A used-up quota or rejected key stops the run, keeping what was
written; channels never reached are `not_fetched`. `show` prints the latest snapshot's "resolved to" title — check it, handles
can hit look-alike channels (decision 0004). `--json` prints plain JSON to stdout
(errors go to stderr, exit ≠ 0) — agents use that. Registry dir: `--channels-dir` / `HAPPYTUBE_CHANNELS_DIR`,
default `channels/` at the repo root. Status is derived: the latest *human*
approve/reject decides; agent reviews never change it; `rejected` is the blocklist
(decision 0003).

`vet` (decision 0005) is the only command calling Claude; it needs only
`ANTHROPIC_API_KEY` (`--dry-run` needs none and writes nothing). Claude Opus 5.5
judges the latest snapshot — identity, plus calm/happy per long-form video (Shorts
are never scored) — and `vet` writes `vet/<stamp>.md` and an agent review
(`claude-vet`, status unchanged). Flags `inactive`, `mostly_shorts`, `identity_doubt`
turn a model approve into `unsure`; `unresolved` and human-`rejected` channels are
skipped without a call. A channel whose latest vet used its latest snapshot is
`skipped_current` unless `--force` (also needed after a prompt or model change). It
reports tokens and an estimated cost (at Opus 5.5 rates, failed calls included); a
rejected key, missing permission or no credit stops the run (`not_vetted` for the
rest).

### Review UI

```bash
happytube serve [--host 127.0.0.1] [--port 8000] [--channels-dir PATH] [--reviewer NAME]
```

Local FastAPI + htmx page (decision 0007) at `http://127.0.0.1:8000/channels`: a
queue (channels without a human review first, flagged/unresolved on top), a detail
page (channel, latest evidence, latest vet, all reviews) and an approve / reject /
unsure form. It needs **no API keys** and writes the same review files as
`channels review` (always `role: human`) into the registry — commit and push them
yourself; the app runs no git. `--channels-dir` is the same option and env as the
`channels` group; `--reviewer` / `HAPPYTUBE_REVIEWER` prefills the form when the
browser has no remembered name. Only loopback `Host` headers and same-origin POSTs
are accepted; a non-loopback `--host` (LAN IPv4/IPv6) warns (no auth), a wildcard
`0.0.0.0` / `::` is refused. htmx is vendored in
`review/static/`, no external JS/CSS.

### Web player

```bash
uv run python -m happytube.web.server   # Flask dev server, http://127.0.0.1:5000
uv run python -m happytube.web.export   # static videos.json for GitHub Pages
./scripts/deploy_web.sh                 # interactive export + deploy helper
```

`.github/workflows/deploy.yml` builds and deploys `src/happytube/web/static` to GitHub
Pages — manual trigger only for now; see [DEPLOYMENT.md](DEPLOYMENT.md). Known gap: the player and export read
legacy raw JSON from `data/fetched/`, which nothing writes any more (the stages write
`stages/`), so the export currently yields 0 videos.

## Stack

uv, ruff (lint/format), ty (type check), pytest, poethepoet (task runner). Python
>=3.12, src layout (`src/happytube/`), hatchling build. Runtime: click, rich, pandas,
pyarrow, pydantic(-settings), anthropic, requests, flask, jinja2, pyyaml, fastapi,
uvicorn, python-multipart (httpx in dev, for `TestClient`).

## Toolbox

The [aesop toolbox](https://mojzis.github.io/aesop/llms.txt) is wired in here. Every
tool explains itself — run `uv run <tool> guide` before reaching for flags, and
`uv run <tool> guide tune` before changing a threshold. Call them as `uv run <tool>`;
ty-find's binary is `tyf`.

### On every commit

**madoqua** is the only commit hook (`hooks/pre-commit`, `core.hooksPath=hooks`). It
acts on staged `.py`/`.pyi` files only — a commit without one is a silent no-op, not a
verified hook.

| phase | steps |
| --- | --- |
| fix (rewrites and re-stages) | `ruff check --fix`, `ruff format` |
| check (blocks) | `ruff check`, `ty check`, `biston scan --focus-args`, `zorilla check`, `gerenuk run` |

Whole hook runs in ~1–2 s here, mostly gerenuk (`uv run madoqua stats` for current
numbers). Don't commit with `--no-verify` or `MADOQUA_SKIP` to get past a
check that is telling the truth.

Two changes from the hook this replaced:

- `ty check` was repo-wide, it is now **staged-only**. Repo-wide diagnostics no longer
  block a clean commit, but a file with existing diagnostics blocks the first commit
  that touches it. `uv run poe typecheck` still checks everything.
- **bandit is gone.** Security checks are ruff's flake8-bandit `S` rules, so they now run
  on commit via `ruff check`; `tests/**` ignores S101/S105/S106 in `per-file-ignores`.

### Every now and then

- `uv run pycoati . --format pretty` — scores every test for suspicion and prints a
  remediation ladder. Run it before a test-cleanup session. Never put it in a hook or
  CI: it runs the suite three times. It needs pytest-cov or coverage is silently null.

### On demand — instead of grep

- `uv run tyf find <symbol>` / `tyf refs` / `tyf list <file>` / `tyf calls` — type-aware
  symbol lookup. **Use these instead of grep** for definitions and references; grep
  cannot tell a definition from a string that happens to match.
- `uv run gerenuk audit <file>` — lists symbols in a module that nothing references.
- `uv run gerenuk impacted-tests` — which tests a working-tree diff reaches, and why.

### Fresh clone

```
uv sync
uv run madoqua install    # once; core.hooksPath is local config, not tracked
```

`.python-version` pins 3.12 so the local venv matches CI. A new `git worktree` has no
`.venv`: run `uv sync` in it before committing, or the madoqua hook blocks with
"no virtualenv".

### Refreshing the toolbox

```
uv lock --refresh --upgrade-package madoqua --upgrade-package gerenuk --upgrade-package biston --upgrade-package zorilla --upgrade-package pycoati --upgrade-package ty-find && uv sync
```

`--refresh` matters: without it uv may serve a cached index and miss a release
published minutes ago.

## Architecture

### Stage-based pipeline

```
Stage 1: FETCH    → stages/fetch/YYYY-MM-DD/*.md
Stage 2: ASSESS   → stages/assess/YYYY-MM-DD/*.md  (with happiness_score)
Stage 3: ENHANCE  → stages/enhance/YYYY-MM-DD/*.md (with enhanced_description)
Stage 4: REPORT   → stages/report/YYYY-MM-DD.html + parquet exports
```

Each stage reads the previous stage's markdown files (YAML frontmatter + body) and can
be rerun for a given `--date`. Paths are relative to the working directory, so run
from the repo root.

1. **Fetch** (`stages/fetch.py`) — YouTube Data API v3 search (`videos.py`), search
   params from `config/base/youtube.yaml`; one markdown file per video.
2. **Assess** (`stages/assess.py`) — sends id/title/description to Claude as CSV, gets
   happiness 1–5 plus reasoning (prompts in `prompts.py`).
3. **Enhance** (`stages/enhance.py`) — for happiness ≥ threshold (default 3), Claude
   rewrites the description without clickbait, spam and promotion.
4. **Report** (`stages/report.py`) — HTML report from `templates/daily_report.html`
   (Jinja, autoescaped) and parquet exports under `parquet/`.
5. **Web player** (`web/`) — Flask app + static export; YouTube embed with
   recommendations disabled.

### Key modules

- `cli/commands.py` — click entry point `happytube`; `cli/channels.py` — the
  `channels` subgroup; `cli/serve.py` — `happytube serve`.
- `channels/` — registry `models.py` (`Channel`, `Review`, `Evidence`, `slugify`),
  `store.py` (`ChannelStore`, `derive_status`), `evidence.py` (pure API → `Evidence`
  builder, Shorts by `UUSH` ids or duration), `collect.py` (resolve / evidence
  runs), `vet.py` (pure vetting: flags, prompt, verdict rule, report) and
  `vet_run.py` (`AnthropicVetClient` behind a `VetClient` protocol, `vet_channels`);
  the CLI and the future web UI share them.
- `review/` — local review UI: `app.py` (`create_app(store, default_reviewer=…)`
  factory, routes, Host/Origin guard), `queue.py` (pure `queue_sections` sort),
  `templates/`, `static/` (vendored htmx, `review.css`); reads and writes only
  through `ChannelStore`.
- `rubric.py` — calm/happy rubric, video flags, `VideoScore`, `is_suitable`; shared
  by channel vetting and (phase 5) video assessment.
- `youtube.py` — `YouTubeClient` (injectable getter, quota count, key-free errors,
  `QuotaExceededError` / `InvalidKeyError`); `videos.py` — legacy search for fetch.
- `config/settings.py` (pydantic settings from `.env`), `config/config_manager.py`
  (YAML from `config/base/`).
- `models/markdown.py` (`MarkdownFile`), `models/video.py` (`Video`, parquet export).
- `utils/` — text-script detection, `utc_now_iso()`, `first_text()` for Claude
  responses, logging setup. `paths.py` — `PROJECT_ROOT`.

### Storage Structure
```
# Stage-based data (new architecture)
stages/
├── fetch/              # Fetched videos
│   └── YYYY-MM-DD/
│       ├── video_abc123.md
│       └── video_def456.md
├── assess/             # Assessed videos (with happiness scores)
│   └── YYYY-MM-DD/
│       └── video_abc123.md
├── enhance/            # Enhanced videos (with improved descriptions)
│   └── YYYY-MM-DD/
│       └── video_abc123.md
└── report/             # Generated reports
    └── YYYY-MM-DD.html

# Channel registry (git-tracked, decisions 0003, 0004, 0005)
channels/
└── bbc-earth/
    ├── channel.yaml                    # metadata by `channels add`; resolve fills a null channel_id
    ├── reviews/                        # append-only, one file per review
    │   └── 20261028T101500Z-matous.yaml
    ├── evidence/                       # append-only API snapshots (stats + recent uploads)
    │   └── 20261028T185312Z.yaml
    └── vet/                            # append-only agent vet reports (frontmatter + markdown)
        └── 20261028T201500Z.md

# Analytics exports
parquet/
├── fetch/
│   └── by-run-date/
│       └── YYYY-MM-DD_last_7_days.parquet
├── assess/
└── enhance/

# Configuration
config/
├── base/
│   ├── app.yaml        # Main app config
│   ├── prompts.yaml    # Claude prompt definitions
│   └── youtube.yaml    # YouTube search configs
└── experiments/        # Override configs for testing

# Templates
templates/
├── base.html
└── daily_report.html

# Logs
logs/
├── YYYY-MM-DD.log     # Daily pipeline logs
└── cron.log           # Cron job logs

# Legacy data (git-ignored; the web player still reads data/fetched/)
data/
├── categories.json      # YouTube category definitions
└── fetched/
    ├── lists/          # Search results
    └── videos/         # Video details

# Review UI (happytube serve)
src/happytube/review/
├── app.py              # FastAPI app factory, routes, Host/Origin guard
├── queue.py            # pure queue order (queue_sections)
├── templates/          # base, queue, channel + partials, error (Jinja, autoescaped)
└── static/             # htmx.min.js (vendored 2.0.11), review.js (htmx errors), review.css

# Web player
src/happytube/web/
├── server.py           # Flask backend (dev mode)
├── export.py           # Static export script
├── static/             # Static assets & deployment files
│   ├── index.html      # Static version for deployment
│   ├── player.js       # Player logic (works in both modes)
│   ├── styles.css      # Styling
│   └── videos.json     # Generated by export.py
└── templates/          # Flask templates
```

## Configuration

### Environment Variables

Required environment variables in `.env`:

```bash
# API Keys (required)
YTKEY=your_youtube_api_key              # YouTube Data API v3 key
ANTHROPIC_API_KEY=your_anthropic_key    # Claude API key (assess, enhance, channels vet)
HAPPYTUBE_REVIEWER=matous               # optional: prefills the review UI's reviewer

# Optional settings
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENVIRONMENT=development                 # development or production
```

### Configuration Files

Configuration files are stored in `config/base/` (if they exist):

- **app.yaml**: Main application settings
  - Stage paths
  - Processing thresholds
  - Default configurations

- **prompts.yaml**: Claude prompt definitions
  - Prompt templates
  - Model configurations
  - Token limits

- **youtube.yaml**: YouTube search configurations
  - Category-specific search params
  - Region codes
  - Video duration filters

## Troubleshooting

- Missing credentials: check `.env` has `YTKEY` and `ANTHROPIC_API_KEY`.
- Stage failed: read `logs/YYYY-MM-DD.log`, inspect `stages/<stage>/<date>/`, fix,
  rerun just that stage.
- Fetch returns 0 videos: YouTube quota (10,000 units/day), key validity, category.
- Debug logging: `LOG_LEVEL=DEBUG uv run happytube run-all`.

## Notes

- ty is in beta — may produce false positives. Prefer `# ty: ignore[rule]` over blanket suppression.
- The commit hook auto-fixes and restages files. Only blocks on unfixable issues.
- Don't run pytest (or `poe check`) concurrently in one checkout: the runs share
  `.coverage` and the combine step can fail with `table coverage_schema already exists`.
- gerenuk diffs the **working tree** against `origin/main`, so unstaged edits count, and
  any commit touching `pyproject.toml` or `uv.lock` runs the full suite. `--base HEAD`
  scopes it to the commit itself.
- ty-find's index goes stale after the hook's `ruff format` rewrites a file. The tell is
  `tyf refs <sym>` listing only the definition, or gerenuk reporting `selected` with an
  empty list. `uv run tyf daemon restart` fixes it.
