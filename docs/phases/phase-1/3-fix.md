# Phase 1 — fix

See [context.md](./context.md) and [log.md](./log.md) (review + QA reports, verbatim) — required reading.

## Task
Fix on branch `phase-1-channels` (main checkout), commit in logical chunks, hooks must
pass, no push. Review and QA overlap; ids in parentheses are duplicates.

### Must fix
- R1 (Q2) path traversal: validate slug against SLUG_PATTERN in every store entry
  point (`_channel_dir`), absolute paths included. Tests: store + CLI, `../x`, `/abs`.
- R2 (Q1) malformed YAML → `ChannelStoreError` naming the file; CLI exit 1, no
  traceback. Non-mapping YAML too.
- R5 (Q3) validation errors from files on disk name the file path.
- `list` / duplicate scan with one broken channel: decide — either fail loudly naming
  the file (simplest, preferred: files are truth, a broken file should be fixed) or
  skip with a stderr warning. Say which in `deviations`. `add` must not silently
  pass a duplicate because a file was skipped.
- R3 (Q6) ordering: sort reviews by (created_at, numeric collision suffix, base = 1);
  `derive_status` takes the last decisive review in that order; use or delete the
  unused `DECISIVE_VERDICTS`. Tie test.
- R4 (Q4, Q5): slug ≠ directory name → error naming the file; `extra="forbid"` on
  both models so typos surface (error names the file).
- R6: duplicate/exists check is about `channel.yaml`, not the directory; race-safe
  create (`open("x")`).
- R7: move list filtering to a pure store function, tested there.
- R8: test gaps listed in R8 + `_review` helper; assert stderr messages.

### Also fix
- R9: narrow the vulture `obj` ignore if cheap; otherwise leave and say why.
- Q7: `--channels-dir` help shows `channels/ at repo root` instead of the absolute
  path (`show_default` string). Table truncation: leave.

### Do NOT fix
- Web player reading `data/fetched/` (phase 5). Seed handles (phase 2).

## Report
Return ONLY JSON (≤400 words):
{"commit_shas": [], "fixed": ["id: what"], "not_fixed": ["id + reason"],
 "deviations": [], "check_output_tail": ""}
