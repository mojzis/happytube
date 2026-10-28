# 0002 Review store: files as truth, CLI for agents, web UI for humans

Date: 2026-10-28
Status: accepted

## Context

Channels and videos are reviewed by the user, other human reviewers and agents. All
of them need to see each other's verdicts and notes, and the history must be easy to
inspect and recover.

## Decision

- Git-tracked YAML/markdown files are the single source of truth for channels,
  evidence and review records. No database.
- Agents work through the CLI (`happytube channels …`) with JSON output.
- Humans work through a web review page in the existing Flask app.
- Both write the same review record: reviewer, role (human / agent), verdict, notes,
  timestamp. Only a human review can move a channel to `approved`.

## Consequences

- History, diffs and backup come from git for free; reviews are readable by hand.
- Concurrent writes are rare but possible; the file layout should keep one record per
  file (or append-only) to avoid merge conflicts.
- Queries ("all candidates without a human review") are done by loading files, which
  is fine at hundreds of channels but not at millions.
- The web UI writing files means the server must run where the repo is checked out.
