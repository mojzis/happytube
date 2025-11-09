# Phase 5: Automation & Polish

**Timeline:** Day 7

## Overview

This final phase focuses on making HappyTube production-ready. We'll create automation scripts, add comprehensive error handling, write tests, and update documentation. This ensures the system can run reliably on a daily schedule.

## Goals

- Create daily automation script for cron
- Improve error handling and recovery
- Add retry logic for API calls
- Write comprehensive tests
- Update README with new architecture
- Document configuration options
- Add monitoring and alerting hooks
- Create troubleshooting guide

## Tasks

### 1. Create Daily Automation Script

**File:** `scripts/daily_run.sh`

**Purpose:** Production script for automated daily runs.

**Implementation:**
```bash
#!/bin/bash
set -euo pipefail

# Configuration
HAPPYTUBE_DIR="${HAPPYTUBE_DIR:-/home/user/happytube}"
LOG_DIR="$HAPPYTUBE_DIR/logs"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
LOG_FILE="$LOG_DIR/$TIMESTAMP.log"

# Categories to process (can be configured)
CATEGORIES="${HAPPYTUBE_CATEGORIES:-Music}"
MAX_VIDEOS="${HAPPYTUBE_MAX_VIDEOS:-50}"

# Email notification settings (optional)
NOTIFY_EMAIL="${HAPPYTUBE_NOTIFY_EMAIL:-}"
SEND_NOTIFICATIONS="${HAPPYTUBE_SEND_NOTIFICATIONS:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

send_notification() {
    local subject="$1"
    local message="$2"

    if [ "$SEND_NOTIFICATIONS" = "true" ] && [ -n "$NOTIFY_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$NOTIFY_EMAIL"
    fi
}

cleanup_old_logs() {
    # Keep logs for 30 days
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete
    log_info "Cleaned up logs older than 30 days"
}

# Main script
main() {
    log_info "========================================="
    log_info "Starting HappyTube daily run for $DATE"
    log_info "========================================="

    # Create log directory
    mkdir -p "$LOG_DIR"

    # Change to project directory
    cd "$HAPPYTUBE_DIR" || {
        log_error "Failed to change to project directory: $HAPPYTUBE_DIR"
        exit 1
    }

    # Check if virtual environment exists
    if [ ! -d ".venv" ]; then
        log_error "Virtual environment not found. Run 'poetry install' first."
        exit 1
    fi

    # Activate virtual environment
    log_info "Activating virtual environment"
    source .venv/bin/activate || {
        log_error "Failed to activate virtual environment"
        exit 1
    }

    # Verify credentials
    if [ ! -f ".env" ]; then
        log_error ".env file not found"
        exit 1
    fi

    # Run the pipeline
    log_info "Running HappyTube pipeline for category: $CATEGORIES"

    if poetry run happytube run-all \
        --category "$CATEGORIES" \
        --max-videos "$MAX_VIDEOS" \
        --date "$DATE" 2>&1 | tee -a "$LOG_FILE"; then

        log_info "Pipeline completed successfully"

        # Check if report was generated
        REPORT_PATH="stages/report/$DATE.html"
        if [ -f "$REPORT_PATH" ]; then
            log_info "Report generated: $REPORT_PATH"

            # Optional: Copy report to web server
            if [ -n "${HAPPYTUBE_WEBSERVER:-}" ]; then
                log_info "Copying report to web server"
                scp "$REPORT_PATH" "$HAPPYTUBE_WEBSERVER" || \
                    log_warn "Failed to copy report to web server"
            fi

            # Send success notification
            send_notification \
                "HappyTube: Success for $DATE" \
                "HappyTube pipeline completed successfully. Report: $REPORT_PATH"

        else
            log_warn "Report file not found: $REPORT_PATH"
        fi

    else
        log_error "Pipeline failed!"
        send_notification \
            "HappyTube: FAILED for $DATE" \
            "HappyTube pipeline failed. Check logs: $LOG_FILE"
        exit 1
    fi

    # Cleanup old logs
    cleanup_old_logs

    # Generate analytics (weekly on Mondays)
    if [ "$(date +%u)" -eq 1 ]; then
        log_info "Generating weekly analytics"
        poetry run happytube analytics --days 7 --export >> "$LOG_FILE" 2>&1 || \
            log_warn "Analytics generation failed"
    fi

    log_info "========================================="
    log_info "Daily run completed successfully"
    log_info "========================================="
}

# Run main function
main

exit 0
```

