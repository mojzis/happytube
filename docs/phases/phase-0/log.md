# Log: phase 0 — template alignment

- Plan: `docs/plan.md`, context: `./context.md`
- Branch: phase-0-template · base a336adc13b020ac763210884b50ad72b071e08d0
- Loop: dev → review ‖ QA → fix → review ‖ QA → learnings

## 2026-10-28 · bootstrap
- User decisions: delete legacy (incl. failed queue experiments mq/tmq); research env = files + CLI (agents) + web UI (humans); runner skill TBD.

## Step 1 — dev (verbatim report)
```json
{"commit_shas": ["dee1460", "d5560ec", "5ef0c02", "4b4f31e"],
 "summary": "Four commits: (1) phase docs as-is, madoqua hook, dependabot, merged .gitignore. (2) Removed the legacy modules, .dlt/ and scripts/ip.sh. Dropped dlt, google-auth-oauthlib, google-api-python-client (nothing imported it), ipython and marimo. Declared pyyaml and requests, which kept code imports but only got transitively. (3) git mv into src/happytube with py.typed and tests/__init__.py. Applied the template pyproject: dev group, all tool config and poe tasks; pytest moved to dev, pydantic declared. Added happytube/paths.py so web/server and web/export find the project root after the move. Fixed paths in the deploy workflow and scripts. Lint/ty fixes, hook passed with no bypass. (4) docs scaffold (constitution, architecture, naming, decisions 0001/0002, research/), modernization-plan moved to docs/research/ with a historical note, CLAUDE.md merged, README/DEPLOYMENT/web docs moved from Poetry to uv. Verified: uv sync, poe check (exit 0), 30 tests pass, happytube --help and every subcommand --help work, web.export runs (0 videos), server imports.",
 "deviations": ["Renamed tests/utils_test.py to tests/test_utils.py (template naming).", "Dropped the <3.13 cap: requires-python = '>=3.12'; suite passes on 3.13.", "Lint fixes that change runtime a little: Jinja autoescape on the HTML report; requests timeout 30s; print replaced by logging; local-tz dates; date.fromisoformat replaces strptime; server reuses export.extract_video_info (biston clone); export's logging.basicConfig moved into main().", "Refactored 3 tests just enough for zorilla ZR001/ZR004 (helper _save_assessed, comprehensions, merged asserts) and replaced B017 pytest.raises(Exception) with ValidationError/yaml.YAMLError."],
 "unresolved_issues": ["The web player and export read data/fetched/, which only the deleted main.py wrote. run-all writes stages/, so the export yields 0 videos. Noted in CLAUDE.md and the web docs.", "Existing bug, not fixed: Search/Videos.__post_init__ in videos.py skip YtQuery.__post_init__, so the YTKEY is never put in params and real fetches likely fail.", "Vulns task: 21 vulns in 12 packages (urllib3, werkzeug, etc.); uv lock --upgrade would fix them, not done.", "vulture (check-all) flags 60%-confidence unused items: Flask routes, setup_logging/get_logger, videos.Videos, store_locally."],
 "ignores_added": ["ruff E501,W291 on src/happytube/prompts.py: prompt literals go to Claude verbatim", "ruff TRY003 on src/happytube/config/**: built-in errors with contextual messages, a custom class each adds nothing", "ruff noqa PLR0915 on cli/commands.py run_all: linear script driving four stages", "deptry known_first_party=[happytube] (src layout) and DEP002 ignore for pyarrow: pandas loads it for to_parquet"],
 "check_output_tail": "ruff: All checks passed! | zorilla: 0 findings | biston: No clones detected. | ty: All checks passed! | pysentry: 21 vulnerabilities (non-blocking, || true) | 30 passed in 1.76s | exit 0"}
```

