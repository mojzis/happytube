# Phase 3 — log

Loop (planned): dev → review ‖ QA (QA runtime-only) → fix → combined verify →
orchestrator committed `vet --all` run → learnings.

Decisions taken with the user before dev (2026-10-28): input = latest snapshot only;
output = report + agent review + per-video scores; re-vet = skip when current,
`--force`; model = claude-opus-5-5.

Pre-phase: `0bbad42` — evidence refresh after the YTKEY fix (UUSH Shorts, 13
snapshots). Sanity: no Shorts >180 s; sub-60 s horizontal clips correctly not Shorts;
smithsonian-channel newest upload 2024-06 (inactive).

## 1 — dev
Report (verbatim JSON, abridged formatting):

- commits: 025eca5 docs plan; 29097c7 anthropic 0.73.0 → 1.17.0; 87afe0b vetting core;
  cafe169 CLI vet + list/show; 87d57bf decision 0005, CLAUDE.md, architecture.
- tests: 287 passed, coverage 75% (was 69%; new modules ~97–100% with fake client).
- real_run: blocked — 1-channel probe got 401 invalid x-api-key (ANTHROPIC_API_KEY in
  .env). Stopped as instructed; stop path clean (exit 1, `aborted`, no key printed,
  nothing written). Dry run: 13 would_vet, ct-decko + zoo-zlin skipped_unresolved;
  smithsonian-channel + zoo-dvur-kralove inactive (orchestrator: correct, newest
  2024-06 / 2024-08).
- deviations: beta `messages.parse` (only it takes `fallbacks`), fallbacks "default";
  frontmatter also stores identity_note/summary/concerns; dry-run status `would_vet`;
  refused/error → exit ≠ 0; input token cost includes cache tokens at base rate;
  0-upload channel flagged inactive + mostly_shorts and still sent for identity;
  credit errors by 401/402/403 or 'credit balance'; parse failure on max_tokens /
  mid-response refusal → `error: model output did not parse`, not `refused`.
- unresolved: bad Anthropic key; prompt quality, max_tokens 16000, fallback, real
  cost unverified.

Orchestrator: user must fix ANTHROPIC_API_KEY (same as phase 2's YTKEY: user only).
Review ‖ QA proceed with fakes.

## 2 — review ‖ QA
Review (verdict ship): R1 medium — beta `parse` validates before return, so refusal
check can't precede output read; max_tokens / out-of-range score → "did not parse"
with stop_reason hidden and tokens (cost) unrecorded; fix: beta `create` with
json_schema format, check stop_reason, then `model_validate_json`. R2 low — fallback
model not recorded, cost priced at Opus 5.5. R3 low — CLAUDE.md "rest need no keys".
R4 low — VetStoppingError subclass of VetCallError (handler order load-bearing);
comment 'credit balance'. R5 low — cleanups (suffix-string loader choice, unused
CHANNEL_FLAGS, summary_dict dumps whole report, verdict typed str). R6 low — prompt
bump leaves vets current; say so in --help. Deviations: all accepted except parse →
R1. Preexisting: ChannelStoreError mid-run aborts whole command, per-channel JSON lost.

QA (verdict ship): all checks green (dry-run, no key, happy path with Czech, re-vet /
--force / same-second collisions, refusal/parse/missing/extra id, 401 mid-run,
529, real client over MockTransport, --json, other commands no keys, secret grep).
Q1 low — `vet --all` vets human-rejected channels (paid, pointless). Q2 low — --json
failure says "see the report above". Q3 low preexisting — legacy `report` needs both
keys. Q4 low — vet asks for key even when nothing needs a call.

Orchestrator: fix R1, R2, R3, R4, R5, R6, Q1, Q2. Defer Q3, Q4, preexisting abort.

## 3 — fix
Fix report: commits 11522c2 (create + json_schema, stop_reason first; skip rejected),
fd9f398 (CLI/store cleanups, --force note), c1806a0 (docs). 298 passed, 75%.
Resolved R1–R6, Q1, Q2. Deviations: `_call_error` returns VetError base; store
imports private `_iso_z`; "did not parse (1 problems)" grammar; architecture.md
unchanged. Unresolved: real-API shapes (json_schema, fallback content layout, usage
across fallbacks) unverified — key still invalid.

## 4 — verify (combined review + QA)
Verify (verdict ship): R1–R6, Q1, Q2 resolved end to end (real SDK over httpx2
MockTransport through the CLI). Deviations accepted. V1 low — tokens of a declined
attempt before a fallback (usage.iterations) not counted. V2 low — text-after-last-
fallback-block layout unverified offline; fails safe. V3 low — text output doesn't
name the answering model. All → backlog.

## 5 — orchestrator real run

User fixed ANTHROPIC_API_KEY. Probe on scratch copy (zoo-praha): approve, 45/50
suitable, 14 210 in / 4 404 out, $0.14; eyeballed: lion feeding → predation, snakes →
scary, army aircraft → war (strict but safe), Czech handled.

Committed run `vet --all`: 13 vetted, 2 skipped_unresolved (ct-decko, zoo-zlin);
118 916 in / 45 204 out tokens, est. $1.38. Verdicts: approve — cincinnati-zoo,
explore-org, san-diego-zoo, zoo-praha; unsure — monterey-bay-aquarium, nat-geo-kids,
national-park-service, pbs-nature, smithsonian-channel [inactive], zoo-dvur-kralove
[inactive, model approve]; reject — bbc-earth, bbc-earth-kids, national-geographic.
All identity_match yes. No fallback, refusal or error.

Observation: run-to-run variance — zoo-praha 45/50 suitable in the probe, 39/50 in
the committed run (same snapshot, same prompt). Per-video scores near the
threshold are not stable; humans judge, phase 5 should not treat one vet as final.
