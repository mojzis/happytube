# HappyTube Web Player - Deployment Guide

This guide explains how to deploy the HappyTube web player to GitHub Pages or other static hosting services.

## Overview

The web player can run in two modes:

1. **Development Mode** (Flask): For local testing with live data updates
2. **Static Mode** (GitHub Pages): For deployment with pre-exported video data

## Quick Deploy to GitHub Pages

### Step 1: Export Video Data

First, fetch and rate videos using the main pipeline:

```bash
# Fetch videos and rate them with Claude
poetry run python -m happytube.main
```

Then export to static JSON:

```bash
# Export videos to static JSON file
poetry run python -m happytube.web.export
```

This creates `happytube/web/static/videos.json` with your curated video list.

### Step 2: Configure GitHub Pages

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Pages**
3. Under "Source", select:
   - **Branch**: `main` (or your deployment branch)
   - **Folder**: `/happytube/web/static`
4. Click **Save**

### Step 3: Access Your Site

After a few minutes, your site will be available at:
```
https://<username>.github.io/<repository-name>/
```

For example: `https://mojzis.github.io/happytube/`

## Update Workflow

To add new videos to your deployed site:

```bash
# 1. Fetch new videos
poetry run python -m happytube.main

# 2. Export to static JSON
poetry run python -m happytube.web.export

# 3. Commit and push
git add happytube/web/static/videos.json
git commit -m "Update video list"
git push
```

GitHub Pages will automatically redeploy within a few minutes.

## Alternative Deployment Options

### Option 1: Netlify

1. Connect your GitHub repository to Netlify
2. Set build settings:
   - **Build command**: `poetry run python -m happytube.web.export`
   - **Publish directory**: `happytube/web/static`
3. Deploy!

Netlify will automatically rebuild when you push to GitHub.

### Option 2: Vercel

1. Import your repository to Vercel
2. Configure:
   - **Framework**: Other
   - **Root Directory**: `happytube/web/static`
   - **Build Command**: (leave empty, pre-build with export script)
3. Deploy!

### Option 3: Custom Domain

After deploying to GitHub Pages:

1. Add a `CNAME` file to `happytube/web/static/`:
   ```
   your-domain.com
   ```
2. Configure DNS settings with your domain provider:
   - Add a CNAME record pointing to `<username>.github.io`
3. In GitHub Settings → Pages, enter your custom domain

## Automation with GitHub Actions

Create `.github/workflows/update-videos.yml` for scheduled updates:

```yaml
name: Update HappyTube Videos

on:
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install Poetry
        run: curl -sSL https://install.python-poetry.org | python3 -

      - name: Install dependencies
        run: poetry install

      - name: Fetch and rate videos
        env:
          YTKEY: ${{ secrets.YTKEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: poetry run python -m happytube.main

      - name: Export to static JSON
        run: poetry run python -m happytube.web.export

      - name: Commit and push if changed
        run: |
          git config --global user.name 'GitHub Actions'
          git config --global user.email 'actions@github.com'
          git add happytube/web/static/videos.json
          git diff --quiet && git diff --staged --quiet || \
            (git commit -m "Auto-update video list [skip ci]" && git push)
```

**Important**: Add your API keys as repository secrets:
- Go to Settings → Secrets and variables → Actions
- Add `YTKEY` and `ANTHROPIC_API_KEY`

## Local Testing

Test the static build locally before deploying:

```bash
# Export videos
poetry run python -m happytube.web.export

# Serve static files (Python 3)
cd happytube/web/static
python -m http.server 8000

# Or use any static server
# npm: npx serve
# Or: poetry run python -m http.server 8000
```

Visit `http://localhost:8000` to test.

## Troubleshooting

### Videos not loading

**Issue**: "Error loading videos. Make sure videos.json exists."

**Solution**:
1. Make sure you ran the export script: `poetry run python -m happytube.web.export`
2. Check that `happytube/web/static/videos.json` exists
3. Verify the JSON file is not empty

### No videos available

**Issue**: "No videos available. Please run the main HappyTube script first."

**Solution**:
1. Run the main pipeline: `poetry run python -m happytube.main`
2. Then export: `poetry run python -m happytube.web.export`

### CORS errors in browser console

**Issue**: Cannot load videos.json due to CORS

**Solution**:
- Must serve from a web server (not `file://` protocol)
- Use `python -m http.server` or deploy to GitHub Pages

### GitHub Pages 404 error

**Issue**: Site shows 404 after enabling GitHub Pages

**Solution**:
1. Verify the publish folder is set to `/happytube/web/static`
2. Check that `index.html` exists in that folder
3. Wait a few minutes for deployment to complete
4. Check GitHub Actions tab for any errors

## Privacy & Security Notes

- All videos are embedded from YouTube with restricted parameters
- No user tracking or analytics in the default implementation
- All data is static - no backend or database
- API keys are only needed for the build process, not deployment

## Cost Considerations

- **GitHub Pages**: Free for public repositories
- **Netlify**: Free tier: 100GB bandwidth, 300 build minutes/month
- **Vercel**: Free tier: 100GB bandwidth, unlimited builds
- **YouTube API**: Free tier: 10,000 quota units/day
- **Claude API**: Pay per use (check Anthropic pricing)

Only the build process (fetching/rating videos) consumes API credits. Once exported, the static site has zero running costs.
