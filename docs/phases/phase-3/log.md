# Phase 3 — log

Loop (planned): dev → review ‖ QA (QA runtime-only) → fix → combined verify →
orchestrator committed `vet --all` run → learnings.

Decisions taken with the user before dev (2026-10-28): input = latest snapshot only;
output = report + agent review + per-video scores; re-vet = skip when current,
`--force`; model = claude-opus-5-5.

Pre-phase: `0bbad42` — evidence refresh after the YTKEY fix (UUSH Shorts, 13
snapshots). Sanity: no Shorts >180 s; sub-60 s horizontal clips correctly not Shorts;
smithsonian-channel newest upload 2024-06 (inactive).

## 1 — dev
