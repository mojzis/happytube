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

1. **User (content):** human reviews, now in the browser:
   `uv run happytube serve --reviewer matous` → http://127.0.0.1:8000. Work the
   *Needs human review* section. Then commit + push `channels/` (the app doesn't run
   git). Open questions: ct-decko, zoo-zlin handles; national-park-service (identity
   yes, content mostly panels); zoo-dvur-kralove / smithsonian inactive.
2. Start **phase 5 — trusted fetch**: write `docs/phases/phase-5/context.md`.
   Scope from plan: fetch only from approved channels (playlistItems, decision 0004),
   skip Shorts, assess with the shared rubric, fetch fails loudly, player/export read
   `stages/`, Flask player → FastAPI app (drop `flask`), video review queue + video
   review records in the review UI. Likely too big for one phase: split first.

## Open decisions (settle in phase 5 context.md)

- Split phase 5? (e.g. 5a trusted fetch + assess with rubric; 5b video review queue;
  5c player port to FastAPI.)
- Video review record format and where it lives (per channel `videos/<id>/reviews/`
  vs a top-level `videos/`).
- Replace legacy assess (happiness 1–5) with the rubric, or keep both for now?

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence (0004); agent vetting (0005); web stack FastAPI +
  htmx (0006); review UI local-only, channels only, reviewer cookie (0007).
- Channel approval = source; agents gate each video with the rubric; humans only
  spot-check videos to test the algorithm (0008). Vet prompt changed: old vets
  are stale (`channels vet --all --force` to refresh, costs credit).
- Merge PRs with a merge commit (full history), not squash.
