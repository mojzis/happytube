# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–5b done; 5c next; backlogs per phase).
- Phase 5b (PR, merge pending): the player shows the trusted pipeline's output.
  `happytube serve` → `/player/` (live from `stages/trusted/` + registry); `python
  -m happytube.web.export` builds `videos.json` for GitHub Pages. Shown = assess
  `suitable` + non-empty enhance description + channel approved **now**, newest
  first; scores from assess only (decision 0010, record `docs/phases/phase-5b/`).
  Flask, `server.py`, `deploy_web.sh` gone.
- GitHub Pages enabled (Actions source): https://mojzis.github.io/happytube/.
  Deploys on push to `main` touching `stages/trusted/`, `channels/`,
  `src/happytube/`, deps or the workflow. **Fails until `stages/trusted/` is
  committed on `main`** (intended: no empty site).
- `scripts/daily_run.sh`: `HAPPYTUBE_PIPELINE=trusted HAPPYTUBE_PUSH=1` runs the
  trusted pipeline and commits + pushes only `stages/trusted/` (retries a failed
  push next run). No cron yet.
- Registry: 11 approved, 2 rejected, 2 candidates (ct-decko, zoo-zlin).
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **User:** merge the 5b PR (merge commit).
2. **User + agent:** first real data on `main`: from the repo root, `happytube
   trusted run --since-days 14` (~35 units, ~$0.30 for ~40 videos), review the
   output, commit + push `stages/trusted/` → first Pages deploy; check the site.
3. **User:** start the daily cron (`HAPPYTUBE_PIPELINE=trusted HAPPYTUBE_PUSH=1
   scripts/daily_run.sh`) on `main`.
4. Phase 5c (video spot-checks): context.md with the user, then the loop.

## Open decisions

- 5c: video review record format and location.
- Grandma-facing player UI (bigger, simpler) — a phase of its own?
- When to retire the legacy pipeline (search fetch, happiness assess).

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence (0004); agent vetting (0005); web stack FastAPI +
  htmx (0006); review UI local-only (0007); channel approval = source, agents gate
  videos (0008); trusted pipeline (0009); trusted player (0010: committed
  `stages/trusted/` feeds Pages, all suitable newest first, hide until enhanced,
  hide videos of channels no longer approved, one FastAPI app).
- Merge PRs with a merge commit (full history), not squash.
