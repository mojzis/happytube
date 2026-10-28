# Phase 2 — verify (combined review + QA, report only)

See [context.md](./context.md), [log.md](./log.md) (R1–R7, Q1–Q6, fix report),
[3-fix.md](./3-fix.md).

## Setup
`git worktree add --detach /tmp/claude-1000/p2-verify phase-2-evidence`, cd, `uv sync`.
Remove + prune at the end. No `.env` there; never use the real API. Read-only.

## Task
1. Fix range `df8c2cc..phase-2-evidence`: for each R/Q id in the fix brief's
   must/also lists → `resolved | partial | not` with evidence. Re-trace each fix end to
   end (CLI exit code + `--json` output), reproduce with fake getters where cheap.
2. Judge the fix's own design choices (where new bugs come from):
   - UUSH: 404 → empty set vs other error → duration fallback; is quota/invalid key
     still a stop during the UUSH call? `maxResults = max_videos` correct when
     max_videos > 50 (pagination)? 0-uploads skip recorded as `uush` — honest?
   - Date-split duration fallback (60 s before 2024-10-15): timezone/boundary.
   - set_channel_id: raw-YAML rewrite keeps unicode, order, nulls; duplicate-id check
     cost; race re-check meaningful; temp file cleaned on failure.
   - `Run` not_fetched/error statuses: exit codes per mix of statuses.
   - latest_evidence by filename vs `fetched_at`: can they disagree (hand-copied
     file, clock skew)? Does `show` agree with `list`?
   - Intermediate commit 6a89bb6 broken (SecretStr) — acceptable or squash?
3. `uv run poe check` green; test count; coverage vs 68%.
4. Docs: 0004, research note, CLAUDE.md, architecture.md match HEAD (quota ~3N+N/50).
5. New findings → V1, V2…

## Report
Return ONLY JSON (≤450 words):
{"items": [{"id": "R1", "status": "resolved|partial|not", "evidence": ""}],
 "findings": [{"id": "V1", "severity": "high|medium|low", "file": "", "issue": "", "fix": ""}],
 "check": "", "verdict": "ship|fix-first"}