## Step 2a — QA (verbatim report)
```json
{"verified": true, "checks": [
{"step": 1, "ok": true, "evidence": "Only docs/phases/phase-0/{2-qa,2-review,log}.md are modified, and those belong to the orchestrator. Log a336adc..HEAD has 4 commits: dee1460, d5560ec, 5ef0c02, 4b4f31e."},
{"step": 2, "ok": true, "evidence": "rm -rf .venv && uv sync succeeded. The venv is Python 3.13.13: requires-python is now >=3.12 and there is no .python-version file."},
{"step": 3, "ok": true, "evidence": "Clean on 4 reruns (rc=0). ruff 'All checks passed!', ty 'All checks passed!', zorilla '0 findings in 3 files', biston 'No clones detected', pysentry 21 vulns (2 critical, 7 high), non-blocking via || true, pytest 30 passed with 62% coverage. The very first run failed with a pytest-cov INTERNALERROR 'table coverage_schema already exists' while combining .coverage. It did not come back, so it was most likely another agent running pytest in the same checkout at the same time."},
{"step": 4, "ok": true, "evidence": "30 passed in 0.95s"},
{"step": 5, "ok": true, "evidence": "happytube --help lists assess, enhance, fetch, report, run-all, status. Each subcommand's --help exits 0."},
{"step": 6, "ok": true, "evidence": "status runs with no data, no .env and the API keys unset: it shows a Rich table with every stage 'Not started', rc=0."},
{"step": 7, "ok": true, "evidence": "Reports 'Exported 0 videos to /home/matous/git/happytube/src/happytube/web/static/videos.json'. That file is tracked and was left unchanged."},
{"step": 8, "ok": true, "evidence": "Results: / 200, /api/videos 200 returning [], /api/videos/nonexistent 404, /static/player.js 200. Server was killed afterwards."},
{"step": 9, "ok": true, "evidence": "core.hooksPath=hooks. In a scratch worktree (after uv sync there) the hook ran ruff, ty, biston, zorilla and gerenuk on a staged .py commit. A commit with a ty invalid-return-type error was blocked. Worktree removed and pruned; the commits were detached and never touched the branch."},
{"step": 10, "ok": true, "evidence": "No live references remain. Hits: 'removed legacy happytube.main' notes in DEPLOYMENT.md and src/happytube/web/{README,DEPLOYMENT}.md, plus Poetry mentions in historical docs/research/modernization-plan.md, all intentional."},
{"step": 11, "ok": true, "evidence": "upload path is 'src/happytube/web/static'; the export step is 'python -m happytube.web.export'; uv python install 3.12."},
{"step": 12, "ok": true, "evidence": "All listed files exist and are tracked (hooks/pre-commit is executable)."},
{"step": 13, "ok": true, "evidence": "Ran happytube report in a temp directory with templates/ and a fake enhance fixture. No literal '&lt;div' in the output and the page structure (div/h2) is intact. User-supplied <script>, & and quotes are escaped as intended."},
{"step": 14, "ok": true, "evidence": "status and report still print readable Rich panels, tables and check marks at the default log level."}],
"issues": [
"The madoqua hook needs a .venv in the worktree. In a fresh worktree it fails with 'madoqua: no virtualenv … uv sync', so it blocks the commit rather than letting it through. This is expected, but worth documenting.",
"`python -m happytube.web.export` and `python -m happytube.web.server` print a runpy RuntimeWarning ('found in sys.modules after import of package'). Cause: web/__init__.py imports server, and server imports export. The warning was there before this phase too; harmless but noisy.",
"`happytube report` (every command except status) fails with a config error unless YTKEY and ANTHROPIC_API_KEY are set, even though report makes no API calls. This was already the behaviour before this phase.",
"The local venv is Python 3.13 while CI installs 3.12. Not a bug, but the two environments differ.",
"Running pytest concurrently in the same checkout can break the coverage combine step (shared .coverage file)."]}
```

