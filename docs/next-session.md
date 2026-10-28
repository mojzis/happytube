# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–4 done, 5 split into 5a/5b/5c, backlog).
- Phases 0–4 merged (PRs #6, #7, #9, #10, #11). Phase 4 = local review UI
  (`happytube serve`, decision 0007, record `docs/phases/phase-4/`).
- Registry: 11 approved channels (bbc-earth, cincinnati-zoo, explore-org,
  monterey-bay-aquarium, nat-geo-kids, national-park-service, pbs-nature,
  san-diego-zoo, smithsonian-channel, zoo-dvur-kralove, zoo-praha), 2 rejected,
  2 candidates (ct-decko, zoo-zlin).
- **Phase 5a planned, not started.** Branch `phase-5a-trusted-fetch` (pushed,
  `72c8390`) holds only docs: `docs/phases/phase-5a/context.md` (full brief,
  user decisions settled) + the plan split. No code yet.
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **Run phase 5a**: `git switch phase-5a-trusted-fetch`, read
   `docs/phases/phase-5a/context.md`, then the per-phase loop (`docs/plan.md`):
   write `1-dev.md` brief → dev → review ‖ QA → fix → verify → learnings → PR.
   Dev's real run uses YTKEY (~35 units) and ≤ ~$1 of Anthropic credit.
2. Then 5b (player on `stages/trusted/`, Flask → FastAPI), then 5c (video
   spot-checks).
3. **User (content), any time:** ct-decko, zoo-zlin still candidates (handles
   unresolved). Human reviews round 2 pushed (`e97b73f`); national-park-service's
   approve is by "QA Tester" (kept on purpose).

## Open decisions

- 5c: video review record format and location (per channel
  `channels/<slug>/videos/<id>/reviews/` vs top-level `videos/`).
- When to retire the legacy pipeline (search fetch, happiness assess).

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence (0004); agent vetting (0005); web stack FastAPI +
  htmx (0006); review UI local-only, channels only, reviewer cookie (0007).
- Channel approval = source; agents gate each video with the rubric; humans only
  spot-check videos to test the algorithm (0008). Vet prompt changed: old vets
  are stale (`channels vet --all --force` to refresh, costs credit).
- Phase 5 split 5a/5b/5c; trusted pipeline side by side with legacy; assess
  with Opus 5.5; enhance only `suitable` (2026-10-28, → decision 0009 in 5a).
- Merge PRs with a merge commit (full history), not squash.
