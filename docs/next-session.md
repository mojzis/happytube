# Next session

_Updated 2026-10-29._

## Where we are

- Plan: `docs/plan.md` (phases 0–5c done; backlogs per phase). No phase 6 defined
  yet.
- Phase 5c (PR, branch `phase-5c-video-spot-checks`): human video spot-checks.
  Records in `video-reviews/<video_id>/<stamp>-<reviewer>.yaml` (verdict
  suitable/unsuitable/unsure, flags, watched, note, snapshot of the agent's call).
  `happytube serve` → `/videos` queue (shown-in-player unreviewed first, then the
  rest, then reviewed; agreement summary) + detail + form; `happytube videos
  list/show/review/stats [--json]`. A latest human `unsuitable` hides the video
  from the player and Pages (decision 0011). Record `docs/phases/phase-5c/`.
- Player / Pages: https://mojzis.github.io/happytube/ — 14 videos from the first
  trusted run (2026-10-28). Deploy also triggers on `video-reviews/**`.
- `scripts/daily_run.sh`: `HAPPYTUBE_PIPELINE=trusted HAPPYTUBE_PUSH=1` runs the
  trusted pipeline, commits + pushes only `stages/trusted/`. No cron yet. It does
  not commit `video-reviews/` — commit your spot-checks yourself.
- Registry: 11 approved, 2 rejected, 2 candidates (ct-decko, zoo-zlin).
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **User:** spot-check the 14 shown videos at `/videos`, commit + push
   `video-reviews/`. The agreement summary is the first measure of the agent.
2. **User, later:** start the daily cron (`HAPPYTUBE_PIPELINE=trusted
   HAPPYTUBE_PUSH=1 scripts/daily_run.sh`) on `main`. Until then, rerun by hand.
3. Define the next phase from the open decisions below (and what spot-checks show).

## Open decisions

- Grandma-facing player UI (bigger, simpler) — a phase of its own?
- Rubric tuning from spot-check disagreements (needs reviews first; bump
  `RUBRIC_VERSION`).
- Run-to-run score drift check (same video re-scored).
- When to retire the legacy pipeline (search fetch, happiness assess).
- Review the 2 candidates (ct-decko, zoo-zlin).

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence (0004); agent vetting (0005); web stack FastAPI +
  htmx (0006); review UI local-only (0007); channel approval = source, agents gate
  videos (0008); trusted pipeline (0009); trusted player (0010); video spot-checks
  (0011: `video-reviews/`, latest human `unsuitable` hides, measure via snapshot).
- Merge PRs with a merge commit (full history), not squash.