## Step 2b — review (verbatim report)
```json
{"findings": [
 {"severity": "high", "file": "scripts/deploy_web.sh:47-49", "issue": "After the src move the script does `cd src/happytube/web/static`, but the return is still `cd ../../..`. That lands in src/, so the later `git status`/`git add src/happytube/web/static/videos.json` resolve to src/src/... and the commit step fails or stages nothing. This only happens when the user starts the local test server.", "fix": "Run the server in a subshell: `(cd src/happytube/web/static && python -m http.server 8000)`, and drop the `cd ../../..`."},
 {"severity": "medium", "file": "src/happytube/web/server.py:20-47", "issue": "`load_video_data` repeats `export.load_videos_from_data_dir`, and the two have already drifted: the server skips non-list JSON and does not dedupe, export does both. The docstring says 'scores >= 3', but nothing filters by score.", "fix": "`return load_videos_from_data_dir(LEGACY_FETCHED_DIR)` and delete the stale docstring and comments."},
 {"severity": "medium", "file": "src/happytube/paths.py / videos.py store_locally", "issue": "Two path anchors. `PROJECT_ROOT` comes from `__file__` via `parents[2]`, which only works in a source or editable checkout. `store_locally`, models/video.py and report.py use paths relative to the current directory, so readers and writers disagree when run outside the repo root.", "fix": "Have `store_locally` use `LEGACY_FETCHED_DIR` and note the checkout assumption in paths.py. Later, put a data_root in Settings."},
 {"severity": "medium", "file": "src/happytube/models/video.py:~98", "issue": "`except Exception` with a DEBUG log skips unparsable files without a trace. After a schema change the parquet export comes out empty and nothing tells the user.", "fix": "Catch `(ValidationError, yaml.YAMLError, OSError)` and log at warning level with the exception."},
 {"severity": "low", "file": "src/happytube/cli/commands.py:23-24,252,362", "issue": "The threshold range is checked by hand in `enhance` and not at all in `run_all --threshold`. The bounds repeat the model's ge/le.", "fix": "Use `type=click.IntRange(MIN_HAPPINESS, MAX_HAPPINESS)` on both options and delete the manual check."},
 {"severity": "low", "file": "src/happytube/utils/__init__.py", "issue": "New `first_text` and `utc_now_iso` have no tests, and `first_text` changes behaviour by skipping non-text blocks. utils now imports anthropic (videos.py loads it too), and `__all__` is stale.", "fix": "Move `first_text` next to the Claude callers, fix `__all__`, and add a parametrized test for `first_text` plus a format test for `utc_now_iso`."},
 {"severity": "low", "file": "src/happytube/cli/commands.py:48, models/video.py:~84", "issue": "`datetime.now().astimezone().date()` appears twice.", "fix": "Add a `today_local()` helper next to `utc_now_iso`."}
],
"preexisting": [
 "videos.py:56,109 (high): `Search.__post_init__` and `Videos.__post_init__` overwrite params and never call `super().__post_init__()`, so YTKEY is never sent and a real `happytube fetch` cannot succeed. Fix: call `super().__post_init__()` at the end of each.",
 "web/export and server read data/fetched/, and nothing writes it now (the only writer, `store_locally`, has no callers), so the player and export are always empty (medium). Separate task: read stages/enhance/*/ frontmatter via MarkdownFile. It is documented, so it does not block.",
 "21 vulns (medium): `uv lock --upgrade` looks safe. Deps are >=-pinned and the bumps are minor or patch (urllib3, werkzeug, pydantic-settings, pytest). Run it with `poe check` and `happytube --help`, then commit the lock on its own.",
 "videos.py `YtQuery.get` logs on the root logger with an f-string and silently returns empty data on HTTP errors. Use a module logger and `raise_for_status()`.",
 "`run_all` re-implements each stage's console reporting. Extracting `_run_stage` would remove the PLR0915 noqa.",
 "tests/test_pipeline.py `test_stage_with_empty_directory` only exercises Path.glob, not stage code."
],
"verdict": "fix-first"}
```
Review side notes: pyproject matches template; ignores narrow/justified; no legacy left; docs faithful; autoescape safe; CLI still uses rich console; zorilla test refactors did not weaken assertions.

