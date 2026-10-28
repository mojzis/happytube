# Phase 0 — context (required reading for every step agent)

Repo: `/home/matous/git/happytube`, branch `phase-0-template`, base commit
`a336adc13b020ac763210884b50ad72b071e08d0`. Overall plan: `docs/plan.md`.

## Goal

Bring the repo in line with `/home/matous/git/python-template` (read its `CLAUDE.md`
and `pyproject.toml` — they are short) and delete legacy code. No feature work.

## Template essentials

- **src layout**: `src/<pkg>/` + `py.typed`; tests in `tests/` with `__init__.py`.
- **pyproject**: deps under `[dependency-groups] dev` (not `optional-dependencies`):
  madoqua, gerenuk, biston, zorilla, pycoati, ty-find, ruff, ty, pytest, pytest-cov,
  vulture, deptry, interrogate, poethepoet. Ruff `line-length = 88`,
  `select = ["E","F","W","I","UP","B","S","SIM","C4","DTZ","T20","PTH","ERA","PL","TRY","RUF"]`,
  tests ignore `S101,S105,S106,PLR2004`. `[tool.ty]`, pytest `--cov=src`, coverage,
  vulture `paths=["src"]`, deptry, interrogate, `[tool.madoqua] extend_check`
  (biston/zorilla/gerenuk), `[tool.biston.scan]`, and the full `[tool.poe.tasks]` set
  (fix, lint, typecheck, test, vulns, test-lint, clones, dead-code, unused-deps,
  _check-parallel, check, check-all, setup). Copy these sections, adapt names/paths.
- **hooks/pre-commit** (madoqua) + `uv run madoqua install` (sets `core.hooksPath`).
- `.github/dependabot.yml` (pip, weekly) — copy as is.
- `.gitignore` — merge template's entries with the existing ones (keep `gkey.json`,
  `secrets.toml`, `key.txt`, `data`, `*.duckdb`, `.env`).
- `CLAUDE.md` — merge: keep the project-specific parts (overview, pipeline stages,
  config, env vars, storage) but drop legacy commands; add the template's Commands,
  Stack and Toolbox sections. Add a short "Project plan" pointer to `docs/plan.md` and
  `docs/next-session.md`. Fix stale info (Poetry, `uv run python -m happytube.main`,
  `scripts/ip.sh`, `optional-dependencies`).

## Current state (observed)

- Python `>=3.12,<3.13`. Keep `>=3.12` (drop the upper bound only if nothing breaks;
  ruff `target-version = "py312"`).
- Build: hatchling, `packages = ["happytube"]` → must become `src/happytube`.
- Entry point `happytube = "happytube.cli.commands:cli"`.
- `uv run pytest` → 30 passed (baseline). ruff not installed in env (dev extra unused).
- Runtime deps include `pytest` (move to dev), `ipython`, `dlt[duckdb]`,
  `google-auth-oauthlib` — re-check each after deleting legacy code (deptry helps).

### Module map

Used by CLI / web / tests (keep): `cli/`, `config/`, `stages/`, `models/`, `web/`,
`prompts.py`, `videos.py` (imported by `stages/fetch.py`), `utils/` package.

Delete (legacy, user approved 2026-10-28; `mq.py`/`tmq.py` were failed asyncio queue experiments — user confirmed remove, also drop any queue-only mentions in docs): `main.py`, `mq.py`, `tmq.py`, `mb.py`,
`nb.py`, `yt_api_pipeline.py`, `yt.py`, `claude.py`, `ip.py`, `iploader.py`,
`utils.py` (duplicate of `utils/__init__.py`; the package wins on import),
`.dlt/`, `scripts/ip.sh`. Verify with grep that nothing kept imports them. Remove
any deps only those used. Update docs that mention them (CLAUDE.md, README.md,
DEPLOYMENT.md, `happytube/web/*.md`, `scripts/deploy_web.sh` mentions
`python -m happytube.main`).

### Path gotchas for the src move

- `web/server.py:24` and `web/export.py:99` use `Path(__file__).parent.parent.parent`
  as project root — that becomes `src/` after the move. Fix (e.g. one more `.parent`,
  or better a single helper / settings value).
- `.github/workflows/deploy.yml:47` uploads `happytube/web/static` → `src/happytube/web/static`.
- `scripts/deploy_web.sh` references `happytube/web/static/...` paths.
- Check `config/`, `templates/` lookups in stages/config_manager (relative to cwd or
  `__file__`?).
- `.vscode/settings.json` may reference paths/tools.

### Lint strategy

The strict ruff set plus ty will flag a lot in kept code. Fix what is cheap and safe.
Where a rule clashes with how the code legitimately works (e.g. `T20` in CLI output
if it uses print, `PLR0913` on CLI commands), add a targeted
`per-file-ignores` entry **with a comment saying why** — no blanket disabling of a
rule family repo-wide without justification. ty: prefer real fixes, then
`# ty: ignore[rule]`. The madoqua hook checks staged files only, so every touched
`.py` must pass ruff + ty to commit. Never `--no-verify` / `MADOQUA_SKIP`.

## docs/ scaffold

Copy from `/home/matous/git/ideas/templates/repo/`: `constitution.md`,
`architecture.md`, `naming.md`, `decisions/README.md`, `research/README.md`.
Fill them briefly from the idea doc
(`/home/matous/git/ideas/projects/happytube/ideas/trusted-channels.md`) and
`docs/plan.md`:
- constitution: purpose (calm/happy videos for vulnerable viewers), goals,
  non-goals, principles (human approves allowlist; calm ≥ happy; files are truth).
- architecture: current pipeline + planned channel registry/review layer.
- `decisions/0001-trusted-channels-first.md` (accepted, 2026-10-28) and
  `decisions/0002-review-store-files-cli-web.md` (files as truth; CLI for agents;
  web UI for humans).
- `docs/modernization-plan.md` is historical — move it to `docs/research/` or leave
  with a note; don't delete.

## Verification baseline

After the phase: `uv sync`, `uv run poe check` green (vulns task may warn, it has
`|| true`), `uv run pytest` ≥ 30 passing, `uv run happytube --help` and each
subcommand `--help` work, `uv run python -m happytube.web.export` runs (may export 0
videos without data), `madoqua` hook installed and runs on a commit with a `.py` file.
