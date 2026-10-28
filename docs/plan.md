# HappyTube revival — plan

Source idea: `~/git/ideas/projects/happytube/ideas/trusted-channels.md` (2026-10-28).

## Goal

A research environment where the user, other reviewers and agents review YouTube
**channels** and **videos** together, to build a strictly vetted allowlist of calm,
happy content (first audience: a grandmother with early dementia, scared by war news).
Then the existing pipeline fetches only from approved channels.

## Shape (decided 2026-10-28)

- **Single source of truth: git-tracked files** (YAML/markdown) — channels, evidence,
  review records. No database.
- **Agents** work through the CLI (`happytube channels …`, JSON output).
- **Humans** work through a web review page (FastAPI + htmx, decision 0006).
- Both write the **same review records**: who (user / agent name), verdict, notes, when.
- Nothing enters the allowlist without a human approval.
- Calm matters as much as happy: no war, disasters, violence, predators hunting, sad
  news, loud/fast cuts — even from trusted channels.
- Languages: Czech + English. No Shorts (check duration per video).

## Phases

| # | Title | Deliverable |
| --- | --- | --- |
| 0 ✅ | Template alignment | Repo matches `~/git/python-template` (src layout, uv dev group, ruff/ty, poe tasks, madoqua hook, aesop toolbox, dependabot); legacy modules deleted; `docs/` scaffold from ideas repo template with decision 0001 = trusted channels. |
| 1 ✅ | Channel registry | Data model + files for channels (`candidate` / `approved` / `rejected`, kind, language, ids) and review records (reviewer, role human/agent, verdict, notes, timestamp). CLI: `channels add / list / show / review` with `--json`. Seed with the starter candidates from the idea doc. |
| 2 ✅ | Channel evidence | Resolve handles → channel ids (`channels.list`), collect stats + recent uploads (RSS and/or `playlistItems`), video durations; cached per channel. Research note + decision record comparing fetch methods with quota math for 50/200/500 channels. |
| 3 ✅ | Agent vetting | Claude vets a channel from its evidence with the calm/happy rubric → markdown vet report + an agent review record. Video-level assessment reuses the same rubric. CLI: `channels vet <id>`. |
| 4 ✅ | Web review UI | FastAPI + htmx app (decision 0006): Jinja2 pages over `ChannelStore` — channel queue, channel detail (evidence, agent reports, all reviews), approve/reject/notes form writing the same review records. Local only, `happytube serve` (decision 0007). |
| 5 | Trusted fetch | Fetch stage pulls new videos only from approved channels (method from phase 2's decision), skips Shorts, feeds assess/enhance/report/player. Video review queue + video review records in the review UI (moved from phase 4). Also: fetch must fail loudly on network/parse errors (today a catch-all exits 0); web player/export read `stages/` instead of legacy `data/fetched/`; the player moves from Flask to the FastAPI app and `flask` is dropped. |

Later (not scheduled): discovery from directories (EAZA/AZA, park services, museums),
featured-channel one-hop expansion, blocklist, per-person channel lists / distribution.

## Per-phase loop

Runner: manual, driven by the user (decided 2026-10-28); a skill may come later,
with `docs/process-learnings.md` as input. The orchestrating session runs:

1. **dev** subagent — builds the deliverable, commits (hooks must pass).
2. **review** subagent (`python-review` skill) and **QA** subagent (functional checks,
   read-only) — in parallel, report only.
3. **fix** subagent — fixes real findings from both, commits.
4. **review + QA again** — confirm fixes, nothing regressed.
5. **learnings** subagent — writes `docs/phases/phase-N/learnings.md` and appends
   process lessons to `docs/process-learnings.md`.
6. Orchestrator updates `docs/next-session.md`.
7. Orchestrator pushes the branch, opens the PR and, once the user says so, merges
   it. **The session ends when the PR is merged** — next-session.md is written for
   the state after the merge.

Working files per phase live in `docs/phases/phase-N/` (`context.md`, step briefs,
`log.md` with verbatim agent reports, `learnings.md`). Each phase runs on its own
branch; merge only after the user says so.

## Backlog (from phase 0, not scheduled)

- `report` requires API keys although it calls no API.
- runpy RuntimeWarning on `python -m happytube.web.*` (web/__init__ imports server).
- 8 real dead-code hits (`uv run poe dead-code`): delete or use.
- Test nits: quota error fixture shape (`error.errors[0].reason`), `test_today_local`
  still pins the implementation, duplicated CLI test setup.
- Coverage 45% (web/ and stages largely untested).
- Paths are relative to cwd; add a `data_root` setting.

## Backlog (from phase 1, not scheduled)

- V1: a channel directory whose name is not a valid slug makes `channels list` fail
  with a "not found" message and no path; raise a store error naming the path.
- V2: ValidationError formatting duplicated in `channels/store.py` and
  `cli/channels.py`; share one helper.
- `channels list` table truncates kind/name at 80 columns without a TTY.
- Seed handles: only `@bbcearth`, `@NatGeo` set; phase 2 resolves the rest.

## Backlog (from phase 2, not scheduled)

- Open content questions live in the registry as agent `unsure` reviews
  (`channels list --needs-human-review`, `channels show <slug>`): ct-decko and
  zoo-zlin handles, national-park-service identity, zoo-dvur-kralove activity.
- Make the tool surface these itself instead of hand-written notes: phase 3 vetting
  (or `resolve`/`evidence`) should flag unresolved handles, inactive channels
  (newest upload > 12 months) and look-alike channels (low subscribers vs the
  name, as `@NatureonPBS` was) as agent reviews; phase 4 queue shows them first.
- V1: `latest_evidence` orders by filename, `evidence()` by `fetched_at`; a renamed or
  hand-copied snapshot makes them disagree. Glob only timestamp names.
- V2: 0-upload channel records `shorts_source: uush` without a UUSH call.
- V3: `not_fetched` placeholders carry null handle/channel_id even when known.
- V4: duplicate-id check parses every channel.yaml per write (O(N²) on `--all`);
  one broken channel.yaml blocks all writes.
- V5: tests for quota/invalid key during the UUSH call and the batched-channels
  error paths (`collect.py`).

## Backlog (from phase 3, not scheduled)

- Q3: legacy `report` needs both API keys though it calls no API (same as phase 0 item).
- Q4: `vet` asks for `ANTHROPIC_API_KEY` even when no selected channel needs a call.
- A `ChannelStoreError` mid-run aborts vet/evidence/resolve; per-channel JSON of
  channels already written (and paid for) is lost.
- V1: tokens of a declined attempt before a fallback (`usage.iterations`) not counted.
- V2: text-after-last-fallback-block layout unverified (no fallback in the real run).
- V3: vet text output doesn't name the answering model on fallback.
- anthropic SDK 2.x (API version `2026-10-21`); now pinned `>=1.17,<2`.
- Cosmetic: "did not parse (1 problems)"; store imports private `_iso_z`.
- Run-to-run variance of per-video scores (zoo-praha 45 vs 39/50 suitable on the
  same snapshot): phase 5 should not treat one vet's video scores as final.

## Backlog (from phase 4, not scheduled)

- V1: `serve --host 0` slips past the wildcard check (`ipaddress` rejects '0',
  getaddrinfo binds 0.0.0.0); resolve the host and refuse unspecified addresses.
- Q3: in an installed wheel the default `--channels-dir` points into the venv
  (`PROJECT_ROOT`); same root cause as the `data_root` item above.
- Name sort ignores Czech collation (ČT sorts with C).
- One broken registry file makes the whole queue a 500 (by design, 0007); a
  per-row error would let the rest be reviewed.
- vulture ignores for FastAPI decorators / QueueSections fields are global names;
  a whitelist file would be tighter.
- Port probe before uvicorn has a tiny race (uvicorn's own error still covers it).
