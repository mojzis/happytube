# HappyTube Modernization Plan

## Overview

This document outlines the plan to transform HappyTube from a prototype into a production-ready system that can run daily, based on patterns learned from the `newsparser` project.

## 🎯 Goals

1. **Daily Automation**: Run on schedule, track what happened
2. **Modular Commands**: Run individual stages or full pipeline
3. **Robust Data Persistence**: Markdown + frontmatter + Parquet analytics
4. **Clear Reporting**: Daily summaries of videos processed, happiness scores, enhancements
5. **Error Resilience**: Handle failures gracefully, enable retries
6. **Configuration Management**: Externalize settings, prompts, and search configs

## 🏗️ Architecture Changes

### Current Flow
```
YouTube API → DataFrame → Claude (CSV) → Filter → Claude (CSV) → Output
```

### New Stage-Based Flow
```
Stage 1: FETCH     → stages/fetch/YYYY-MM-DD/*.md
Stage 2: ASSESS    → stages/assess/YYYY-MM-DD/*.md  (with happiness_score)
Stage 3: ENHANCE   → stages/enhance/YYYY-MM-DD/*.md (with enhanced_description)
Stage 4: REPORT    → reports/YYYY-MM-DD.html + parquet export
```

**Benefits:**
- ✅ Each stage processes independently (can rerun individual stages)
- ✅ Stores human-readable markdown files with YAML frontmatter
- ✅ Tracks processing status and errors
- ✅ Enables partial reruns and debugging
- ✅ Git-friendly data format

## 📁 New Directory Structure

```
happytube/
├── config/
│   ├── base/
│   │   ├── app.yaml           # Main app config
│   │   ├── prompts.yaml       # Claude prompt definitions
│   │   └── youtube.yaml       # YouTube search configs
│   └── experiments/           # Override configs for testing
│       └── test-search.yaml
├── stages/
│   ├── fetch/
│   │   └── 2025-11-09/
│   │       ├── video_abc123.md
│   │       └── video_def456.md
│   ├── assess/
│   │   └── 2025-11-09/
│   │       ├── video_abc123.md  # + happiness_score in frontmatter
│   │       └── video_def456.md
│   ├── enhance/
│   │   └── 2025-11-09/
│   │       └── video_abc123.md  # + enhanced_description
│   └── report/
│       └── 2025-11-09.html
├── parquet/                   # Analytics exports
│   ├── fetch/
│   │   └── 2025-11-09_last_7_days.parquet
│   ├── assess/
│   └── enhance/
├── templates/
│   ├── base.html
│   └── daily_report.html
├── happytube/
│   ├── cli/
│   │   ├── commands.py        # Click CLI commands
│   │   └── stage_commands.py  # Individual stage commands
│   ├── stages/
│   │   ├── base.py           # Base Stage class
│   │   ├── fetch.py          # FetchStage
│   │   ├── assess.py         # AssessStage
│   │   ├── enhance.py        # EnhanceStage
│   │   └── report.py         # ReportStage
│   ├── config/
│   │   ├── settings.py       # Pydantic Settings
│   │   ├── config_manager.py # Config loader
│   │   └── models.py         # Config Pydantic models
│   ├── models/
│   │   ├── video.py          # Video Pydantic model with analytics
│   │   └── markdown.py       # MarkdownFile class
│   └── utils/
│       └── logging.py        # Centralized logging
└── scripts/
    └── daily_run.sh          # Cron job script
```

## 🔧 Key Components

### 1. CLI with Click

**Entry point via Poetry:**
```toml
[tool.poetry.scripts]
happytube = "happytube.cli.commands:cli"
```

**Commands:**
```bash
# Individual stages
happytube fetch --category Music --max-videos 50
happytube assess --date 2025-11-09
happytube enhance --threshold 3

# Full pipeline
happytube run-all --category Music

# Status checking
happytube status --date 2025-11-09
```

