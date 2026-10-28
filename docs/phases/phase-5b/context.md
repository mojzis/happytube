# Phase 5b — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-5b-trusted-player`, base `89398db`
(main after phase 5a). Plan: `docs/plan.md` (5b row). Principles:
`docs/constitution.md`. Decisions: 0006 (FastAPI + htmx), 0007 (review UI local),
0008 (channel approval = source, agents gate videos), 0009 (trusted pipeline).
Phase 5a record: `docs/phases/phase-5a/`. Process lessons: `docs/process-learnings.md`.

## Goal

The player (local and the GitHub Pages export) shows the trusted pipeline's output:
suitable videos from approved channels, with their cleaned descriptions. The Flask
player is replaced by routes in the existing FastAPI app; `flask` is dropped. The
legacy `data/fetched/` reader goes.

## Decisions settled (user, 2026-10-28)

Record in `docs/decisions/0010-trusted-player.md` (accepted).

- **Deployed data = committed `stages/trusted/`.** The stage files are tracked in
  git (public repo; public YouTube metadata only — no keys, no personal data). The
  Pages workflow builds `videos.json` from them in CI and auto-deploys again on push
  to `main`. `videos.json` is a build product: untracked, git-ignored.
- **Shown: every suitable video ever assessed, newest `published_at` first.** No
  window, no grouping.
- **Hide until enhanced.** A suitable video with no enhance file is not shown.

## Settled by the orchestrator (defaults; dev may argue in `deviations`)

- **Selection rule** (one pure function, used by both the live route and the
  export): a video is shown iff
  1. it has an assess file with `suitable: true`,
  2. it has an enhance file with a non-empty `enhanced_description`,
  3. its channel (`channel_slug`) is **currently `approved`** in the registry
     (`derive_status`). A channel approved at fetch time and rejected later
     (blocklist, decision 0003) disappears from the player — safety beats history.
     Unknown slug → not shown.
