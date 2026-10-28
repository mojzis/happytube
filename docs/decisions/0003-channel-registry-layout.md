# 0003 Channel registry layout: a directory per channel, derived status

Date: 2026-10-28
Status: accepted

## Context

Decision 0002 made git-tracked files the review store, with one record per file so
concurrent writers (the user, other humans, agents) never conflict. Phase 1 needs the
concrete layout, the channel and review fields, and a rule for a channel's status.

## Decision

- **Layout** — `channels/<slug>/channel.yaml` plus `channels/<slug>/reviews/`, one
  append-only file per review named `<UTC YYYYMMDDTHHMMSSZ>-<reviewer slug>.yaml`; on
  a name collision `-2`, `-3`… is appended. Files are created exclusively, never
  overwritten. Later phases add `evidence/` (phase 2) and `vet/` (phase 3) next to
  `reviews/`.
- **channel.yaml** — `slug`, `name`, `kind`
  (`broadcaster|zoo|aquarium|park|museum|other`), `languages` (`cs`, `en`), `handle`
  (`@…`, optional), `channel_id` (`UC…`, optional), `url`, `added_by`, `added_at`
  (UTC ISO), `notes`. Written once by `channels add`; afterwards only humans edit it.
- **Review** — `reviewer`, `role` (`human|agent`), `verdict`
  (`approve|reject|unsure`), `notes`, `created_at` (UTC ISO).
- **Status is derived, not stored** — the latest human review with verdict `approve`
  or `reject` decides (`approved` / `rejected`); otherwise the channel is a
  `candidate`. Agent reviews never change status. "Latest" is by `created_at`; on a
  tie the collision suffix decides (base name before `-2`, `-3`…), so within one
  reviewer the later-written file wins. A tie between different reviewers is
  decided by filename and is arbitrary — real timestamps have microseconds, so this
  only happens with hand-written files.
- **Blocklist** — no separate list: a `rejected` channel is the blocklist entry.
- **Slug** — kebab-case ASCII of the name (diacritics stripped) or given explicitly.
  Adding a channel fails if the slug, `channel_id` or handle (case-insensitive) is
  already registered. The slug in `channel.yaml` must equal its directory name, and
  a slug never becomes a path unless it matches the slug pattern.
- **Files are validated strictly** — unknown keys, bad values and malformed YAML are
  errors that name the file. A broken file fails `list` and `add` (whose duplicate
  check reads every channel) until it is fixed; it is never silently skipped.
- Code: `happytube.channels` (`models.py`, `store.py`); `happytube channels` CLI is a
  thin layer over the store, and the phase 4 web UI will use the same store.

## Consequences

- Two reviewers can never touch the same file, so merges stay conflict-free.
- Status cannot drift from the reviews, and an agent cannot approve a channel.
- Every status query loads all reviews of a channel — fine at hundreds of channels.
- Undoing a decision means adding a newer human review, not editing history.
