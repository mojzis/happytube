# Phase 0 — dev

See [context.md](./context.md) — required reading. Do NOT re-explore what it already documents.
Plan: `docs/plan.md`.

## Task
Align the repo with `/home/matous/git/python-template` and delete legacy code, as
described in context.md: src layout, pyproject (dev group, ruff/ty/pytest/coverage/
vulture/deptry/interrogate/madoqua/biston/poe config), hooks/pre-commit + madoqua
install, dependabot, .gitignore merge, CLAUDE.md merge, path fixes for the src move,
legacy deletion + dep cleanup, docs/ scaffold with decisions 0001 and 0002.

## Out of scope
New features, behaviour changes to stages, rewriting tests beyond what lint/move needs.
Don't touch `docs/plan.md`, `docs/next-session.md`, `docs/phases/`.

## Mode
Make it work and clean enough to commit. Review nits belong to the review step.

## Contract
- Use `git mv` for the src move so history follows.
- Commit in logical chunks (e.g. tooling+move, legacy deletion, lint fixes, docs).
  Hooks must pass. No `--no-verify`, no `MADOQUA_SKIP`. Do NOT push.
- Before finishing: `uv sync`, `uv run poe check`, `uv run happytube --help` all OK.
- Commit `docs/phases/` + `docs/plan.md` + `docs/next-session.md` (already written by
  the orchestrator, untracked) in your first commit as-is.

## Report
Return ONLY this JSON (≤400 words):
{"commit_shas": [], "summary": "", "deviations": [], "unresolved_issues": [],
 "ignores_added": ["rule + scope + why"], "check_output_tail": ""}
