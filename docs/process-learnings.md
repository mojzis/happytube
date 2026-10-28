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

## Phase 1 (2026-10-28)

Source: `docs/phases/phase-1/` (channel registry, 5 agent steps + 1 orchestrator
doc fix). Loop run: dev → review ‖ QA → fix → combined verify → orchestrator.

### Loop design
- **One combined review+QA verify as round 2 was enough** when round 1 found no
  high-severity logic in untested paths and the fix touched one module: all 16
  round-1 ids resolved/justified, 3 low new findings, `ship`. Answers phase 0's
  "should final verify always run": make the combined verify *the* round 2 for small
  diffs; split review ‖ QA again only for large or high-risk fixes.
- **Review and QA overlap heavily on a small, well-specified feature** (6 of 7 QA
  issues duplicated review findings). Both briefs asked the same edge cases
  (traversal, malformed YAML, ties). Either give QA only runtime/env checks and
  review only logic, or accept the overlap as cross-confirmation — but don't send
  the same orchestrator-added question to both.
- The fix round is where new edge bugs come from (V3 came from the fix's own
  "-N only if base exists" rule). The verify brief should explicitly ask to judge
  each design choice listed in the fix's `deviations`.
- Exit rule evidence: stopping at `ship` with low findings deferred worked; no
  second fix round was needed.

### Briefs & context
- Settling all design decisions in context.md (layout, status rule, fields, CLI
  contract) left dev nothing to invent; review findings were about edges, not shape.
- Confirmed: orchestrator checks added from dev's `unresolved_issues` hit — they
  produced 3 of 6 medium findings.
- Fix brief: merge duplicate ids (`R1 (Q2)`) and pre-decide open design options with
  a stated preference; the fix agent then reports which it took in `deviations`.
- Reviewers who reproduce (run the CLI in a temp dir) give findings with evidence;
  say "reproduce where cheap" in review briefs.

### Agent reports
- Asking QA for positive evidence (what was verified and how) is useful even when
  findings duplicate review — it is what proves no-keys runs, unicode on disk and
  concurrent writes.

### Tooling gotchas
- **Separate worktrees for review ‖ QA work** — no `.coverage` collision. Each agent
  runs `uv sync` in its own worktree and removes + prunes it at the end (answers phase
  0's "who owns `uv sync`": the agent that creates the worktree).
- `git worktree add <path> <branch>` fails when the branch is checked out in the main
  checkout; read-only agents must use `git worktree add --detach <path> <branch>`.

### Orchestrator self-fixes
- Phase 1 rule in practice: a doc-only reword (V3 → decision 0003) after `ship`, no
  code, logged in log.md, committed with the reports. Fine. Code fixes, even small
  ones (V1, V2), went to the backlog instead of a new loop.

### Open questions (new)
- Should the log.md header be updated to the loop actually run, or should it only
  record the plan and the learnings record deviations?
- Is a dedicated QA agent worth it for a small, pure-logic phase, or should
  combined review+QA run in round 1 too?

## Phase 2 (2026-10-28)

Source: `docs/phases/phase-2/` (channel evidence, real YouTube API, 4 agent steps +
1 orchestrator data commit). Loop run: dev → review ‖ QA (QA runtime-only) → fix →
combined verify, as planned.

### Loop design
- **Real external calls belong in the loop.** The dev step's real run found what no
  mock could: a wrong settled rule (Shorts ≤180 s) and a look-alike channel that
  resolved "successfully". For phases that touch an external system, keep a real
  run in dev, even if only as research.
- **Dev's real-run data should not be committed before review.** Dev committed
  snapshots computed by a rule the next step overturned. Append-only data then stays
  wrong until a re-run. Better: dev's real run is exploratory. The committed run
  comes after the fix, or after verify.
- **Plan for a blocked real re-run.** The fix step's re-run was blocked by a bad
  credential, and the phase shipped without it. The learnings and next-session must
  carry the re-run as an explicit pending step.
- Confirms phase 1: combined verify as round 2 was enough (9/9 resolved, 6 low,
  `ship`). Asking verify to judge the fix's deviations found V2 again.
- Confirms phase 0's exit rule: one fix round, stop at `ship`, defer lows.

### Briefs & context
- **Settled decisions about external behaviour are hypotheses.** context.md settled
  the Shorts rule from general knowledge. The "flag it in deviations, don't silently
  switch" clause turned the wrong rule into a one-round fix, not a silent change or a
  redesign loop. Keep that clause in every context that settles external facts.
  Cheaper still: one research spike before settling.
- **Every brief with real credentials must say what to do when they fail.** "Stop
  and report" is the rule. The dev brief didn't say it, and dev truncated the key in
  a scratch wrapper. The fix brief said it, and the fix agent stopped after 1 unit.
- **Add a 1-call credential probe before a batch run.** The batch run spent 15
  calls on a bad key before the early stop existed.
- **Phase 1's "don't send the same orchestrator-added question to both" was not
  applied.** Four added questions went into both review and QA briefs, and both
  answered them. Without them, QA's runtime-only base checks had almost no overlap
  with review. Route each added question to one agent: logic → review,
  data/runtime → QA.
- Human-judgement questions found during a phase (identity, activity, unknown
  handles) go into the product's own data where it has a place for them (here:
  agent `unsure` reviews). That beats a doc note: the tool surfaces them.

