# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HappyTube is a Python application that analyzes YouTube videos to identify and enhance "happy" content. It fetches videos from YouTube API, uses Claude AI to assess happiness scores, and improves video descriptions for highly-rated content.

## Commands

### CLI Commands (Stage-Based Architecture)

The project now uses a modern CLI interface with modular stage-based commands:

```bash
# Run the complete pipeline (recommended for daily use)
happytube run-all --category Music --max-videos 50

# Run individual stages
happytube fetch --category Music --max-videos 50 --date 2025-11-16
happytube assess --date 2025-11-16
happytube enhance --threshold 3 --date 2025-11-16
happytube report --date 2025-11-16 --days-back 7

# Check pipeline status
happytube status --date 2025-11-16

# Get help
happytube --help
happytube fetch --help
```

### Development Environment
```bash
# Install dependencies
poetry install

# Run the modernized CLI pipeline
happytube run-all --category Music

# Run the legacy main application (deprecated)
poetry run python -m happytube.main

# Interactive development environment
./scripts/ip.sh  # or: ipython -i happytube/ip.py

# Run tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_pipeline.py -v

# Lint code
poetry run ruff check .
poetry run ruff format .
```

### Daily Automation
```bash
# Run the automated daily pipeline
./scripts/daily_run.sh

# Setup cron job for daily execution at 8 AM
# crontab -e
# Add: 0 8 * * * /home/user/happytube/scripts/daily_run.sh >> /home/user/happytube/logs/cron.log 2>&1
```

### Web Player
```bash
# Start the web player for local development (after running main application)
poetry run python -m happytube.web.server

# Access at http://127.0.0.1:5000
```

### Static Deployment
```bash
# Export videos to static JSON for GitHub Pages deployment
poetry run python -m happytube.web.export

# Or use the deployment script (interactive)
./scripts/deploy_web.sh
```

## Architecture

### Modern Stage-Based Pipeline

The project has been modernized with a stage-based architecture for better modularity and debugging:

```
Stage 1: FETCH    → stages/fetch/YYYY-MM-DD/*.md
Stage 2: ASSESS   → stages/assess/YYYY-MM-DD/*.md  (with happiness_score)
Stage 3: ENHANCE  → stages/enhance/YYYY-MM-DD/*.md (with enhanced_description)
Stage 4: REPORT   → stages/report/YYYY-MM-DD.html + parquet exports
```

**Benefits:**
- Each stage can be run independently
- Human-readable markdown files with YAML frontmatter
- Git-friendly data format
- Easy to debug and inspect intermediate results
- Can reprocess specific dates without restarting pipeline

### Core Pipeline Stages

1. **Fetch Stage** (`stages/fetch.py`)
   - Uses YouTube Data API v3 to search for videos
   - Configurable by category, duration, region, etc.
   - Saves each video as markdown file with frontmatter
   - Results stored in `stages/fetch/YYYY-MM-DD/`
   - Legacy data in `data/fetched/`

2. **Assess Stage** (`stages/assess.py`)
   - Loads videos from fetch stage
   - Sends video metadata to Claude API in CSV format
   - Returns happiness scores (1-5 scale)
   - Uses configurable prompts from `prompts.py`
   - Updates markdown files with happiness scores and reasoning
   - Saves to `stages/assess/YYYY-MM-DD/`

3. **Enhance Stage** (`stages/enhance.py`)
   - Loads videos with happiness ≥ threshold (default: 3)
   - Generates improved descriptions via Claude
   - Removes clickbait, spam, and promotional content
   - Saves enhanced versions to `stages/enhance/YYYY-MM-DD/`

4. **Report Stage** (`stages/report.py`)
   - Generates HTML report with all enhanced videos
   - Exports analytics to Parquet format
   - Creates visualizations and statistics
   - Saves report to `stages/report/YYYY-MM-DD.html`
   - Exports parquet files to `parquet/` directory

5. **Web Player** (`web/`)
   - Flask-based web interface for video playback
   - Controlled YouTube embed with disabled recommendations
   - Playlist navigation and search functionality
   - Only shows curated videos from the pipeline
   - Supports both local development (Flask) and static deployment (GitHub Pages)

### Key Components

- **API Integration**: 
  - YouTube API credentials in `gkey.json` and `YTKEY` env var
  - Claude API via `ANTHROPIC_API_KEY` env var
  
- **Data Flow**:
  - All data exchange between modules uses pandas DataFrames
  - CSV format for Claude API communication
  - JSON storage for raw YouTube data
  
- **Configuration**:
  - Environment variables loaded from `.env`
  - Poetry for dependency management (Python >=3.12, <3.13)

