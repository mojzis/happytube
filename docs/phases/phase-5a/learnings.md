# Phase 5a — learnings

Source: this directory (context, 1-dev, 2-review, 2-qa, 3-fix, 4-verify, log).
Loop run as planned: dev → review ‖ QA → fix → combined verify → orchestrator real
probe → learnings. 4 agent steps after dev; one fix round.

## What the phase delivered

- `happytube trusted fetch | assess | enhance | run | status`: a daily pipeline that
  reads only approved channels, scores each long-form video with the shared rubric
  (Claude Opus 5.5) and rewrites descriptions of the suitable ones. Own stage dirs
  under `stages/trusted/`, side by side with the legacy pipeline.
- Shared pieces: `claude.py` (one Claude call, model constant, prices, errors) used by
  vet and assess; `RUBRIC_VERSION`; Shorts/uploads helpers shared with evidence.
- Nothing stranded by a failed run: assess and enhance pick up every pending file up
  to `--date`; `run` continues past per-channel and per-batch errors (exit 1) and
  stops only on quota / key / credit.
- A re-score to unsuitable deletes the video's enhance file.
- Legacy `fetch` now fails loudly (exit 1) instead of reporting "0 new".
- `cli/common.py` for options shared by `channels`, `trusted`, `serve`.
- Decision 0009, CLAUDE.md, architecture updated. Tests 406 → 456, coverage 78% → 82%.
- Promoted preexisting fixes: Czech stays readable in stage files
  (`allow_unicode`); `daily_run.sh` runs from its own repo dir.

## What went well

- Dev's real run worked first time. Keys were valid; the 1-call probe (one channel,
  one small assess batch) ran before the full run, as briefed.
- Idempotence held on real data: second fetch 0 new, files byte-identical; assess
  rerun 0 calls.
- Fail-loudly held end to end: fake keys stop with exit 1, nothing written, no key
  text anywhere.
- Review checked the extracted Claude call against the SDK source in `.venv`, not
  just the fakes: vet behaviour byte-identical.
- One fix round, then verify said `ship` with only lows (V1–V5).

## What went badly

- context.md had settled "assess/enhance read only `--date`" and "any failing step
  stops `run`". Together they strand videos: a channel that fails on day D blocks the
  chain, the seen set stops refetching, and later runs never assess D's other
  videos. Review found it (R1). The rule was wrong in its consequences, not in an
  external fact.
- `assess --force` turning a video unsuitable left its enhance file behind (R2/Q1).
  Context said nothing about re-scores going down.
- Dev's "quota stop mid-channel leaves files" concern was wrong; review showed no
  file is written before the stop. Cost a review check, no harm.

## Product findings

- **The video gate does the work.** BBC Earth, an approved channel: 1 of 8 videos
  suitable (predation compilations failed). Explore.org 3/3. Channel approval alone
  is not enough; per-video scoring is needed.
- Orchestrator probe (San Diego + Cincinnati zoo): 7 new, 5 suitable. A press-style
  livestream announcement (calm 3) and a raptor podcast about hunting (happy 3) were
  rejected; birth-watch and vet-tech videos passed 4/4. Judgements look right.
- **Cost:** about $0.05 for 7 videos (assess $0.03 + enhance $0.02). YouTube: ~3
  units per channel; all 11 approved channels ≈ 33 units. Shorts dominate uploads
  (221 excluded in dev's run, 76 in the probe), all caught via `UUSH`.
- Many approved channels post rarely: 5 of 11 had 0 new videos in 14 days.
- Enhanced descriptions are plain, with no links.
- 5b must read calm/happy/suitable from assess, and only `enhanced_description` from
  enhance (an enhance file can hold stale scores after a re-score).

## Process lessons

- A settled rule in context.md can be wrong in its consequences. Review should trace
  multi-day and partial-failure scenarios against the rules, not just the code.
- The orchestrator chose the R1 fix design in the fix brief (pending up to `--date`,
  output under the fetch date, `--force` only `--date`). The fix agent built it with
  no back-and-forth.
- Review and QA found the same bug (R2 = Q1) independently, one by logic, one at
  runtime.
- The orchestrator's own real probe after verify gave fresh eyes on real output at
  low cost ($0.05, 6 units).
- zsh: `H="uv run happytube"; $H trusted …` fails (no word-splitting). Use a shell
  function.
