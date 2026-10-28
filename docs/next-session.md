# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–4 and 5a done; 5b, 5c next; backlog).
- Phases 0–5a merged (PRs #6, #7, #9, #10, #11, phase 5a PR). Phase 5a = trusted
  pipeline: `happytube trusted fetch/assess/enhance/run/status` (decision 0009,
  record `docs/phases/phase-5a/`). Fetches long-form videos only from approved
  channels into `stages/trusted/`, scores each with the rubric (Opus 5.5),
  rewrites descriptions of `suitable` ones. Legacy pipeline unchanged, side by side.
- Real runs (scratch, nothing committed): 42 new videos over 14 days from 11
  approved channels (~33 units); ~$0.05 per 7 videos assess+enhance. BBC Earth 1/8
  suitable (predation), zoos mostly suitable.
- `scripts/daily_run.sh`: legacy by default, `HAPPYTUBE_PIPELINE=trusted` for the
  new one; no cron set up yet.
- Registry: 11 approved, 2 rejected, 2 candidates (ct-decko, zoo-zlin).
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **Phase 5b (trusted player)**: write `docs/phases/phase-5b/context.md` with the
   user (open choices up front, one multiple-choice question), then the per-phase
   loop. Scope: player + static export read `stages/trusted/`; Flask player → the
   FastAPI app; drop `flask`. **Readers take calm/happy/suitable from assess and
   only `enhanced_description` from enhance** (stale scores possible in enhance).
   Only `suitable: true` videos are shown. Where do stage files live for the
   deployed player (GitHub Pages export vs. committed stages) — decide in 5b.
2. Then 5c (video spot-checks).
3. **User, any time:** decide whether to start a daily trusted run (cron with
   `HAPPYTUBE_PIPELINE=trusted`); ct-decko, zoo-zlin still candidates.

## Open decisions

- 5b: where the trusted stage data comes from for the deployed static player.
- 5c: video review record format and location.
- When to retire the legacy pipeline (search fetch, happiness assess).

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence (0004); agent vetting (0005); web stack FastAPI +
  htmx (0006); review UI local-only (0007); channel approval = source, agents gate
  videos (0008); trusted pipeline (0009: side by side, Opus 5.5, enhance only
  suitable, pending files up to `--date` picked up, `run` continues past
  per-channel errors, stops on quota/key).
- Merge PRs with a merge commit (full history), not squash.
