# Phase 3 — fix

See [context.md](./context.md) and [log.md](./log.md) (review + QA findings).
Main checkout, branch `phase-3-vetting`. Small commits; `uv run poe typecheck`
before each; hooks must pass; no `--no-verify`.

## Must fix
- **R1** `vet_run.py`: switch to `client.beta.messages.create` with
  `output_config={"effort": "medium", "format": <json_schema from VetOutput>}`, same
  betas + `fallbacks="default"` (load the `claude-api` skill for the exact
  json_schema format shape / SDK helper; don't guess). Check `stop_reason` first
  (`refusal` → refused with category; `max_tokens` → error naming it), then
  `VetOutput.model_validate_json(text)`. Every outcome records usage tokens, so
  failed calls appear in totals/cost. Tests: max_tokens cutoff, out-of-range score,
  refusal — each records tokens, writes no files.
- **R2** record the answering model (`reply.model`) per channel in VetResult and in the
  report frontmatter `model` field (requested model stays `MODEL`); run-level key
  `requested_model`; cost note "estimate at Opus 5.5 rates".
- **Q1** `vet` skips channels whose derived status is `rejected` → status
  `skipped_rejected`, no call (also in `--dry-run`). Don't change `evidence`.
- **Q2** `--json` failure message on stderr must not say "see the report above";
  point to stdout JSON.

## Also fix
- **R3** CLAUDE.md line: "the rest except `vet` need no keys".
- **R4** sibling errors under a `VetError` base; comment why 'credit balance' is
  matched (low credit is a 400 invalid_request_error).
- **R5** cleanups: explicit loader instead of suffix-string choice; delete unused
  `CHANNEL_FLAGS` (or use it); `vetted_at` without dumping the whole report; type
  verdict fields as `Verdict`.
- **R6** `vet --help`: prompt/model change needs `--force`. Update 0005 for R1/R2/Q1.

## Do NOT fix
Q3 (legacy report keys), Q4 (key asked when nothing to call), preexisting
mid-run ChannelStoreError abort — backlog. No real API calls (the key is invalid).

## Report
Return ONLY JSON (≤400 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X%",
 "resolved": [{"id": "R1", "how": ""}], "deviations": [""], "unresolved_issues": [""]}
