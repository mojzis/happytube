# Phase 1 — learnings (channel registry)

Branch `phase-1-channels`, `ce54e00..5434194`, 8 commits, 2026-10-28.
Loop actually run: dev → review ‖ QA (separate worktrees) → fix → combined
review + QA verify (verdict `ship`) → orchestrator doc-only fix (V3) → learnings.
Planned was dev → review ‖ QA → fix → review ‖ QA; round 2 ran as one agent.

## Delivered

- `happytube.channels` package: pydantic `Channel` / `Review` (`extra="forbid"`),
  `ChannelStore` (dir per channel, append-only review files via `open("x")`, `-N`
  collision suffix), `derive_status` (latest human approve/reject), pure
  `filter_entries`, duplicate checks on slug / channel_id / handle.
- `happytube channels add/list/show/review` with `--json` (stdout only, errors on
  stderr, exit 1), `--channels-dir` / `HAPPYTUBE_CHANNELS_DIR`, no API keys needed.
- 15 seeded candidates in `channels/` (diacritics literal on disk); decision 0003;
  CLAUDE.md + architecture.md.
- Hardened after review: slug validated at every entry point (traversal), broken /
  non-mapping YAML and pydantic errors name the file, slug ≠ dir rejected,
  numeric tie order, race-safe create.
- Tests 46 → 88 (dev) → 122 (fix); coverage 45% → 57% → 59%; `poe check` green.

## What worked

- **context.md that settled the design up front** (layout, derived status, fields,
  CLI shape, seed list, verification baseline). Dev made no design calls of its own
  beyond three small deviations; no re-exploration.
- **Separate worktrees for review and QA.** No `.coverage` collision this time
  (phase 0's INTERNALERROR is gone). The verify agent also used its own worktree.
- **Orchestrator-added checks derived from dev's `unresolved_issues`.** Dev flagged
  the `-2` tie order and null-field hand-editing; the added brief items produced R3,
  R4, Q4, Q5, Q6 — three of the medium findings.
- **Reviewer reproducing, not just reading.** R1 (traversal: `review ../evil` wrote
  outside the registry) and R4 (slug ≠ dir → duplicate `zlin`) were both executed.
- **Fix brief deduplicating review + QA ids** (`R1 (Q2)`) and pre-deciding the
  open design choice (fail loudly on a broken file) — the fix agent did all 9
  must-fix items in one pass and said which option it took.
- **Verify brief asking to judge the fix's own design choices** ("-N is a suffix
  only if base exists") — that is exactly where V3 came from.
- **One combined round-2 verify** was enough: 16/16 round-1 items resolved or
  justified-partial, 3 low findings, `ship`.

## What each step caught that the previous missed

- **Dev (1)** self-reported the inverted tie order (became R3/Q6) and that it kept
  null optional fields — both seeded the orchestrator's added checks.
- **QA (2a)** and **review (2b)** overlapped heavily: Q1–Q6 map 1:1 onto R1–R6.
  Review-only: R7 (filter logic in the CLI, phase-4 fit), R8 (test gaps, copy-paste),
  R9 (vulture `obj` ignore). QA-only: Q7 (absolute path in `--help`, table
  truncation) and the positive evidence — diacritics on disk, parallel same-second
  writes (`bot`, `bot-2`, `bot-3`), no-keys run. QA also found the `/abs` slug variant
  and that a broken file blocks every `add`, which shaped the fix brief.
- **Verify (4)** found what the fix introduced or left at the edges: V3 (the new
  "-N only if base exists" rule compares suffixes across reviewers — `bot` vs
  `bot-9`, contradicting 0003), V1 (non-slug directory name → misleading
  "not found" without a path), V2 (ValidationError formatting duplicated and already
  drifted between store and CLI). It also confirmed the fail-loudly choice does not
  block `show` of a healthy channel.

## Friction

- Brief said `git worktree add <path> phase-1-channels`; that fails while the branch
  is checked out in the main checkout. QA and verify used `--detach`. Fix the
  template.
- log.md header still announces the planned loop ("review ‖ QA → learnings"), not
  the one run.
- Round 1 cost two agents for largely one set of findings (6 of 7 QA issues were
  duplicates of review findings).

## Wasted effort

- Little. The duplicate R/Q findings cost reading time, not a fix round.
- QA check 10/11 and review's "dev deviations" section tested the same two things
  in parallel.

## Deferred backlog

- V1: `slugs()` should raise `ChannelStoreError` naming the path for a directory
  name that isn't a valid slug.
- V2: one shared `describe_validation_error()` for store and CLI.
- R9: vulture `ignore_names = ["obj"]` stays global (click `ctx.obj`).
- Q7: `list` table truncates kind/name at 80 columns without a TTY.
- Seed handles other than `@bbcearth` / `@NatGeo` and all `channel_id`s → phase 2.
- R8 tail: a few CLI tests don't go through `_no_traceback`.