### Storage Structure
```
# Stage-based data (new architecture)
stages/
├── fetch/              # Fetched videos
│   └── YYYY-MM-DD/
│       ├── video_abc123.md
│       └── video_def456.md
├── assess/             # Assessed videos (with happiness scores)
│   └── YYYY-MM-DD/
│       └── video_abc123.md
├── enhance/            # Enhanced videos (with improved descriptions)
│   └── YYYY-MM-DD/
│       └── video_abc123.md
└── report/             # Generated reports
    └── YYYY-MM-DD.html

# Analytics exports
parquet/
├── fetch/
│   └── by-run-date/
│       └── YYYY-MM-DD_last_7_days.parquet
├── assess/
└── enhance/

# Configuration
config/
├── base/
│   ├── app.yaml        # Main app config
│   ├── prompts.yaml    # Claude prompt definitions
│   └── youtube.yaml    # YouTube search configs
└── experiments/        # Override configs for testing

# Templates
templates/
├── base.html
└── daily_report.html

# Logs
logs/
├── YYYY-MM-DD.log     # Daily pipeline logs
└── cron.log           # Cron job logs

# Legacy data (being phased out)
data/
├── categories.json      # YouTube category definitions
└── fetched/
    ├── lists/          # Search results
    └── videos/         # Video details

# Web player
happytube/web/
├── server.py           # Flask backend (dev mode)
├── export.py           # Static export script
├── static/             # Static assets & deployment files
│   ├── index.html      # Static version for deployment
│   ├── player.js       # Player logic (works in both modes)
│   ├── styles.css      # Styling
│   └── videos.json     # Generated by export.py
└── templates/          # Flask templates
```

## Configuration

### Environment Variables

Required environment variables in `.env`:

```bash
# API Keys (required)
YTKEY=your_youtube_api_key              # YouTube Data API v3 key
ANTHROPIC_API_KEY=your_anthropic_key    # Claude API key

# Optional settings
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENVIRONMENT=development                 # development or production
```

### Configuration Files

Configuration files are stored in `config/base/` (if they exist):

- **app.yaml**: Main application settings
  - Stage paths
  - Processing thresholds
  - Default configurations

- **prompts.yaml**: Claude prompt definitions
  - Prompt templates
  - Model configurations
  - Token limits

- **youtube.yaml**: YouTube search configurations
  - Category-specific search params
  - Region codes
  - Video duration filters

## Common Workflows

### Daily Video Processing

```bash
# Run the complete pipeline for today
happytube run-all --category Music --max-videos 50

# Or use the automation script
./scripts/daily_run.sh
```

### Reprocessing Old Data

```bash
# Reprocess videos from a specific date
happytube assess --date 2025-11-15
happytube enhance --date 2025-11-15
happytube report --date 2025-11-15
```

### Testing Different Categories

```bash
# Fetch music videos
happytube fetch --category Music --max-videos 50

# Fetch educational content
happytube fetch --category Education --max-videos 30

# Fetch entertainment videos
happytube fetch --category Entertainment --max-videos 50
```

### Checking Pipeline Status

```bash
# View status for today
happytube status

# View status for a specific date
happytube status --date 2025-11-15
```

### Inspecting Results

```bash
# View fetched videos
ls stages/fetch/2025-11-16/
cat stages/fetch/2025-11-16/video_abc123.md

# View assessed videos (with happiness scores)
cat stages/assess/2025-11-16/video_abc123.md

# View enhanced videos
cat stages/enhance/2025-11-16/video_abc123.md

# Open the daily report in browser
open stages/report/2025-11-16.html
```

## Troubleshooting

### Configuration Issues

**Problem**: Missing API credentials
```bash
# Check if .env file exists and has required keys
cat .env | grep -E "YTKEY|ANTHROPIC_API_KEY"
```

**Solution**: Create or update `.env` file with valid API keys

### Pipeline Errors

**Problem**: Stage fails midway
```bash
# Check the logs
cat logs/$(date +%Y-%m-%d).log

# Inspect the stage directory
ls -la stages/fetch/$(date +%Y-%m-%d)/
```

**Solution**: Fix the issue and rerun just that stage

### No Videos Found

**Problem**: Fetch stage returns 0 videos
- Check YouTube API quota (10,000 units/day)
- Verify API key is valid
- Check network connectivity
- Try different search category

### Claude API Errors

**Problem**: Assess or Enhance stage fails
- Verify ANTHROPIC_API_KEY is valid
- Check Claude API rate limits
- Review prompt format in logs
- Ensure sufficient API credits

### Debug Mode

Run with increased logging:
```bash
export LOG_LEVEL=DEBUG
happytube run-all --category Music
```

## Important Notes

- The project uses modern Python tooling (Poetry, Ruff) instead of traditional pip/flake8
- All async operations and API calls should include proper error handling
- Data processing uses markdown files with YAML frontmatter for stage-based architecture
- Legacy CSV format is still used for Claude API communication
- The happiness scoring system uses a 1-5 scale where ≥3 is considered "happy"
- Each stage can be run independently for debugging or reprocessing
- Logs are stored in `logs/` directory with daily rotation