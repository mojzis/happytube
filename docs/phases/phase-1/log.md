# Log: phase 1 — channel registry

- Plan: `docs/plan.md`, context: `./context.md`
- Branch: phase-1-channels · base ce54e00ebfd5bec3623997c6bc38608d35dc0b6c
- Loop: dev → review ‖ QA → fix → review ‖ QA → learnings

## 2026-10-28 · bootstrap
- Orchestrator settled: dir per channel + append-only review files; status derived
  from latest human approve/reject; rejected = blocklist; no API calls this phase.

## Step 1 — dev (verbatim report)
```json
{"commit_shas": ["9767eb5325b0cfceb96758e770155272f256d668", "da0e1ead3ced4303d26a925a1f3889a4d69b3704", "cd61974d5243144d69905ffffc19a4ccc13e16b9", "9b03d0d81ab1c14e8bab3bbebe0c1ee65c8872df"],
 "summary": "Added the happytube.channels package. models.py has the Channel and Review pydantic models with Literal kinds, languages, roles and verdicts, pattern checks for slug, handle and channel_id, UTC 'Z' timestamps, and slugify. store.py has ChannelStore with one directory per channel and append-only review files written with open('x') and -2/-3 suffixes on collision. It also has derive_status, where only the latest human approve/reject counts, plus duplicate checks on slug, channel_id and handle (case-insensitive) and summary/detail dicts for JSON. The CLI is a thin layer in cli/channels.py (add/list/show/review, --json to stdout, errors to stderr with exit 1, --channels-dir / HAPPYTUBE_CHANNELS_DIR, no API keys needed), registered with cli.add_command in commands.py. There are 42 new tests (27 store, 15 CLI). The 15 candidates are seeded in channels/ with added_by claude-seed and the 'seed from idea doc, unverified' note. Only @bbcearth and @NatGeo have handles; no channel_ids are set. ČT uses slug ct-decko. Docs: decision 0003, CLAUDE.md (CLI section, key modules, storage tree) and architecture.md (registry moved from Planned to Components/Data). No .env exists, and `env -u YTKEY -u ANTHROPIC_API_KEY happytube channels list --json` returns 15 candidates. Tests: 88 pass, coverage 57%.",
 "deviations": ["The first commit holds docs/phases/phase-1/ together with the models/store code instead of being a separate commit.", "channel.yaml keeps null optional fields (handle/channel_id/url: null) so people can see which fields exist when editing by hand.", "The list table's Slug column is no_wrap so slugs can be copied whole."],
 "unresolved_issues": ["Seed handles other than @bbcearth and @NatGeo are left empty on purpose (not confident); phase 2 resolves them.", "Reviews from the same reviewer in the same second are ordered by created_at, which has microsecond precision. If two reviews ever have identical created_at values, the filename tie-break puts '-2' before the base name."],
 "ignores_added": ["ruff PLR0913 noqa on add_channel/list_channels/review_channel in src/happytube/cli/channels.py: one parameter per click option", "vulture ignore_decorators += @channels.command, @field_serializer (framework-registered); ignore_names += added_at (pydantic field), obj (click ctx.obj read via pass_obj)"],
 "check_output_tail": "All checks passed! / zorilla 0 findings / No clones detected. / 0 vulnerabilities / TOTAL 1219 521 57% / 88 passed in 1.87s (poe check exit 0)"}
```

