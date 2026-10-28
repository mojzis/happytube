# 0001 Trusted channels first

Date: 2026-10-28
Status: accepted

## Context

The pipeline searches YouTube by category and sorts by view count, then asks Claude
to score happiness from title and description. Open search now returns too much odd
content, and a title-based score cannot catch it. The first viewer is a grandmother
with early dementia, so a single bad video matters. Source:
`~/git/ideas/projects/happytube/ideas/trusted-channels.md`.

## Decision

Decide *who* is trusted before *what* to show. Build a vetted allowlist of channels
(big broadcasters, zoos, aquariums, parks, museums; Czech and English) through a
discovery and vetting phase. Fetch new videos only from approved channels. The
happiness score still filters within them, and the rubric weighs calm as much as
happy. A human approves every channel.

## Consequences

- Fetch has to change from open search to per-channel reads; the method (RSS,
  uploads playlists, search) is researched in phase 2 with quota math.
- Channel-upload reads have no duration filter, so Shorts must be dropped per video.
- Good videos from unknown channels have no way in until discovery adds them.
- New work up front: registry, evidence, vetting, review UI (phases 1–4).
