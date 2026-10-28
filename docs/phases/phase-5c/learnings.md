# Phase 5c — learnings

Loop: context (4 questions to the user, one call) → dev → review ‖ QA → fix →
combined verify → orchestrator probe. 5 agent steps incl. dev; no paid calls in
the whole phase (no Anthropic, no YouTube units): every run used the committed
`stages/trusted/` + `channels/` data.

## Loop design
- **Listing failure scenarios in context.md held a second time** (10 listed): QA's
  seeded reviews for every scenario passed, the guard, bad ids, CLI JSON, missing
  dir and CI simulation too. Both mediums sat outside the list (assess files
  lacking snapshot fields; undecodable review files).
- Review and QA overlapped on the medium (R2 = Q1, non-UTF-8 file / dir named
  `x.yaml` → 500s), found by logic and at runtime. Q2 shared a root with dev's
  unresolved note and R1. Overlap again cost no extra round.
- **The orchestrator's extra review item found a real gap**: shown videos whose
  assess lacks snapshot fields were missing from the queue and 404'd, so a human
  could not hide them (R1 medium). Dev had listed "queue skips assess files
  lacking snapshot fields" as a deviation; the orchestrator turned it into a check.
- One fix round + combined verify held again (phases 0–5c). Verify: `ship`, two
  info items only (V1, V2).
- Probe at the repo root on final code: export 14, `videos stats` 42 assessed /
  0 reviewed, `videos list --section shown` 14 = player. No paid calls needed.

## Briefs & context
- Four open choices in one question call, recommended option first; the user
  picked all four recommendations. One round trip, as in 5b.
- "Settled by the orchestrator (dev may argue)" was long this time (model, store,
  dir option, routes, CLI, deploy). Dev argued none of the design, deviated on
  details only: `--watched` required in the CLI, `StageRecord.body`, queue skipping
  incomplete assess files, a plain iframe embed, DEPLOYMENT.md paths fixed.
- The fix brief chose the design for each finding (R1 optional snapshot fields +
  "incomplete assess" marker, R3 hidden `assessed_at` + 422, R5 subclass, R6 public
  helpers). The fix agent built them with no questions (5a lesson holds).
- The fix brief named the R1, Q1 and R3 repros for verify, and verify reproduced
  them. Asking verify to judge the fix deviations ("can either make a hidden video
  show?") gave a clear no.

## Agent reports
- A dev deviation was the medium. "Queue skips assess files lacking snapshot
  fields" read like a detail; traced against the goal ("unsuitable hides"), it
  made shown videos unhideable. Read deviations as possible findings.
- Dev's unresolved item (warning printed twice) shared its root with Q2 and R1;
  the R1 fix (parse once) closed it.
- Fix agent's unresolved item (bad flags/note silently empty) came back as
  verify's V2 info. Not a safety gap, worth a backlog line.
- Review's preexisting item (undecodable channel review crashes
  `channel_statuses`) was fixed by the same R2 change.

## Tooling gotchas
- Nothing new. Own worktree per parallel agent, `poe typecheck` per commit, kill
  servers by pid: all held.

## Open questions
- Should dev's `deviations` get a routine "trace against the goal" item in the
  review brief, since one hid the medium here?
- Should hand-edited or curl-posted reviews without `assessed_at` (V1) be guarded,
  or is the UI path enough?
