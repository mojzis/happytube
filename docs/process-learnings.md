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

## Phase 3 (2026-10-28)

Source: `docs/phases/phase-3/` (agent vetting, real Claude API, 4 agent steps +
orchestrator probe and committed run). Loop run: dev → review ‖ QA (QA runtime-only)
→ fix → combined verify → orchestrator real run, as planned.

### Loop design
- **Decide open design questions with the user up front, as one multiple-choice
  question.** Four choices (input, output, re-vet, model) took one exchange. Dev had
  nothing left to invent, and no finding was about shape.
- **Exploratory dev run, committed run after verify (phase 2 lesson applied).** It
  paid off. R1 changed how the Claude call works. Data from the old call would have
  stayed in the append-only registry. The committed run used the verified code.
- **A blocked dev real run moves real-API checking to the end.** Review, QA, fix and
  verify all used fakes. The orchestrator's 1-channel probe after the user's key fix
  was the first real call. It worked, but only one probe stood between fakes and a
  committed run. Keep the probe step even when the dev run worked.
- Confirms phases 1–2: combined verify as round 2 was enough (8/8 resolved, 3 low,
  `ship`). One fix round, stop at `ship`, defer lows.

### Briefs & context
- **Routing each added question to one agent worked.** Review got the logic list
  (rubric, append-only, SDK shape), QA got runtime (no key, mid-run 401, collisions).
  Overlap dropped to zero: R1–R6 and Q1–Q4 are all distinct. Keep it.
- **Settled SDK choices are hypotheses too.** context.md settled `parse` +
  fallbacks. Review found that `parse` validates before it returns, so stop_reason
  can't be checked first. The "flag it, don't silently switch" clause covered it.
- **"Stop and report on credential failure" worked first time.** Dev stopped after
  one 401, wrote nothing, printed no key. Phase 2's rule is now proven in both
  directions.
- Check command lines in context.md by running them. The example put a group option
  after the subcommand.

### Agent reports
- **Review caught an SDK-shape issue that QA's fake could not.** A fake returns
  whatever the test wants. Only reading the SDK (with the `claude-api` skill) showed
  `parse` raises before stop_reason is visible. For external SDKs, ask review to
  check behaviour against the SDK source, not just the fake.
- Verify exercised the real SDK over an `httpx` MockTransport. That is the closest
  offline check to the real API and worth asking for by name.
- Ask for a run ledger on paid calls (tokens, cost per channel). It made variance
  visible: the same channel scored 45/50 then 39/50.

### Tooling gotchas
- **Click group options go before the subcommand**:
  `happytube channels --channels-dir X vet …`, not `vet … --channels-dir X`.
- Credentials in `.env` are a recurring blocker (2 phases in a row). Only the user
  fixes them. A 1-call probe before the batch makes the failure cheap.
- Model scoring is not deterministic. A second run of the same input is a cheap
  check of score stability.

### Answers to earlier open questions
- *Should dev commit real-run data at all?* (phase 2) No. Dev's run is exploratory on
  a scratch copy; the orchestrator commits after verify. Phase 3 did this and the
  committed data matched the final code.
- *Who fixes a bad credential?* (phase 2) The user, still. It worked: dev stopped,
  the user fixed it, the orchestrator probed.
- *Should the orchestrator eyeball real-data output?* (phase 2) Yes. It is cheap and
  it found the strict flags (army aircraft → war) and the run-to-run variance.
- *Full `poe typecheck` per commit?* (phase 2) The briefs required it; no broken
  intermediate commit this phase.

### Open questions (new)
- When dev's real run is blocked, should the loop pause for the user's fix, or carry
  on with fakes and probe at the end (as here)?
- Should model-scored output be run twice (or averaged) before it is committed?
- Is QA's fake-client runtime check worth its cost when the main risk is the
  external SDK shape, which only review and verify caught?

## Phase 4 (2026-10-28)

Source: `docs/phases/phase-4/` (local review UI, FastAPI + htmx, 4 agent steps + 1
orchestrator CSS fix). Loop run: dev → review ‖ QA (QA runtime + real browser) →
fix → combined verify → learnings, as planned. No external API.

### Loop design
- **First phase with a real browser check by QA (Chrome tools).** Curl had covered
  every route and status code. The browser added what curl can't see: htmx swaps,
  `hx-push-url` and the back button, the OOB badge, the 422 form in place, cookie
  prefill after reload, console errors, which hosts the page loads from, and layout
  (Q4 columns). In verify it was the only proof that the R1 alert JS works; the fix
  agent had no browser and listed that as unresolved. For any UI phase, put a
  browser check in QA and in verify.
- Review still found the most important UI bug (R1, silent htmx errors) by reading
  the vendored htmx source and reproducing with TestClient. The browser confirmed
  the fix. Review and browser QA complement each other; neither replaces the other.
- Confirms phases 1–3: one fix round, combined verify as round 2 (all resolved, one
  partial, `ship`), stop at `ship`, defer lows.