## Step 2b — review (verbatim report)
```json
{"findings": [
{"id": "R1", "severity": "high", "file": "src/happytube/channels/store.py (_channel_dir)", "issue": "Path traversal. show/review/get pass the raw slug into root/slug. I reproduced it: `review ../evil` wrote evil/reviews/*.yaml outside the registry. Phase-4 Flask will take the slug from a URL.", "fix": "In _channel_dir, fullmatch SLUG_PATTERN and raise ChannelNotFoundError if it fails. Add store and CLI tests for '../x'."},
{"id": "R2", "severity": "high", "file": "src/happytube/channels/store.py (_load_yaml)", "issue": "Malformed YAML on disk raises an uncaught yaml.YAMLError, so the CLI prints a traceback. This is an expected case because humans edit the files by hand.", "fix": "Wrap safe_load and re-raise ChannelStoreError(f'{path}: invalid YAML: {e}')."},
{"id": "R3", "severity": "medium", "file": "src/happytube/channels/store.py (derive_status, reviews)", "issue": "Ties are handled wrongly in two places. (a) derive_status uses max(), which returns the FIRST of equal keys, so approve then reject at the same created_at gives 'approved'. (b) reviews() sorts ties by filename: '-' < '.' puts '-2' before the base name, and '-10' sorts before '-2'. A real tie needs an identical microsecond timestamp, so it mostly comes from hand-written files with second precision, but the rule is wrong as written.", "fix": "Sort by (created_at, numeric suffix parsed from the filename, base=1), and have derive_status take the last decisive review from that order. Return DECISIVE_VERDICTS[verdict], which is currently defined but unused. Add a tie test."},
{"id": "R4", "severity": "medium", "file": "src/happytube/channels/store.py (slugs/get/_find_duplicate)", "issue": "A hand-edited slug that no longer matches the directory name is not detected. I reproduced it: list --json reports slug 'zlin', `show zlin` fails with 'No channel', and `add --slug zlin` then succeeds, which gives two entries with slug 'zlin'. Unknown keys such as a typo 'chanel_id' are dropped silently. Deleting a null key is fine.", "fix": "On load, raise ChannelStoreError if channel.slug != dir name. Set model_config extra='forbid' (or warn) so typos surface."},
{"id": "R5", "severity": "medium", "file": "src/happytube/cli/channels.py (_store_errors_as_click); store.py", "issue": "A ValidationError from a file on disk is reported as 'Invalid input: kind: …' without the file path. One bad file also breaks `list` for every channel.", "fix": "Catch ValidationError around model_validate in the store and re-raise ChannelStoreError(f'{path}: …'). Optionally let entries() skip and report broken channels."},
{"id": "R6", "severity": "low", "file": "src/happytube/channels/store.py (add/_find_duplicate)", "issue": "Any directory without channel.yaml blocks add with 'already registered', yet list does not show it. A failed write_text after mkdir leaves exactly such a directory, which blocks that slug for good.", "fix": "Check for CHANNEL_FILE rather than the directory. Use mkdir(exist_ok=True) and open('x') on channel.yaml as the race-safe check."},
{"id": "R7", "severity": "low", "file": "src/happytube/cli/channels.py (list_channels)", "issue": "The status/kind/language/needs-human-review filter is business logic that phase-4 Flask will need, but it lives in the CLI. The store itself is clean: no click or rich.", "fix": "Move it to a pure filter_entries() in store.py and test it there."},
{"id": "R8", "severity": "low", "file": "tests/test_cli_channels.py, tests/test_channel_store.py", "issue": "Assertions are behavioural, not tied to the implementation, but some are weak. test_add_explicit_slug does not check exit_code, and the unknown-slug test does not check stderr. Untested: traversal, malformed YAML, ties, the empty-slug path, the 'reviewer' fallback, non-mapping YAML. The review invocation is copy-pasted 5 times.", "fix": "Add a _review helper and the missing cases, and assert on stderr messages."},
{"id": "R9", "severity": "low", "file": "pyproject.toml [tool.vulture]", "issue": "The decorator ignores (@channels.command, @field_serializer) are fine. 'added_at' matches the existing pattern. 'obj' is a global name ignore across src/.", "fix": "Acceptable. Narrower: drop 'obj' and use ctx.ensure_object / a whitelist entry."}
],
"preexisting": ["The web player/export read legacy data/fetched/, which nothing writes (known gap in CLAUDE.md)."],
"verdict": "fix-first"}
```

