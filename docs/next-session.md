# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–5 + backlog). Source idea:
  `~/git/ideas/projects/happytube/ideas/trusted-channels.md`.
- Phase 0 merged to `main` (PR #6).
- **Phase 1 done** on branch `phase-1-channels` (not pushed, no PR yet):
  `happytube.channels` package (`Channel`/`Review` models, `ChannelStore`,
  `derive_status`, `filter_entries`), `happytube channels add/list/show/review`
  with `--json`, no API keys needed. 15 seed candidates in `channels/`
  (only `@bbcearth`, `@NatGeo` have handles; no channel ids). Decision 0003 (layout).
  Tests 46 → 122, `poe check` green, coverage 59%.
  Record: `docs/phases/phase-1/` (log.md has every agent report, learnings.md).
- Process lessons (cumulative): `docs/process-learnings.md`.

## Next step

1. User: review + merge phase 1 (push `phase-1-channels`, open PR).
2. Start **phase 2 — channel evidence**: write `docs/phases/phase-2/context.md`, then
   run the loop (same as phase 1; see learnings for brief tweaks: `--detach`
   worktrees, split review/QA scope, verify judges every fix deviation).
   Phase 2 scope (from plan): resolve handles → channel ids (`channels.list`
   `forHandle`), stats + recent uploads (RSS vs `playlistItems`), video durations
   (Shorts), cached per channel under `channels/<slug>/evidence/`; research note +
   decision record comparing fetch methods with quota math for 50/200/500 channels.

## Open decisions (settle in phase 2 context.md)

- Needs a real `YTKEY` for the resolve/evidence run (no `.env` in the repo now):
  user provides one, or phase 2 builds + tests with mocks and the user runs it.
- Evidence format: YAML snapshot per fetch (timestamped, append-only like reviews)
  vs one overwritten `evidence.yaml` (git history keeps old ones).
- Seed handles for the 13 unresolved channels: agent proposes via search
  (100 units each) or the user fills them by hand.
- Allowlist vs blocklist: closed — `rejected` channel = blocklist (decision 0003).

## Decided

- Runner: manual; the user drives the loop from the session (`docs/plan.md` →
  Per-phase loop). No runner skill yet.
- Registry layout (decision 0003): `channels/<slug>/channel.yaml` +
  append-only `reviews/`; status derived from latest human approve/reject.
