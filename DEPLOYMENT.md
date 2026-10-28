# HappyTube Deployment Guide

How the HappyTube web player gets to GitHub Pages (decision 0010). This is the
only deployment guide; `src/happytube/web/README.md` covers the player itself.

## What is deployed

- The player page (`src/happytube/web/static/`: `index.html`, `player.js`,
  `styles.css`) and a `videos.json` built in CI.
- `videos.json` is built from the **committed** `stages/trusted/` (assess and
  enhance files of the trusted pipeline) and the channel registry `channels/`. It
  is a build product: git-ignored, never committed.
- Shown: every video assessed `suitable: true` that has a non-empty cleaned
  description (enhance file) and whose channel is **currently approved**, newest
  first. Rejecting a channel removes its videos on the next deploy.

## GitHub Pages

Pages is enabled on `mojzis/happytube` with the **GitHub Actions** source:
https://mojzis.github.io/happytube/

The workflow `.github/workflows/deploy.yml` runs:

- on a push to `main` touching `stages/trusted/**`, `channels/**`,
  `src/happytube/web/**`, `src/happytube/trusted/player.py` or the workflow, and
- manually (**Actions** → **Deploy HappyTube to GitHub Pages** → **Run workflow**).

Steps: checkout → uv + Python 3.12 → `uv sync` →
`uv run python -m happytube.web.export` (from the repo root) → upload
`src/happytube/web/static` → deploy.

The export **fails the build** when `stages/trusted/` or `channels/` is missing,
so a wrong path never deploys an empty player. Until the first `stages/trusted/`
commit lands on `main`, every run fails at that step — expected. An existing but
empty selection deploys with a warning in the log (the page says "No videos
available yet").

## Updating the videos

1. Run the trusted pipeline (needs `YTKEY` and `ANTHROPIC_API_KEY` in `.env`):
   ```bash
   uv run happytube trusted run
   ```
2. Commit and push only the stage files:
   ```bash
   git add stages/trusted
   git commit -m "trusted run $(date +%F)"
   git push
   ```
   The push to `main` redeploys.

Or let the daily script do both: `HAPPYTUBE_PIPELINE=trusted HAPPYTUBE_PUSH=1
./scripts/daily_run.sh` commits only `stages/trusted/` (also after a partly
failed run that wrote files), pushes, and exits non-zero if the commit or push
fails. It pushes the current branch; only `main` deploys.

## Local preview

No export needed: the local app serves the same selection live.

```bash
uv run happytube serve            # http://127.0.0.1:8000/player/
```

It reads `stages/` in the current directory (`--stages-dir` /
`HAPPYTUBE_STAGES_DIR`) and the registry (`--channels-dir` /
`HAPPYTUBE_CHANNELS_DIR`). To check the export itself:

```bash
uv run python -m happytube.web.export --output /tmp/videos.json
```

## Troubleshooting

- **Workflow fails at "Export videos"** — read the log line: `stages/trusted not
  found` means no stage data is committed on `main` yet (or a wrong cwd).
- **A video is missing** — check its assess file says `suitable: true`, an enhance
  file with `enhanced_description` exists, and its channel is approved
  (`happytube channels show <slug>`). Skipped malformed files are named in the
  export log.
- **Pages not updating** — check the Actions run; wait a few minutes; hard-refresh.

## Security notes

- The workflow has minimal permissions (read contents, write pages) and needs no
  API keys: the export only reads committed files.
- Stage files hold public YouTube metadata only; never commit `.env` or keys.