**File:** `scripts/setup_cron.sh`

**Purpose:** Helper script to set up cron job.

```bash
#!/bin/bash

# Configuration
HAPPYTUBE_DIR="${HAPPYTUBE_DIR:-/home/user/happytube}"
CRON_TIME="${HAPPYTUBE_CRON_TIME:-0 8 * * *}"  # Default: 8 AM daily

# Create cron job entry
CRON_JOB="$CRON_TIME $HAPPYTUBE_DIR/scripts/daily_run.sh >> $HAPPYTUBE_DIR/logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "daily_run.sh"; then
    echo "Cron job already exists. Updating..."
    crontab -l | grep -v "daily_run.sh" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job installed successfully!"
echo "Schedule: $CRON_TIME"
echo "Script: $HAPPYTUBE_DIR/scripts/daily_run.sh"
echo ""
echo "To view cron jobs: crontab -l"
echo "To edit cron jobs: crontab -e"
echo "To remove this job: crontab -l | grep -v daily_run.sh | crontab -"
```

Make scripts executable:
```bash
chmod +x scripts/daily_run.sh
chmod +x scripts/setup_cron.sh
```

### 2. Add Retry Logic for API Calls

**File:** `happytube/utils/retry.py`

**Purpose:** Retry decorator for API calls with exponential backoff.

**Implementation:**
```python
import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple

logger = logging.getLogger("happytube")

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                    delay *= backoff_factor

            return None  # Should never reach here

        return wrapper
    return decorator
```

**File:** `happytube/utils/retry_async.py`

**Purpose:** Async version of retry decorator.

```python
import asyncio
import logging
from functools import wraps
from typing import Callable, Type, Tuple

logger = logging.getLogger("happytube")

def async_retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Async version of retry decorator."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    await asyncio.sleep(delay)
                    delay *= backoff_factor

            return None

        return wrapper
    return decorator
```

### 3. Enhance Error Handling in Stages

Update stage implementations to use retry logic:

**Example for `happytube/claude.py`:**

```python
from happytube.utils.retry import retry_with_backoff
import anthropic

@retry_with_backoff(max_retries=3, initial_delay=2.0, exceptions=(anthropic.APIError,))
def call_claude_api(prompt: str, model: str, max_tokens: int) -> str:
    """Call Claude API with retry logic."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

### 4. Add Comprehensive Tests

**File:** `tests/test_markdown.py`

```python
import pytest
from pathlib import Path
from happytube.models.markdown import MarkdownFile

def test_markdown_create_and_save(tmp_path):
    """Test creating and saving markdown file."""
    frontmatter = {"video_id": "test123", "title": "Test Video"}
    content = "# Test Video\n\nTest description"

    md_file = MarkdownFile(frontmatter, content)
    output_path = tmp_path / "test.md"

    md_file.save(output_path)
    assert output_path.exists()

def test_markdown_load(tmp_path):
    """Test loading markdown file."""
    test_content = """---
video_id: test123
title: Test Video
---

# Test Video

Test description"""

    test_file = tmp_path / "test.md"
    test_file.write_text(test_content)

    md_file = MarkdownFile.load(test_file)
    assert md_file.frontmatter["video_id"] == "test123"
    assert "Test description" in md_file.content

def test_markdown_update_frontmatter(tmp_path):
    """Test updating frontmatter."""
    md_file = MarkdownFile({"key": "value"}, "content")
    md_file.update_frontmatter({"new_key": "new_value"})

    assert md_file.frontmatter["key"] == "value"
    assert md_file.frontmatter["new_key"] == "new_value"
```

**File:** `tests/test_config.py`

```python
import pytest
from happytube.config.config_manager import ConfigManager
from pathlib import Path

def test_config_manager_load_base():
    """Test loading base configuration."""
    cm = ConfigManager()
    config = cm.load_base_config('app')

    assert 'version' in config
    assert 'metadata' in config
    assert config['metadata']['name'] == 'happytube'

