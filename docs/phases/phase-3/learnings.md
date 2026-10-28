# Phase 3 — learnings (agent vetting)

Branch `phase-3-vetting`, `0bbad42..e3f36a6`, 12 commits, 2026-10-28.
Loop run: dev (real run blocked: invalid key) → review ‖ QA (QA runtime-only,
separate worktrees) → fix → combined verify (`ship`) → orchestrator probe + committed
`vet --all` run → learnings. This matched "Loop (planned)" in log.md. The only change:
the orchestrator ran a 1-channel probe on a scratch copy before the committed run,
because dev's exploratory run never happened.

## Delivered

- `anthropic` 0.73.0 → 1.17.0 (newest 1.x) as its own commit. Legacy assess/enhance
  stages kept working.
- `happytube/rubric.py`: calm/happy 1–5, closed `Flag` list, `is_suitable` in code.
  Shared with phase 5 video assessment.
- `channels/vet.py`: deterministic flags (`unresolved`, `inactive`, `mostly_shorts`,
  `identity_doubt`), verdict rule (approve → unsure on any flag), prompt build (Shorts
  never sent), report render. Claude call behind an injectable seam.
- Claude call: beta `messages.create` with `output_config` (effort medium + json_schema
  from `VetOutput`), `fallbacks="default"`, `stop_reason` checked first, then
  `model_validate_json`. Every outcome records tokens. Answering model recorded.
- Store: `add_vet`, `vets`, `latest_vet` (append-only, `-N`). One `claude-vet` agent
  review per vet.
- CLI `channels vet [SLUG…] [--all] [--force] [--dry-run] [--json]`. Statuses
  `vetted`, `skipped_current`, `skipped_unresolved`, `skipped_rejected`, `refused`,
  `error`, `not_vetted`. Token totals and cost estimate. `show` / `list` show the
  latest vet.
- Decision 0005, CLAUDE.md, architecture.md.
- Tests 212 → 287 (dev) → 298 (fix); coverage 69% → 75%; `poe check` green.
- Committed run (e3f36a6): 13 vet reports + 13 agent reviews.

## What each step found

- **Dev (1)**: built everything. Real run blocked by a 401 on `ANTHROPIC_API_KEY`. It
  stopped as told: exit 1, `aborted`, no key printed, nothing written. Dry run was
  correct (13 would vet, 2 unresolved, smithsonian + dvur-kralove inactive). Honest
  deviations list: beta `parse` (only it takes `fallbacks`), cost counting cache
  tokens at base rate, parse failure reported as `error` not `refused`.
- **Review (2b)**: R1 (medium) — beta `parse` validates before it returns. So the
  refusal check can't come first, and a `max_tokens` cutoff or an out-of-range score
  shows as "did not parse" with no stop_reason and no tokens counted. Fix: `create` +
  json_schema, stop_reason first, then validate. R2 fallback model not recorded.
  R3–R6 docs, error-class chain, cleanups, `--force` note. Preexisting: a
  `ChannelStoreError` mid-run aborts the whole command.
- **QA (2a)**, runtime only: Q1 `vet --all` vets human-rejected channels (paid,
  pointless). Q2 `--json` failure text said "see the report above". Q3, Q4 low.
  Positive evidence: dry run without key, Czech unicode, same-second collisions,
  401 mid-run, 529, real SDK over MockTransport, no secrets in history.
- **Fix (3)**: R1–R6, Q1, Q2 in three commits. Own deviations: `_call_error` returns
  the `VetError` base; store imports private `_iso_z`; "1 problems" grammar.
- **Verify (4)**: 8/8 resolved end to end through the real SDK over MockTransport.
  V1–V3 low, all backlog.
- **Orchestrator real run (5)**: probe, then `vet --all`. No fallback, refusal or
  error.

## Product learnings

- **Verdicts look sane.** Approve: cincinnati-zoo, explore-org, san-diego-zoo,
  zoo-praha. Reject: bbc-earth, bbc-earth-kids, national-geographic (predators,
  crime, disasters). Unsure: monterey-bay-aquarium, nat-geo-kids,
  national-park-service, pbs-nature, smithsonian-channel, zoo-dvur-kralove. All
  identity_match `yes`.
- **The verdict rule did its job once.** zoo-dvur-kralove: model approve → unsure
  (inactive). smithsonian-channel was already unsure from the model.
- **Flags are strict but safe.** Lion feeding → predation, snakes → scary, army
  aircraft → war. For this audience a false "unsuitable" costs little. A human may
  still want to see why a calm video was dropped.
- **Run-to-run variance is real.** zoo-praha scored 45/50 suitable in the probe and
  39/50 in the committed run. Same snapshot, same prompt. Scores near the threshold
  flip. One vet is a signal, not a verdict. Phase 5 should not treat one score as
  final; humans decide channels anyway (decision 0003).
- **Small long-form samples.** cincinnati-zoo and san-diego-zoo had 38 Shorts of 50,
  so 12 long-form videos were scored. They are above the `mostly_shorts` bar (<5)
  but the sample is thin. Worth a look before raising trust in their approve.
- **Cost is low.** 13 channels: 118 916 in / 45 204 out tokens, est. $1.38 (~$0.11
  per channel). Re-vetting the registry is cheap. The probe alone was $0.14.
- Czech titles and descriptions were handled without trouble.

## Friction

- **Bad credential again** (second phase in a row, now `ANTHROPIC_API_KEY`). Dev
  stopped cleanly, but review, QA, fix and verify all ran on fakes. Real-API shapes
  (json_schema, fallback layout, usage across fallbacks) stayed unverified until the
  orchestrator's run after the user fixed the key.
- **`--channels-dir` is a group option.** It must come before the subcommand:
  `happytube channels --channels-dir X vet …`. context.md wrote it after `vet`.
- R1 came from the settled SDK choice (`parse` + fallbacks). The "flag it, don't
  silently switch" clause made dev report it; review judged it.

## Deferred backlog

- **Q3** (preexisting): legacy `report` needs both keys.
- **Q4**: `vet` asks for `ANTHROPIC_API_KEY` even when every channel would be
  skipped (nothing to call).
- **Preexisting**: a `ChannelStoreError` mid-run aborts the whole `vet` command; the
  per-channel JSON of channels already done is lost.
- **V1**: tokens of a declined attempt before a fallback are not counted. Read
  `usage.iterations` to include them.
- **V2**: text layout after fallback blocks is unverified. No fallback happened in
  the real run, so it is still untested on real data. It fails safe (error, no files).
- **V3**: text output doesn't name the answering model (JSON and report do).
- **anthropic SDK 2.x** (API version `2026-10-21`): out of scope, still to do.
- "did not parse (1 problems)" grammar.
- Store imports the private `_iso_z` from models; make it public or move it.
- Product: thin long-form samples on Shorts-heavy channels; variance means phase 5
  needs a policy for repeated or averaged scores.
