# Phase 5a — log

Loop (planned): dev → review ‖ QA (QA runtime-only, incl. failure paths and cost
counters) → fix → combined verify → learnings.

Decisions taken with the user before dev (2026-10-28): see context.md "Decisions
settled" (5a/5b/5c split, side by side, Opus 5.5 assess, enhance on suitable,
no human video approval).

Orchestrator pre-checks: baseline 406 passed / 78%; YTKEY and ANTHROPIC_API_KEY
present in `.env`; no crontab entry for happytube.

## 1 — dev
Report (verbatim JSON, abridged formatting):

- commits: 4e66017 shared Claude call + RUBRIC_VERSION; 914ba36 shared Shorts/uploads
  helpers + video-id check; 6e671b8 legacy fetch fatal error → exit 1; 8d5580f
  `happytube trusted` fetch/assess/enhance/run/status; 30f6247 decision 0009, docs,
  daily_run.sh.
- tests: 445 passed (was 406), coverage 82% (was 78%; new modules well covered).
- shared extraction: `claude.py` (MODEL, EFFORT, prices, estimate_usd, Prompt,
  ClaudeError/CallError/StoppingError, call_error, Reply[T], output_format,
  ClaudeCaller.call); vet_run keeps old names as aliases, AnthropicVetClient
  delegates; rubric RUBRIC_VERSION=1 + id_mismatch(); collect.fetch_short_ids public;
  evidence.uploads_playlist_id, evidence_video(description_max=None).
- real run: zoo-praha probe 3 units 0 new (newest 2026-09-15); all 11 approved: 42
  new, 33 units; assess probe explore-org 3/3 suitable; explore-org + bbc-earth
  assess+enhance, opus-5-5 no fallback; second fetch 0 new, files md5-identical;
  assess rerun 0 calls; fake YTKEY → stop, not_fetched, exit 1, no key printed;
  fake Anthropic key → 401 stop, exit 1.
- cost: YouTube ~78 units; Anthropic ≈ $0.08.
- eyeball: bbc-earth 8, cincinnati 6, explore-org 3, nat-geo-kids 13, pbs-nature 11,
  san-diego 1, others 0. 221 Shorts excluded (all via UUSH), 9 live/upcoming.
  Suitable explore-org 3/3, bbc-earth 1/8 (predation compilations). Example notes:
  "High-speed chase of an Arctic wolf pursuing a newborn caribou calf…" (1/1,
  predation); "Gentle highlights of beluga whales…" (5/5).
- deviations: TrustedStage.run() raises NotImplementedError (work in
  fetch/assess/enhance_trusted); own --date callback (circular import), bad date →
  exit 2; UUSH Shorts dropped before videos.list, recounted as `shorts` each run;
  approved-but-unresolved = skipped_unresolved, exit 0; daily_run.sh `pipefail`
  (affects legacy too), HAPPYTUBE_PIPELINE=trusted; enhance one call/video,
  structured output, new TRUSTED_ENHANCE_PROMPT; Usage = alias of VetUsage;
  cli/trusted.py imports private helpers from cli/channels.py.
- unresolved: player still legacy (5b); failed/refused batch re-paid each rerun;
  quota stop mid-channel leaves files but result `error` with no paths.
