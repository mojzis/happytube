# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–5 + backlog).
- Phases 0–4 merged (PRs #6, #7, #9, #10, phase 4 PR). **Phase 4 done** (web review UI).
  - `happytube serve [--host 127.0.0.1] [--port 8000] [--channels-dir …]
    [--reviewer NAME]` — FastAPI + htmx app in `src/happytube/review/`, no keys.
  - Queue: *Needs human review* first (attention = vet flags or unresolved, then
    vet verdict unsure → reject → approve → not vetted), then *Reviewed*. Filters
    status / kind / language (htmx, plain GET works too).
  - Detail: channel, latest evidence ("resolved to" title prominent), latest vet
    (summary, concerns, video table with thumbnails, read-only), all reviews.
  - Review form writes the same `Review` records as `channels review`
    (`role: human`) via `ChannelStore.add_review`; reviewer name remembered in a
    cookie, default `--reviewer` / `HAPPYTUBE_REVIEWER`.
  - Local only, no auth: Host allow-list (DNS rebinding), Origin /
    Sec-Fetch-Site check on POST, wildcard binds refused, htmx 2.0.11 vendored.
  - Decision 0007. Tests 298 → 398+, coverage 75% → 78%. Browser-checked by QA.
  - Record: `docs/phases/phase-4/` (log.md, learnings.md).
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **Run phase 5a** from `docs/phases/phase-5a/context.md` (branch
   `phase-5a-trusted-fetch`): dev → review ‖ QA → fix → verify → learnings → PR.
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
