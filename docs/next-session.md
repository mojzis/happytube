# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–5 + backlog).
- Phases 0–3 merged (PRs #6, #7, #9, phase 3 PR). **Phase 3 done** (agent vetting).
  - `happytube channels vet [SLUG…] [--all] [--force] [--dry-run] [--json]` —
    Claude Opus 5.5 judges the latest evidence snapshot: identity, calm/happy 1–5 and
    flags per long-form video (Shorts never scored), channel verdict. Writes
    `channels/<slug>/vet/<ts>.md` + an agent review (`claude-vet`). Flags
    `inactive` / `mostly_shorts` / `identity_doubt` turn approve into `unsure`;
    unresolved and human-rejected channels are skipped; re-vet only on a new
    snapshot or `--force`. Shared rubric in `happytube/rubric.py` (phase 5 reuses).
  - Decision 0005. anthropic SDK 0.73 → 1.17.
  - First real run committed: approve — zoo-praha, cincinnati-zoo, san-diego-zoo,
    explore-org; unsure — monterey-bay-aquarium, nat-geo-kids,
    national-park-service, pbs-nature, smithsonian-channel (inactive),
    zoo-dvur-kralove (inactive); reject — bbc-earth, bbc-earth-kids,
    national-geographic. ct-decko, zoo-zlin skipped (unresolved). $1.38.
  - Per-video scores vary run to run near the threshold (zoo-praha 45 vs 39/50).
  - Tests 212 → 298+, coverage 69% → 75%.
  - Record: `docs/phases/phase-3/` (log.md, learnings.md).
- Process lessons: `docs/process-learnings.md`.

## Next step

1. **User (content, deferred):** human reviews. `channels list --needs-human-review`,
   `channels show <slug>` (now with the vet summary), read `vet/*.md`, then
   `channels review <slug> --reviewer matous --role human --verdict …`. Open
   questions still: ct-decko, zoo-zlin handles; national-park-service (vet says
   identity yes, content mostly panels); zoo-dvur-kralove / smithsonian inactive.
2. Start **phase 4 — web review UI**: write `docs/phases/phase-4/context.md`
   (Flask pages: channel queue ordered by needs-review / agent flags first, channel
   detail with evidence + vet report + all reviews, approve/reject/notes form writing
   the same review records via `ChannelStore`; video review queue from vet scores?).
   Then run the loop.

## Open decisions (settle in phase 4 context.md)

- Reviewer identity in the web UI: fixed name from config, or a field per review?
- Video review queue in phase 4, or only channels (videos in phase 5)?
- Local-only Flask (no auth) vs anything deployable.

## Decided

- Runner: manual; the user drives the loop from the session.
- Registry layout (0003); evidence (0004); agent vetting (0005): snapshot-only input,
  report + agent review + per-video scores, skip-when-current, Opus 5.5.
- Merge PRs with a merge commit (full history), not squash.
