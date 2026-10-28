# Phase 5c — log

Loop (planned): dev → review ‖ QA → fix → combined verify → orchestrator probe →
learnings.

Decisions taken with the user before dev (2026-10-28, one question call, all four
recommended options): `video-reviews/<id>/` top-level; verdict + flags + watched +
note; queue = all assessed, shown-in-player unreviewed first; latest human
`unsuitable` hides from the player (amends 0008/0010). Orchestrator defaults in
context.md "Settled by the orchestrator" (snapshot of agent call in the record,
derived status, dir must exist, unreadable review hides, `videos` CLI group).

Orchestrator pre-checks: baseline 498 passed / 85%.
