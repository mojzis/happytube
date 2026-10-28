# Phase 0 — review (report only)

See [context.md](./context.md) — required reading.

## Scope
Commit range `a336adc13b020ac763210884b50ad72b071e08d0..HEAD` on branch `phase-0-template`.
Also read `log.md` (dev report: deviations, ignores added).

## Task
1. Invoke the `python-review` skill (Skill tool) over that range.
2. Additionally judge, specific to this phase:
   - Does pyproject match the template faithfully (sections present, sensible
     adaptations, no leftover `optional-dependencies`, runtime vs dev deps correct)?
   - Is every ruff/ty ignore justified and as narrow as possible?
   - Was anything deleted that kept code still needed, or legacy left behind?
   - Path fixes after the src move: robust, not just `.parent` stacking in many places?
   - CLAUDE.md / README / DEPLOYMENT accurate for the new layout, no stale commands?
   - docs/ scaffold content true to the idea doc.
3. Pre-existing issues in untouched logic: list separately as `preexisting`, don't
   count them as findings.

## Constraints
Read-only. Do NOT edit or commit.

## Report
Return ONLY JSON (≤500 words):
{"findings": [{"severity": "high|medium|low", "file": "", "issue": "", "fix": ""}],
 "preexisting": [""], "verdict": "ship|fix-first"}

## Dev deviations to cover (added by orchestrator)
- Runtime-affecting lint fixes: Jinja autoescape on the HTML report (does the report
  template now double-escape or break intentionally-HTML content?), requests timeout,
  print→logging (CLI user-facing output lost?), local-tz dates, date.fromisoformat,
  server reusing export.extract_video_info, new `src/happytube/paths.py`.
- Test refactors for zorilla — did they weaken any assertion?
- Known unresolved (judge severity, propose fix): web/export read `data/fetched/`
  (no producer left); `videos.py` YTKEY never set (Search/Videos skip
  YtQuery.__post_init__); 21 vulns (would `uv lock --upgrade` be safe?).
