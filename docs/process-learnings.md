# Process learnings (cumulative)

Phase-independent lessons for the runner skill (dev → review ‖ QA → fix → review ‖ QA
→ learnings → next-session). Newest phase notes appended under its own heading.

## Phase 0 (2026-10-28)

Source: `docs/phases/phase-0/` (template alignment, 7 agent steps + 1 orchestrator fix).

### Loop design
- Two fix rounds were not enough; a third read-only "final verify" step found the real
  cause of a metric swing. Budget: fix rounds until review verdict is `ship`, cap ~3.
- Review catches what QA can't: logic on untested paths (interactive script branch,
  swallowed exception). QA catches env facts review can't (Python version, hook
  needs venv, concurrency). Keep both; neither substitutes.
- Round-2 review must re-trace each fix **end to end** (CLI exit code), not just the
  changed function — the r1 error-handling fix was swallowed one layer up.
- Round-2 QA re-running all round-1 checks is mostly noise; rerun only checks whose
  inputs changed (diff-gated, like the hook test skip) plus fix-specific checks.
- Final verify as a single combined review+QA agent on a small diff worked well.
- Orchestrator doing a one-line fix (`__init__.py`) itself was fine and saved a loop.

### Briefs & context
- context.md with module map, path gotchas and verification baseline prevented
  re-exploration; worth the upfront cost.
- Orchestrator appending "added after dev" checks to review/QA briefs, derived from
  the dev report's deviations, targeted exactly the risky changes. Make this a step.
- Fix briefs need three lists: must-fix, also-fix (promoted preexisting), do-NOT-fix
  (deferred). The do-not list kept scope tight.
- Number findings (SF1…) so later rounds can reference them unambiguously.
- Ask for explanations of metric changes explicitly ("coverage moved X→Y: why?") —
  agents otherwise rationalise them.

### Agent reports
- Strict JSON schema with word cap: scannable, pasteable verbatim into log.md.
- `preexisting` bucket separate from `findings` keeps verdicts honest and surfaces
  real bugs for promotion.
- `deviations` field is where the important judgement shows (targeted lock upgrade,
  key-leak-safe exception). Always require it.
- Agents' baseline claims can be wrong ("18d0ed6 also 51%") — verify numbers that
  justify "not a regression" in a clean worktree before accepting.
- `verified: true` from QA ≠ requirement met; QA only proves what its checks test.

### Tooling gotchas
- madoqua hook needs `.venv` per worktree: `uv sync` in every new worktree first, or
  commits are blocked ("no virtualenv").
- Parallel pytest in one checkout collides on `.coverage` (INTERNALERROR
  `coverage_schema already exists`). Run review ‖ QA in separate worktrees, or set
  `COVERAGE_FILE` per agent.
- Missing package `__init__.py` under src layout → namespace package → coverage only
  counts imported modules; percentage swings as tests import more. Check early.
- No `.python-version` → uv picks newest interpreter (3.13) while CI uses 3.12.
- `requests.HTTPError` message contains the URL → leaks API keys passed as params.
- Blanket `uv lock --upgrade` pulls majors; use `--upgrade-package` for vuln fixes.
- vulture at 60% flags framework-registered names (click, Flask routes, pydantic);
  needs `ignore_decorators` / whitelist before dead-code is useful.
- Scratch worktrees under `/tmp/claude-1000/`; remove + prune after.

### Open questions for the skill
- Fix-round cap and exit rule: stop at `ship`, or at N rounds with leftovers deferred?
- When may the orchestrator fix trivially itself (one-liner, no logic)? Needs a rule
  (e.g. ≤5 lines, hook passes, logged in log.md) to avoid bypassing review.
- Parallel review ‖ QA: separate worktrees by default? Who owns `uv sync` there?
- Should final verify always run, or only when round-2 left partials / unexplained
  metrics?
- Should QA include an end-to-end "failure path" check per fix (exit codes, logs)?
- Who decides promotion of `preexisting` → fix: orchestrator alone, or ask user?
- Where does the deferred backlog live across phases (next-session.md vs a file)?