## Step 2a — QA (verbatim report)
```json
{"verified": true,
 "checks": [
  {"step": 1, "ok": true, "evidence": "ce54e00..HEAD has 4 commits: 9767eb5, da0e1ea, cd61974, 9b03d0d. The worktree is clean. It was created with --detach because the branch is checked out in the main checkout."},
  {"step": 2, "ok": true, "evidence": "poe check exits 0. ruff and the test lint print 'All checks passed!'. No clones, 0 vulnerabilities in 65 packages. 88 passed (46 + 42). Coverage is 57%: channels models 98%, store 95%, cli/channels 98%."},
  {"step": 3, "ok": true, "evidence": "The channels group help and all 4 subcommand helps exit 0 and list the choices for kind, language, role, verdict and status."},
  {"step": 4, "ok": true, "evidence": "With YTKEY and ANTHROPIC_API_KEY unset and no .env: list shows a table of 15, list --json parses with json.tool, and show zoo-zlin --json exits 0."},
  {"step": 5, "ok": true, "evidence": "15 channels, all candidate, no reviews/ directories. Zoo Zlín, ZOO Dvůr Králové and ČT :D / Déčko are written literally in the YAML on disk (no \\u escapes) and also print correctly in the table and JSON."},
  {"step": 6, "ok": true, "evidence": "Status after each review: agent approve → candidate, human approve → approved, human unsure → approved, human reject → rejected. The --status, --needs-human-review, --kind, --language and combined filters all returned the expected sets."},
  {"step": 7, "ok": false, "evidence": "Duplicate slug, duplicate handle (case-insensitive), duplicate channel_id, unknown slug, bad slug/handle/channel_id and empty reviewer all exit 1 with a clean stderr message and empty stdout. Bad kind/language/role/verdict exit 2 (click usage error). Slug '../x' is rejected. Reviewer '../../evil' is sanitised to the file name ...-evil.yaml. Failures: Q1, Q2, Q3."},
  {"step": 8, "ok": true, "evidence": "Three human reviews in the same second through the store gave matous.yaml, matous-2.yaml and matous-3.yaml. Three agent reviews run in parallel through the CLI gave bot, bot-2 and bot-3. Nothing was overwritten."},
  {"step": 9, "ok": true, "evidence": "happytube --help lists every command, including channels. status runs and exits 0 without keys."},
  {"step": 10, "ok": false, "evidence": "Deleting url: null is fine (it defaults to null). An unknown key is silently ignored. A slug that differs from its directory name is accepted. See Q4 and Q5."},
  {"step": 11, "ok": false, "evidence": "Two human reviews have identical created_at. Whichever is in the base-name file (the first one written) sorts last and decides the status; the -2 file sorts first. See Q6."}
 ],
 "issues": [
  {"id": "Q1", "issue": "A malformed channel.yaml or review YAML (a syntax error like 'slug: [unclosed') makes list, show and add print a full yaml.ParserError traceback. _store_errors_as_click does not catch yaml.YAMLError. One broken file also blocks every add, because the duplicate scan reads every channel."},
  {"id": "Q2", "issue": "show, review and add_review do not validate the slug, so paths outside the registry work. `review ../other/victim` and `review /abs/dir` exit 0 and write a review file into any directory that contains a channel.yaml, outside --channels-dir. `show ../p1-qa-tmp/museo` also resolves. The slug pattern is only checked on add."},
  {"id": "Q3", "issue": "When a hand-edited file fails pydantic validation (e.g. kind: spaceship), the error says 'Invalid input: kind: …' without naming the file or slug, so it is hard to find in a registry of many channels."},
  {"id": "Q4", "issue": "Slug/directory mismatch. If channel.yaml in directory alpha/ says slug: gamma, list reports slug 'gamma' while reading data from alpha/. show alpha prints slug gamma, and add 'Gamma' then succeeds, so list has two entries with slug 'gamma'. An agent that copies a slug from the list into review/show ends up on the wrong channel. The store should enforce or override slug = directory name."},
  {"id": "Q5", "issue": "Unknown keys in channel.yaml or review files are silently ignored (pydantic extra=ignore). A typo such as 'chanel_id:' is lost without any warning. Consider extra='forbid' or a warning."},
  {"id": "Q6", "issue": "When created_at values are identical, ties are broken by file name. '-' sorts before '.', so 'X-matous-2.yaml' comes before 'X-matous.yaml', and the earlier-written review counts as the latest and decides the status. Only reachable with hand-crafted or coarse timestamps, but the ordering is inverted. Sort by the numeric collision suffix instead."},
  {"id": "Q7", "issue": "Minor: the channels --help default shows the absolute PROJECT_ROOT/channels path. With 80 columns and no TTY, the list table truncates kind ('broadcas…') and names."}
 ]}
```

