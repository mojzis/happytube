# Phase 1 — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-1-channels`, base commit
`ce54e00ebfd5bec3623997c6bc38608d35dc0b6c`. Plan: `docs/plan.md` (phase 1 row). Principles: `docs/constitution.md`.
Decisions: `docs/decisions/0002-review-store-files-cli-web.md`. Source idea:
`/home/matous/git/ideas/projects/happytube/ideas/trusted-channels.md`.

## Goal

A git-tracked channel registry with review records, and a `happytube channels` CLI
(`add / list / show / review`, `--json`) that agents and humans use. Seeded with the
starter candidates. No YouTube or Claude calls in this phase.

## Decisions settled for this phase (orchestrator, 2026-10-28)

Record them as `docs/decisions/0003-channel-registry-layout.md` (accepted).

- **Layout** — one directory per channel, co-located reviews (append-only, one file
  per review, so concurrent writers never touch the same file). Phase 2 will add
  `evidence/`, phase 3 `vet/` next to them.
  ```
  channels/
    bbc-earth/
      channel.yaml
      reviews/
        20261028T101500Z-matous.yaml
        20261028T102030Z-claude-vetter.yaml
  ```
  Review filename: `<UTC compact timestamp>-<reviewer slug>.yaml`; on collision
  append `-2`, `-3`. Never overwrite.
- **Status is derived, not stored**: the latest *human* review whose verdict is
  `approve` or `reject` decides (`approved` / `rejected`); otherwise
  `candidate`. Agent reviews never change status (constitution: a human approves).
  So `channel.yaml` is written once by `add` and only by humans editing metadata.
- **Blocklist**: no separate list — a `rejected` channel is the blocklist entry
  (closes the open question in the idea doc / next-session.md).
- **channel.yaml** fields: `slug`, `name`, `kind`
  (`broadcaster|zoo|aquarium|park|museum|other`), `languages` (list, `cs`/`en`,
  validate against a small allowed set), `handle` (`@…`, optional),
  `channel_id` (`UC…`, optional — phase 2 resolves), `url` (optional),
  `added_by`, `added_at` (UTC ISO), `notes` (optional).
- **Review record** fields: `reviewer` (name), `role` (`human|agent`),
  `verdict` (`approve|reject|unsure`), `notes`, `created_at` (UTC ISO).
- Pydantic models for both (existing style: `models/`). YAML via `yaml.safe_load`
  / `safe_dump`, `sort_keys=False`, `allow_unicode=True` (Czech names: Zoo Zlín,
  Dvůr Králové).
- **Slug**: kebab-case ASCII from the name (strip diacritics), or `--slug`. `add`
  fails (exit ≠ 0, clear message) if the slug exists or a channel with the same
  `channel_id`/`handle` exists.
- **Location**: `channels/` at repo root. CLI group option
  `--channels-dir` (click `envvar="HAPPYTUBE_CHANNELS_DIR"`, default
  `PROJECT_ROOT / "channels"` from `happytube/paths.py`) — tests use `tmp_path`.
  Not `Settings`: it requires API keys.

## CLI shape

`happytube channels …` — a click subgroup. **Must not require API keys**
(`require_credentials` is per-command, the root group doesn't validate — keep it so).

- `add NAME --kind K --language cs [--language en] [--handle] [--channel-id]
  [--url] [--slug] [--notes] --added-by WHO [--json]` → prints slug / JSON.
- `list [--status candidate|approved|rejected] [--kind] [--language]
  [--needs-human-review] [--json]` → rich table or JSON array (each item includes
  derived `status` and review counts). `--needs-human-review`: no human review yet.
- `show SLUG [--json]` → channel + derived status + all reviews (chronological).
- `review SLUG --reviewer WHO --role human|agent --verdict approve|reject|unsure
  [--notes] [--json]` → writes a review file, prints the new derived status.
- JSON goes to stdout only (no rich markup mixed in), stable keys, exit 0;
  errors → stderr, exit ≠ 0. Agents parse this.

Keep logic in a small module (e.g. `happytube/channels/` package: `models.py`,
`store.py`) — the CLI is a thin layer; phase 4's Flask UI will call the same store.

## Seed

`channels add` (or a one-off script — don't commit the script) for the idea doc's
starter list, all `candidate`, `added_by: claude-seed`, notes "seed from idea doc,
unverified": BBC Earth, BBC Earth Kids, National Geographic, Nat Geo Kids,
Smithsonian Channel, PBS Nature, San Diego Zoo, Monterey Bay Aquarium, Cincinnati
Zoo, National Park Service, explore.org, Zoo Praha, Zoo Zlín, ZOO Dvůr Králové,
Česká televize (children's — name it e.g. "ČT :D / Déčko"). Handles only where you
are confident; leave `channel_id` empty (phase 2 resolves). No reviews in the seed.

## Existing code to know

- `cli/commands.py` — root group `cli`; add the subgroup in a new module
  (e.g. `cli/channels.py`) and register it, don't grow commands.py.
- `models/markdown.py`, `models/video.py` — pydantic/yaml style references.
- `utils`: `utc_now_iso()`; `paths.PROJECT_ROOT`.
- Tests: `tests/test_cli.py` uses `CliRunner` + `monkeypatch`.

## Docs to update

CLAUDE.md (CLI section + storage tree: `channels/`), `docs/architecture.md`
(registry moves from Planned to Components/Data), decision 0003. Don't touch
`docs/plan.md`, `docs/next-session.md`, `docs/phases/`.

## Verification baseline

Before: 46 tests pass, `poe check` green, coverage 45%. After: `uv run poe check`
green, new tests for store (status derivation incl. agent-approve-doesn't-count,
latest-human-wins, collision-safe filenames, duplicate detection, unicode round
trip) and CLI (each command, `--json` parseable, works with no API keys in env),
`happytube channels list` shows 15 seeded candidates.

## Tooling gotchas (from phase 0)

- Don't run pytest concurrently in one checkout (shared `.coverage`); parallel
  agents use their own worktree (`uv sync` there first) or `COVERAGE_FILE`.
- madoqua hook runs on staged .py only; never `--no-verify` / `MADOQUA_SKIP`.
- `tyf` index can go stale after hook reformat: `uv run tyf daemon restart`.
