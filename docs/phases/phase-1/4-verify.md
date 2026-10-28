# Phase 1 — round 2: combined review + QA (report only)

See [context.md](./context.md) and [log.md](./log.md) — required reading (R1–R9,
Q1–Q7, fix report).

## Setup
Own worktree: `git worktree add --detach /tmp/claude-1000/p1-verify phase-1-channels`,
cd, `uv sync`. Remove + prune at the end. Temp channels dir for any writes.

## Task
1. Review `9b03d0d..phase-1-channels` with the `python-review` skill. For each of
   R1–R9 and Q1–Q7: resolved / partial / not. Trace each fix **end to end through the
   CLI** (exit code, stderr, stdout clean under `--json`), not just the store function.
2. Re-run only the QA checks whose inputs changed: 7 (all error cases incl. `/abs`
   slug, malformed YAML in channel.yaml *and* in a review file), 10 (hand-edit:
   unknown key, slug ≠ dir), 11 (identical `created_at`, plus `-10` vs `-2`), and the
   happy path of 6 (agent approve → candidate → human approve → approved).
3. Judge the fix's design choices: fail-loudly on one broken file (does one typo
   now block every `list` and `add` — acceptable for files-as-truth, or should `show`
   of a healthy channel still work?); the "-N is a suffix only if base exists" rule.
4. `uv run poe check` green; `channels list --json` = 15 candidates.

## Constraints
Read-only on the branch.

## Report
Return ONLY JSON (≤400 words):
{"round1": [{"id": "R1", "status": "resolved|partial|not", "note": ""}],
 "new_findings": [{"id": "V1", "severity": "", "file": "", "issue": "", "fix": ""}],
 "qa_ok": true, "qa_evidence": "", "verdict": "ship|fix-first"}
