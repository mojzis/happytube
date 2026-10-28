# 0009 The trusted pipeline

Date: 2026-10-28
Status: accepted

## Context

Phase 5 turns approved channels (decision 0008: a human approves channels, agents
gate videos) into the videos she is shown. The legacy pipeline searches YouTube by
category and scores "happiness" 1–5 with a retired model; it has no notion of
trusted sources and its fetch swallowed errors as "0 new videos". Phase 5 is split:
5a this pipeline, 5b the player reading it, 5c human spot-checks of videos.

## Decision

- **Side by side with the legacy pipeline.** `happytube trusted fetch | assess |
  enhance | run | status` is a new command group with its own stage directories,
  `stages/trusted/{fetch,assess,enhance}/YYYY-MM-DD/<video_id>.md`. The legacy
  `fetch`/`assess`/`enhance`/`report`/`run-all` keep working unchanged and never
  share a directory with it.
- **Source = approved channels only** (`derive_status == approved`). Candidate and
  rejected channels are never fetched; an approved channel without a `channel_id`
  is reported, not fetched; naming a non-approved channel is an error.
- **Fetch method as decision 0004:** uploads playlist (`UU…`), Shorts from `UUSH…`
  (duration rule when it can't be read), `videos.list` for the rest — ~3 quota
  units per channel. Kept: long-form, not live/upcoming, published within
  `--since-days` (default 14) of the date.
- **Dedup:** a video id found anywhere under `stages/trusted/fetch/*/` is never
  fetched again; reruns are idempotent. Assess and enhance likewise skip a video
  done on any date unless `--force`.
- **Assess:** Claude Opus 5.5 with the shared rubric (`rubric.RUBRIC`, versioned
  by `RUBRIC_VERSION`), one call per channel batch (≤ 25 videos), the same call
  shape as `channels vet` (`happytube.claude`: structured output, effort `medium`,
  refusal fallback; one model constant). Every video sent must be scored exactly
  once or nothing is written for that batch. `suitable` is computed in code
  (`is_suitable`), never by the model.
- **Enhance:** only `suitable: true` videos, one call per video, same model.
- **No human approval of videos** (0008): suitable = shown (by phase 5b).
- **Fail loudly.** A used-up YouTube quota or rejected key, or an Anthropic
  key / permission / credit problem, stops the run (files written stay, the rest
  are `not_fetched` / `not_run`); any per-channel or per-batch failure exits
  non-zero after the others finish; `run` stops at the first failing step. Zero
  new videos without errors is a normal exit 0. The legacy fetch's catch-all now
  fails the run too.

## Consequences

- The player (5b) can read `stages/trusted/enhance/` (suitable, cleaned) and
  `assess/` (all scores) without touching legacy data.
- Each date's files are a complete record of what the agent decided and with
  which rubric version and model, for 5c's spot-checks to measure.
- Scores are taken once and kept; run-to-run variance is not averaged out.
- Rubric or prompt changes don't re-score old videos unless `--force` per date.
- Two pipelines to keep working until the legacy one is retired.
