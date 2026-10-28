# Phase 5a — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-5a-trusted-fetch`, base `e97b73f`
(main after the second round of human reviews). Plan: `docs/plan.md` (phase 5 row,
split below). Principles: `docs/constitution.md`. Decisions: 0004 (evidence, fetch
method), 0005 (vetting), 0008 (channel approval = source, agents gate videos).
Phase 3/4 records: `docs/phases/phase-3/`, `docs/phases/phase-4/`. Process
lessons: `docs/process-learnings.md`.

## Goal

A daily pipeline that pulls new long-form videos **only from approved channels**,
scores each one with the shared calm/happy rubric (Claude Opus 5.5), and rewrites
the descriptions of the suitable ones. Its output is what phase 5b's player will
show. It fails loudly.

## Phase 5 split (user, 2026-10-28)

- **5a (this phase):** trusted fetch + rubric assess + enhance on suitable.
- **5b:** player and static export read the trusted stages; Flask player → the
  FastAPI app; `flask` dropped.
- **5c:** video spot-check queue + video review records in the review UI (format
  and location settled in 5c's context; decision 0008: spot-checks measure the
  agent, they don't gate).

## Decisions settled (user, 2026-10-28)

Record in `docs/decisions/0009-trusted-pipeline.md` (accepted).

- **Side by side with the legacy pipeline.** Legacy `fetch` (YouTube search by
  category), `assess` (happiness 1–5), `enhance`, `report`, `run-all` keep working
  unchanged. The trusted pipeline is a new command group with its own stage dirs.
  No shared stage directory, so the two can never mix.
- **Assess model: Claude Opus 5.5** (`claude-opus-5-5`), same call shape as
  `channels vet` (structured output, effort `medium`, refusal fallback). One model
  constant shared with vet, not a second string.
- **Enhance: kept, gated on `suitable: true`** (the rubric's `is_suitable`, decided
  in code), not on happiness ≥ threshold. Trusted enhance uses the current model,
  not the retired `claude-3-opus-20240229` the legacy stages default to.
- **Video needs no human approval** (0008). Suitable = shown.

## CLI

New group `happytube trusted` (top-level, like `channels`), sharing the
`--channels-dir` option definition with `channels` / `serve` (don't copy it):

```
happytube trusted fetch   [--date D] [--since-days 14] [--max-per-channel 50] [SLUG…] [--json]   # YTKEY
happytube trusted assess  [--date D] [--force] [--dry-run] [--json]                               # ANTHROPIC_API_KEY
happytube trusted enhance [--date D] [--force] [--dry-run] [--json]                               # ANTHROPIC_API_KEY
happytube trusted run     [--date D] [--since-days 14] [--max-per-channel 50] [--json]            # both
happytube trusted status  [--date D] [--json]                                                     # no keys
```

- Each command asks only for the key it uses (phase 3 Q4 lesson: `--dry-run` and
  commands with nothing to do need none).
- `--json`: plain JSON to stdout, errors to stderr, exit ≠ 0 on failure — same
  contract as `channels`.
- `--date` defaults to today (local), same parsing as the legacy commands
  (`parse_date`).
- `SLUG…` on fetch limits to those channels; a named channel that isn't approved
  is an error naming its status, not a silent skip.

## Stage layout

```
stages/trusted/
├── fetch/YYYY-MM-DD/<video_id>.md     # one per new long-form video
├── assess/YYYY-MM-DD/<video_id>.md    # fetch frontmatter + rubric score
└── enhance/YYYY-MM-DD/<video_id>.md   # assess frontmatter + enhanced_description
```

`MarkdownFile` (YAML frontmatter + body), base path `stages/` relative to cwd like
the legacy stages (the `data_root` backlog item is not this phase). Reuse `Stage`
for dirs; the trusted stages are new classes, not flags on the legacy ones.

Fetch frontmatter: `video_id`, `title`, `channel_slug`, `channel_id`,
`channel_name`, `languages` (from the channel), `published_at`, `duration_s`,
`shorts_source` (`uush` | `duration`), `fetched_at`, `stage: trusted_fetch`. Body:
`# <title>\n\n<description>` (full description; the prompt truncates).

Assess adds: `calm`, `happy`, `flags`, `note`, `suitable`, `model` (the answering
model, which may be a fallback), `assessed_at`, `rubric_version`. Enhance adds
`enhanced_description`, `enhanced_at`, `enhance_model`.

## Fetch (YouTube, decision 0004 method)

Per **approved** channel (`derive_status` == `approved`; candidate/rejected never
fetched, unresolved — no `channel_id` — reported, not fetched):

1. `playlistItems` on the uploads playlist (`UU…`), newest `--max-per-channel`.
2. Shorts: the channel's `UUSH…` playlist (reuse `collect._short_ids` /
   `evidence.shorts_playlist_id`, `upload_video_ids`; move helpers to a shared
   place if needed, don't copy). Duration fallback `evidence.is_short` when UUSH
   can't be read; `shorts_source` says which.
3. `videos.list` for duration/description of the candidates (batched by 50).
4. Keep: long-form, published within `--since-days` of `--date`, not live/upcoming
   (`duration_s` 0 / `P0D`), **not already fetched on any earlier date** (seen set
   = video ids found under `stages/trusted/fetch/*/`; a plain scan is fine at this
   size). Re-running fetch for the same date is idempotent (same files, no dupes).

Quota: ~3 units per channel; report `quota_units` like `channels evidence`.

**Fails loudly** (plan requirement):
- `QuotaExceededError` / `InvalidKeyError` stop the run, keep files written, the
  rest are `not_fetched`, exit ≠ 0 — same `Run` pattern as `collect.py` (reuse
  `ChannelResult` / `Run` shapes or a small sibling; don't invent a third style).
- Any other per-channel API/network/parse error: that channel `error` with a
  key-free message, others continue, **exit ≠ 0 at the end**.
- No catch-all that turns a failure into "0 new videos". Zero new videos with no
  errors is a normal exit 0.
- Also fix the **legacy** `FetchStage` catch-all (`stages/fetch.py`, returns
  `new_videos: 0` and the CLI exits 0 on any non-YouTube exception): it must exit
  ≠ 0. Small, in scope; the rest of the legacy pipeline is untouched.

## Assess (rubric, Claude Opus 5.5)

- Input: fetch files for `--date` that have no assess file yet (any date) —
  never re-score and re-pay for a video unless `--force`. `--force` re-scores the
  date's videos and overwrites their assess files for that date.
- **One call per channel** (its new videos as a batch, chunk at ~25 videos), so
  the model sees one channel's context. Prompt = `rubric.RUBRIC` + per-video id,
  title, description (truncated, e.g. 1000 chars), duration, published date. The
  model returns `list[VideoScore]`; `suitable` is computed with `is_suitable` in
  code, never by the model.
- Validate like vet: every input id answered exactly once, no unknown ids
  (`check_video_ids` pattern); a bad reply is an `error` for that batch, nothing
  written for it, others continue, exit ≠ 0.
- Client: generalise or mirror `AnthropicVetClient` behind a protocol so tests use
  a fake (no network). Reuse its error mapping (`_call_error`, stopping types
  401/402/403 stop the run; refusal and `max_tokens` are per-batch results),
  token counting and `estimate_usd`. Don't fork 100 lines — extract the shared
  call into one place both vet and assess use.
- Report tokens + estimated USD like vet.
- `rubric_version`: a constant next to `RUBRIC` (bump when the rubric text
  changes); written into each assess file.
- Run-to-run variance (phase 3 backlog) is known; 5a scores once and stores it.
  Measuring misses is 5c.

## Enhance (suitable only)

- Input: assess files for `--date` with `suitable: true` and no enhance file yet
  (`--force` redoes). Unsuitable videos are never enhanced and never reach
  `stages/trusted/enhance/`.
- Reuse the legacy description-rewrite prompt (`prompts.py`,
  `make_description_meaningful`) or a small new one in the same place; output plain
  text, no clickbait/promo/links. Model = the shared Opus 5.5 constant. One call
  per video is fine (volume is small) or batch — dev's choice, say why.
- Same error/stop rules and cost report as assess.

## `trusted run` / `trusted status`

- `run` = fetch → assess → enhance for `--date`. Any failing step (quota stop or
  a per-channel error) stops the chain with exit ≠ 0; rerun is cheap and
  idempotent.
- `status`: counts per stage for the date (fetched, assessed, suitable,
  enhanced), per channel; no keys.
- `scripts/daily_run.sh`: add the trusted run alongside (or instead of, behind a
  variable) the legacy one; legacy behaviour stays the default only if the script
  is already used by cron — check, say what you did.

## Tests (no network)

Fake `YouTubeClient` getter (as in `tests/` for collect) and fake Claude client.
Cover: only approved channels fetched (candidate, rejected, unresolved, named
non-approved slug → error); Shorts excluded via UUSH and via duration fallback;
`--since-days` window; live/upcoming skipped; seen-set dedup across dates and
idempotent rerun; quota stop mid-run (files kept, `not_fetched`, exit ≠ 0);
per-channel error → exit ≠ 0, others written; legacy fetch catch-all now exits ≠ 0;
assess batching per channel + chunking, id check failure writes nothing for that
batch, `is_suitable` decides `suitable`, skip already-assessed, `--force`,
`--dry-run` needs no key, stopping error; enhance only on suitable, skip existing;
`run` stops on failure; `status` counts; `--json` shape and stderr/exit contract;
legacy commands still pass their existing tests untouched.

Baseline: 406 tests pass, coverage 78%, `uv run poe check` green. After: `poe
check` green; `uv run poe typecheck` before each commit of a multi-commit step.

## Real run (dev, exploratory, nothing committed)

Copy `channels/` to scratch; run from a scratch cwd so `stages/` lands there, not
in the repo. `trusted fetch --since-days 14` over all approved channels (YTKEY,
~35 quota units — fine). Then `trusted assess` / `enhance` on **at most two
channels' videos** (Anthropic credit; cap ~$1, report the estimate). Report:
videos per channel, Shorts excluded, suitable count, two example notes, cost.
Nothing from scratch is committed.

## Docs

- `docs/decisions/0009-trusted-pipeline.md` (accepted): split, side-by-side,
  stage layout, dedup rule, model, enhance gate, fail-loudly rules.
- CLAUDE.md: `trusted` commands (keys each needs), `stages/trusted/` in the
  storage tree, new modules in key modules, legacy marked as legacy.
- `docs/architecture.md`: the trusted pipeline.
- `docs/plan.md` phase 5 row: already split by the orchestrator; don't edit.
- Don't touch `docs/next-session.md`, `docs/phases/` (except committing
  `docs/phases/phase-5a/` as-is first).

## Existing code to know

- `channels/store.py`: `ChannelStore`, `ChannelEntry.status`, `derive_status`.
- `channels/collect.py`: `Run`, `ChannelResult`, `_short_ids`, `_fetch_channels`,
  resolve/evidence flow — the pattern for a YouTube run that stops on quota.
- `channels/evidence.py`: `shorts_playlist_id`, `is_short`, `upload_video_ids`,
  duration parsing helpers.
- `youtube.py`: `YouTubeClient` (`playlist_items`, `videos`, `quota_units`),
  `RunStoppingError`, `QuotaExceededError`, `InvalidKeyError`,
  `is_playlist_not_found`.
- `channels/vet.py` (`MODEL`, `check_video_ids`, prompt building) and
  `channels/vet_run.py` (`AnthropicVetClient`, error mapping, `estimate_usd`).
- `rubric.py`: `RUBRIC`, `VideoScore`, `is_suitable`, `FLAGS`.
- `stages/base.py` `Stage`; `models/markdown.py` `MarkdownFile`;
  `stages/fetch.py`/`assess.py`/`enhance.py` (legacy, for reference and the
  fetch catch-all fix); `cli/commands.py` (`parse_date`, `cli`),
  `cli/channels.py` (`--channels-dir` option, `--json` conventions).

## Tooling gotchas

- Parallel agents: own worktree via `git worktree add --detach <path>
  phase-5a-trusted-fetch`, `uv sync` there, remove + prune after.
- Don't run pytest concurrently in one checkout (shared `.coverage`).
- madoqua hook on staged .py only; never `--no-verify` / `MADOQUA_SKIP`.
- Staged-only `ty` misses cross-file breakage: `uv run poe typecheck` per commit.
- `tyf` index stale after hook reformat: `uv run tyf daemon restart`.
- Click group options go before the subcommand (`happytube trusted
  --channels-dir X fetch`).
- API keys: never in messages, logs or files written; `requests` errors carry the
  URL (with `key=`) — use `youtube.py`'s key-free errors.
