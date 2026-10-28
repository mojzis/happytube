# Phase 5b — QA

See [context.md](./context.md) and the dev report in [log.md](./log.md). Read-only:
report, don't fix. Runtime checks only (review covers logic).

## Where
Own worktree: `git worktree add --detach /tmp/claude-1000/p5b-qa
phase-5b-trusted-player`, `uv sync` there; remove + `git worktree prune` at the end.
Scratch cwd with a copied `channels/` and hand-made `stages/trusted/` md files.
No real API calls (none needed). Dev's real scratch data is in
`/tmp/claude-1000/p5b-real` (read-only reuse is fine; its registry has a test
reject of explore-org).

## Check
1. `uv run poe check` green; numbers (495 / 85%).
2. Added after dev (runtime — yours only):
   a. Seeded stage dir covering: suitable+enhanced, suitable no enhance, enhance
      with empty description, unsuitable with lingering enhance file, stale scores
      in enhance, assess and enhance under different date dirs, duplicate id on two
      dates, malformed frontmatter, rejected / candidate / unknown channel. Export
      and live `/player/videos.json` agree and show exactly the right set, sorted.
   b. Export exit codes: missing stages dir, missing registry, empty, normal; run
      from a different cwd with `--stages-dir` / env.
   c. `happytube serve` → `/player/`, `/player/player.js`, `/player/styles.css`,
      `/player/videos.json`, `/player` (no slash), `/player/../...` traversal, bad
      Host → 400. Page actually loads videos (check player.js's fetch path).
   d. `scripts/daily_run.sh` with `HAPPYTUBE_PIPELINE=trusted HAPPYTUBE_PUSH=1` in a
      throwaway git repo with a bare local remote and a stubbed `uv` on PATH: commit
      only stages/trusted, nothing changed → no commit, push failure → exit ≠ 0,
      run failure path.
   e. `python -m happytube.web.export` no runpy warning; `import flask` not needed
      (uv pip show flask absent).
   f. Simulate the CI export: fresh clone of the branch, `uv sync`, run the
      workflow's export command from the repo root → expected exit (no
      stages/trusted committed yet).

## Report
Return ONLY JSON (≤600 words):
{"verified": true, "numbers": "", "findings": [{"id": "Q1", "severity": "high|medium|low",
 "what": "", "repro": ""}], "checks": [{"check": "", "result": ""}], "preexisting": [""]}
