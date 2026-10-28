---
title: HappyTube
pitch: A strictly vetted allowlist of calm, happy YouTube channels and videos, reviewed by people and agents together.
created: 2026-10-28
updated: 2026-10-28
---

# HappyTube

## Purpose

Open YouTube is full of content that scares or confuses vulnerable viewers. The first
audience is a grandmother with early dementia, frightened by war news. HappyTube
builds a small, trusted set of calm, happy videos she can watch safely, and may help
other people like her.

## Goals

- A git-tracked allowlist of trusted channels (broadcasters, zoos, parks, museums),
  reviewed by humans and agents together.
- Fetch new videos only from approved channels, score them, and play them in a
  player without recommendations.
- Czech and English content. No Shorts.

## Non-goals

- Open YouTube search as the main source.
- A recommendation engine or anything that maximises watch time.
- A database or hosted backend; files in git are enough.
- Distribution to other people or per-person lists (later, not now).

## Principles

- **A human approves the allowlist.** Agents propose and vet; nothing becomes
  `approved` without a human review record.
- **Calm matters as much as happy.** No war, disasters, violence, predators hunting,
  sad news, or loud, fast cuts — even from a trusted channel.
- **Files are the truth.** Channels, evidence and reviews are YAML/markdown in git.
  CLI and web UI both read and write those files.
- **Trust the channel first, then the video.** The happiness score filters within
  trusted channels; it does not replace vetting.

## Open questions

- Hard allowlist filter or a strong boost, so good videos from unknown channels have
  a way in?
- Blocklist for channels that turn out bad?
- How other viewers would get it, and whether each gets their own channel list.
