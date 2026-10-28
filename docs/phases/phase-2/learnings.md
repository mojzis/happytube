# Phase 2 — learnings (channel evidence)

Branch `phase-2-evidence`, `2a22ea7..dd47a67`, 15 commits, 2026-10-28.
Loop run: dev (incl. real API run) → review ‖ QA (QA scoped to runtime/env, separate
worktrees) → fix (real re-run skipped: invalid key) → orchestrator data commit (agent
reviews, at user's request) → combined verify (verdict `ship`) → learnings.
This matched the planned loop in log.md.

## Delivered

- `happytube/youtube.py`: `YouTubeClient` with an injectable getter, batching at 50,
  ISO-duration parsing, unit counting, key-safe errors (`RequestException` → no URL),
  `QuotaExceededError` / `InvalidKeyError` stop the run.
- `Evidence` model, pure `build_evidence`, `channels/collect.py` run logic. Store:
  `add_evidence` (append-only, `open("x")`, `-N`), `evidence`, `latest_evidence`,
  `set_channel_id` (null-only, raw-YAML rewrite, duplicate-id check, atomic replace).
- `channels resolve [--verify]`, `channels evidence`; `show` / `list` show evidence.
  Every requested channel appears in the output, also on an aborted run
  (`not_fetched`).
- Shorts are decided by UUSH-playlist membership. Fallback is the duration rule:
  ≤60 s before 2024-10-15, ≤180 s after. `shorts_source` is recorded.
- Real run: 13 of 15 handles resolved, 13 snapshots committed, ~57 units in total.
  Three seed handles corrected. ct-decko and zoo-zlin not found.
- Decision 0004, research note `channel-fetch-methods.md` (API vs RSS vs search,
  quota ~3N + N/50 per refresh, RSS recommended for phase 5 polling).
- Preexisting key leak in `videos.py` `YtQuery.get` fixed.
- Tests 122 → 183 (dev) → 212 (fix); coverage 59% → 68% → 69%; `poe check` green.

## What worked

- **Real API in the dev step.** It produced the phase's most important finding (see
  next point) and the look-alike channel. Mocks alone would have shipped a wrong
  Shorts rule and a wrong channel.
- **"If research shows the API path is wrong, flag it in deviations, don't silently
  switch."** Dev measured the orchestrator's ≤180 s Shorts rule on real data (Zoo
  Praha: 33/50 flagged, 0 real Shorts) and reported it rather than changing it. The
  orchestrator sent the question to review and QA. Both costed the UUSH switch. The
  fix brief then fixed the design. The settled decision was overturned in one round
  without a redesign loop.
- **Key hygiene held under pressure.** No agent read or printed `.env`. Dev found the
  stray character from the length (40 vs 39) and the API error alone. QA used a
  key-shaped regex (`AIza[0-9A-Za-z_-]{20,}`) over trees and `git log -p`, which
  avoids the false hits that the plain `AIza` grep gets on the briefs.
- **The fix brief forbade the workaround explicitly.** The fix agent stopped after
  1 unit on `API_KEY_INVALID`, wrote nothing, and reported `skipped: invalid key`.
  That aborted run also showed R1 working on real data (14 `not_fetched`).
- **Fix brief with pre-decided shapes** (404 = no Shorts, `shorts_source` default so
  old snapshots load, `not_fetched` status not message compare). All 9 items
  resolved in one pass. Verify: 9/9 resolved.
- **Verify judged the fix's own choices.** V2 (0-uploads skip labelled `uush`) came
  straight from a fix deviation; V3 from the new `Run.for_slugs` placeholders.
- **Content questions as registry data.** At the user's request the orchestrator
  recorded the four open human questions as agent `unsure` reviews (296c441). They
  appear in `channels list --needs-human-review` instead of a doc nobody reads.

## What each step caught that the previous missed

- **Dev (1)**: the Shorts false positives, the UUSH/UULF trick working, RSS shape
  (15 entries, no duration). It also found the `@NatureonPBS` look-alike (454
  subscribers), but only by reading the snapshot. forHandle "resolved" it fine. It
  fixed a preexisting broken test (`test_pipeline.py` read the real `.env`).
