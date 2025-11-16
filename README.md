# HappyTube

A Python application that analyzes YouTube videos to identify and enhance "happy" content. It fetches videos from YouTube API, uses Claude AI to assess happiness scores, and provides a curated web player for viewing.

## Features

- **Video Fetching**: Search and fetch videos from YouTube API by category, length, and order
- **AI Assessment**: Use Claude AI to assess video happiness from title & description
- **Description Enhancement**: Improve video descriptions by removing clickbait and spam
- **Stage-Based Pipeline**: Modular architecture with independent, rerunnable stages
- **Daily Automation**: Cron-ready script for automated daily processing
- **Web Player**: Simple, controlled video player with disabled YouTube recommendations
- **Curated Playlists**: Only display videos that meet happiness criteria
- **Analytics Export**: Export data to Parquet format for analysis

## Quick Start

### Installation

```bash
# Install dependencies
poetry install

# Set up environment variables (.env file)
YTKEY=your_youtube_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### Using the Modern CLI (Recommended)

```bash
# Run the complete pipeline (fetch → assess → enhance → report)
happytube run-all --category Music --max-videos 50

# Or run individual stages
happytube fetch --category Music --max-videos 50
happytube assess
happytube enhance --threshold 3
happytube report

# Check pipeline status
happytube status

# Get help
happytube --help
```

### Legacy Method (Deprecated)

```bash
# Run the legacy main pipeline
poetry run python -m happytube.main
```

### Daily Automation

```bash
# Run the automated daily pipeline
./scripts/daily_run.sh

# Set up cron job for daily execution at 8 AM
# crontab -e
# Add: 0 8 * * * /home/user/happytube/scripts/daily_run.sh >> /home/user/happytube/logs/cron.log 2>&1
```

## Web Player

The web player provides a controlled YouTube viewing experience:

- Embeds videos with disabled recommendations and related content
- Search and filter through your curated video collection
- Keyboard navigation (arrow keys or n/p)
- Auto-play next video option
- Fullscreen support
- **Deploy to GitHub Pages for free** - no backend required!

### Deployment

Deploy your curated video collection to GitHub Pages:

```bash
# Export videos to static files
poetry run python -m happytube.web.export

# Or use the interactive deployment script
./scripts/deploy_web.sh
```

See `happytube/web/DEPLOYMENT.md` for detailed deployment instructions including:
- GitHub Pages setup
- Netlify/Vercel deployment
- GitHub Actions automation
- Custom domains

See `happytube/web/README.md` for player details.

## Modernized Architecture

HappyTube has been modernized with a **stage-based pipeline architecture** for better modularity, debugging, and daily automation.

### Stage-Based Pipeline

```
Stage 1: FETCH    → stages/fetch/YYYY-MM-DD/*.md
Stage 2: ASSESS   → stages/assess/YYYY-MM-DD/*.md  (with happiness_score)
Stage 3: ENHANCE  → stages/enhance/YYYY-MM-DD/*.md (with enhanced_description)
Stage 4: REPORT   → stages/report/YYYY-MM-DD.html + parquet exports
```

**Key Benefits:**
- Each stage can be run independently
- Human-readable markdown files with YAML frontmatter
- Git-friendly data format
- Easy to debug and inspect intermediate results
- Can reprocess specific dates without restarting pipeline
- Automatic error handling and logging

### Data Storage

```
stages/              # Stage-based data (new architecture)
├── fetch/          # Fetched videos
├── assess/         # Assessed videos (with happiness scores)
├── enhance/        # Enhanced videos (with improved descriptions)
└── report/         # Generated HTML reports

parquet/            # Analytics exports
├── fetch/
├── assess/
└── enhance/

logs/               # Pipeline execution logs
├── YYYY-MM-DD.log
└── cron.log

templates/          # Report templates
├── base.html
└── daily_report.html

config/             # Configuration files (optional)
├── base/
│   ├── app.yaml
│   ├── prompts.yaml
│   └── youtube.yaml
└── experiments/
```

### Configuration

Configuration files can be created in `config/base/` to customize:
- YouTube search parameters
- Claude prompt templates
- Processing thresholds
- Model configurations

See `docs/modernization-plan.md` for detailed architecture documentation.

## Pipeline Details

The pipeline processes videos through four stages:

1. **Fetch**: Search YouTube API for videos by category, length, and order
2. **Assess**: Use Claude AI to rate video happiness (1-5 scale) from title & description
3. **Enhance**: Improve descriptions for happy videos (≥3) by removing clickbait and spam
4. **Report**: Generate HTML reports and export analytics to Parquet

### Future Enhancements
- [planned] Fetch video comments and assess comment sentiment
- [planned] Channel statistics and reputation tracking
- [planned] Multi-language support beyond LATIN script
- [planned] Video thumbnail analysis


## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_pipeline.py -v

# Run specific test
poetry run pytest tests/test_pipeline.py::TestMarkdownFile::test_create_and_save -v

# Run with coverage
poetry run pytest --cov=happytube --cov-report=html
```

### Code Quality

```bash
# Lint code
poetry run ruff check .

# Format code
poetry run ruff format .

# Run both linting and formatting
poetry run ruff check . && poetry run ruff format .
```

### Interactive Development

```bash
# Start IPython with happytube modules loaded
./scripts/ip.sh

# Or manually
ipython -i happytube/ip.py
```

### Inspecting Pipeline Data

```bash
# View fetched videos
ls -la stages/fetch/$(date +%Y-%m-%d)/

# Read a video's frontmatter and content
cat stages/fetch/$(date +%Y-%m-%d)/video_abc123.md

# Check happiness scores
grep "happiness_score:" stages/assess/$(date +%Y-%m-%d)/*.md

# View today's report
open stages/report/$(date +%Y-%m-%d).html
```

## Contributing

See `docs/modernization-plan.md` for the architectural vision and implementation phases.

## TODO (Future Enhancements)
- parse `thumbnails`, put the middle one into the df
- store stats about the call to claude - how long it took, tokens used
- experiment with more sophisticated prompts
- try various models, observe the happiness distribution
- implement async processing with queues for better performance


## https://www.googleapis.com/youtube/v3/search

according to https://developers.google.com/youtube/v3/docs/search/list

part=snippet




in case i manage to identify channels channelId

maxResults=50

order=rating

q = general query - do we bother ?

regionCode=CZ

safeSearch=strict

topicId - look at the page, should be useful

type=video

videoCategoryId= as per https://developers.google.com/youtube/v3/docs/videoCategories

https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=CZ





