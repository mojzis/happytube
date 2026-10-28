# Phase 2 — QA (runtime/env verification, report only)

See [context.md](./context.md) — required reading, esp. "CLI" and "Verification
baseline". Dev report in [log.md](./log.md). Review covers code logic; you cover
behaviour as a user/agent sees it.

## Setup
Own worktree: `git worktree add --detach /tmp/claude-1000/p2-qa phase-2-evidence`,
cd there, `uv sync`. Remove + prune at the end. Write tests in a temp channels dir
(`--channels-dir`), never the tracked `channels/`. **Never use the real API key**;
the worktree has no `.env`. For API behaviour, drive the CLI with a fake getter
from a scratch script (CliRunner / injected client) or the tests' fakes.

## Checks (positive evidence for each)
1. `git log --oneline 2a22ea7..HEAD`; status clean; `git grep -n AIza $(git rev-list 2a22ea7..HEAD)` → none.
2. `uv run poe check` — each sub-tool; test count ≥ 122 + new; coverage vs 59%.
3. `--help` for `channels`, `resolve`, `evidence`.
4. No keys (`env -u YTKEY -u ANTHROPIC_API_KEY`, no .env): `list`, `list --json`,
   `show <slug> --json` work; `resolve --all` / `evidence --all` fail cleanly
   (stderr message, exit ≠ 0, no traceback, stdout JSON-clean with `--json`).
5. Committed data: every `channels/*/evidence/*.yaml` loads, Czech text literal,
   shorts flagged where duration ≤ 180, `channel_id` set in channel.yaml for each
   resolved channel; `show` of a Czech channel looks right.
6. Fake-API runs in a temp dir: resolve statuses (resolved/already/not_found/
   no_handle/mismatch) and exit codes; evidence twice in the same second → two
   files, none overwritten; quotaExceeded mid-run → earlier snapshots kept, exit ≠ 0.
7. Network error path: fake getter raising `requests.ConnectionError` with a URL
   containing `key=SECRET` → output/stderr never contains `SECRET`.
8. Existing commands unaffected: `happytube --help`, `status`, `channels review`.

## Constraints
Don't modify tracked files or commit on the branch.

## Report
Return ONLY JSON (≤500 words), number issues Q1, Q2…:
{"verified": true, "checks": [{"step": 1, "ok": true, "evidence": ""}],
 "issues": [{"id": "Q1", "issue": ""}]}

## Added by orchestrator after dev
- Shorts: dev's research shows `0 < duration_s <= 180` gives heavy false positives
  (Zoo Praha 33/50). Assess the cost/shape of switching `is_short` to UUSH-playlist
  membership (playlistItems on `UUSH…`, 1 unit/page) with duration as fallback when
  the UUSH call fails/404s. What breaks in snapshots/tests/docs?
- Dev's scratch wrapper for the truncated key: confirm nothing of it landed in the
  repo (no script, no key, no `.env` change tracked).
- `InvalidKeyError` early stop and the `test_pipeline.py` chdir fix: correct?
- Handle edits for explore-org / zoo-dvur-kralove / pbs-nature: snapshot titles match
  the intended channels?