**Implementation pattern:**
```python
import click
from rich.console import Console

console = Console()

@click.group()
def cli():
    """HappyTube - YouTube happiness analyzer"""
    # Validate configuration on startup
    pass

@cli.command()
@click.option("--category", default="Music", help="YouTube category")
@click.option("--max-videos", default=50, help="Max videos to fetch")
@click.option("--date", help="Target date (YYYY-MM-DD)")
def fetch(category, max_videos, date):
    """Fetch videos from YouTube"""
    console.print("🔍 Fetching videos...", style="bold blue")
    # Run FetchStage

@cli.command()
@click.option("--date", help="Target date (YYYY-MM-DD)")
@click.option("--category", default="Music")
@click.option("--max-videos", default=50)
def run_all(date, category, max_videos):
    """Run complete pipeline: fetch → assess → enhance → report"""
    console.print("🚀 Starting HappyTube pipeline...", style="bold green")
    # Run all stages sequentially with progress reporting
```

### 2. Stage-Based Architecture

**Base Stage Class:**
```python
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import date
from typing import Iterator

class Stage(ABC):
    """Base class for all processing stages."""

    def __init__(self, stage_name: str, base_path: Path = Path("stages")):
        self.stage_name = stage_name
        self.stage_path = base_path / stage_name

    def get_stage_dir(self, target_date: date) -> Path:
        """Get stage directory for date."""
        return self.stage_path / target_date.strftime("%Y-%m-%d")

    def ensure_stage_dir(self, target_date: date) -> Path:
        """Create stage directory if needed."""
        stage_dir = self.get_stage_dir(target_date)
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir

    @abstractmethod
    async def run(self, target_date: date) -> dict:
        """Run the stage. Returns stats dict."""
        pass
```

**Concrete Stage Example:**
```python
class FetchStage(Stage):
    """Fetches videos from YouTube and stores as markdown files."""

    def __init__(self, youtube_config: dict, max_videos: int = 50):
        super().__init__("fetch")
        self.youtube_config = youtube_config
        self.max_videos = max_videos

    async def run(self, target_date: date) -> dict:
        """Fetch videos and save as markdown files."""
        stage_dir = self.ensure_stage_dir(target_date)

        # Use existing videos.py Search class
        search = Search(**self.youtube_config)
        videos_df = search.get_df()

        saved_count = 0
        for _, row in videos_df.iterrows():
            # Create markdown file with frontmatter
            frontmatter = {
                "video_id": row["video_id"],
                "title": row["title"],
                "channel": row.get("channel", ""),
                "fetched_at": datetime.utcnow().isoformat() + 'Z',
                "stage": "fetched",
                "script_type": row.get("script_type", ""),
            }
            content = f"# {row['title']}\n\n{row['description']}"

            md_file = MarkdownFile(frontmatter, content)
            output_path = stage_dir / f"video_{row['video_id']}.md"
            md_file.save(output_path)
            saved_count += 1

        return {
            "new_videos": saved_count,
            "date": target_date.strftime("%Y-%m-%d"),
        }
```

### 3. Markdown Files with YAML Frontmatter

**MarkdownFile Class:**
```python
import yaml
from pathlib import Path
from typing import Dict, Any

class MarkdownFile:
    """Represents a Markdown file with YAML frontmatter."""

    def __init__(self, frontmatter: Dict[str, Any], content: str):
        self.frontmatter = frontmatter
        self.content = content

    @classmethod
    def load(cls, file_path: Path) -> "MarkdownFile":
        """Load a Markdown file with frontmatter."""
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Split frontmatter and content
        if text.startswith('---\n'):
            parts = text.split('---\n', 2)
            frontmatter = yaml.safe_load(parts[1])
            content = parts[2].strip()
        else:
            frontmatter = {}
            content = text

        return cls(frontmatter, content)

    def save(self, file_path: Path) -> None:
        """Save the Markdown file with frontmatter."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_string())

    def to_string(self) -> str:
        """Convert to string format with frontmatter."""
        yaml_str = yaml.dump(self.frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n\n{self.content}"

    def update_frontmatter(self, updates: Dict[str, Any]) -> None:
        """Update frontmatter with new values."""
        self.frontmatter.update(updates)
```

**Example File: `stages/fetch/2025-11-09/video_abc123.md`**
```yaml
---
video_id: abc123
title: "Happy Cat Playing Piano"
channel: "CatChannel"
category: "Music"
duration: 300
fetched_at: "2025-11-09T10:00:00Z"
stage: "fetched"
script_type: "LATIN"
---

# Happy Cat Playing Piano

Watch this amazing cat play Beethoven's Moonlight Sonata!
Like and subscribe for more cat content...
```

