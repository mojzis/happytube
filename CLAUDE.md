# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HappyTube is a Python application that analyzes YouTube videos to identify and enhance "happy" content. It fetches videos from YouTube API, uses Claude AI to assess happiness scores, and improves video descriptions for highly-rated content.

## Commands

### Development Environment
```bash
# Install dependencies
poetry install

# Run the main application
poetry run python -m happytube.main

# Interactive development environment
./scripts/ip.sh  # or: ipython -i happytube/ip.py

# Run tests
poetry run pytest

# Lint code
poetry run ruff check .
poetry run ruff format .
```

### Running a Single Test
```bash
poetry run pytest tests/utils_test.py::test_function_name -v
```

### Web Player
```bash
# Start the web player (after running main application)
poetry run python -m happytube.web.server

# Access at http://127.0.0.1:5000
```

## Architecture

### Core Pipeline Flow
1. **Video Fetching** (`videos.py`, `yt.py`)
   - Uses YouTube Data API v3 to search for videos
   - Configurable by category, duration, region, etc.
   - Results stored in `data/fetched/`

2. **Happiness Assessment** (`claude.py`, `prompts.py`)
   - Sends video metadata to Claude API
   - Returns happiness scores (1-5 scale)
   - Uses configurable prompts from `prompt_definitions`

3. **Description Enhancement** (`claude.py`)
   - Processes videos with happiness ≥ 3
   - Generates improved descriptions via Claude
   - Maintains CSV format for data exchange

4. **Web Player** (`web/`)
   - Flask-based web interface for video playback
   - Controlled YouTube embed with disabled recommendations
   - Playlist navigation and search functionality
   - Only shows curated videos from the pipeline

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
data/
├── categories.json      # YouTube category definitions
└── fetched/
    ├── lists/          # Search results
    └── videos/         # Video details

happytube/web/          # Web player
├── server.py           # Flask backend
├── static/             # CSS, JS assets
└── templates/          # HTML templates
```

## Important Notes

- The project uses modern Python tooling (Poetry, Ruff) instead of traditional pip/flake8
- All async operations and API calls should include proper error handling
- Data processing maintains CSV format when communicating with Claude API
- The happiness scoring system uses a 1-5 scale where ≥3 is considered "happy"