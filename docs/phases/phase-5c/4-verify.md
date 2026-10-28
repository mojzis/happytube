# Phase 5c — verify (review + QA combined)

See [context.md](./context.md) and [log.md](./log.md) (review, QA, fix). Read-only:
report, don't fix.

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5c-verify
phase-5c-video-spot-checks`, `uv sync`; remove + prune at the end. Fix diff:
`git diff 97ade36..phase-5c-video-spot-checks`. Scratch data as in 2-qa.md, no API
calls.

## Check
1. `uv run poe check` green; numbers.
2. Each R1–R8, Q1–Q3 really fixed — reproduce the original repro where one exists
   (R1: shown video with assess lacking rubric_version → queued, reviewable,
   hidden; Q1: non-UTF-8 review + dir named x.yaml → 200s, video hidden; R3: rescore
   between GET and POST → 422, nothing written).
3. Nothing regressed: rerun 2-qa.md 2a–2g briefly; selection rule unchanged for
   the committed real data (14 shown).
4. Fix deviations acceptable? (POST without `assessed_at` unchecked; bad
   flags/note silently empty — does either let a hidden video show or a review
   record a wrong snapshot?)

## Report
Return ONLY JSON (≤500 words):
{"verdict": "ship|fix", "numbers": "", "confirmed": [{"id": "", "result": ""}],
 "findings": [{"id": "V1", "severity": "high|medium|low|info", "what": "", "repro": ""}]}