## Step 3 — fix (verbatim report)
```json
{"commit_shas": ["a2f5149", "b69d8da", "cc21777", "816d393", "fc39db5", "acacfa9", "1995ff8", "9bab91a", "012500c", "18d0ed6"],
"fixed": ["R-high: deploy_web.sh now starts the test server in a subshell and the cd ../../.. line is gone", "R-med: server.load_video_data now just returns export.load_videos_from_data_dir(LEGACY_FETCHED_DIR); the stale docstring and the unused logging are gone", "R-med: store_locally writes under LEGACY_FETCHED_DIR; paths.py docstring says PROJECT_ROOT assumes a source/editable checkout and that a data_root setting should come later", "R-med: Video.df_from_stage_dir catches (ValidationError, YAMLError, OSError) and logs a warning that includes the error", "R-low: --threshold on enhance and run-all uses click.IntRange(MIN_HAPPINESS, MAX_HAPPINESS); the constants now live in models/video.py and also set the Field ge/le; the manual check is gone", "R-low: first_text moved to stages/claude_response.py, so utils no longer imports anthropic; utils.__all__ fixed; parametrized first_text test plus tests for the utc_now_iso format and today_local", "R-low: added today_local() and used it in the CLI and the Video model", "YTKEY: Search/Videos call super().__post_init__(); tests/test_videos.py proves the key lands in params", "YtQuery.get: module logger; raises YouTubeAPIError on any non-200 reply; tested", "Lock: the 12 vulnerable packages upgraded, in a commit of their own", ".python-version = 3.12 (venv is now 3.12.13)", "CLAUDE.md: a worktree needs uv sync before the hook works; don't run pytest concurrently in one checkout (shared .coverage)", "_run_stage and a shared load_youtube_config extracted; PLR0915 noqa removed"],
"not_fixed": ["Web/export reads data/fetched: deferred per brief", "report requires API keys: deferred", "runpy RuntimeWarning: deferred", "test_stage_with_empty_directory only tests Path.glob: not in scope"],
"deviations": ["Used targeted `uv lock --upgrade-package` on the 12 vulnerable packages, not a blanket `uv lock --upgrade`. The blanket upgrade does clear all vulns and passes check, but it brings major bumps the review didn't expect (anthropic 0.73→2.3, pandas 2→3, rich 15, python-dateutil 3, httpx→httpx2). The one major bump left is pyarrow 22→26; I checked parquet write/read by hand", "YtQuery.get raises YouTubeAPIError (status + reason) instead of calling raise_for_status(), because HTTPError's message includes the request URL and that URL carries the API key. A test asserts the key is not in the error message", "store_locally now returns a Path instead of a str (it has no callers)", "run-all's fetch step now prints whether the YouTube config was loaded (it used to be silent), because it shares the loader with `fetch`; the unused all_results dict is gone", "Smoke test of run-all with a fake YTKEY: Google answered API_KEY_INVALID, so the key is now sent; FetchStage handles the error and the pipeline stops cleanly"],
"vulns_before_after": "21 vulns in 12 packages (2 critical, 7 high) -> 0 (65 packages scanned)",
"check_output_tail": "zorilla 0 findings | biston No clones detected | ruff All checks passed | ty All checks passed | pysentry 0 vulnerabilities | 42 passed (was 30), coverage 70% | happytube --help + all 6 subcommand --help OK | web.export OK (0 videos) | every commit passed the madoqua hook, no bypass"}
```

