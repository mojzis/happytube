# Next session

_Updated 2026-10-28._

## Where we are

- Plan: `docs/plan.md` (phases 0–5 + backlog). Source idea:
  `~/git/ideas/projects/happytube/ideas/trusted-channels.md`.
- **Phase 0 done** on branch `phase-0-template` (not pushed, no PR yet): src layout,
  template tooling (uv dev group, ruff/ty, poe, madoqua hook, aesop toolbox,
  dependabot), legacy + queue experiments deleted, docs scaffold
  (constitution, architecture, decisions 0001/0002), YTKEY bug fixed, vulns 21 → 0,
  46 tests. Record: `docs/phases/phase-0/` (log.md has every agent report).
- Process lessons for the future runner skill: `docs/process-learnings.md`.

## Next step

1. Start **phase 1 — channel registry**: write `docs/phases/phase-1/context.md`
   (data model for channels + review records, file layout, CLI `channels
   add/list/show/review --json`, seed list from the idea doc), then run the loop.

## Decided (2026-10-28)

- Phase 0 merged to `main` (PR from `phase-0-template`).
- Runner: manual for now — the user drives the loop from the session, same steps as
  phase 0 (`docs/plan.md` → Per-phase loop). No runner skill yet.
- Phase 1 layout: **one file per channel** (merge-friendly; people and agents write
  concurrently).

## Open decisions

- Phase 1: exact per-channel file shape (YAML with embedded review list vs. channel
  YAML + separate review files) — settle in phase 1 context.md.
- Allowlist only, or also blocklist (idea doc open question).
