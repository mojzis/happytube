# Phase 5b — log

Loop (planned): dev → review ‖ QA → fix → combined verify → orchestrator probe →
learnings.

Decisions taken with the user before dev (2026-10-28): deployed data = committed
`stages/trusted/`; show all suitable newest first; hide until enhanced. Orchestrator
defaults in context.md "Settled by the orchestrator" (channel-status filter, one
app, JSON shape, export fails on missing dir, push opt-in in daily_run.sh).

Orchestrator pre-checks: baseline 456 passed / 82%; GitHub Pages not enabled on the
repo (API 404); `stages/` untracked, not ignored; `static/videos.json` tracked (empty).