## Step 4a — review round 2 (verbatim report)
```json
{"round1":[
{"finding":"deploy_web.sh cd ../../..","status":"resolved","note":"subshell correct"},
{"finding":"server duplicates export loader","status":"resolved","note":"now logs a warning on every /api/videos request (data/fetched has no writer)"},
{"finding":"path anchors / store_locally","status":"resolved","note":"PROJECT_ROOT limits documented; stages/ is still relative to cwd, deferred as planned"},
{"finding":"broad except + DEBUG in df_from_stage_dir","status":"resolved","note":"narrowed to warning, but untested"},
{"finding":"threshold -> click.IntRange","status":"resolved","note":"constants in models/video.py feed both Field and CLI, one source of truth"},
{"finding":"first_text/utils/__all__","status":"resolved","note":"stages/claude_response.py is a sensible home"},
{"finding":"today_local helper","status":"resolved","note":"test is weak, see findings"},
{"finding":"YTKEY via super().__post_init__","status":"resolved","note":"env key, explicit key and subclass defaults all tested"},
{"finding":"YtQuery silently returns empty data","status":"partial","note":"YtQuery now raises YouTubeAPIError, but FetchStage.run's catch-all except swallows it, so fetch/run-all exit 0 and daily_run.sh's set -e never fires"},
{"finding":"vulnerable packages","status":"resolved","note":"targeted --upgrade-package was right; pyarrow 22->26 fits >=18.1.0 and pandas 2, but only checked by hand"},
{"finding":"run_all PLR0915 / _run_stage extraction","status":"resolved","note":"noqa removed; output order changed"},
{"finding":".python-version / CLAUDE.md notes","status":"resolved","note":""}],
"findings":[
{"severity":"should-fix","file":"src/happytube/stages/fetch.py:133-140, src/happytube/cli/commands.py:164-175,415-418","issue":"YouTubeAPIError becomes {errors:1} and the CLI exits 0, so a quota or key failure looks like a quiet day","fix":"Re-raise YouTubeAPIError before the generic except (or sys.exit(1) on error_message). Add a CliRunner test that mocks a 403 and asserts exit_code!=0"},
{"severity":"should-fix","file":"src/happytube/videos.py:47-54","issue":"The error is logged and also raised; the useful YouTube error.message only reaches the log","fix":"Drop logger.error and put the API error message (no URL) in the exception; extend the key-leak test"},
{"severity":"should-fix","file":"src/happytube/cli/commands.py:411-414","issue":"load_youtube_config runs before _run_stage prints its header, so the config message appears above 'Stage 1/4'","fix":"Have _run_stage take a stage factory, or split out the header"},
{"severity":"should-fix","file":"tests/test_utils.py:51-52","issue":"test_today_local copies the implementation (tautology) and can fail at midnight","fix":"Freeze time and set TZ, assert the local date differs from UTC, or delete the test"},
{"severity":"should-fix","file":"src/happytube/models/video.py:91-110","issue":"New warning/skip path is untested, and no parquet round-trip test covers the pyarrow bump","fix":"tmp_path test with good, bad-YAML and out-of-range files: assert 1 row plus 2 caplog warnings, then to_parquet/read_parquet"},
{"severity":"suggestion","file":"src/happytube/web/server.py:14-16, web/export.py:60-66","issue":"Every request logs; logger calls use f-strings","fix":"Use %s args and log the missing directory at info/debug or once at startup"},
{"severity":"suggestion","file":"src/happytube/cli/commands.py:98-104","issue":"'/4' hard-coded","fix":"Constant or a total parameter"}],
"preexisting":[
"Search/Videos __post_init__ overwrite self.params, silently dropping a constructor params=",
"FetchStage.run is about 100 lines mixing API, DataFrame and file I/O inside a broad except Exception (cause of the partial finding)",
"test_stage_with_empty_directory only exercises Path.glob"],
"verdict":"fix-first"}
```

