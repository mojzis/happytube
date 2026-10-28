# HappyTube Deployment Guide

How the HappyTube web player gets to GitHub Pages (decision 0010). This is the
only deployment guide; `src/happytube/web/README.md` covers the player itself.

## What is deployed

- The player page (`src/happytube/web/static/`: `index.html`, `player.js`,
  `styles.css`) and a `videos.json` built in CI.
- `videos.json` is built from the **committed** `stages/trusted/` (assess and
  enhance files of the trusted pipeline), the channel registry `channels/` and the
  video spot-checks `video-reviews/` (decision 0011). It is a build product:
  git-ignored, never committed.
- Shown: every video assessed `suitable: true` that has a non-empty cleaned
  description (enhance file), whose channel is **currently approved** and that no
  human spot-check hides (latest human verdict `unsuitable`, or an unreadable
  review file), newest first. Rejecting a channel or a human "unsuitable" removes
  the videos on the next deploy.

## GitHub Pages

Pages is enabled on `mojzis/happytube` with the **GitHub Actions** source:
https://mojzis.github.io/happytube/

The workflow `.github/workflows/deploy.yml` runs:

- on a push to `main` touching `stages/trusted/**`, `channels/**`,
  `video-reviews/**`, `src/happytube/**`, `pyproject.toml`, `uv.lock` or the
  workflow, and
- manually (**Actions** → **Deploy HappyTube to GitHub Pages** → **Run workflow**).

Steps: checkout → uv + Python 3.12 → `uv sync` →
`uv run python -m happytube.web.export` (from the repo root) → upload
`src/happytube/web/static` → deploy.

The export **fails the build** when `stages/trusted/`, `channels/` or
`video-reviews/` is missing, so a wrong path never deploys an empty player nor one
showing a video a human hid. Until the first `stages/trusted/`
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
failed run that wrote files), pushes on every run (so a commit left local by
a failed push goes out next time), and exits non-zero if the commit or push
fails. No `stages/trusted/` yet → nothing is committed or pushed. It pushes the current branch; only `main` deploys.
It never commits `video-reviews/`: spot-checks are committed by the human who
made them (`git add video-reviews && git commit && git push`), which redeploys.

## Local preview

No export needed: the local app serves the same selection live.

```bash
uv run happytube serve            # http://127.0.0.1:8000/player/
```

It reads `stages/` in the current directory (`--stages-dir` /
`HAPPYTUBE_STAGES_DIR`), the registry (`--channels-dir` /
`HAPPYTUBE_CHANNELS_DIR`) and the spot-checks (`--video-reviews-dir` /
`HAPPYTUBE_VIDEO_REVIEWS_DIR`, default `video-reviews/` at the repo root). To check the export itself:

```bash
uv run python -m happytube.web.export --output /tmp/videos.json
```

## Troubleshooting

- **Workflow fails at "Export videos"** — read the log line: `stages/trusted not
  found` means no stage data is committed on `main` yet (or a wrong cwd);
  `video-reviews not found` means the directory (kept by its README) is gone.
- **A video is missing** — check its assess file says `suitable: true`, an enhance
  file with `enhanced_description` exists, and its channel is approved
  (`happytube channels show <slug>`), and that no human spot-check hides it
  (`happytube videos show <id>`). Skipped malformed files are named in the export
  log.
- **Pages not updating** — check the Actions run; wait a few minutes; hard-refresh.

## Security notes

- The workflow has minimal permissions (read contents, write pages) and needs no
  API keys: the export only reads committed files.
- Stage files hold public YouTube metadata only; never commit `.env` or keys.
