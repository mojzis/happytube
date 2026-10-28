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
  `candidate`. Agent reviews never change status.
- **Blocklist** — no separate list: a `rejected` channel is the blocklist entry.
- **Slug** — kebab-case ASCII of the name (diacritics stripped) or given explicitly.
  Adding a channel fails if the slug, `channel_id` or handle (case-insensitive) is
  already registered.
- Code: `happytube.channels` (`models.py`, `store.py`); `happytube channels` CLI is a
  thin layer over the store, and the phase 4 web UI will use the same store.

## Consequences

- Two reviewers can never touch the same file, so merges stay conflict-free.
- Status cannot drift from the reviews, and an agent cannot approve a channel.
- Every status query loads all reviews of a channel — fine at hundreds of channels.
- Undoing a decision means adding a newer human review, not editing history.
