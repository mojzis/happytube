# Phase 5a — QA

See [context.md](./context.md) and the dev report in [log.md](./log.md). Read-only:
report, don't fix. Runtime checks only (review covers logic).

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5a-qa
phase-5a-trusted-fetch`, `uv sync` there; remove + `git worktree prune` at the end.
Copy `channels/` to a scratch dir and run the CLI from a scratch cwd so `stages/`
lands there.

## Money / keys
No real Anthropic calls, no real YouTube calls with the real key. Fake keys are
fine (an invalid key costs nothing). Drive success paths with a small Python
harness that injects fake clients (as the tests do), not the network. Never print
the real keys.

## Check
1. `uv run poe check` green; numbers (445 / 82%).
2. Added after dev (runtime — yours only):
   a. `--json` contract for every `trusted` subcommand: stdout parses as JSON,
      errors on stderr, exit codes (success, per-channel error, stop, bad `--date`,
      named non-approved slug, unknown slug).
   b. Which key each command asks for: `status`, `assess --dry-run`,
      `enhance --dry-run`, assess/enhance with nothing to do — no key needed?
      `fetch` without YTKEY, assess without ANTHROPIC_API_KEY → clear error, exit ≠ 0.
   c. Fake-key stop: fetch and assess with invalid keys → stop, exit ≠ 0, no key
      text in stdout/stderr/files.
   d. `run` with a failing step stops the chain (exit ≠ 0, later stages not run).
   e. `status` counts on a seeded stage dir (hand-made md files) match.
   f. `scripts/daily_run.sh`: `bash -n`; with a stubbed `uv` on PATH, legacy
      default and `HAPPYTUBE_PIPELINE=trusted` call the right command, and a
      failing stub makes the script exit ≠ 0 (pipefail).
   g. Legacy commands: `happytube fetch` with a fake key now exits ≠ 0; `--help`
      of legacy commands unchanged; `channels vet --dry-run` still works.
   h. Stage files: frontmatter fields as listed in context.md "Stage layout";
      unicode (Czech) titles round-trip.

## Report
Return ONLY JSON (≤600 words):
{"verdict": "ship|fix", "verified": [{"check": "", "how": "", "result": ""}],
 "issues": [{"id": "Q1", "severity": "high|medium|low", "what": "", "repro": "",
 "fix": ""}], "preexisting": [""]}
