# Phase 5c — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-5c-video-spot-checks`, base
`61a04a8` (main after phase 5b + first trusted data). Plan: `docs/plan.md` (5c row).
Principles: `docs/constitution.md`. Decisions: 0003 (registry layout, derived
status), 0007 (review UI local), 0008 (channel approval = source, agents gate
videos), 0009 (trusted pipeline), 0010 (trusted player). Phase 5b record:
`docs/phases/phase-5b/`. Process lessons: `docs/process-learnings.md`.

## Goal

A human can spot-check the trusted pipeline's videos in the review UI (and the
CLI): watch, give a verdict, see how often the agent agrees. A human
"unsuitable" also hides the video from the player and the Pages export.

## Decisions settled (user, 2026-10-28)

Record in `docs/decisions/0011-video-spot-checks.md` (accepted; amends 0008 and the
0010 selection rule).

- **Location:** top-level `video-reviews/<video_id>/<stamp>-<reviewer>.yaml`,
  append-only, one file per review, git-tracked (public repo: notes are public —
  the form says so). Separate from `channels/` and from `stages/`.
- **Record:** verdict `suitable | unsuitable | unsure`, optional rubric flags, a
  note, how much was watched (`full | part | title`).
- **Queue:** all assessed trusted videos. Unreviewed videos currently shown in the
  player first (false positives hurt her), then the other unreviewed ones (agent
  misses, for tuning), then reviewed. An agreement summary on the queue page.
- **Override:** the latest *human* verdict `unsuitable` hides the video from the
  player (live route + export). `suitable` never shows a video the agent scored
  unsuitable; `unsure` changes nothing.

## Settled by the orchestrator (defaults; dev may argue in `deviations`)

- **Model** `VideoReview` (pydantic, `extra="forbid"`, same style as `Review`):
  `reviewer`, `role` (`human | agent`, reuse `Role`), `verdict`, `flags:
  list[Flag]` (rubric `Flag`), `watched`, `notes: str | None`, `created_at` (UTC,
  `Z`), plus a snapshot of what the human compared against, taken from the assess
  file at review time: `agent_suitable: bool`, `rubric_version: int`,
  `assessed_at`. (Assess can be redone with `--force`; stats must compare against
  the call the human actually saw.) The video id is the directory, not a field.
- **Status derived, like channels (0003):** the latest human review decides; agent
  reviews are stored but never hide and never count in the agreement summary.
- **Store:** one module (e.g. `trusted/video_reviews.py`: `VideoReviewStore`,
  `latest_human_verdict`/`hidden_ids`), file naming + collision handling shared with
  `channels/store.py` (extract a helper rather than copy — zorilla checks clones).
  Video ids validated with `is_video_id` before any path is built (no traversal).
- **Dir option:** `--video-reviews-dir` / `HAPPYTUBE_VIDEO_REVIEWS_DIR`, default
  `video-reviews/` at the repo root — mirror `channels_dir_option`, don't invent a
  second convention. On `serve`, the export and the new CLI group.
- **Dir always exists:** commit `video-reviews/README.md` (what it is, file format,
  that notes are public). A **missing** dir in the export / serve is an error (exit
  1 / startup warning + route error), same reason as 5b's missing stages dir: a
  wrong path in CI must not silently show videos a human hid. An empty dir = no
  reviews.
- **Selection rule** (`select_videos`, one pure function, still shared by route
  and export) gains rule 4: not hidden by a human. An unreadable / invalid review
  file for a video → that video hidden, warning naming the path (safety, as with
  unreadable channel reviews in 5b). Public JSON shape unchanged.
- **Review UI:** `GET /videos` (queue, three sections as above, agreement summary
  on top: latest human verdict × agent `suitable` at review time, counts, and a
  "disagreements" filter or section), `GET /videos/{video_id}` (title, channel,
  published, duration, agent calm/happy/flags/note/suitable/rubric_version, the
  original description, the enhanced description if any, whether it's shown in
  the player now, an embedded YouTube player like the player page uses + a link
  out, all reviews, the form), `POST /videos/{video_id}/reviews` (always `role:
  human`, htmx partial swap like the channel form, reviewer cookie/prefill as for
  channels). Unknown / non-assessed id → 404; invalid id → 404 without touching the
  filesystem. Nav: Channels · Videos · Player in `base.html`. Host/Origin guard
  covers the new routes. No external JS/CSS (YouTube iframe is the one embed, as in
  the player). Form copy states 0008/0011: spot-checks measure the agent;
  "unsuitable" also hides the video.
- **CLI:** `happytube videos` group mirroring `channels`: `list [--section
  shown|unreviewed|reviewed|disagree] [--json]`, `show ID [--json]`, `review ID
  --reviewer --role --verdict [--flag …] [--watched] [--notes] [--json]`, `stats
  [--json]`. No API keys. Check the name `videos` is free (legacy top-level
  commands); if not, pick another and say why.
