# 0005 Agent vetting of channels

Date: 2026-10-28
Status: accepted

## Context

Phase 3 lets an agent do the first pass over candidate channels, so the human
reviewer (phase 4) starts from a judgement, not a blank page. The evidence snapshots
of decision 0004 hold what an agent can judge by. Calm matters as much as happy
(constitution), and a human approves the allowlist: agent reviews never change
status (0003). Per-video scores should be reusable by video assessment in phase 5.

## Decision

- **Input: the latest evidence snapshot only.** No transcripts, no thumbnails, no new
  YouTube calls. `channels vet` needs only `ANTHROPIC_API_KEY`.
- **Rubric** (`happytube/rubric.py`, shared with phase 5): `calm` 1–5 and `happy`
  1–5 per video, plus flags from a closed list — `war`, `disaster`, `violence`,
  `predation`, `death_sadness`, `scary`, `loud_fast`, `news`, `clickbait`, `promo`,
  `other`. A video is **suitable** when `calm >= 4`, `happy >= 3` and it has none of
  `war`, `disaster`, `violence`, `predation`, `death_sadness`, `scary`, `news`.
  Code decides suitability, not the model.
- **No Shorts scoring.** Only long-form videos (`is_short == false`) are sent and
  scored; the report counts Shorts as skipped.
- **Flags** (code, before any call): `unresolved` (no `channel_id` or no snapshot —
  no call, no report, no review: status `skipped_unresolved`), `inactive` (newest
  upload more than 365 days before `fetched_at`, or none), `mostly_shorts` (fewer
  than 5 long-form videos). `identity_doubt` is added when the model's
  `identity_match` is not `yes` (it compares the registry entry with the snapshot's
  title, custom URL, description, country and subscribers — look-alikes, 0004).
- **Verdict rule** (code): the model's `approve` becomes `unsure` when `inactive`,
  `mostly_shorts` or `identity_doubt` is set; `reject` and `unsure` pass through.
  The report keeps both `verdict` (final) and `model_verdict`.
- **Model output** (structured, strict pydantic): `identity_match`, `identity_note`,
  `channel_calm`, `channel_happy`, `verdict`, `summary`, `concerns`, and one score
  per long-form video. Every video sent must be scored exactly once; a missing,
  extra or repeated id is an error for that channel and nothing is written.
- **Vet report** — `channels/<slug>/vet/<UTC YYYYMMDDTHHMMSSZ>.md`, created
  exclusively (`-2`, `-3`… on collision, like evidence and reviews). YAML
  frontmatter (`VetReport`: `vetted_at`, `model`, `prompt_version`, `evidence_at`,
  `verdict`, `model_verdict`, `flags`, `identity_match`, `identity_note`,
  `channel_calm`, `channel_happy`, `summary`, `concerns`, `usage`, `videos` with
  `suitable`, `shorts_skipped`) and a markdown body for people (summary, identity,
  concerns, video table). The latest report is the newest `vetted_at`.
- **Agent review** — each successful vet also writes a `Review` with
  `reviewer: claude-vet`, `role: agent`, the final verdict, and notes with the
  summary, flags, why an approve was downgraded, and the report file name.
- **Re-vet: skip when current.** A channel whose latest report's `evidence_at`
  equals its latest snapshot's `fetched_at` is `skipped_current`; `--force` re-vets.
  Nothing is overwritten.
- **Model and SDK** — `claude-opus-5-5`, adaptive thinking (its default; `thinking`
  is not sent), `output_config.effort: medium`, structured output through
  `client.beta.messages.parse(output_format=VetOutput)` with the server-side refusal
  fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`). The
  beta namespace is needed for `fallbacks`. `stop_reason == "refusal"` is checked
  before reading output: a refused channel is `refused`, nothing written. `anthropic`
  is on the newest 1.x (1.17.0); 2.x (API version `2026-10-21`) is a later step.
- **Run safety** — an authentication, permission or billing error stops the run
  (later channels `not_vetted`), keeping files already written; rate limits and 5xx
  are retried by the SDK and then become a per-channel `error`. Messages carry the
  API's error type and text, never headers or the key. `--dry-run` makes no call,
  needs no key and writes nothing.
- **Cost** is reported per channel and in total from the response usage, at Opus 5.5
  list prices ($4 / $20 per million input / output tokens; one constant each).
- Code: `happytube/rubric.py`, `channels/vet.py` (pure: flags, prompt, verdict rule,
  report), `channels/vet_run.py` (`AnthropicVetClient`, `vet_channels`),
  `ChannelStore.add_vet` / `vets` / `latest_vet`, CLI `channels vet`; `list` and
  `show` include the latest vet.

## Consequences

- A human sees a verdict, the reasons, and a scored list of recent videos before
  deciding; every vet stays in git, so later reviewers can see what the agent saw.
- Per-video calm/happy scores and flags exist before phase 5 and use the same rubric.
- Judging from titles and descriptions misses what is only on screen; the rubric
  asks the model to score lower when in doubt.
- Each vet costs money (roughly 50 videos of text per channel); the skip-when-current
  rule keeps re-runs cheap. Changing the prompt means bumping `prompt_version`, and
  `--force` to re-vet.
- A mid-response refusal that leaves unparseable text surfaces as an `error`
  (parse fails before `stop_reason` can be read), not as `refused`.