- **Field sources:** title, channel name/slug, published_at, duration_s,
  calm/happy/suitable come from the **assess** file; only `enhanced_description`
  comes from the **enhance** file (a re-scored video can keep an enhance file with
  stale scores — 5a lesson). Join by `video_id`, across date dirs (a video's assess
  and enhance live under its fetch date, but don't rely on equal dates).
- Duplicate `video_id` across date dirs (shouldn't happen; `--force` rewrites in
  place): take the latest date dir, deterministic. Unreadable / malformed stage file:
  skip with a warning naming the path, never crash the export, never show it.
- **One app.** The player joins the review app (`review/app.py` `create_app`), served
  by `happytube serve`: `GET /player/` serves the static player page, `GET
  /player/videos.json` returns the selection live from `stages/trusted/` + registry.
  `/` keeps redirecting to `/channels`. The Host / Origin guard covers the player
  too (it's local). The app gets the stages root the same way the CLI does (cwd
  `stages/` default; an option/param for tests — dev picks, mirror `--channels-dir`
  style, don't invent a second convention).
- **One player.js code path:** it fetches `videos.json` relative to the page; works
  under `/player/` locally and at the Pages root. Drop the `/api/videos` probe +
  fallback. `templates/player.html` (Flask duplicate of `static/index.html`) goes.
- **JSON shape** (one record per video, a pydantic model or TypedDict, not ad hoc
  dicts): `video_id`, `title`, `channel_name`, `channel_slug`, `published_at`,
  `duration_s`, `description` (= `enhanced_description`). No scores in the public
  JSON (not needed by the player; keep it minimal). player.js updated to the names.
- **Export:** `python -m happytube.web.export` stays the entry (workflow uses it),
  now reading `stages/trusted/` + `channels/`; writes `static/videos.json`; logs the
  count; exits ≠ 0 if the stages dir is missing (fail loudly — a CI export of 0
  videos because of a wrong path must not deploy silently). 0 videos with the dir
  present is exit 0 with a warning.
- **Flask gone:** `web/server.py`, `templates/player.html` deleted; `flask` removed
  from `pyproject.toml` + `uv.lock`. Legacy `export.load_videos_from_data_dir` /
  `extract_video_info` deleted. `LEGACY_FETCHED_DIR` stays only if `videos.py`
  (legacy search fetch) still writes it — check, say what you did.
- **Git:** `.gitignore` ignores `/stages/*` except `/stages/trusted/` (legacy stage
  dirs never get committed by accident) and `src/happytube/web/static/videos.json`
  (`git rm --cached` it). Nothing commits real stage data in this phase except as
  noted under "Real data" below.
- **`scripts/daily_run.sh`:** with `HAPPYTUBE_PIPELINE=trusted` and opt-in
  `HAPPYTUBE_PUSH=1`, after a run that exited 0 *or* ≠ 0 with files written: `git add
  stages/trusted` → commit (`trusted run YYYY-MM-DD`) → `git push`; no commit when
  nothing changed. Default off (cron is not set up yet; the user decides).
  Never `git add -A`. A failed push is a logged error and exit ≠ 0.
- **Deploy workflow:** re-add `push: branches: [main]` with `paths:` covering
  `stages/trusted/**`, `channels/**`, `src/happytube/web/**`, the workflow file.
  Export reads from the repo root (CI cwd). `deploy_web.sh`: update to the new
  export or delete it if it only duplicates the workflow — dev judges, says why.
- Player UI look and behaviour otherwise unchanged (grandma-specific UI is not this
  phase). Fix only what the field rename touches.

## Failure scenarios dev must design for (5a lesson: list them up front)

- Assess suitable, enhance missing (enhance failed / not run yet) → hidden.
- Re-scored unsuitable after an earlier enhance → `trusted assess` already deletes
  the enhance file; even if one lingers, assess `suitable: false` hides it.
- Re-scored suitable after an earlier unsuitable → enhance file may carry stale
  scores → scores ignored from enhance.
- Channel rejected after videos shown → hidden on next export / page load.
- Stages dir missing (CI checkout path wrong) → export exit ≠ 0.
- Malformed frontmatter / missing keys in one file → that file skipped, warning,
  others shown.
- Empty selection → page shows the existing "No videos" message, not an error.

## Tests (no network)

Pure selection function: table test over the rules above (suitable/unsuitable,
enhance missing/empty, stale enhance scores ignored, channel approved / rejected /
candidate / unknown, duplicate ids, malformed file, sort order). FastAPI
`TestClient`: `/player/` 200 HTML, `/player/videos.json` shape, Host guard applies.
Export: writes file, count, missing dir → exit ≠ 0, empty → exit 0 + warning. No
remaining `flask` import anywhere (`import happytube.web` works without flask).
Existing review-app tests untouched in behaviour.

Baseline: 456 passed, coverage 82%, `uv run poe check` green. After: `poe check`
green; `uv run poe typecheck` before each commit of a multi-commit step.

## Real data (dev, exploratory)

Scratch cwd under `/tmp/claude-1000/`, copy `channels/`. Fetch the approved
channels `--since-days 14` (YTKEY, ~35 units), assess + enhance **at most two
channels** (Anthropic cap ~$0.50; probe one batch first; credential failure →
stop and report). Run the export and `happytube serve` against that cwd; load
`/player/videos.json` and `/player/` (curl is enough), report count, two records,
and that a hidden case (unsuitable / not enhanced) is really absent. Commit nothing
from scratch. The first real `stages/trusted/` commit to the repo is the user's
call after merge.

## Docs

- `docs/decisions/0010-trusted-player.md` (accepted): data source, selection rule,
  hide-until-enhanced, channel-status filter, one app, Flask dropped.
- CLAUDE.md: Web player section (`happytube serve` → `/player/`, export, Pages
  data source), stack (no flask), known-gap note removed, storage tree
  (`stages/trusted/` tracked), key modules.
- `DEPLOYMENT.md` (root and `src/happytube/web/` — dedupe if they're copies; say
  what you did): new data source, push trigger back, enabling Pages is a one-time
  user step (Settings → Pages → GitHub Actions; not enabled today).
- `docs/architecture.md`: player reads trusted stages.
- Don't touch `docs/plan.md`, `docs/next-session.md`, `docs/phases/` (except
  committing `docs/phases/phase-5b/` as-is first).

## Existing code to know

- `trusted/stages.py`: `TrustedStage` (`files`, `load`, `load_until`,
  `video_ids`), `video_id_of`, `status_counts` — reuse for reading; don't add a
  second file-walking style.
- `models/markdown.py` `MarkdownFile`; `channels/store.py` `ChannelStore`,
  `derive_status`, `ChannelEntry.status`.
- `review/app.py` `create_app`, guard, `_Pages`, static mount; `cli/serve.py`;
  `cli/common.py` `channels_dir_option`.
- `web/export.py`, `web/server.py`, `web/static/{index.html,player.js,styles.css}`,
  `web/templates/player.html`; `.github/workflows/deploy.yml`;
  `scripts/deploy_web.sh`, `scripts/daily_run.sh`; `paths.py`.

## Tooling gotchas

- Parallel agents: own worktree via `git worktree add --detach <path>
  phase-5b-trusted-player`, `uv sync` there, remove + prune after.
- Don't run pytest concurrently in one checkout (shared `.coverage`).
- madoqua hook on staged .py only; never `--no-verify` / `MADOQUA_SKIP`. Any commit
  touching `pyproject.toml` / `uv.lock` runs the full suite.
- Staged-only `ty` misses cross-file breakage: `uv run poe typecheck` per commit.
- `tyf` index stale after hook reformat: `uv run tyf daemon restart`.
- zsh doesn't word-split `$H`: use a shell function for repeated CLI calls.
- Keys: `set -a; . /home/matous/git/happytube/.env; set +a`; never print them.
