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
