# Phase 2 — dev

See [context.md](./context.md) — required reading. Do NOT re-explore what it documents.

## Task
Build channel evidence exactly as context.md describes: YouTube client (injectable
getter, key-safe errors, quota count), `Evidence` model, store evidence methods +
channel_id write-back, `channels resolve` / `channels evidence`, `show`/`list`
additions, tests, agent-proposed seed handles, research note, decision 0004,
CLAUDE.md + architecture.md. Last: the real run in the main checkout, commit the
snapshots.

## Out of scope
Claude vetting, web UI, the fetch stage rewrite, RSS implementation, `search.list`.
Don't touch `docs/plan.md`, `docs/next-session.md`, `docs/phases/` (except: commit
`docs/phases/phase-2/` as-is in your first commit).

## Mode
Make it work and clean enough to commit. Review nits belong to the review step.

## Contract
- Work in the main checkout on `phase-2-evidence`. Commit in logical chunks
  (client+tests, model/store+tests, CLI+tests, seed handles, docs, real-run
  snapshots). Hooks must pass. No `--no-verify`, no `MADOQUA_SKIP`. Do NOT push.
- Never read, print or commit `.env` or the key. Grep your commits for the key's
  prefix pattern `AIza` before finishing — must be zero hits.
- Before finishing: `uv run poe check` green; `env -u YTKEY -u ANTHROPIC_API_KEY
  uv run happytube channels list --json` works; real run done (or say exactly why not).

## Report
Return ONLY this JSON (≤500 words):
{"commit_shas": [], "summary": "", "real_run": {"resolved": [], "not_found": [],
 "quota_units": 0, "snapshots": 0}, "research_findings": "", "deviations": [],
 "unresolved_issues": [], "ignores_added": ["rule + scope + why"],
 "check_output_tail": ""}