- **Review (2b)**: R1 (aborted run drops unreached channels; reproduced with 3
  slugs), R2 (`set_channel_id` rewrote the whole file, invented `added_at`, no
  duplicate check), R4 (key as plain str), R5 (legacy reasons, empty playlist 404,
  missing `publishedAt`), R6, R7, and the preexisting `videos.py` key leak. It noted
  the UUSH 404 trap (404 = no Shorts, not "fall back").
- **QA (2a)**, scoped to runtime: Q3 — `resolve` re-verified already-resolved
  channels, spending 13 units. This was an undeclared dev deviation that review
  missed. Also the ≤60 s pre-2024-10-15 Shorts rule (Dvůr Králové 47/50) and the
  Dvůr Králové activity question (newest upload 2024-08). Positive evidence: no-keys
  runs, same-second double write, quota mid-run, `ConnectionError` with `key=SECRET`.
- **Did the QA scoping work?** Mostly. QA's 8 base checks had no overlap with
  review's logic list. The overlap (Q1≈R3, Q2≈R1, Q4/Q5/Q6 ≈ review's `checks_ok`)
  came from the four orchestrator-added questions, which were copied into both
  briefs. That repeats the mistake phase 1 named. Q2≈R1 is real convergence: QA hit
  it through its quota-mid-run check, review through code reading.
- **Verify (4)**: V1 (latest by filename vs `fetched_at` can disagree), V2, V3, V4
  (O(N²) duplicate check; one broken channel.yaml blocks all writes), V5 (UUSH
  quota/invalid-key path tested only by hand), V6 (broken intermediate commit
  6a89bb6).

## Friction

- **Stray character in the key.** Dev worked around it by passing the first 39
  characters through a scratch wrapper. The brief didn't authorize that. It worked
  and nothing leaked (review and QA confirmed). But it was a judgement call on
  secrets that the user should make. 15 calls failed before `InvalidKeyError`
  existed. The fix brief forbade the workaround, so the real re-run is still pending.
- **Committed data is stale.** The 13 snapshots carry the old ≤180 s flags. They are
  append-only, so they stay; only a re-run adds correct ones.
- **forHandle "success" is not identity.** `@NatureonPBS` resolved to an unofficial
  channel. Nothing in the code flags it. The snapshot's title + subscriber count was
  the only signal, and only because dev looked.
- **Broken intermediate commit (6a89bb6).** The fix split commits by topic. The
  staged-only `ty` hook checked `settings.py` but not `cli/channels.py`, which still
  passed a `SecretStr` where a `str` was expected. Squash-merge covers it.
- `0004` says "one page" of UUSH while `max_videos > 50` paginates (wording nit).

## Wasted effort

- 15 failed API calls with the bad key, before the early stop existed.
- The four orchestrator-added questions answered twice (review and QA).
- Dev's real run committed data under a rule that was overturned in the next step.

## Deferred backlog

- V1: `latest_evidence` by filename vs `evidence()` by `fetched_at` — glob only
  timestamp names, or document the name as canonical.
- V2: 0-uploads snapshot records `shorts_source: uush` without a UUSH call —
  document in 0004 or record `duration`.
- V3: `not_fetched` placeholders should carry `handle` / `channel_id` from
  channel.yaml; would-be `no_handle` channels show as `not_fetched`.
- V4: duplicate-id check parses every channel.yaml per write (O(N²)); one broken
  file blocks all writes; unquoted `added_at` reformatted. One id index per run later.
- V5: tests for quota / invalid key during the UUSH call and the batched-channels
  error paths (`collect.py` 242-245, 249-251).
- V6: broken intermediate 6a89bb6 — merged as-is (user prefers full history over squash).
- **Real re-run pending**: fix `YTKEY` in `.env` (stray trailing character), then
  `uv run happytube channels evidence --all` (~42 units) and commit the UUSH-based
  snapshots.
- **Content questions** (agent `unsure` reviews, 296c441): ct-decko and zoo-zlin
  handles unknown; national-park-service identity (30.5k subscribers); zoo-dvur-kralove
  activity (newest upload 2024-08).
- Plan backlog: vetting should flag unresolved handles, inactive channels and
  look-alikes (low subscribers vs the name) as agent reviews itself.
- Still open from earlier: `videos.py` reads `YTKEY` via `os.getenv` (phase 5).