**After Assessment: `stages/assess/2025-11-09/video_abc123.md`**
```yaml
---
video_id: abc123
title: "Happy Cat Playing Piano"
channel: "CatChannel"
category: "Music"
duration: 300
fetched_at: "2025-11-09T10:00:00Z"
stage: "assessed"
happiness_score: 4
happiness_reasoning: "Cute cat content with musical performance creates positive emotions"
assessed_at: "2025-11-09T10:30:00Z"
prompt_version: "happiness_v2"
---

# Happy Cat Playing Piano

Watch this amazing cat play Beethoven's Moonlight Sonata!
Like and subscribe for more cat content...
```

### 4. Configuration Files

**`config/base/app.yaml`:**
```yaml
version: "1.0"
metadata:
  name: "happytube"
  description: "YouTube happiness analyzer"

paths:
  stages_base: "stages"
  templates: "templates"
  parquet_export: "parquet"

processing:
  happiness_threshold: 3
  max_videos_per_run: 50
  default_youtube_config: "music_search"
  default_prompt_config: "happiness_v2"

export:
  parquet_days_back: 7
  report_format: "html"
```

**`config/base/prompts.yaml`:**
```yaml
version: "1.0"
prompts:
  happiness_v2:
    name: "Happiness Assessment CSV v2"
    version: "2.0"
    model: "claude-3-opus-20240229"
    max_tokens: 4096
    template: |
      {csv_content}

      Rate the happiness level (1-5 scale) of each video based on:
      - Title sentiment
      - Description content
      - Category context

      Return CSV with columns: video_id,happiness,reasoning
      Keep reasoning concise (max 100 chars).

  enhance_description_v1:
    name: "Description Enhancement v1"
    version: "1.0"
    model: "claude-3-opus-20240229"
    max_tokens: 2048
    template: |
      Improve this video description by removing:
      - Clickbait language
      - "Like and subscribe" spam
      - Excessive links
      - Overly promotional content

      Title: {title}
      Description: {description}

      Return only the enhanced description. Keep it natural and informative.
```

**`config/base/youtube.yaml`:**
```yaml
version: "1.0"
searches:
  music_search:
    name: "Music Videos"
    params:
      regionCode: "CZ"
      videoDuration: "medium"
      videoCategoryId: 15  # Music
      order: "viewCount"
      safeSearch: "strict"
      maxResults: 50

  educational_search:
    name: "Educational Content"
    params:
      regionCode: "US"
      videoDuration: "medium"
      videoCategoryId: 27  # Education
      order: "relevance"
      safeSearch: "strict"
      maxResults: 30

  entertainment_search:
    name: "Entertainment Videos"
    params:
      regionCode: "CZ"
      videoDuration: "medium"
      videoCategoryId: 24  # Entertainment
      order: "viewCount"
      safeSearch: "strict"
      maxResults: 50
```

### 5. Pydantic Settings

**`happytube/config/settings.py`:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Keys
    youtube_api_key: str = Field(..., alias="YTKEY", description="YouTube Data API key")
    anthropic_api_key: str = Field(..., description="Anthropic Claude API key")

    # Application
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment name")

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @property
    def has_all_credentials(self) -> bool:
        """Check if all required credentials are configured."""
        return bool(self.youtube_api_key and self.anthropic_api_key)

def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
```

### 6. Video Analytics Model

**`happytube/models/video.py`:**
```python
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from typing import Optional
import pandas as pd
from pathlib import Path

