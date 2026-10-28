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

## 2a — review
Verdict `fix`. Findings (verbatim, abridged):

- R1 medium — a per-channel fetch error (or assess batch error) stops `run`; assess/
  enhance read only `--date`, seen set blocks refetch → other channels' videos of
  that date never assessed by later daily runs. Reproduced with fakes. Fix: assess/
  enhance pick up every pending file up to `--date`, or `run` continues past
  per-channel fetch errors (exit ≠ 0, stop only on quota/key). Record in 0009.
- R2 medium — `assess --force` turning a video unsuitable leaves its enhance file
  (reproduced). Fix: delete enhance file when no longer suitable, or readers gate on
  assess `suitable`; test.
- R3 low — `run` without ANTHROPIC_API_KEY: ClickException in assess before anything
  printed; fetch report lost, `--json` empty. Fix: check key up front or print fetch
  step first.
- R4 low — YouTube video_id becomes a filename unchecked. Fix: `^[A-Za-z0-9_-]{11}$`.
- R5 low — claude.py imports VetUsage from channels.models (layering). Fix: Usage in
  claude.py, VetUsage the alias.
- R6 low — cli/trusted.py imports 4 private helpers from cli/channels.py. Fix: public
  or cli/common.py.
- preexisting: UTC published date vs local `--date` window edge; fallback/cache priced
  at Opus base rates (documented).
- deviations judged: ClaudeCaller byte-identical to old vet call, checked vs SDK;
  aliases used by tests, OK; no fail path ends exit 0; quota mid-channel can't leave
  files (videos() returns before first write) — dev's concern doesn't apply;
  TrustedStage/--date callback/skipped_unresolved OK; re-paid batches OK for now.

## 2b — QA
Verdict `fix`. poe check green (445, 82%). Verified (abridged): `--json` contract and
exit codes for every subcommand (success 0, error 1, stop 1, bad date 2, unknown /
candidate slug 1); keys: status, dry-runs, nothing-to-do need none, missing key →
clear error exit 1; fake YTKEY (1 unit) and fake Anthropic key stop, nothing
written, no key text anywhere; run chain stops on fetch error and assess stop;
status counts match seeded files; daily_run.sh stubbed both modes, failure → exit 1,
unknown pipeline → 2; legacy fetch fake key → exit 1, legacy help unchanged, vet
dry-run OK; frontmatter fields complete, Czech + emoji round-trip; idempotent.

- Q1 medium — = R2 (enhance file stays after `assess --force` → unsuitable).
- Q2 low — fetch JSON: `channel_id` null for not_fetched and the stopping channel.
- Q3 low — fetch checks YTKEY before slugs: unknown slug without key → "YTKEY is not
  set".
- preexisting: MarkdownFile.save without allow_unicode (Czech escaped in files);
  daily_run.sh hardcodes HAPPYTUBE_DIR=/home/user/happytube; legacy stages ~20% cov.

## 3 — fix
Commits 72e865d..5ab4997 (4). 456 passed, coverage 82%, poe check green.

- R1: `TrustedStage.load_until()` + `stages.pending()`; assess/enhance pick up every
  pending file ≤ `--date`, output under the fetch file's date; `--force` only
  `--date`. `run` continues past per-channel / per-batch errors (exit 1, "Some items
  failed in <steps>"), chain ends only on aborted. Tests incl. review's repro. 0009,
  CLAUDE.md, architecture updated.
- R2 (Q1): suitable:false deletes enhance files (all dates), `unenhanced` in result.
- R3: run builds both clients before fetch; no Claude key → exit 1, nothing fetched.
- R4: `is_video_id()`; bad id → unreadable, not written.
- R5: Usage model in claude.py, VetUsage alias; 13 committed vet files load.
- R6: `cli/common.py` (shared options and helpers) used by channels, trusted, serve.
- Q2: not_fetched carry channel_id. Q3: slugs validated before YTKEY.
- Promoted: MarkdownFile allow_unicode; daily_run.sh HAPPYTUBE_DIR defaults to repo.
- deviations: same id fetched on two dates → processed once (earliest, or target
  under --force); `skipped` counts only target date; fetch_trusted(channels, …).
- unresolved: re-scored-suitable video keeps old enhance file with stale scores in
  frontmatter (readers should take scores from assess).