def test_config_manager_merge():
    """Test merging configurations."""
    cm = ConfigManager()
    base = {"a": 1, "b": {"c": 2}}
    override = {"b": {"c": 3, "d": 4}}

    merged = cm.merge_configs(base, override)

    assert merged["a"] == 1
    assert merged["b"]["c"] == 3
    assert merged["b"]["d"] == 4
```

**File:** `tests/test_retry.py`

```python
import pytest
from happytube.utils.retry import retry_with_backoff

def test_retry_success_first_attempt():
    """Test successful execution on first attempt."""
    call_count = 0

    @retry_with_backoff(max_retries=3)
    def always_succeeds():
        nonlocal call_count
        call_count += 1
        return "success"

    result = always_succeeds()
    assert result == "success"
    assert call_count == 1

def test_retry_success_after_failures():
    """Test successful execution after retries."""
    call_count = 0

    @retry_with_backoff(max_retries=3, initial_delay=0.1)
    def fails_twice():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Temporary error")
        return "success"

    result = fails_twice()
    assert result == "success"
    assert call_count == 3

def test_retry_max_retries_exceeded():
    """Test that max retries is respected."""
    @retry_with_backoff(max_retries=2, initial_delay=0.1)
    def always_fails():
        raise ValueError("Permanent error")

    with pytest.raises(ValueError, match="Permanent error"):
        always_fails()
```

### 5. Update README

**File:** `README.md` (major update)

```markdown
# HappyTube 🎥

YouTube happiness analyzer that fetches videos, assesses their happiness level using Claude AI, enhances descriptions for happy content, and generates beautiful reports.

## Features

✨ **Stage-Based Pipeline**: Modular architecture with independent stages
📊 **Rich Analytics**: Track happiness trends over time with Parquet exports
🎨 **Beautiful Reports**: HTML reports with responsive design
🤖 **AI-Powered**: Claude AI for happiness assessment and content enhancement
⚙️ **Flexible Configuration**: YAML-based configuration system
🔄 **Daily Automation**: Cron-ready scripts for automated runs
📈 **Progress Tracking**: Rich console output with progress bars

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/happytube.git
cd happytube

# Install dependencies
poetry install

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys:
# - YTKEY (YouTube Data API v3)
# - ANTHROPIC_API_KEY (Claude API)
```

### Basic Usage

```bash
# Run complete pipeline
happytube run-all --category Music --max-videos 50

# Run individual stages
happytube fetch --category Music --max-videos 50
happytube assess --date 2025-11-09
happytube enhance --threshold 3

# Check status
happytube status --date 2025-11-09

