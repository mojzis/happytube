# Phase 2 — review (report only)

See [context.md](./context.md) — required reading. Also [log.md](./log.md) (dev report).

## Scope
Commit range `2a22ea7..phase-2-evidence`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p2-review phase-2-evidence`, cd there,
`uv sync`. Remove + prune at the end. No `.env` there: never call the real API.

## Task
1. Invoke the `python-review` skill (Skill tool) over that range.
2. Logic judgement (QA covers runtime/env; don't duplicate its checks):
   - Key leak: can any error path (RequestException, non-200, JSON decode, logging,
     `repr` of client/settings) put the key into a message, log, file or stdout?
   - Append-only: can any path overwrite an evidence or review file? Is the review
     ordering logic reused, not copied?
   - channel_id write-back: null-only rule and mismatch, also with hand-edited YAML;
     channel.yaml rewrite keeps other fields/unicode/order intact.
   - Client: batching at 50, pagination, duration parsing edge cases, missing
     fields in API items (hidden subs, deleted/private videos, no
     contentDetails), quotaExceeded stops cleanly with earlier snapshots kept.
   - Evidence builder pure and tested with realistic shapes; tests not
     implementation-pinned; injected getter, no network.
   - Store API fit for phase 3/4 (no click/rich).
   - Docs (0004, research note quota math, CLAUDE.md, architecture.md) match code;
     check the quota arithmetic.
   - Committed snapshots: sane, no key, no surprising PII.
3. Reproduce where cheap (fake getter in a scratch script, temp channels dir).
4. Number findings R1, R2… Pre-existing issues in untouched code → `preexisting`.

## Constraints
Read-only. Do NOT edit or commit on the branch.

## Report
Return ONLY JSON (≤500 words):
{"findings": [{"id": "R1", "severity": "high|medium|low", "file": "", "issue": "", "fix": ""}],
 "preexisting": [""], "verdict": "ship|fix-first"}

## Added by orchestrator after dev
- Shorts: dev's research shows `0 < duration_s <= 180` gives heavy false positives
  (Zoo Praha 33/50). Assess the cost/shape of switching `is_short` to UUSH-playlist
  membership (playlistItems on `UUSH…`, 1 unit/page) with duration as fallback when
  the UUSH call fails/404s. What breaks in snapshots/tests/docs?
- Dev's scratch wrapper for the truncated key: confirm nothing of it landed in the
  repo (no script, no key, no `.env` change tracked).
- `InvalidKeyError` early stop and the `test_pipeline.py` chdir fix: correct?
- Handle edits for explore-org / zoo-dvur-kralove / pbs-nature: snapshot titles match
  the intended channels?