class Video(BaseModel):
    """Video model with analytics export capabilities."""

    video_id: str
    title: str
    channel: str
    category: Optional[str] = None
    duration: Optional[int] = None
    fetched_at: datetime
    stage: str
    script_type: Optional[str] = None

    # Assessment fields
    happiness_score: Optional[int] = None
    happiness_reasoning: Optional[str] = None
    assessed_at: Optional[datetime] = None

    # Enhancement fields
    enhanced_description: Optional[str] = None
    enhanced_at: Optional[datetime] = None

    @classmethod
    def from_frontmatter(cls, frontmatter: dict) -> "Video":
        """Create Video from markdown frontmatter."""
        return cls.model_validate(frontmatter)

    def to_pandas_dict(self) -> dict:
        """Convert to dict suitable for pandas DataFrame."""
        return self.model_dump()

    @classmethod
    def df_from_stage_dir(cls, stage_name: str, days_back: int = 7) -> pd.DataFrame:
        """Load videos from stage directory into DataFrame."""
        from happytube.models.markdown import MarkdownFile

        base_path = Path("stages") / stage_name
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back - 1)

        all_videos = []
        current_date = start_date

        while current_date <= end_date:
            date_dir = base_path / current_date.strftime("%Y-%m-%d")
            if date_dir.exists():
                for md_file_path in date_dir.glob("*.md"):
                    md_file = MarkdownFile.load(md_file_path)
                    video = cls.from_frontmatter(md_file.frontmatter)
                    all_videos.append(video.to_pandas_dict())
            current_date += timedelta(days=1)

        return pd.DataFrame(all_videos)

    @classmethod
    def to_parquet(cls, df: pd.DataFrame, output_path: Path) -> None:
        """Export DataFrame to Parquet."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(
            output_path,
            engine='pyarrow',
            compression='snappy',
            index=False
        )
```

### 7. Report Generation

**`happytube/stages/report.py`:**
```python
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import date
from happytube.stages.base import Stage
from happytube.models.video import Video
from happytube.models.markdown import MarkdownFile

class ReportStage(Stage):
    """Generates daily HTML reports and exports analytics."""

    def __init__(self, template_dir: Path = Path("templates")):
        super().__init__("report")
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def _load_enhanced_videos(self, target_date: date) -> list[Video]:
        """Load all enhanced videos for the target date."""
        enhance_dir = Path("stages") / "enhance" / target_date.strftime("%Y-%m-%d")

        if not enhance_dir.exists():
            return []

        videos = []
        for md_path in enhance_dir.glob("*.md"):
            md_file = MarkdownFile.load(md_path)
            video = Video.from_frontmatter(md_file.frontmatter)
            videos.append(video)

        return sorted(videos, key=lambda v: v.happiness_score or 0, reverse=True)

    def _export_parquet(self, target_date: date, days_back: int = 7) -> None:
        """Export stage data to Parquet for analytics."""
        for stage_name in ["fetch", "assess", "enhance"]:
            df = Video.df_from_stage_dir(stage_name, days_back=days_back)

            if not df.empty:
                output_dir = Path("parquet") / stage_name / "by-run-date"
                output_file = output_dir / f"{target_date.strftime('%Y-%m-%d')}_last_{days_back}_days.parquet"
                Video.to_parquet(df, output_file)

    async def run(self, target_date: date) -> dict:
        """Generate report for the date."""
        # Load enhanced videos
        videos = self._load_enhanced_videos(target_date)

        if not videos:
            return {"videos_reported": 0, "message": "No enhanced videos found"}

        # Calculate statistics
        avg_happiness = sum(v.happiness_score for v in videos) / len(videos)

        # Generate HTML report
        template = self.env.get_template("daily_report.html")
        html = template.render(
            date=target_date.strftime("%Y-%m-%d"),
            videos=videos,
            total_count=len(videos),
            avg_happiness=avg_happiness,
        )

        # Save report
        report_path = self.stage_path / f"{target_date.strftime('%Y-%m-%d')}.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(html)

        # Export to parquet for analytics
        self._export_parquet(target_date)

        return {
            "videos_reported": len(videos),
            "avg_happiness": round(avg_happiness, 2),
            "report_path": str(report_path),
        }
```

**`templates/daily_report.html`:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>HappyTube Report - {{ date }}</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .header h1 {
            margin: 0;
            font-size: 2em;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }
        .stat {
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 5px;
        }
        .video {
            background: white;
            border: 1px solid #ddd;
            margin: 15px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .video h2 {
            margin-top: 0;
            color: #333;
        }
        .happiness {
            display: inline-block;
            font-weight: bold;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            margin-bottom: 10px;
        }
        .happiness-5 { background-color: #28a745; }
        .happiness-4 { background-color: #5cb85c; }
        .happiness-3 { background-color: #f0ad4e; }
        .happiness-2 { background-color: #d9534f; }
        .happiness-1 { background-color: #c9302c; }
        .meta {
            color: #666;
            font-size: 0.9em;
            margin: 10px 0;
        }
        .description {
            line-height: 1.6;
            color: #444;
            margin: 15px 0;
        }
        .link {
            display: inline-block;
            background-color: #667eea;
            color: white;
            padding: 8px 20px;
            border-radius: 5px;
            text-decoration: none;
            margin-top: 10px;
        }
        .link:hover {
            background-color: #5568d3;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎥 HappyTube Report</h1>
        <div class="stats">
            <div class="stat">
                <strong>Date:</strong> {{ date }}
            </div>
            <div class="stat">
                <strong>Videos:</strong> {{ total_count }}
            </div>
            <div class="stat">
                <strong>Avg Happiness:</strong> {{ "%.1f"|format(avg_happiness) }}/5
            </div>
        </div>
    </div>

    {% for video in videos %}
    <div class="video">
        <span class="happiness happiness-{{ video.happiness_score }}">
            Happiness: {{ video.happiness_score }}/5
        </span>

        <h2>{{ video.title }}</h2>

        <div class="meta">
            <strong>Channel:</strong> {{ video.channel }}
            {% if video.category %}
            | <strong>Category:</strong> {{ video.category }}
            {% endif %}
            {% if video.duration %}
            | <strong>Duration:</strong> {{ (video.duration // 60)|int }}:{{ "%02d"|format(video.duration % 60) }}
            {% endif %}
        </div>

        {% if video.happiness_reasoning %}
        <div class="meta">
            <strong>Why it's happy:</strong> {{ video.happiness_reasoning }}
        </div>
        {% endif %}

        {% if video.enhanced_description %}
        <div class="description">
            <strong>Enhanced Description:</strong><br>
            {{ video.enhanced_description }}
        </div>
        {% endif %}

        <a href="https://youtube.com/watch?v={{ video.video_id }}" class="link" target="_blank">
            Watch Video →
        </a>
    </div>
    {% endfor %}

    <div style="text-align: center; margin-top: 30px; color: #999;">
        Generated by HappyTube
    </div>
</body>
</html>
```

### 8. Daily Automation

**`scripts/daily_run.sh`:**
```bash
#!/bin/bash
set -e

# Configuration
HAPPYTUBE_DIR="/home/user/happytube"
LOG_DIR="$HAPPYTUBE_DIR/logs"
DATE=$(date +%Y-%m-%d)

# Create log directory
mkdir -p "$LOG_DIR"

# Change to project directory
cd "$HAPPYTUBE_DIR"

# Activate virtual environment
source .venv/bin/activate

# Run full pipeline
echo "[$DATE] Starting HappyTube pipeline..."
poetry run happytube run-all \
    --category Music \
    --max-videos 50 \
    --date "$DATE" 2>&1 | tee "$LOG_DIR/$DATE.log"

# Check if report was generated
REPORT_PATH="stages/report/$DATE.html"
if [ -f "$REPORT_PATH" ]; then
    echo "[$DATE] Report generated successfully: $REPORT_PATH"

    # Optional: Copy report to web server
    # scp "$REPORT_PATH" user@server:/var/www/happytube/reports/

    # Optional: Send email notification
    # echo "HappyTube report for $DATE is ready" | mail -s "HappyTube Report" user@example.com
else
    echo "[$DATE] ERROR: Report not generated!"
    exit 1
fi

echo "[$DATE] Pipeline completed successfully"
```

**Cron job setup:**
```bash
# Edit crontab
crontab -e

# Add this line to run daily at 8 AM
0 8 * * * /home/user/happytube/scripts/daily_run.sh >> /home/user/happytube/logs/cron.log 2>&1
```

## 🚀 Implementation Plan

### Phase 1: Core Infrastructure (Day 1-2)
- [ ] Create directory structure (config/, stages/, templates/, docs/)
- [ ] Implement `MarkdownFile` class with frontmatter support
- [ ] Set up Pydantic `Settings` with `.env` validation
- [ ] Create `ConfigManager` for YAML config loading
- [ ] Implement base `Stage` class
- [ ] Set up centralized logging

### Phase 2: Stage Implementation (Day 3-4)
- [ ] Implement `FetchStage` (adapt existing `videos.py`)
- [ ] Implement `AssessStage` (adapt existing `claude.py`)
- [ ] Implement `EnhanceStage` (adapt existing `claude.py`)
- [ ] Implement `ReportStage` with Jinja2 templates
- [ ] Add error handling and status tracking

### Phase 3: CLI & Commands (Day 5)
- [ ] Set up Click CLI with individual stage commands
- [ ] Implement `fetch`, `assess`, `enhance` commands
- [ ] Implement `run-all` pipeline command
- [ ] Implement `status` command with Rich table output
- [ ] Add progress reporting with Rich console

### Phase 4: Analytics & Reporting (Day 6)
- [ ] Implement `Video` analytics model
- [ ] Add Parquet export functionality
- [ ] Create HTML report templates (daily_report.html, base.html)
- [ ] Add template filters and helpers
- [ ] Test full pipeline end-to-end

### Phase 5: Automation & Polish (Day 7)
- [ ] Create daily automation script (daily_run.sh)
- [ ] Add comprehensive error handling
- [ ] Write integration tests
- [ ] Update README with new usage instructions
- [ ] Document configuration options

## 📊 Success Metrics

After implementation, you'll have:

✅ **Daily automated runs** producing:
- Markdown files for each video (traceable, git-friendly)
- HTML report summarizing the day's finds
- Parquet files for long-term analytics

✅ **Flexible execution**:
```bash
happytube run-all              # Full pipeline
happytube fetch --category Music  # Just fetch
happytube assess --date 2025-11-08  # Reprocess old data
happytube status               # Check progress
```

✅ **Easy debugging**:
- Human-readable markdown files
- Clear stage progression
- Error tracking in frontmatter

✅ **Analytics ready**:
- Parquet exports for pandas/duckdb analysis
- Track happiness trends over time
- Analyze by category, channel, etc.

## 🤔 Design Decisions

### Why Stage-Based Architecture?
- **Modularity**: Each stage can be developed and tested independently
- **Reprocessing**: Can rerun any stage without starting from scratch
- **Debugging**: Easy to inspect intermediate results
- **Flexibility**: Can add new stages without changing existing ones

### Why Markdown + Frontmatter?
- **Human-readable**: Easy to inspect and debug
- **Git-friendly**: Can track changes to data over time
- **Flexible**: Frontmatter for structured data, markdown for content
- **Tool support**: Works with standard markdown editors

### Why Skip Message Queue for Now?
- **Current scale**: 50 videos/day doesn't justify MQ complexity
- **Simple parallelization**: Stage-based already enables parallel runs
- **Operational overhead**: MQ requires broker, monitoring, etc.
- **Future option**: Can add async processing within stages first

**When to reconsider MQ:**
- Processing 500+ videos per day
- Need for real-time processing
- Multiple concurrent pipelines
- Distributed processing across machines

## 🔄 Future Enhancements

### Short-term (Next 1-2 months)
- Add more YouTube search configurations
- Experiment with different Claude models
- Add email notifications for daily reports
- Create web dashboard for analytics

### Medium-term (Next 3-6 months)
- Multi-language support (not just LATIN script)
- Video thumbnail analysis
- Category-specific happiness assessments
- Trend detection (rising/falling happiness)

### Long-term (6+ months)
- Machine learning for happiness prediction
- Custom fine-tuned models
- Real-time processing pipeline
- Public API for accessing data

## 📚 References

- **Newsparser project**: Patterns for stage-based processing, CLI design, configuration management
- **YouTube Data API v3**: Video search and metadata
- **Claude API**: Content assessment and enhancement
- **Click documentation**: CLI framework
- **Rich documentation**: Terminal UI components
- **Pydantic documentation**: Settings and data validation
- **Jinja2 documentation**: Template engine

## 🆘 Troubleshooting

### Common Issues

**1. Configuration validation fails**
- Check that all required fields are in config files
- Validate YAML syntax
- Ensure environment variables are set

**2. Stage fails midway**
- Check logs for specific error
- Files are saved with error status in frontmatter
- Can rerun just that stage after fixing issue

**3. No videos found**
- Check YouTube API quota
- Verify search configuration
- Check network connectivity

**4. Claude API errors**
- Verify API key is valid
- Check rate limits
- Review prompt format

### Debug Mode

Run with increased logging:
```bash
export LOG_LEVEL=DEBUG
happytube run-all --category Music
```

### Manual Stage Inspection

Check what happened in a stage:
```bash
# List files in stage
ls stages/fetch/2025-11-09/

# View a specific video file
cat stages/fetch/2025-11-09/video_abc123.md

# Check stage statistics
happytube status --date 2025-11-09
```
