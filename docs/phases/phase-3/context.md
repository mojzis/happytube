# Phase 3 — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-3-vetting`, base commit `c94a639`
(main after PR #9) + `0bbad42` (UUSH evidence refresh). Plan: `docs/plan.md` (phase 3
row). Principles: `docs/constitution.md`. Registry: decisions 0003, 0004. Phase 2
record: `docs/phases/phase-2/`. Process lessons: `docs/process-learnings.md`.

## Goal

`happytube channels vet` — Claude judges a channel from its latest evidence snapshot
against the calm/happy rubric, writes an append-only **vet report** and an **agent
review record**. Per-video calm/happy scores in the report are reused later by video
assessment (phase 5). Deterministic **flags** (unresolved, inactive, mostly Shorts,
identity doubt) make the tool surface human questions itself (phase 2 backlog).

## Decisions settled (user + orchestrator, 2026-10-28)

Record in `docs/decisions/0005-agent-vetting.md` (accepted).

- **Input: latest evidence snapshot only.** No transcripts, no thumbnails, no new
  YouTube calls. Vet is Anthropic-only (`ANTHROPIC_API_KEY`), no `YTKEY`.
- **Output: report + agent review + per-video scores** (format below).
- **Re-vet: skip when current.** A channel whose latest vet report has
  `evidence_at` == latest snapshot's `fetched_at` is skipped (`skipped_current`);
  `--force` re-vets. Append-only: nothing is overwritten.
