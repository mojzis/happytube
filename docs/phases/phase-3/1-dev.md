# Phase 3 — dev

See [context.md](./context.md) — required reading; it settles the design.

## Where
Main checkout `/home/matous/git/happytube`, branch `phase-3-vetting` (already
checked out). First commit `docs/phases/phase-3/` as-is.

## Task
1. Load the `claude-api` skill (Skill tool) before any Claude code.
2. Commit A: `anthropic` → newest 1.x per `sdk-upgrade.md`; `poe check` green.
3. Build rubric, flags, vet, store, CLI, tests, docs as in context.md. Small
   coherent commits; `uv run poe typecheck` before each; hooks must pass.
4. Exploratory real run on a scratch copy (context.md "Real run"); 1-channel probe
   first; stop and report on any credential failure. Commit nothing from it.
5. `uv run poe check` green at the end.

## Report
Return ONLY JSON (≤600 words):
{"commits": ["sha subject"], "tests": "N passed, coverage X% (was 69%: why moved)",
 "sdk_upgrade": "from→to, what changed",
 "real_run": [{"slug": "", "verdict": "", "model_verdict": "", "flags": [],
   "long_form_scored": 0, "suitable": 0, "in_tokens": 0, "out_tokens": 0, "usd": 0}],
 "real_run_eyeball": "do scores look sane? examples",
 "deviations": ["anything differing from context.md, incl. workarounds"],
 "unresolved_issues": [""]}