- **Orchestrator self-fix rule in practice:** V2 was one CSS line, no logic, logged
  in log.md, committed with the verify log. V1 (`--host 0`) needs code and a test,
  so it went to the backlog. Same line as phase 1: cosmetic or doc → orchestrator;
  code → backlog or a loop.

### Briefs & context
- **All four design decisions (reviewer identity, scope, local-only, location)
  settled with the user in one multiple-choice question up front.** Second phase in
  a row. Again no finding was about shape.
- **Safety rules spelled out in context.md (Host, Origin / Sec-Fetch-Site,
  autoescape, vendored JS) gave review a checklist.** Review and verify tested
  bypasses (forged Origin, odd IPv4/IPv6 Host forms) instead of asking whether there should
  be a check. For a local app that writes files, put the threat model in context.
- A settled detail can still be wrong: "non-loopback `--host` is allowed" did not
  cover wildcard binds, which a Host check makes useless. Dev flagged it as
  unresolved; review made it R2. The "flag it, don't silently switch" clause covered
  a design detail here, not only external facts.
- Routing added questions to one agent (logic → review, runtime/browser → QA) held.
  Only one duplicate (Q2 = R2), found independently.
- Fix brief with must-fix / do-NOT-fix lists and a stated preference per option
  (e.g. Q1: probe or friendly error, "say which") worked again.

### Agent reports
- Dev's `unresolved_issues` named exactly the two gaps that became findings
  (wildcard host, no browser check). Turning dev's unresolved list into review/QA
  checks keeps paying off.
- Fix agent reported "htmx alert JS not tried in a real browser" as unresolved;
  the verify brief then asked for that browser check by name. That chain worked.
- QA screenshots stayed in the session scratchpad, not committed. Enough for the
  orchestrator; the log records only what they showed.

### Tooling gotchas
- Chrome tools must be loaded via ToolSearch, and the `claude-in-chrome` skill read
  first. Agents worked in a new tab only.
- Background servers in agent steps: kill them and check the port is free; QA's
  port-in-use check (Q1) came from that brief line.
- `uv build` + install in a throwaway venv + run from another cwd is the cheap check
  that package data (templates, static) ships. It also surfaced Q3 (default paths
  resolve inside the venv).
- deptry and vulture need entries for framework-loaded code (python-multipart,
  starlette, FastAPI decorators). Ask review to judge each ignore: justified or
  masking.

### Answers to earlier open questions
- *Is a dedicated QA agent worth it for a small, pure-logic phase?* (phase 1) This
  phase was UI, not pure logic. For UI, yes: the browser check, wheel install and
  concurrent CLI + web writes were all QA-only evidence. Pure-logic phases are still
  open.
- *When may the orchestrator fix trivially itself?* (phase 0) Evidence for the rule
  so far: doc rewording (phase 1) and one CSS line (phase 4), after `ship`, logged.
  Code with behaviour goes to the backlog.
- *Should final verify always run?* (phase 0) Four phases, verify ran each time and
  found 1–3 new lows each time (here V1, V2). Keep it.
- Credential questions (phases 2–3): no evidence this phase; no API keys were
  involved.

### Open questions (new)
- Should browser screenshots be kept (committed or attached to the PR), or is the
  log's description enough?
- Should the browser check move into dev's real run for UI phases, so fix agents
  can also see their change?
- Should vendored assets (htmx) get a check (hash vs header comment) in `poe check`?

## Phase 5a (2026-10-28)

Source: `docs/phases/phase-5a/` (trusted fetch + rubric assess + enhance, 4 agent
steps after dev + 1 orchestrator real probe). Loop run: dev → review ‖ QA → fix →
combined verify → orchestrator probe → learnings, as planned. Real paid APIs.

### Loop design
- **Review found a design gap that context.md had settled.** "Assess/enhance read
  only `--date`" plus "any failing step stops `run`" strands videos for good (R1).
  Not an external fact this time: a settled rule that was wrong in its
  consequences. Phase 4 had a settled detail go wrong; this one was bigger.
  Ask review to trace multi-day and partial-failure scenarios against the rules.
- Review and QA found the same bug independently (R2 = Q1), by logic and at
  runtime. Confirms phase 4: one duplicate, no wasted round.
- Verify again found only lows (V1–V5). Confirms phases 0–4: keep verify; one fix
  round is enough when verify says `ship`.
- **Orchestrator real probe after verify** (scratch copy, 2 channels, 6 units,
  $0.05) gave fresh eyes on real output from the fixed code. Cheap; keep it for
  phases that call paid APIs.

### Briefs & context
- **The orchestrator decided the R1 fix design in the fix brief** (pending up to
  `--date`, output under the fetch file's date, `--force` stays `--date` only, `run`
  stops only on quota / key / credit). The fix agent built it with no questions.
  When review offers two fixes, pick one in the brief.
- Dev's real-run brief (probe first, ≤1 USD cap, stop on credential failure, nothing
  committed from scratch) worked first time. Keys were valid; the probe preceded
  the full run.