### Agent reports
- **`deviations` must include unauthorized workarounds, and the orchestrator must
  rule on them.** Dev reported the key truncation honestly. The orchestrator then
  asked review and QA to confirm nothing landed, and the fix brief forbade a repeat.
  Keep this three-step response.
- QA found an undeclared deviation (Q3: `resolve` re-verified resolved channels,
  costing units). Review missed it. Runtime checks with a cost counter catch
  behaviour that reads fine in code.
- Ask dev for a cost ledger when calls cost money or quota. Dev's report split units
  by purpose (resolve, evidence, rerun, probes), which made the overspend visible.

### Tooling gotchas
- **The staged-only `ty` hook does not catch cross-file type breakage.** A commit that
  changes a type in one file (settings → `SecretStr`) passes while an unstaged
  caller breaks. Run `uv run poe typecheck` before each commit of a multi-commit fix.
  The user prefers regular merges (full history, imperfect intermediates accepted)
  over squash-merge.
- **Secret grep**: plain `git grep AIza` hits the briefs that mention the pattern.
  Use a key-shaped regex (`AIza[0-9A-Za-z_-]{20,}`) over trees and `git log -p`.
- Tests that build `Settings` read `.env` relative to cwd. Once a real `.env` exists,
  "missing credentials" tests must `chdir(tmp_path)`.
- An identity check like `forHandle` returning an id is not proof of identity.
  Store human-checkable fields (title, custom_url, subscribers) in the snapshot and
  look at them.

### Answers to earlier open questions
- *Is a dedicated QA agent worth it for a small phase?* (phase 1) For a phase with
  external I/O, yes. Runtime-only QA found Q3, the pre-2024 Shorts rule and the
  inactive channel, and gave the positive evidence on key safety. For a pure-logic
  phase it is still open.
- *Should the log.md header record the plan or the loop run?* (phase 1) Labelling it
  "Loop (planned)" worked. Learnings record deviations from it.
- *Where does the deferred backlog live?* (phase 0) Code items: `docs/plan.md`
  backlog section plus phase learnings. Human content questions: the registry
  itself (agent reviews).
- *Who decides promotion of `preexisting` → fix?* (phase 0) The orchestrator alone
  promoted the `videos.py` key leak (security, minimal change), and it was fine.
  Non-security preexisting items stayed deferred.
- *Should QA include an end-to-end failure-path check per fix?* (phase 0) Yes. QA's
  quota-mid-run check found Q2, which matched review's R1.

### Open questions (new)
- Should dev commit real-run data at all, or only report it, with the committed run
  after verify?
- Who fixes a bad credential: always the user, or may the orchestrator ask the user
  for permission to work around it? The rule today: user only.
- Should the orchestrator itself eyeball real-data output (titles, counts) after
  dev, or is that a QA check by default?
- Should multi-commit fix steps run full `poe typecheck` per commit? (Squash-merge is
  out: the user keeps full history.)
