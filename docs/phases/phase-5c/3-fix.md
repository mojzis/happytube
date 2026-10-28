# Phase 5c — fix

See [context.md](./context.md) and the review + QA findings in [log.md](./log.md).

## Where
Main checkout, branch `phase-5c-video-spot-checks`. Baseline 594 passed / 87%.

## Fix
All of R1–R8 and Q1–Q3 (Q1 = R2). Choices:
- R1: parse each assess file once; a video shown in the player must always be in
  the queue and reviewable. Missing snapshot fields → keep it in the queue marked
  "incomplete assess"; the review stores what is available (snapshot fields
  optional) — never block hiding a shown video. Test: shown file without
  `rubric_version` is in `shown` and can be reviewed + hidden. Also removes the
  double warning (Q2) — check.
- R2/Q1: `load_yaml` raises `StoreError` naming the path for OSError and
  UnicodeDecodeError too (fixes the preexisting channel case as well); tests for a
  non-UTF-8 file and a directory named `x.yaml` (video hidden, queue renders;
  channel hidden).
- R3: hidden `assessed_at` in the form; mismatch → 422 form error "the agent
  re-scored this video, reload".
- R5: drop the alias pattern ambiguity — handler catches `StoreError`;
  `ChannelStoreError` a subclass.
- R6: public time helpers in `records.py` or `utils/`; `records.py` must not import
  `channels.models`.
- Others as the findings say.
Small commits, `uv run poe typecheck` before each, hooks pass, `poe check` green.
No API calls.

## Report
Return ONLY JSON (≤400 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X%",
 "fixed": [{"id": "", "how": ""}], "deviations": [""], "unresolved_issues": [""]}