## Step 3 — fix (verbatim report)
```json
{"commit_shas": ["a761c46e9ede642ff4a8d4554159cbfb149ce7d7", "e2aa15ae7de46df1925ef1a59b4b6a232423fd79", "1bb6a631cc2f57aa97d0165c2ba23cd86bc14eb8"],
 "fixed": [
  "R1/Q2: _channel_dir now checks the slug against SLUG_PATTERN with fullmatch and raises ChannelNotFoundError ('not a valid slug'). Store tests cover ../x, /abs, a/b, .., the empty string and a real absolute path; CLI tests cover show and review.",
  "R2/Q1: malformed YAML and YAML that is not a mapping raise ChannelStoreError naming the file. The CLI exits 1 with the message on stderr and no traceback.",
  "R5/Q3: _load_model turns pydantic errors from files on disk into '<path>: field: msg'.",
  "Broken file: entries() and add() both fail loudly and name the file. add cannot skip a broken channel and let a duplicate through (tested).",
  "R3/Q6: reviews sort by (created_at, collision suffix as a number, base file = 1, filename). derive_status does a stable sort by created_at, takes the last decisive review and returns DECISIVE_VERDICTS[verdict]. Tests: a tie, -10 vs -2 vs base, and a reviewer slug ending in digits.",
  "R4/Q4/Q5: get_channel raises if the slug differs from the directory name, naming the file. extra='forbid' is on Channel and Review; unknown keys produce an error naming the file.",
  "R6: the exists check looks for channel.yaml, not the directory. add does mkdir(exist_ok=True) then open('x'); losing the race gives a clean ChannelExistsError (tested).",
  "R7: new pure filter_entries() in store.py, used by the CLI and tested with parametrized cases in the store tests.",
  "R8: _review CLI helper replaces 5 copies; added tests for traversal, malformed YAML, ties, empty slug (pass --slug), the 'reviewer' fallback and non-mapping YAML; test_add_explicit_slug now checks exit_code; stderr messages are asserted.",
  "Q7: --channels-dir help shows '[default: (channels/ at repo root)]' (tested)."
 ],
 "not_fixed": [
  "R9: the vulture 'obj' ignore is left. Only one place sets it (ctx.obj in the channels group), and a vulture whitelist entry would also match by name, so it would not be narrower. Getting rid of it means changing how click passes the store, which isn't cheap.",
  "Q7 table truncation: left, as the brief says.",
  "Web player data/fetched/ and seed handles: out of scope (phases 5 and 2)."
 ],
 "deviations": [
  "Broken files: I chose to fail loudly (the preferred option). list and add stop with an error naming the broken file; nothing is skipped.",
  "A trailing -N counts as a collision suffix only when the base file exists, so the reviewer slug 'bot-9' is not read as collision 9.",
  "derive_status still accepts reviews in any order: a stable sort by created_at keeps the store's order for ties.",
  "Decision 0003 now records the tie order, the slug = directory rule and strict validation."
 ],
 "check_output_tail": "uv run poe check exit 0: ruff All checks passed / zorilla 0 findings / No clones detected / 0 vulnerabilities in 65 packages / TOTAL 1252 514 59% / 122 passed in 2.13s. channels list --json still returns 15 channels. The hook passed on all 3 commits; nothing pushed; docs/phases/phase-1/ not touched."}
```