## Step 4b — QA round 2 (verbatim report)
```json
{"verified": true, "checks": [
{"step": 2, "ok": true, "evidence": "rm -rf .venv && uv sync rc=0"},
{"step": 3, "ok": true, "evidence": "poe check rc=0: zorilla 0 findings, biston no clones, ruff and ty All checks passed, pysentry 0 vulns (65 pkgs), 42 passed, cov 70%"},
{"step": 4, "ok": true, "evidence": "42 passed"},
{"step": 5, "ok": true, "evidence": "--help plus all 6 subcommand --help rc=0"},
{"step": 6, "ok": true, "evidence": "status with no keys and no .env: Rich table with every stage 'Not started', rc=0"},
{"step": 7, "ok": true, "evidence": "Exported 0 videos to src/happytube/web/static/videos.json; tracked file unchanged"},
{"step": 8, "ok": true, "evidence": "/ 200, /api/videos 200 [], /api/videos/nonexistent 404, /static/player.js 200; server stopped"},
{"step": 9, "ok": true, "evidence": "Skipped per brief: hooks/ and pyproject.toml unchanged since 4b4f31e (empty git diff)"},
{"step": 10, "ok": true, "evidence": "Only the intentional 'removed legacy happytube.main' notes and the historical docs/research/modernization-plan.md remain"},
{"step": 11, "ok": true, "evidence": "deploy.yml: upload path src/happytube/web/static, python -m happytube.web.export, uv python install 3.12"},
{"step": 12, "ok": true, "evidence": "All template files tracked; hooks/pre-commit is executable; .python-version tracked"},
{"step": 13, "ok": true, "evidence": "happytube report on a temp fixture of 2 enhance videos: no literal &lt;div, 14 <div and 2 <h2 intact, <script>/&/quotes escaped, no raw <script>alert"},
{"step": 14, "ok": true, "evidence": "status and report print Rich panels, tables and check marks at the default level"},
{"step": 15, "ok": true, "evidence": "uv run python --version gives Python 3.12.13"},
{"step": 16, "ok": true, "evidence": "check-all rc=0 (ignore_fail): lint, ty, vulns 0, zorilla, biston, deptry 'No dependency issues found', 42 passed. vulture: 29 findings at 60% confidence (click commands, pydantic fields, settings) — false positives"},
{"step": 17, "ok": true, "evidence": "enhance --threshold 9: 'Invalid value for '--threshold': 9 is not in the range 1<=x<=5.' rc=2. run-all --threshold 0: same error for 0, rc=2. Keys unset, so it failed at argument parsing with no API calls"},
{"step": 18, "ok": true, "evidence": "tests/test_videos.py 5/5 passed; test_get_raises_without_leaking_key_on_http_error mocks a 403, expects YouTubeAPIError matching '403', checks that 'secret-key' is not in the message and that data == []"},
{"step": 19, "ok": true, "evidence": "Every path is src/happytube/web/static/... from the repo root; the test server runs in a subshell; there is no cd ../../.. any more; git add/status paths are consistent"},
{"step": 20, "ok": true, "evidence": "Report wrote parquet/enhance/by-run-date/<date>_last_7_days.parquet (2 rows). Read back on pyarrow 26.0.0 / pandas 2.3.3; fetched_at is datetime64[ns, UTC]; rows load back into Video; the re-export via Video.to_parquet equals the original (True)"}
],
"issues": [
"deploy_web.sh counts videos with system `python -c` rather than `uv run python`. That works because it only needs json, but it isn't consistent. The `if [ $? -ne 0 ]` after the export is dead code under set -e (this was already there).",
"vulture reports 29 findings at 60% confidence that are false positives. A whitelist would make check-all quiet.",
"Still deferred from round 1: report needs dummy API keys, and the web export reads data/fetched/, so it yields 0 videos."
]}
```

## Step 5 — fix round 2 (verbatim report)
```json
{"commit_shas": ["bf90784", "97a824f", "e279f51", "9dfb369"],
"fixed": [
"SF1: FetchStage re-raises YouTubeAPIError, so fetch and run-all exit 1. tests/test_cli.py has CliRunner tests that mock a 403 for both commands, check exit_code==1 and check the key is not in the output",
"SF2: the YouTubeAPIError message now carries YouTube's error.message (no URL, no key). Falls back to plain status + reason when the body is not JSON. logger.error removed (logger now unused, so dropped). Key-leak test extended, non-JSON body test added",
"SF3: _run_stage takes a stage factory and builds the stage after printing the header. The run-all test asserts 'Stage 1/4: Fetch' comes before the config message",
"SF4: test_today_local replaced. Time frozen at 23:30 UTC with TZ=Pacific/Kiritimati; asserts the local date is the next day",
"SF5: tests/test_video_model.py uses tmp_path with a good file, a bad-YAML file and an out-of-range file. Asserts 1 row, 2 warnings naming the skipped files, then a parquet write/read round-trip and Video re-validation",
"Suggestion: web/export.py logs with lazy %s args; the missing data dir is logged at debug (the server calls the loader on every request)",
"Suggestion: '/4' replaced by the RUN_ALL_STAGE_COUNT constant",
"QA: deploy_web.sh counts videos with uv run python and checks the export via `if ! uv run ...`",
"QA: [tool.vulture] ignore_decorators (@cli.command, @app.route, @field_validator) and ignore_names (model_config plus the pydantic fields), with comments. 21 false positives silenced"],
"not_fixed": [
"8 vulture hits left unsilenced because they really are unused in src: get_prompt_config, get_config_manager, setup_logging, get_logger, store_locally, get_list_for_claude, get_csv, Videos (used only by tests). Deleting them was out of scope, so poe dead-code still reports these 8"],
"deviations": [
"deploy_web.sh: kept the export-failure message by turning the dead $? check into a live `if !` instead of deleting it",
"Parquet round-trip uses assert_frame_equal(check_dtype=False) plus an explicit check that the dtype string is 'datetime64[ns, UTC]': pyarrow gives back a different UTC tzinfo object",
"Coverage is 51%, not the 70% reported earlier. The base commit 18d0ed6 also measures 51% in this run, so this is not a regression"],
"check_output_tail": "poe check rc=0: ruff All checks passed | zorilla 0 findings | biston No clones | ty All checks passed | pysentry 0 vulns (65 pkgs) | 46 passed, cov 51% | happytube --help and all 6 subcommand --help OK | all 4 commits passed the madoqua hook, no bypass; not pushed"}
```

