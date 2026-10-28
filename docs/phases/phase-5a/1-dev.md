# Phase 5a — dev

See [context.md](./context.md) — required reading; it settles the design.

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-5a-trusted-fetch` (already
checked out; context.md is committed). Baseline: 406 passed, coverage 78%,
`poe check` green. No crontab entry uses `scripts/daily_run.sh` (checked by the
orchestrator) — keep legacy the default there, trusted behind a variable or flag.

## Task
1. Shared pieces first (small commits): extract the Claude call shared by vet and
   assess (one place, vet keeps passing its tests unchanged in behaviour); shared
   model constant; `rubric_version`; move Shorts/uploads helpers if needed.
2. Trusted fetch / assess / enhance / run / status, tests, legacy fetch catch-all
   fix, decision 0009, CLAUDE.md, architecture — as in context.md. Small coherent
   commits; `uv run poe typecheck` before each; hooks must pass.
3. Exploratory real run on a scratch copy (context.md "Real run"): scratch dir
   under `/tmp/claude-1000/`, copy `channels/` there, run from that cwd with
   `--channels-dir` pointing at the copy. Load keys from the repo `.env` (e.g.
   `set -a; . /home/matous/git/happytube/.env; set +a`) — never print, echo,
   truncate or write them anywhere.
   - Probe first: one channel fetch (1–3 units) and one assess batch on ≤ 5 videos
     before the full run.
   - **Credential failure (401/403/invalid key, no credit): stop and report.** No
     workarounds.
   - Fetch all approved channels (~35 units). Assess + enhance on at most two
     channels' videos (`trusted fetch SLUG…` into a separate scratch cwd is fine),
     cap ~$1 total Anthropic estimate.
   - Run fetch a second time for the same date → confirm idempotent, 0 new.
   Commit nothing from scratch.
4. `uv run poe check` green at the end.

## Report
Return ONLY JSON (≤700 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X% (was 78%: why moved)",
 "shared_extraction": "what moved where (Claude call, model const, Shorts helpers)",
 "real_run": [{"check": "", "result": ""}],
 "cost_ledger": {"youtube_units": "by purpose", "anthropic": "tokens + USD per call/batch"},
 "real_run_eyeball": "videos per channel, shorts excluded, suitable count, two example notes, does it look right?",
 "deviations": ["anything differing from context.md, incl. workarounds"],
 "unresolved_issues": [""]}
