# Phase 1 — QA (functional verification, report only)

See [context.md](./context.md) — required reading, esp. "CLI shape" and
"Verification baseline". Dev report in [log.md](./log.md).

## Setup
Own worktree: `git worktree add /tmp/claude-1000/p1-qa phase-1-channels`, cd there,
`uv sync`. Remove + prune at the end. For write tests use a temp channels dir
(`HAPPYTUBE_CHANNELS_DIR` or `--channels-dir`), never the tracked `channels/`.

## Checks
1. `git log --oneline ce54e00..HEAD`; `git status` clean.
2. `uv run poe check` — each sub-tool result; test count ≥ 46 + new.
3. `uv run happytube channels --help` and each subcommand `--help`.
4. With `env -u YTKEY -u ANTHROPIC_API_KEY` and no `.env` (worktree has none):
   `channels list`, `list --json | python -m json.tool`, `show <seeded slug> --json`.
5. Seed: 15 channels, all `candidate`, names incl. diacritics render correctly in
   YAML on disk (not `\u` escapes) and in output.
6. Full flow in temp dir: add → review agent approve (status stays candidate) →
   human approve (approved) → human unsure (still approved?) → human reject
   (rejected). `list --status`, `--needs-human-review`, `--kind`, `--language`
   filters return the right sets.
7. Errors (exit code ≠ 0, message on stderr, no traceback, stdout JSON-clean when
   `--json`): duplicate slug, duplicate handle/channel_id, unknown slug, bad
   kind/language/role/verdict, malformed `channel.yaml`, slug like `../x`,
   reviewer like `../../evil`.
8. Two reviews by the same reviewer in the same second → two files, none
   overwritten.
9. Existing commands unaffected: `happytube --help`, `status`.

## Constraints
Don't modify tracked files or commit on the branch.

## Report
Return ONLY JSON (≤500 words), number issues Q1, Q2…:
{"verified": true, "checks": [{"step": 1, "ok": true, "evidence": ""}],
 "issues": [{"id": "Q1", "issue": ""}]}

## Added by orchestrator after dev
10. Hand-edit tolerance in a temp dir: delete `url: null` from a channel.yaml, add an
    unknown key, change `slug` to differ from dir name → what do list/show do?
11. Two reviews written with identical `created_at` (craft files by hand) → which
    one `show` lists last and which decides status.
