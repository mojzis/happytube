# Phase 0 — learnings (template alignment)

Branch `phase-0-template`, `a336adc..ec4330c`, 19 commits, 2026-10-28.
Loop actually run: dev → review ‖ QA → fix → review ‖ QA → fix → final verify
(review + QA in one agent) → orchestrator one-liner → learnings.

## Delivered

- src layout (`git mv`), template pyproject (dev group, ruff/ty/pytest-cov/vulture/
  deptry/interrogate/madoqua/biston/poe), madoqua hook, dependabot, merged
  `.gitignore`, `.python-version` 3.12, `src/happytube/__init__.py`.
- Legacy deleted (main, mq/tmq, mb, nb, yt*, claude, ip*, utils.py, .dlt, ip.sh);
  deps pruned (dlt, google-auth-oauthlib, google-api-python-client, ipython, marimo);
  pyyaml/requests/pydantic declared.
- docs scaffold: constitution, architecture, naming, decisions 0001/0002, research/.
- Real bugs fixed on the way: YTKEY never sent (`__post_init__` skipped super),
  `YtQuery.get` silently returned empty data, fetch/run-all exited 0 on API errors,
  `deploy_web.sh` cd bug, 21 vulns → 0 (targeted lock upgrades).
- Tests 30 → 46; `poe check` green; honest coverage 45% (931 stmts).

## What worked

- **context.md with a module map and path gotchas.** Dev did not re-explore; every
  listed gotcha (`parent.parent.parent`, deploy.yml, deploy_web.sh) was handled.
- **Orchestrator appending targeted checks to briefs after reading the dev report**
  (autoescape, print→logging, zorilla test refactors). QA step 13/14 confirmed the
  riskiest runtime-affecting lint fixes were safe instead of leaving it to guesswork.
- **Strict JSON report schemas.** log.md is scannable; round-2 briefs could reference
  findings by id (SF1–SF5).
- **"preexisting" bucket in review.** It kept round 1 focused while still surfacing the
  YTKEY bug, which the orchestrator then promoted into the fix brief.
- **Explicit "do NOT fix (deferred)" list in fix briefs** — fix agent stayed in scope.
- **Fix agent judgement on deviations**: targeted `--upgrade-package` instead of blanket
  `uv lock --upgrade` (would have pulled anthropic 2.x, pandas 3); custom
  `YouTubeAPIError` because `HTTPError` text contains the key-bearing URL.
- Hooks never bypassed; every commit passed madoqua.

## What each step caught that the previous missed

- **Dev (1)** self-reported the unresolved YTKEY bug, data/fetched orphan, 21 vulns.
- **QA r1 (2a)** found environment facts dev didn't: venv was 3.13 (no
  `.python-version`), madoqua hook needs `.venv` in a fresh worktree, parallel pytest
  breaks the shared `.coverage` combine (it hit that itself — review ran concurrently),
  `report` needs API keys though it calls none, runpy warning.
- **Review r1 (2b)** caught the `deploy_web.sh` `cd ../../..` bug (high) that QA's
  read-through and dev's run missed (only on the interactive path), server/export
  loader drift, two path anchors, silent `except Exception` in `df_from_stage_dir`.
- **Review r2 (4a)** caught that the fix for "YtQuery silently returns empty" was
  **swallowed**: `FetchStage.run`'s catch-all turned `YouTubeAPIError` into
  `{errors: 1}` and exit 0, so `daily_run.sh`'s `set -e` never fires. QA r2 passed
  everything — its checks tested `YtQuery` in isolation, not the CLI exit code.
  Also: tautological `test_today_local`, new warn path untested, config message
  printed before the stage header.
- **QA r2 (4b)** caught deploy_web.sh dead `$?` under `set -e`, system `python` vs
  `uv run`, 29 vulture false positives; verified pyarrow 26 parquet round-trip.
- **Final verify (6)** found the **missing `src/happytube/__init__.py`** (pre-existing,
  namespace package) as the cause of the 70% → 51% coverage swing: coverage only
  counted imported modules, and new `test_cli.py` pulled in 540 more statements.
  It also **refuted the fix agent's claim** that 18d0ed6 "also gives 51%" (measured
  70% in a fresh worktree). True figure with `__init__.py`: 45%. Also: fetch
  catch-all still hides Timeout/ConnectionError/KeyError; quota error fixtures use the
  wrong body shape (`error.errors[0].reason`, not `error.message`); SF4 still
  partially pins the implementation.

## Friction

- Fix agent r2 contradicted itself on coverage: reported 51% as "not a regression"
  with an unreproducible baseline, rather than flagging the swing as unexplained.
  Cost an extra investigation item in step 6.
- Coverage number was untrustworthy for the whole phase (62% → 70% → 51% → 45%)
  because of the namespace-package issue; nobody noticed until asked directly.
- Parallel review ‖ QA in the same checkout collided on `.coverage` (first QA
  `poe check` INTERNALERROR). Harmless, but it looked like a failure.
- Round 2 needed a third pass (step 6) — the plan's loop budgeted two rounds.
- QA r2 re-ran ~12 round-1 checks that could not have regressed (help output,
  template files present) — mostly cheap but noisy.

## Wasted effort

- Step 4b's green "verified: true" gave false comfort on the swallowed-error path —
  QA checks were unit-level where the requirement was end-to-end (exit code).
- The weak `test_today_local` was written in fix r1, flagged in r2, rewritten, and
  still flagged partial in step 6 — three passes on a trivial helper test.
- Fix r2's coverage baseline measurement (wrong) + step 6 re-measuring in a worktree.

## Deferred backlog

- `FetchStage.run` catch-all hides network/parse errors (exit 0) → phase 5 rewrite.
- Web player/export read `data/fetched/` (no writer) → should read `stages/` (phase 4/5).
- `report` (and others) require YTKEY/ANTHROPIC_API_KEY though they call no API.
- runpy RuntimeWarning on `python -m happytube.web.*` (web/__init__ imports server).
- 8 real dead-code hits: get_prompt_config, get_config_manager, setup_logging,
  get_logger, store_locally, get_list_for_claude, get_csv, Videos.
- Quota error body shape: parse `error.errors[0].reason`; fix test fixtures.
- Test nits: run-all CLI test lacks key-leak assert + duplicated setup; `_response`
  pairs 500 with "Forbidden"; `test_today_local` still pins `.astimezone()`;
  `r.args[0]` brittle; `test_stage_with_empty_directory` only tests `Path.glob`.
- `deploy_web.sh` reports "0 videos" as success.
- vulture `ignore_names` is global; a whitelist module would be tighter.
- Stage dirs relative to cwd; `PROJECT_ROOT` assumes source/editable checkout →
  add `data_root` setting.
- Search/Videos `__post_init__` overwrite a constructor `params=`.
- Coverage 45%; web/* and utils/logging.py at 0%.