- **Model: `claude-opus-5-5`**, adaptive thinking (default — don't send `thinking`),
  `output_config.effort` explicitly `"medium"`. Structured output via
  `client.messages.parse(..., output_format=<pydantic model>)`. Load the
  `claude-api` skill (Skill tool) before writing Claude code; never guess SDK usage.
  Refusal fallbacks: the skill says to include server-side `fallbacks` by default for
  opus-5-5; add it if the installed SDK supports it with `parse`, otherwise flag in
  `deviations`. Always check `stop_reason == "refusal"` before reading output.
- **SDK upgrade first.** Installed `anthropic` is 0.73.0 (latest 2.3.0). Upgrade to the
  **newest 1.x** as a separate first commit, following the skill's
  `python/claude-api/sdk-upgrade.md` (`uv lock --upgrade-package anthropic` with a
  `>=1.x,<2` pin; existing `stages/assess.py`, `enhance.py`, `claude_response.py`
  must keep working — tests). 2.x (API version `2026-10-21`) is out of scope → backlog.
  Don't touch the legacy stages' models/prompts beyond what the upgrade requires.
- These are settled facts about an external system as far as we know. If the real
  run shows one is wrong (SDK shape, parse support, model behaviour), **flag it in
  `deviations`, don't silently switch.**

## Rubric (shared module, reused by phase 5 video assessment)

New module `happytube/rubric.py`: the rubric text + the video-score model, so the
channel vet and later video assessment use the same definitions. Audience: an
elderly viewer with early dementia, easily frightened, scared by war news; Czech or
English. From the constitution: **calm matters as much as happy.**

- `calm` 1–5: 5 = gentle, slow, quiet narration/music, no tension; 1 = alarming,
  loud, fast cuts, suspense, shouting.
- `happy` 1–5: 5 = joyful, warm, cute, uplifting; 1 = sad, grim, distressing.
- `flags` (closed list, a video can have several): `war`, `disaster`, `violence`,
  `predation` (predators hunting/killing, injured animals), `death_sadness`
  (death, illness, loss, rescue of suffering animals), `scary` (creepy, horror,
  dangerous animals framed as threat), `loud_fast` (hype editing, shouting,
  countdowns), `news` (news/current affairs/politics), `clickbait`, `promo`
  (ads, merch, fundraising appeals dominating), `other`.
- A video is **suitable** when `calm >= 4 and happy >= 3 and no flag` in
  {war, disaster, violence, predation, death_sadness, scary, news}. Expose this as a
  function; don't let the model decide it.
- Score **only long-form videos** (`is_short == false`); Shorts are listed as
  skipped, never sent for scoring (No Shorts principle).

## Flags (deterministic, computed before any Claude call)

Pure function over `Channel` + latest `Evidence` → list of flags:
- `unresolved` — `channel_id` null or no evidence snapshot. **No Claude call**;
  status `skipped_unresolved`, no report, no review (an orchestrator `unsure`
  review already exists for these; don't add duplicates on every run).
- `inactive` — newest upload older than 365 days before `fetched_at`.
- `mostly_shorts` — fewer than 5 long-form videos in the snapshot.
- `identity_doubt` — set from the model's `identity_match` answer (below) when it is
  not `yes`. Claude compares registry name/kind/languages with snapshot title,
  custom_url, description, country, subscribers (look-alikes like `@NatureonPBS`).

**Final verdict rule** (code, not model): model verdict `approve` becomes `unsure`
when any of `inactive`, `mostly_shorts`, `identity_doubt` is set. `reject` and
`unsure` pass through. The review note says why.

## Model output (pydantic, `extra="forbid"`)

```
identity_match: yes | no | unsure
identity_note: str
channel_calm: 1–5
channel_happy: 1–5
verdict: approve | reject | unsure
summary: str            # 1–3 sentences, plain language, for the human reviewer
concerns: list[str]     # concrete, cite video titles
videos: list[{video_id, calm, happy, flags: list[Flag], note}]   # long-form only
```

Validate after parse: every scored `video_id` is one of the long-form ids sent; a
missing or extra id → error for that channel (no files written).

## Vet report (append-only file)

`channels/<slug>/vet/<UTC compact ts>.md`, created exclusively like evidence/reviews
(reuse `_write_new` / `_stamp`; `-N` on collision). YAML frontmatter (pydantic
`VetReport`, `extra="forbid"`) + markdown body:

```yaml
vetted_at: '2026-10-28T…Z'
model: claude-opus-5-5
prompt_version: 1
evidence_at: '2026-10-28T19:16:18.770826Z'   # fetched_at of the snapshot used
verdict: unsure            # final, after the rule
model_verdict: approve
flags: [inactive]
identity_match: yes
channel_calm: 4
channel_happy: 4
usage: {input_tokens: …, output_tokens: …}
videos:                     # long-form only, snapshot order
- {video_id: …, title: …, calm: 5, happy: 4, flags: [], suitable: true, note: …}
shorts_skipped: 4
```

Body: `# <channel name> — vet`, summary, identity note, concerns, a table of videos
(title, calm, happy, flags, suitable). Human-readable; unicode literal.

Store: `ChannelStore.add_vet(slug, report, body)`, `vets(slug)` (ordered),
`latest_vet(slug)`; store stays click/rich-free (phase 4 Flask reuses it). Read the
frontmatter back with the same validation path as other records.

## Agent review

One `Review` per successful vet: `reviewer="claude-vet"`, `role="agent"`,
`verdict` = final verdict, `notes` = summary + flags + `vet/<filename>`. Agent
reviews never change status (decision 0003) — unchanged.

## CLI

`happytube channels vet [SLUG…] [--all] [--force] [--dry-run] [--json]`

- Per channel status: `vetted` / `skipped_current` / `skipped_unresolved` /
  `refused` (stop_reason refusal; no files) / `error` (with message).
- `--dry-run`: no Claude call, no key needed, no files — prints flags and what would
  be vetted/skipped.
- Totals: input/output tokens and an estimated cost (Opus 5.5: $4 in / $20 out per
  MTok; constants in one place).
- Missing `ANTHROPIC_API_KEY` → clear error, exit ≠ 0 (except `--dry-run`).
  `AnthropicSettings(BaseSettings)` with only that key as `SecretStr`, like
  `YouTubeSettings`. Other commands keep working with no keys.
- Authentication / permission / credit errors stop the run (later channels
  `not_vetted`), keep files already written, exit ≠ 0. Rate limit / 5xx: SDK retries;
  if still failing, that channel is `error`, run continues. Never print the key or
  the raw exception if it might contain headers.
- `show` gains a latest-vet summary (verdict, flags, calm/happy, suitable count,
  path; full report in `--json`). `list` JSON gains `vetted_at` and `vet_verdict`.
- JSON contract as before: stdout only, errors on stderr, exit ≠ 0 on failure.

## Code shape

- `happytube/rubric.py` — rubric text, `Flag` literal, `VideoScore`, `is_suitable`.
- `happytube/channels/vet.py` — pure parts: `channel_flags`, `build_prompt`
  (system + user content; deterministic, cache-friendly: stable system first),
  `apply_verdict_rule`, `render_report`. The Claude call behind an injectable
  callable/protocol so tests use a fake; **no network in tests**.
- Orchestration in `channels/collect.py` style (a `vet_channels` run returning a
  `Run`-like result), CLI in `cli/channels.py`.
- Prompt: system = role + audience + rubric + output instructions; user = registry
  entry + snapshot fields + long-form videos (id, title, published, duration,
  language, description). Keep `prompt_version` constant; bump on change.

## Real run

- Dev: **exploratory only, nothing committed.** Copy `channels/` to a scratch dir
  (`/tmp/claude-1000/-home-matous-git-happytube/…/scratchpad/p3-channels`), run
  `uv run happytube channels vet bbc-earth zoo-praha national-park-service
  --channels-dir <copy>` in the main checkout (only it has `.env`). Do a 1-channel
  probe first. If the key fails, **stop and report** — don't work around it. Report
  verdicts, flags, tokens, cost per channel, and whether the scores look sane by eye
  (e.g. predation videos flagged, Czech handled).
- Never print, log, cat or commit `.env` or any key.
- The committed `vet --all` run happens after verify, by the orchestrator.

## Docs

`docs/decisions/0005-agent-vetting.md` (accepted): rubric, flags, verdict rule,
report layout, re-vet rule, model + SDK, no-Shorts scoring. Update CLAUDE.md
(channels CLI `vet`, storage tree `vet/`, key notes: vet needs only
`ANTHROPIC_API_KEY`) and `docs/architecture.md`. Don't touch `docs/plan.md`,
`docs/next-session.md`, `docs/phases/` (except committing `docs/phases/phase-3/`
as-is first).

## Existing code to know

- `channels/models.py` (`Channel`, `Review`, `Evidence`, `EvidenceVideo`, `_iso_z`,
  UTC validators), `channels/store.py` (`ChannelStore`, `_write_new`, `_stamp`,
  `_load_records`, `_latest_by_name`, `_load_model`, `ChannelStoreError`),
  `channels/collect.py` (`Run`, `ChannelResult`, stop semantics),
  `cli/channels.py` (subgroup, `--json`, `_store_errors_as_click`, `_select_slugs`,
  `_report`), `config/settings.py` (`YouTubeSettings` pattern).
- `stages/assess.py`, `enhance.py`, `claude_response.py` — legacy Claude use; must
  survive the SDK upgrade.

## Verification baseline

Before: 212 tests pass, `poe check` green, coverage 69%. After: `uv run poe check`
green; `uv run poe typecheck` before each commit of a multi-commit step. New tests:
flags (each rule, boundaries 365 days / 5 videos), verdict rule, prompt build
(Shorts excluded, deterministic), output validation (missing/extra ids), report
render + store round-trip (append-only, latest, collision), re-vet skip/force,
refusal and auth-error paths with a fake client, CLI vet `--json`/`--dry-run`/no key,
list/show with and without vets.

## Tooling gotchas

- Parallel agents: own worktree via `git worktree add --detach <path> phase-3-vetting`,
  `uv sync` there, remove + prune after. Worktrees have no `.env`: fakes only.
- Don't run pytest concurrently in one checkout (shared `.coverage`).
- madoqua hook on staged .py only; never `--no-verify` / `MADOQUA_SKIP`.
- Staged-only `ty` misses cross-file breakage: `uv run poe typecheck` per commit.
- `tyf` index stale after hook reformat: `uv run tyf daemon restart`.
- Secret grep: `git grep -E 'sk-ant-[A-Za-z0-9_-]{20,}'` and over `git log -p`.