# View analytics
happytube analytics --days 7
```

## Architecture

### Stage-Based Flow

```
FetchStage    → stages/fetch/YYYY-MM-DD/*.md
   ↓
AssessStage   → stages/assess/YYYY-MM-DD/*.md (+ happiness_score)
   ↓
EnhanceStage  → stages/enhance/YYYY-MM-DD/*.md (+ enhanced_description)
   ↓
ReportStage   → stages/report/YYYY-MM-DD.html + parquet exports
```

### Directory Structure

```
happytube/
├── config/              # YAML configuration files
│   ├── base/           # Base configurations
│   └── experiments/    # Experiment overrides
├── stages/             # Processing stages (markdown files)
│   ├── fetch/
│   ├── assess/
│   ├── enhance/
│   └── report/
├── parquet/            # Analytics exports
├── templates/          # HTML templates
├── happytube/          # Source code
│   ├── cli/           # CLI commands
│   ├── stages/        # Stage implementations
│   ├── config/        # Configuration management
│   ├── models/        # Data models
│   └── utils/         # Utilities
└── scripts/           # Automation scripts
```

## Daily Automation

### Set Up Cron Job

```bash
# Run setup script
./scripts/setup_cron.sh

# Or manually add to crontab:
crontab -e

# Add this line (runs daily at 8 AM):
0 8 * * * /home/user/happytube/scripts/daily_run.sh >> /home/user/happytube/logs/cron.log 2>&1
```

### Environment Variables for Automation

```bash
export HAPPYTUBE_DIR="/home/user/happytube"
export HAPPYTUBE_CATEGORIES="Music"
export HAPPYTUBE_MAX_VIDEOS="50"
export HAPPYTUBE_SEND_NOTIFICATIONS="true"
export HAPPYTUBE_NOTIFY_EMAIL="your@email.com"
```

## Configuration

### YouTube Search Configs (`config/base/youtube.yaml`)

Define different search configurations for various categories:

```yaml
searches:
  music_search:
    name: "Music Videos"
    params:
      regionCode: "CZ"
      videoDuration: "medium"
      videoCategoryId: 15
      maxResults: 50
```

### Prompt Configs (`config/base/prompts.yaml`)

Customize Claude prompts for assessment and enhancement:

```yaml
prompts:
  happiness_v2:
    model: "claude-3-opus-20240229"
    max_tokens: 4096
    template: |
      Rate happiness level (1-5 scale)...
```

## Analytics

View happiness trends and statistics:

```bash
# Show analytics for last 7 days
happytube analytics --days 7

# Export to CSV
happytube analytics --days 30 --export
```

Analytics include:
- Overall happiness distribution
- Top channels by happiness
- Category analysis
- Time-series trends

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=happytube

# Run specific test file
poetry run pytest tests/test_pipeline.py -v
```

## Development

```bash
# Install development dependencies
poetry install

# Run linter
poetry run ruff check .

# Format code
poetry run ruff format .

# Interactive development
./scripts/ip.sh
```

## Troubleshooting

### Common Issues

**No videos found**
- Check YouTube API quota
- Verify API key in `.env`
- Check search configuration

**Claude API errors**
- Verify `ANTHROPIC_API_KEY`
- Check rate limits
- Review prompt format

**Pipeline fails midway**
- Check logs in `logs/` directory
- Inspect stage directories for error status
- Rerun specific stage: `happytube assess --date YYYY-MM-DD`

### Debug Mode

```bash
happytube --log-level DEBUG run-all --max-videos 5
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
```

### 6. Create Environment Example File

**File:** `.env.example`

```bash
# YouTube Data API v3
YTKEY=your_youtube_api_key_here

# Anthropic Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: Logging
LOG_LEVEL=INFO
ENVIRONMENT=production

# Optional: Automation
HAPPYTUBE_CATEGORIES=Music
HAPPYTUBE_MAX_VIDEOS=50
HAPPYTUBE_SEND_NOTIFICATIONS=false
HAPPYTUBE_NOTIFY_EMAIL=
```

### 7. Add Pre-commit Hooks (Optional)

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

## Testing Phase 5

```bash
# Test automation script
./scripts/daily_run.sh

# Test cron setup
./scripts/setup_cron.sh
crontab -l

# Run all tests
poetry run pytest -v --cov=happytube

# Test retry logic
poetry run pytest tests/test_retry.py -v

# Verify documentation
cat README.md
```

## Dependencies Summary

No new dependencies - all tools from previous phases.

Optional for pre-commit:
```bash
poetry add --group dev pre-commit
pre-commit install
```

## Success Criteria

- ✅ Daily automation script works
- ✅ Cron job setup successful
- ✅ Retry logic handles API failures
- ✅ All tests pass
- ✅ Test coverage > 80%
- ✅ README is comprehensive
- ✅ Configuration documented
- ✅ Error handling robust
- ✅ Logging helpful for debugging
- ✅ System production-ready

## Production Checklist

Before going live:

- [ ] All API keys configured in `.env`
- [ ] Cron job scheduled
- [ ] Log rotation configured
- [ ] Email notifications tested (if enabled)
- [ ] Disk space monitored
- [ ] Backup strategy for data
- [ ] Error alerting configured
- [ ] Documentation reviewed
- [ ] All tests passing
- [ ] Dry run completed successfully

## Monitoring

Key metrics to monitor:
- Daily pipeline success rate
- Average happiness scores over time
- API quota usage (YouTube)
- Claude API costs
- Disk space usage
- Error rates

## Future Enhancements

Consider for future versions:
- Web dashboard for analytics
- Multi-language support
- Real-time processing
- Machine learning predictions
- Public API
- Mobile app integration

## Complete!

After Phase 5, HappyTube is production-ready with:
- ✅ Automated daily runs
- ✅ Comprehensive error handling
- ✅ Full test coverage
- ✅ Beautiful reports
- ✅ Flexible configuration
- ✅ Rich analytics
- ✅ Complete documentation
