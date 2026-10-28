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

1. User: review branch, push + PR/merge `phase-0-template`.
2. Decide the runner (new skill vs. manual loop as in phase 0).
3. Start **phase 1 — channel registry**: write `docs/phases/phase-1/context.md`
   (data model for channels + review records, file layout, CLI `channels
   add/list/show/review --json`, seed list from the idea doc), then run the loop.

## Open decisions

- Runner skill for the per-phase loop.
- Phase 1 file layout: one YAML per channel (`channels/<id>.yaml`) vs one
  `config/channels.yaml` + per-channel review files. Leaning per-channel files
  (merge-friendly, agents and humans write concurrently).
- Allowlist only, or also blocklist (idea doc open question).
