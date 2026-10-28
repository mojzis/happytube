# Phase 5c — QA

See [context.md](./context.md) and the dev report in [log.md](./log.md). Read-only:
report, don't fix. Runtime checks only (review covers logic).

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5c-qa
phase-5c-video-spot-checks`, `uv sync` there; remove + `git worktree prune` at the end.
Scratch cwd `/tmp/claude-1000/p5c-qa-data` with copies of the committed
`stages/trusted/` + `channels/` and hand-made `video-reviews/` files. No API calls.

## Check
1. `uv run poe check` green; numbers.
2. Runtime:
   a. Seeded reviews covering every failure scenario in context.md: export and
      live `/player/videos.json` agree and show exactly the right set.
   b. `happytube serve` → `/videos`: section order, agreement counts by hand vs
      page; detail page renders (agent fields, both descriptions, embed, reviews);
      POST via the form (htmx header and plain) writes one file with `role: human`
      and the snapshot; reviewer prefill/cookie; bad Host → 400, cross-origin POST
      → refused.
   c. Bad ids in URLs and CLI (`../x`, `%2e%2e`, 10/12 chars, unknown valid id) →
      404 / error, no file created anywhere (`find` before/after).
   d. `videos list|show|review|stats --json`: valid JSON on stdout, errors on
      stderr, exit codes.
   e. `video-reviews/` missing → export exit 1; serve warning and loud route
      errors. Export from another cwd with the option / env.
   f. Malformed review YAML → video hidden in player, queue still renders.
   g. Simulate CI: fresh clone of the branch, `uv sync`, run the workflow's export
      command from the repo root → exit 0 and the expected count.

## Report
Return ONLY JSON (≤600 words):
{"verified": true, "numbers": "", "findings": [{"id": "Q1", "severity": "high|medium|low",
 "what": "", "repro": ""}], "checks": [{"check": "", "result": ""}], "preexisting": [""]}