## Step 6 — final verify (verbatim report)
```json
{"round2": [
 {"finding": "SF1 fetch/run-all exit 0 on YouTubeAPIError", "status": "resolved (partial in spirit): YouTubeAPIError is re-raised and CliRunner tests check exit 1. But FetchStage's catch-all still turns requests.Timeout, ConnectionError and KeyError (missing or empty items) into errors:1 with exit 0"},
 {"finding": "SF2 API error.message in exception, no double log", "status": "resolved; the fixtures use the wrong body shape: quotaExceeded is in error.errors[0].reason, not error.message"},
 {"finding": "SF3 config message after stage header", "status": "resolved (stage factory, order asserted)"},
 {"finding": "SF4 tautological test_today_local", "status": "partial: the fake now() returns an aware UTC datetime, so the test still pins the .astimezone() implementation; one assert only checks a constant"},
 {"finding": "SF5 skip/warn + parquet round-trip test", "status": "resolved; the test covers 3 behaviours and reads r.args[0] (brittle)"},
 {"finding": "lazy %s logging / missing dir at debug", "status": "resolved"},
 {"finding": "hard-coded /4", "status": "resolved (constant); the step numbers are still literals"},
 {"finding": "deploy_web.sh uv run + dead $? check", "status": "resolved"},
 {"finding": "vulture whitelist", "status": "resolved; ignore_names applies everywhere (channel, duration…), a whitelist module would be tighter"}],
"new_findings": [
 "should-fix: src/happytube/__init__.py is missing (pre-existing, so happytube is a namespace package; the template has one). This is the cause of the coverage puzzle",
 "should-fix: fetch.py catch-all still hides network and parse failures (exit 0)",
 "suggestion: tests/test_cli.py run-all test lacks the key-leak assert; the setup is duplicated",
 "suggestion: tests/test_videos.py _response pairs 500 with Forbidden",
 "suggestion: deploy_web.sh reports '0 videos' as success"],
"qa_ok": true,
"qa_evidence": "uv sync rc=0; poe check rc=0 (ruff/ty pass, zorilla 0, biston none, pysentry 0 vulns/65 pkgs, 46 passed, 51%); poe dead-code shows exactly the 8 known hits; happytube --help rc=0; test_cli.py 2/2 passed; git status clean apart from docs/phases/phase-0/*; scratch worktree removed and pruned",
"coverage_explanation": "Not stale data and not --cov=src vs happytube: happytube imports from src/ (editable install). src/happytube has no __init__.py, so coverage cannot find files no test imports, and only imported modules count. At 18d0ed6 (fresh worktree, uv sync) I measured 42 tests, 285 stmts, 70%. At HEAD the new tests/test_cli.py imports cli.commands, which brings in cli (215), assess, enhance and report: 824 stmts, 51%. The fix agent's '18d0ed6 also 51%' does not reproduce. Coverage dropped because more code is now counted, not because tests got worse. Even 51% overstates: with __init__.py added, HEAD measures 931 stmts at 45% (web/* and utils/logging.py at 0%).",
"coverage_fix": "Add an empty src/happytube/__init__.py to match the template (src/python_template/__init__.py). Keep --cov=src / source=['src']. Expect about 45% until web/ and the stages get tests.",
"verdict": "ship"}
```

## Orchestrator
- ec4330c: added `src/happytube/__init__.py` (one-liner, hook passed). Coverage now honest: 931 stmts, 45%, 46 tests.
- Deferred → backlog: fetch catch-all hides network/parse errors (phase 5 rewrites fetch); web/export read data/fetched (phase 4/5); report needs API keys; runpy warning; 8 real dead-code hits; test nits from Step 6; quota error body shape (error.errors[0].reason).
