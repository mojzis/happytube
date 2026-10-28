# Phase 5a — review

See [context.md](./context.md) and the dev report in [log.md](./log.md). Read-only:
report, don't fix. Use the `python-review` skill and the `claude-api` skill.

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5a-review
phase-5a-trusted-fetch`, `uv sync` there; remove + `git worktree prune` at the end.
Diff: `git diff e97b73f..HEAD -- src tests scripts`. No real API calls.

## Check
Design vs context.md, logic, tests, naming. Reproduce where cheap (fakes, tmp dirs).
Added after dev (logic — yours only):
1. `claude.py` extraction: vet behaviour identical (error mapping, fallback,
   token counting, refusal / max_tokens)? Check `ClaudeCaller.call` against the
   anthropic SDK source in `.venv`, not just the fakes. Are the vet_run aliases
   needed or dead weight?
2. Fail-loudly: trace every failure to the CLI exit code (fetch per-channel error,
   quota stop, assess bad reply / refusal, enhance error, `run` chaining). Any path
   that ends as exit 0 or "0 new" on failure?
3. Quota stop mid-channel: files written but result `error` with no paths — wrong
   status or misleading report? Rerun skips them as seen: correct?
4. Dedup / seen set and `--force` semantics: can a video be scored twice, lost, or
   enhanced when unsuitable? `suitable` only from `is_suitable`?
5. Judge deviations: TrustedStage with NotImplementedError run(); own --date
   callback vs `parse_date`; private helper imports from cli/channels.py;
   `Usage` alias of `VetUsage`; skipped_unresolved = exit 0.
6. Re-paid failed batches on rerun: acceptable for now or must fix?
7. Legacy fetch fix: minimal, and legacy tests otherwise untouched?

## Report
Return ONLY JSON (≤600 words):
{"verdict": "ship|fix", "findings": [{"id": "R1", "severity": "high|medium|low",
 "where": "file:line", "what": "", "evidence": "", "fix": ""}],
 "preexisting": [""], "deviations_judged": [""]}
