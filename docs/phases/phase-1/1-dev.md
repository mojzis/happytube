# Phase 1 — dev

See [context.md](./context.md) — required reading. Do NOT re-explore what it documents.

## Task
Build the channel registry exactly as context.md describes: models + store module,
`happytube channels add/list/show/review` subgroup with `--json`, tests, seed the 15
candidates into `channels/`, decision 0003, CLAUDE.md + architecture.md updates.

## Out of scope
YouTube/Claude calls, handle resolution, evidence, web UI. Don't touch
`docs/plan.md`, `docs/next-session.md`, `docs/phases/` (except: commit
`docs/phases/phase-1/` as-is in your first commit).

## Mode
Make it work and clean enough to commit. Review nits belong to the review step.

## Contract
- Commit in logical chunks (models/store+tests, CLI+tests, seed data, docs). Hooks
  must pass. No `--no-verify`, no `MADOQUA_SKIP`. Do NOT push.
- Before finishing: `uv run poe check` green, `uv run happytube channels list` shows
  15 candidates, `env -u YTKEY -u ANTHROPIC_API_KEY uv run happytube channels list
  --json` works (also with no `.env` keys — check whether `.env` exists).

## Report
Return ONLY this JSON (≤400 words):
{"commit_shas": [], "summary": "", "deviations": [], "unresolved_issues": [],
 "ignores_added": ["rule + scope + why"], "check_output_tail": ""}
