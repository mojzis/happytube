# Phase 5a — verify (combined review + QA)

See [context.md](./context.md) and all reports in [log.md](./log.md). Read-only:
report, don't fix. Use the `python-review` skill.

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5a-verify
phase-5a-trusted-fetch`, `uv sync` there; remove + `git worktree prune` at the end.
Fix diff: `git diff d971e7f..HEAD -- src tests scripts`. No real paid API calls
(fakes / fake keys only); never print real keys.

## Check
1. `uv run poe check` green; numbers.
2. Each R1–R6, Q1–Q3 and the two promoted items: resolved / partial / not, with
   evidence. Trace R1 and R3 end to end to the CLI exit code and stdout/stderr.
3. Judge the fix's deviations and choices: run continues past per-channel errors
   (anything now silently swallowed?); enhance deletion across all dates (can it
   delete something it shouldn't?); same id on two dates; `skipped` semantics;
   `cli/common.py` move (channels/serve behaviour unchanged, `--help` texts).
4. The fix's unresolved item: re-scored-suitable keeps an enhance file with stale
   scores — fine for 5b if readers take scores from assess, or must it be fixed
   now? Say which.
5. Runtime spot checks on a scratch cwd with a fake-client harness: a two-day
   scenario (day D one channel errors, D+1 run) ends with every video assessed and
   status per date coherent; `daily_run.sh` from another cwd with a stub `uv`.
6. Any new findings.

## Report
Return ONLY JSON (≤500 words):
{"verdict": "ship|fix", "resolved": [{"id": "", "status": "resolved|partial|not",
 "evidence": ""}], "deviations_judged": [""], "new_findings": [{"id": "V1",
 "severity": "", "where": "", "what": "", "fix": ""}]}