- "Added after dev" checks, routed to one agent each, held again. Review's SDK
  check against `.venv` source (not fakes) confirmed the extracted Claude call.

### Agent reports
- Dev's `unresolved_issues` had one wrong worry (quota stop mid-channel leaves
  files). Review disproved it cheaply. An unresolved item is a question, not a
  finding.
- The fix agent's unresolved item (stale scores in a re-enhanced file) became a
  verify question and then a 5b rule: readers take scores from assess.
- Dev's eyeball field (counts per channel, two example notes) made the product
  finding visible: BBC Earth 1/8 suitable.

### Tooling gotchas
- zsh (the orchestrator's shell) does not word-split variables:
  `H="uv run happytube"; $H trusted …` fails. Use a shell function.
- Real keys: `set -a; . .env; set +a` in the scratch cwd; never echo them. QA and
  verify used fake keys only and checked no key text reached any output.

### Answers to earlier open questions
- *When dev's real run is blocked, pause or carry on?* (phase 3) Not tested: the
  run was not blocked. The probe-first rule meant a block would have cost 1 call.
- *Should the orchestrator eyeball real-data output?* (phase 2) Yes, and it worked
  best as its own small probe after verify, on the final code.
- *Should dev commit real-run data?* (phase 2) Dev committed nothing from scratch;
  the run was reported only. No loss. Keep it that way until 5b needs real data.
- *Is QA's fake-client check worth it when the risk is the SDK shape?* (phase 3)
  Here QA found two lows (Q2, Q3) and the R2 bug independently; review owned the SDK
  check. Worth it for a CLI with many exit paths.

### Open questions (new)
- Should context.md list the failure scenarios (one channel fails, quota mid-run,
  rerun next day) so dev designs for them, not review?
- Should the orchestrator probe after verify be a named step in the loop?
- Should model scores be checked for drift across runs (same video, re-scored)
  before 5b shows them?

## Phase 5b (2026-10-28)

Source: `docs/phases/phase-5b/` (trusted player, 5 agent steps after dev + 1
orchestrator probe). Loop: dev → review ‖ QA → fix → combined verify → probe.

### Loop design
- Failure scenarios listed in context.md (5a open question → yes): dev handled
  all, review found no selection logic gap; findings moved to shell glue and
  deploy wiring.
- QA running the shell script against a bare remote with a stubbed `uv` found the
  only medium (failed push never retried). Give scripts a runtime QA item.
- One fix round + combined verify held again (0–5b).
- Probe on dev's existing real scratch data: final code, no paid calls.

### Briefs & context
- Open choices as one question call (3 questions, recommended option first) + a
  "settled by the orchestrator, dev may argue" list: one round trip with the user.
- Safety defaults (hide a later-rejected channel's videos) can be settled by the
  orchestrator and stated, not asked.
- One-time external steps the user asks for (Pages enable via `gh`): do them,
  message the running dev, log it.

### Tooling gotchas
- `pkill -f` from the Bash tool can match its own shell (exit 144); use pgrep/pid.

### Open questions (new)
- Default runtime QA item for any phase that touches `scripts/`?


## Phase 5c (2026-10-29)

Source: `docs/phases/phase-5c/` (video spot-checks, 4 agent steps after dev + 1
orchestrator probe). Loop: dev → review ‖ QA → fix → combined verify → probe. No
paid calls in the whole phase.

### Loop design
- Failure scenarios in context.md held again (10 listed, all QA-seeded cases
  passed). The mediums came from cases outside the list.
- Review and QA overlapped on the medium (R2 = Q1, undecodable review file → 500s):
  logic and runtime found the same bug, as in phases 4 and 5a.
- One fix round + combined verify held again (0–5c); verify found info items only.
- The orchestrator added a review item from a dev deviation (queue skips assess
  files lacking snapshot fields); it became R1 medium (shown videos unhideable).

### Briefs & context
- Four open choices in one question call, recommended first; the user took all
  four. Rest settled by the orchestrator; dev deviated on details only.
- Fix brief picked the fix design per finding and named repros for verify; both
  worked without questions.

### Agent reports
- A dev `deviation` can be a finding. Trace each against the phase goal before
  review, or give review that item.

### Answers to earlier open questions
- *Should context.md list the failure scenarios?* (5a) Second phase with yes: dev
  designed for all, QA's seeded cases passed. Findings move to cases not listed.
- *Should the orchestrator probe after verify be a named step?* (5a) Ran in 5a,
  5b and 5c, cheap each time (here no paid calls). Treat it as a step.
- *Default runtime QA item for phases touching `scripts/`?* (5b) No evidence: 5c
  touched no scripts (only `deploy.yml` paths; QA's CI simulation covered it).
- *Model score drift across runs?* (5a) Not checked; 5c stores the agent call the
  human saw (snapshot), so later spot-check stats can measure it.

### Open questions (new)
- Routine review item: "trace each dev deviation against the goal"?
- Guard reviews posted without `assessed_at` (curl, hand edits), or is the UI
  path enough?
