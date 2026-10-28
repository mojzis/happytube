# 0008 What a channel approval means

Date: 2026-10-28
Status: accepted (amended by 0011: a human "unsuitable" spot-check also hides
that one video)

## Context

Vet reports suggested "individual videos could be hand-picked, but whole-channel
approval is risky" (smithsonian-channel), but no one had said what an approval lets
through. There is no time for a human to review every video every day.

## Decision

- **Human approves channels; agents gate videos.** An `approved` channel is a
  source: phase 5 fetches its new long-form videos, and each one shows only if an
  agent scores it suitable with the shared rubric (`is_suitable`). No daily human
  review of videos.
- **Humans spot-check videos to test the algorithm**, not as a gate. Video review
  records (phase 5) are for measuring agent accuracy and tuning the rubric.
- **Channel verdicts mean:**
  - approve: most videos suit her, and the unsuitable ones are the kind the
    per-video check catches (titles/descriptions show them).
  - reject: unsuitable content is the channel's core or is hard to spot per video
    (e.g. war documentaries as a staple, or calm titles over distressing footage).
  - unsure: mixed, too little evidence, inactive, or identity in doubt.
- The vet prompt and the review form state this, so neither model nor reviewer
  assumes per-video human picking.

## Consequences

- Settles phase 5's "does a video need a human approval?": no.
- The per-video agent check is the last line of defence; run-to-run score variance
  (phase 3 backlog) matters more, and phase 5 needs a way to measure its misses.
- Changing the vet prompt makes existing vets stale for comparison; rerun with
  `channels vet --all --force` when wanted (costs API credit).
