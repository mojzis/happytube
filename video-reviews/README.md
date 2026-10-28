# Video spot-checks

Human (and agent) spot-checks of the trusted pipeline's videos — decision
[0011](../docs/decisions/0011-video-spot-checks.md). Written by the review UI
(`happytube serve`, `/videos`) and `happytube videos review`; commit and push
them yourself.

**This repo is public: everything here, notes included, is public.**

## Layout

```
video-reviews/<video_id>/<YYYYMMDDTHHMMSSZ>-<reviewer>[-N].yaml
```

One file per review, append-only: a new review never changes an old one. Two
reviews in the same second get `-2`, `-3` … The video id is the directory name.

## Fields

```yaml
reviewer: mojzis
role: human               # human | agent — only human reviews count
verdict: unsuitable       # suitable | unsuitable | unsure
flags: [scary]            # rubric flags, optional
watched: full             # full | part | title
notes: Loud music halfway through.
created_at: '2026-10-28T20:15:00Z'
# The agent's call the reviewer compared with, copied from the assess file:
agent_suitable: true
rubric_version: 1
assessed_at: '2026-10-28T19:00:00Z'
```

## What a review does

- The **latest human** verdict counts; agent reviews are stored but never count.
- `unsuitable` hides the video from the player (local and GitHub Pages).
- `suitable` never shows a video the agent scored unsuitable; `unsure` changes
  nothing.
- A file that cannot be read hides its video until it is fixed.
- The agreement summary compares the verdict with `agent_suitable` above, so
  rescoring a video later doesn't rewrite history.

This directory must exist (the player and the export refuse to run without it,
so a wrong path never shows a video a human hid).
