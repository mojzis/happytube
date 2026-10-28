# Phase 5c — review

See [context.md](./context.md) and the dev report in [log.md](./log.md). Use the
`python-review` skill. Read-only: report, don't fix.

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5c-review
phase-5c-video-spot-checks`, `uv sync` there; remove + `git worktree prune` at the end.
Diff: `git diff 2991291..phase-5c-video-spot-checks`.

## Focus
1. Rule 4 is safe: every path where a human `unsuitable` must hide a video (live
   route, export, unreadable review, missing dir, tie order, agent reviews
   ignored). One shared function, not two copies.
2. Stats compare against the snapshot, not the current assess; orphans and
   malformed files don't crash.
3. Path safety: video id validated before any filesystem path; POST writes only
   `role: human`; guard covers the new routes; templates autoescape notes.
4. Reuse: naming/collision helper shared with `channels/store.py`, CLI mirrors
   `channels` helpers, no clone (zorilla), no dead code (gerenuk audit on new
   modules).
5. Docs match the code (CLAUDE.md, 0011, DEPLOYMENT.md, deploy paths).

## Report
Return ONLY JSON (≤600 words):
{"verdict": "ship|fix", "findings": [{"id": "R1", "severity": "high|medium|low",
 "file": "path:line", "what": "", "fix": ""}], "preexisting": [""]}