- **Deploy:** `deploy.yml` `paths:` add `video-reviews/**`; export reads it from
  the repo root. `scripts/daily_run.sh` does **not** commit `video-reviews/` (the
  human commits their reviews, as with channel reviews).
- **Not in scope:** rubric changes, rescoring, grandma-facing UI, sampling.

## Failure scenarios dev must design for

- Human unsuitable on a shown video → gone from `/player/videos.json` and the
  export on next request / build.
- Human unsuitable, later human suitable → shown again (if the agent says suitable
  + enhanced + channel approved). Latest human wins; ties on `created_at` broken
  deterministically (filename order).
- Agent review only → no effect on player or stats.
- Human suitable on an agent-unsuitable video → still hidden; counts as a
  disagreement.
- Assess redone after a review (different `suitable`) → stats use the snapshot;
  the detail page shows both the current call and the one reviewed.
- Review dir for an id with no assess file (orphan) → ignored by queue, still
  hides nothing (nothing to show anyway), `videos list` doesn't crash.
- Malformed review YAML → video hidden + warning; queue page still renders (that
  video marked "unreadable review").
- `video-reviews/` missing → export exit 1; serve warns at start, player route and
  `/videos` fail loudly (not empty).
- Invalid video id in a URL / CLI arg (`../x`, wrong length) → 404 / error, no fs
  access.
- Same reviewer, same second, two reviews → no overwrite (collision suffix).

## Tests (no network)

Store round-trip + derived verdict (latest human wins, agents ignored, ties,
malformed file); `select_videos` table extended with rule 4; agreement stats
(snapshot vs current); queue order; routes via `TestClient` (queue, detail, POST
writes a file with `role: human` + snapshot, 404s, Host/Origin guard, htmx partial);
CLI `--json` shapes and exit codes; export with a hiding review and with the dir
missing. Existing tests unchanged in behaviour.

Baseline: 498 passed, coverage 85%, `uv run poe check` green. After: `poe check`
green; `uv run poe typecheck` before each commit of a multi-commit step.

## Real data (dev, exploratory, no paid calls)

Scratch cwd `/tmp/claude-1000/p5c-real`: copy the repo's committed `stages/trusted/`
and `channels/`, make an empty `video-reviews/`. `happytube serve` there; curl
`/videos`, a detail page, POST a review (unsuitable) for one shown video, check it
left `/player/videos.json`; run the export with and without the review. Report
counts and one stored review file. No YouTube or Anthropic calls. Commit nothing
from scratch.

## Docs

- `docs/decisions/0011-video-spot-checks.md` (accepted), and a one-line "amended
  by 0011" note in 0008 and 0010.
- CLAUDE.md: new `videos` CLI section, review UI routes, player selection rule 4,
  storage tree (`video-reviews/`), key modules, deploy paths.
- `DEPLOYMENT.md`, `docs/architecture.md`: video reviews feed the export.
- Don't touch `docs/plan.md`, `docs/next-session.md`, `docs/phases/` (except
  committing `docs/phases/phase-5c/` as-is first).

## Existing code to know

- `channels/models.py` (`Review`, `Role`, `Verdict`, `_as_utc`, `_iso_z`),
  `channels/store.py` (`ChannelStore`, `derive_status`, `_collision_index`,
  `_dump_yaml`, `_load_yaml`, `_load_records`).
- `rubric.py` (`Flag`, `FLAGS`, `is_suitable`, `RUBRIC_VERSION`).
- `trusted/stages.py` (`TrustedStage`, `is_video_id`), `trusted/player.py`
  (`select_videos`, `read_stage`, `channel_statuses`, `player_videos`).
- `review/app.py` (`create_app`, guard, reviewer cookie, `_Pages`), `review/queue.py`,
  `review/templates/` (`queue.html`, `channel.html`, `_review_form.html`,
  `_reviews.html`), `review/static/review.css`.
- `cli/channels.py`, `cli/common.py` (`channels_dir_option`, `stages_dir_option`,
  JSON output helpers), `cli/serve.py`, `web/export.py`, `web/static/player.js`
  (how it embeds YouTube).

## Tooling gotchas

- Parallel agents: own worktree via `git worktree add --detach <path>
  phase-5c-video-spot-checks`, `uv sync` there, remove + prune after.
- Don't run pytest concurrently in one checkout (shared `.coverage`).
- madoqua hook on staged .py only; never `--no-verify` / `MADOQUA_SKIP`. Any commit
  touching `pyproject.toml` / `uv.lock` runs the full suite.
- Staged-only `ty` misses cross-file breakage: `uv run poe typecheck` per commit.
- `tyf` index stale after hook reformat: `uv run tyf daemon restart`.
- zsh doesn't word-split `$H`: use a shell function for repeated CLI calls.
- `pkill -f` from the Bash tool can kill its own shell: kill by pid.
