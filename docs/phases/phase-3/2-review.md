# Phase 3 — review (report only)

See [context.md](./context.md) — required reading. Also [log.md](./log.md) (dev report).

## Scope
Commit range `0bbad42..phase-3-vetting`. Own worktree:
`git worktree add --detach /tmp/claude-1000/p3-review phase-3-vetting`, cd there,
`uv sync`. Remove + prune at the end. No `.env` there: never call the real API.

## Task
1. Invoke the `python-review` skill (Skill tool) over that range.
2. Logic judgement (QA covers runtime/env; don't duplicate):
   - Rubric/flags/verdict rule match context.md exactly (boundaries 365 d / 5 videos,
     approve→unsure downgrade, suitability computed in code, Shorts never sent).
   - Output validation: missing/extra/duplicate video ids; scores out of range.
   - Append-only: no path overwrites a vet report or review; ordering logic reused,
     not copied (cf. phase-2 backlog V1 on name vs timestamp ordering).
   - Re-vet skip compares the right timestamps (timezone/format round-trip).
   - Claude call: SDK usage matches the claude-api skill (load it): beta parse +
     fallbacks, effort, refusal handling, error class chain, no key in messages.
   - Prompt: deterministic, stable system first, rubric shared with phase 5.
   - Store API fit for phase 4 (no click/rich).
   - Docs (0005, CLAUDE.md, architecture.md) match code.
3. Judge each dev `deviation` in log.md: accept, or finding.
4. Reproduce where cheap (fake client, temp channels dir).
5. Number findings R1, R2…; pre-existing issues in untouched code → `preexisting`.

## Constraints
Read-only. Do NOT edit or commit on the branch.

## Report
Return ONLY JSON (≤500 words):
{"findings": [{"id": "R1", "severity": "high|medium|low", "file": "", "issue": "", "fix": ""}],
 "deviations_judged": [{"deviation": "", "ruling": "accept|finding Rn"}],
 "preexisting": [""], "verdict": "ship|fix-first"}
