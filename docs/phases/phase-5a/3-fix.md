# Phase 5a — fix

See [context.md](./context.md) and review/QA reports in [log.md](./log.md).

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-5a-trusted-fetch`. Small
commits; `uv run poe typecheck` before each; hooks must pass. No real paid API
calls (fakes only); none needed.

## Must fix
- **R1** (stuck videos). Decision (orchestrator): assess picks up **every** fetch
  file with no assess file, on any date ≤ `--date`; enhance picks up every assess
  file with `suitable: true` and no enhance file, on any date ≤ `--date`. Each
  output file goes under the **same date dir as its fetch file** (so per-date
  `status` stays coherent). Batching stays per channel. `--force` keeps its current
  meaning: re-score/redo only `--date`'s videos. Also: `run` continues into assess /
  enhance after **per-channel** fetch errors (still exit ≠ 0 at the end), and stops
  the chain only on a stop (quota / key / credit). Update decision 0009 and
  CLAUDE.md. Tests: the review's repro (channel b fails on D, a's video assessed by
  the D+1 run); run continues past a per-channel error; stop still stops.
- **R2 (Q1)**: when assess writes `suitable: false`, delete that video's enhance file
  if present (report it in the result, e.g. `unenhanced`). Test.

## Also fix
- R3: `run` checks the Anthropic key up front (before fetch) unless there's nothing
  to assess is impossible to know — so: fail fast before fetch if the key is
  missing, clear message, exit ≠ 0. (Pick the simpler correct behaviour; say which.)
- R4: video_id must match `^[A-Za-z0-9_-]{11}$`; others counted as unreadable, not
  written. Test.
- R5: `Usage` defined in claude.py; `VetUsage` becomes the alias (vet YAML unchanged —
  check a committed vet file still loads).
- R6: helpers public in a small `cli/common.py` (or public in channels.py; prefer
  common.py).
- Q2: not_fetched / stopping results carry the known channel_id.
- Q3: validate slugs before requiring YTKEY.
- Preexisting, promoted: `MarkdownFile.save` with `allow_unicode=True` (Czech
  readable on disk; check legacy tests); `scripts/daily_run.sh` HAPPYTUBE_DIR
  defaults to the script's repo dir (overridable).

## Do NOT fix
UTC vs local window edge; fallback pricing; re-paid failed batches; legacy stage
coverage; player (5b).

## Report
Return ONLY JSON (≤500 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X%",
 "fixed": [{"id": "R1", "how": ""}], "deviations": ["incl. any choice made"],
 "unresolved_issues": [""]}