## Step 4 — round 2 combined review + QA (verbatim report)
```json
{"round1": [
{"id":"R1","status":"resolved","note":"Through the CLI, show and review with /abs, /tmp/x and ../c/zoo-zlin exit 1 with 'not a valid slug' on stderr and an empty stdout."},
{"id":"R2","status":"resolved","note":"Malformed YAML in channel.yaml and in a review file gives exit 1 and a stderr message naming the file. No traceback."},
{"id":"R3","status":"resolved","note":"On a tie, m-2 beats the base file, and -10 sorts after -2. One edge case remains, see V3."},
{"id":"R4","status":"resolved","note":"A slug that doesn't match its directory makes list, show and add exit 1 and name the file. extra=forbid is on."},
{"id":"R5","status":"resolved","note":"Validation errors from files show as '<path>: field: msg'."},
{"id":"R6","status":"resolved","note":"The exists check looks for channel.yaml. add uses open('x'), and that path is tested."},
{"id":"R7","status":"resolved","note":"filter_entries() is pure and lives in store.py."},
{"id":"R8","status":"resolved","note":"There is a _review helper now, and stderr is asserted. A few tests still don't go through _no_traceback."},
{"id":"R9","status":"partial","note":"The 'obj' vulture ignore is kept on purpose. The reason given holds."},
{"id":"Q1","status":"resolved","note":""},{"id":"Q2","status":"resolved","note":""},{"id":"Q3","status":"resolved","note":""},{"id":"Q4","status":"resolved","note":""},{"id":"Q5","status":"resolved","note":""},{"id":"Q6","status":"resolved","note":""},
{"id":"Q7","status":"partial","note":"The help default is fixed. The table truncation is left in place as the brief allows."}],
"new_findings": [
{"id":"V1","severity":"low","file":"src/happytube/channels/store.py (slugs)","issue":"A directory whose name is not a valid slug (e.g. 'Foo Bar/channel.yaml') makes list fail with 'No channel with slug … (not a valid slug)'. The message gives no file path and calls it not-found.","fix":"In slugs(), raise ChannelStoreError naming the path when a directory name doesn't match SLUG_PATTERN. Add a test."},
{"id":"V2","severity":"low","file":"store.py _load_model / cli/channels.py _store_errors_as_click","issue":"The ValidationError formatting is duplicated, and the two copies have already drifted.","fix":"Use one shared describe_validation_error() in models.py."},
{"id":"V3","severity":"low","file":"store.py _collision_index; docs/decisions/0003","issue":"The -N suffix is compared across different reviewers. I reproduced it: reviewers 'bot' and 'bot-9' at the same created_at, and bot-9 is read as collision 9 and wins. A tie between different reviewers is decided by filename, but 0003 says the later-written file wins.","fix":"Compare suffixes only within one reviewer's files, or reword 0003. Rewording is cheaper."}],
"qa_ok": true,
"qa_evidence": "Check 7: the /abs, ../ and duplicate slug/handle cases and an unknown slug all exit 1, with stderr only and an empty stdout. Malformed YAML in channel.yaml and in a review file both name the path. Check 10: an unknown key gives '<path>: chanel_id: Extra inputs are not permitted'. A slug ≠ dir mismatch blocks list, show and add, so the duplicate 'gamma' can no longer be added. Check 11: on an identical created_at, the reject in m-2 wins over the approve in the base file. Adding m-10 (approve) makes it approved, so -10 sorts after -2. Check 6: agent approve leaves the channel a candidate, then human approve makes it approved. Design: fail-loudly is acceptable. show of a healthy channel still works while another channel is broken. A broken review file does not block add, because the duplicate scan reads only channel.yaml. A broken channel.yaml blocks list and add, which is right for files-as-truth since a duplicate could otherwise slip in. The '-N only if the base exists' rule is sound for one reviewer, except V3. poe check: 122 passed, 59% coverage. With no API keys in the env, channels list --json gives 15 candidates. The worktree was removed and pruned.",
"verdict": "ship"}
```

## Orchestrator
- Verdict ship. V3: reworded decision 0003 (doc only, no code). V1, V2 (low) →
  backlog in `docs/plan.md`.
