# Phase 2: Stage Implementation

**Timeline:** Day 3-4

## Overview

This phase implements the four concrete stage classes that form the processing pipeline. Each stage builds on the infrastructure from Phase 1 and adapts existing code from the prototype.

## Goals

- Implement FetchStage to retrieve videos from YouTube
- Implement AssessStage to score happiness using Claude
- Implement EnhanceStage to improve video descriptions
- Implement ReportStage to generate HTML reports
- Add robust error handling and status tracking
- Enable stage-level progress reporting

## Stage Pipeline Flow

```
FetchStage    → stages/fetch/YYYY-MM-DD/*.md
   ↓
AssessStage   → stages/assess/YYYY-MM-DD/*.md (+ happiness_score)
   ↓
EnhanceStage  → stages/enhance/YYYY-MM-DD/*.md (+ enhanced_description)
   ↓
ReportStage   → stages/report/YYYY-MM-DD.html + parquet exports
```

## Tasks

### 1. Implement FetchStage

**File:** `happytube/stages/fetch.py`

**Purpose:** Fetch videos from YouTube API and save as markdown files.

**Key Features:**
- Use existing `videos.py` Search class
- Convert DataFrame rows to markdown files
- Store video metadata in frontmatter
- Track fetch timestamps
- Handle API errors gracefully

**Implementation:**
```python
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from happytube.stages.base import Stage
from happytube.models.markdown import MarkdownFile
from happytube.videos import Search
from happytube.utils.logging import get_logger

logger = get_logger()

class FetchStage(Stage):
    """Fetches videos from YouTube and stores as markdown files."""

    def __init__(self, youtube_config: Dict[str, Any], max_videos: int = 50):
        super().__init__("fetch")
        self.youtube_config = youtube_config
        self.max_videos = max_videos

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Fetch videos and save as markdown files."""
        logger.info(f"[bold blue]🔍 Fetching videos for {target_date}[/bold blue]", extra={"markup": True})

        stage_dir = self.ensure_stage_dir(target_date)

        # Use existing videos.py Search class
        try:
            search = Search(**self.youtube_config)
            videos_df = search.get_df()

            if videos_df.empty:
                logger.warning("No videos found")
                return {
                    "new_videos": 0,
                    "date": target_date.strftime("%Y-%m-%d"),
                    "status": "no_videos_found"
                }

            # Limit to max_videos
            if len(videos_df) > self.max_videos:
                videos_df = videos_df.head(self.max_videos)

            saved_count = 0
            error_count = 0

            for idx, row in videos_df.iterrows():
                try:
                    # Create markdown file with frontmatter
                    frontmatter = {
                        "video_id": row["video_id"],
                        "title": row["title"],
                        "channel": row.get("channel", ""),
                        "category": row.get("category", ""),
                        "duration": row.get("duration"),
                        "fetched_at": datetime.utcnow().isoformat() + 'Z',
                        "stage": "fetched",
                        "script_type": row.get("script_type", ""),
                    }

                    content = f"# {row['title']}\n\n{row.get('description', '')}"

                    md_file = MarkdownFile(frontmatter, content)
                    output_path = stage_dir / f"video_{row['video_id']}.md"
                    md_file.save(output_path)
                    saved_count += 1

                except Exception as e:
                    logger.error(f"Error saving video {row.get('video_id', 'unknown')}: {e}")
                    error_count += 1

            logger.info(f"[green]✓ Saved {saved_count} videos to {stage_dir}[/green]", extra={"markup": True})

            if error_count > 0:
                logger.warning(f"Failed to save {error_count} videos")

            return {
                "new_videos": saved_count,
                "errors": error_count,
                "date": target_date.strftime("%Y-%m-%d"),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"[red]✗ FetchStage failed: {e}[/red]", extra={"markup": True})
            return {
                "new_videos": 0,
                "date": target_date.strftime("%Y-%m-%d"),
                "status": "failed",
                "error": str(e)
            }
```

### 2. Implement AssessStage

**File:** `happytube/stages/assess.py`

**Purpose:** Assess happiness scores for fetched videos using Claude API.

**Key Features:**
- Load videos from fetch stage
- Batch videos for efficient Claude API usage
- Parse CSV responses from Claude
- Update markdown files with happiness scores
- Track prompt version used

**Implementation:**
```python
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import io

from happytube.stages.base import Stage
from happytube.models.markdown import MarkdownFile
from happytube.claude import assess_happiness_csv
from happytube.utils.logging import get_logger

logger = get_logger()

class AssessStage(Stage):
    """Assesses happiness scores for videos using Claude API."""

    def __init__(self, prompt_config: Dict[str, Any], batch_size: int = 20):
        super().__init__("assess")
        self.prompt_config = prompt_config
        self.batch_size = batch_size

    def _load_fetched_videos(self, target_date: date) -> List[MarkdownFile]:
        """Load all fetched videos for the target date."""
        fetch_dir = Path("stages") / "fetch" / target_date.strftime("%Y-%m-%d")

        if not fetch_dir.exists():
            logger.warning(f"No fetch directory found for {target_date}")
            return []

        videos = []
        for md_path in fetch_dir.glob("*.md"):
            try:
                md_file = MarkdownFile.load(md_path)
                videos.append(md_file)
            except Exception as e:
                logger.error(f"Error loading {md_path}: {e}")

        return videos

    def _create_csv_for_batch(self, videos: List[MarkdownFile]) -> str:
        """Create CSV string from video batch."""
        rows = []
        for md_file in videos:
            fm = md_file.frontmatter
            rows.append({
                "video_id": fm["video_id"],
                "title": fm["title"],
                "description": md_file.content.replace("# " + fm["title"], "").strip(),
                "category": fm.get("category", ""),
            })

        df = pd.DataFrame(rows)
        return df.to_csv(index=False)

    def _parse_happiness_response(self, response_csv: str) -> pd.DataFrame:
        """Parse Claude's CSV response into DataFrame."""
        return pd.read_csv(io.StringIO(response_csv))

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Assess happiness for all fetched videos."""
        logger.info(f"[bold yellow]🎯 Assessing happiness for {target_date}[/bold yellow]", extra={"markup": True})

        stage_dir = self.ensure_stage_dir(target_date)
        videos = self._load_fetched_videos(target_date)

        if not videos:
            return {
                "assessed_videos": 0,
                "date": target_date.strftime("%Y-%m-%d"),
                "status": "no_videos_to_assess"
            }

        assessed_count = 0
        error_count = 0

        # Process in batches
        for i in range(0, len(videos), self.batch_size):
            batch = videos[i:i + self.batch_size]
            logger.info(f"Processing batch {i // self.batch_size + 1} ({len(batch)} videos)")

            try:
                # Create CSV for batch
                csv_input = self._create_csv_for_batch(batch)

                # Call Claude API (adapt existing function)
                response_csv = assess_happiness_csv(
                    csv_input,
                    model=self.prompt_config.get("model"),
                    max_tokens=self.prompt_config.get("max_tokens")
                )

                # Parse response
                happiness_df = self._parse_happiness_response(response_csv)

                # Update markdown files
                for md_file in batch:
                    video_id = md_file.frontmatter["video_id"]

                    # Find happiness score in response
                    happiness_row = happiness_df[happiness_df["video_id"] == video_id]

                    if not happiness_row.empty:
                        happiness_score = int(happiness_row.iloc[0]["happiness"])
                        reasoning = happiness_row.iloc[0].get("reasoning", "")

                        # Update frontmatter
                        md_file.update_frontmatter({
                            "stage": "assessed",
                            "happiness_score": happiness_score,
                            "happiness_reasoning": reasoning,
                            "assessed_at": datetime.utcnow().isoformat() + 'Z',
                            "prompt_version": self.prompt_config.get("version", "unknown")
                        })

                        # Save to assess stage
                        output_path = stage_dir / f"video_{video_id}.md"
                        md_file.save(output_path)
                        assessed_count += 1
                    else:
                        logger.warning(f"No happiness score found for video {video_id}")
                        error_count += 1

            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                error_count += len(batch)

        logger.info(f"[green]✓ Assessed {assessed_count} videos[/green]", extra={"markup": True})

        if error_count > 0:
            logger.warning(f"Failed to assess {error_count} videos")

        return {
            "assessed_videos": assessed_count,
            "errors": error_count,
            "date": target_date.strftime("%Y-%m-%d"),
            "status": "success"
        }
```

### 3. Implement EnhanceStage

**File:** `happytube/stages/enhance.py`

**Purpose:** Enhance descriptions for videos with high happiness scores.

**Key Features:**
- Load assessed videos
- Filter by happiness threshold
- Enhance descriptions using Claude
- Update markdown files with enhanced content
- Track enhancement timestamps

**Implementation:**
```python
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List

from happytube.stages.base import Stage
from happytube.models.markdown import MarkdownFile
from happytube.claude import enhance_description
from happytube.utils.logging import get_logger

logger = get_logger()

class EnhanceStage(Stage):
    """Enhances descriptions for happy videos using Claude API."""

    def __init__(self, prompt_config: Dict[str, Any], happiness_threshold: int = 3):
        super().__init__("enhance")
        self.prompt_config = prompt_config
        self.happiness_threshold = happiness_threshold

    def _load_assessed_videos(self, target_date: date) -> List[MarkdownFile]:
        """Load all assessed videos for the target date."""
        assess_dir = Path("stages") / "assess" / target_date.strftime("%Y-%m-%d")

        if not assess_dir.exists():
            logger.warning(f"No assess directory found for {target_date}")
            return []

        videos = []
        for md_path in assess_dir.glob("*.md"):
            try:
                md_file = MarkdownFile.load(md_path)

                # Filter by happiness threshold
                happiness_score = md_file.frontmatter.get("happiness_score")
                if happiness_score and happiness_score >= self.happiness_threshold:
                    videos.append(md_file)

            except Exception as e:
                logger.error(f"Error loading {md_path}: {e}")

        return videos

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Enhance descriptions for happy videos."""
        logger.info(f"[bold magenta]✨ Enhancing descriptions for {target_date}[/bold magenta]", extra={"markup": True})

        stage_dir = self.ensure_stage_dir(target_date)
        videos = self._load_assessed_videos(target_date)

        if not videos:
            return {
                "enhanced_videos": 0,
                "date": target_date.strftime("%Y-%m-%d"),
                "status": "no_videos_to_enhance"
            }

        logger.info(f"Found {len(videos)} videos with happiness >= {self.happiness_threshold}")

        enhanced_count = 0
        error_count = 0

        for md_file in videos:
            video_id = md_file.frontmatter["video_id"]
            title = md_file.frontmatter["title"]
            description = md_file.content.replace(f"# {title}", "").strip()

            try:
                # Call Claude API to enhance description
                enhanced_desc = enhance_description(
                    title=title,
                    description=description,
                    model=self.prompt_config.get("model"),
                    max_tokens=self.prompt_config.get("max_tokens")
                )

                # Update frontmatter and content
                md_file.update_frontmatter({
                    "stage": "enhanced",
                    "enhanced_at": datetime.utcnow().isoformat() + 'Z',
                })

                # Update content with enhanced description
                md_file.content = f"# {title}\n\n## Original Description\n\n{description}\n\n## Enhanced Description\n\n{enhanced_desc}"

                # Save to enhance stage
                output_path = stage_dir / f"video_{video_id}.md"
                md_file.save(output_path)
                enhanced_count += 1

            except Exception as e:
                logger.error(f"Error enhancing video {video_id}: {e}")
                error_count += 1

        logger.info(f"[green]✓ Enhanced {enhanced_count} videos[/green]", extra={"markup": True})

        if error_count > 0:
            logger.warning(f"Failed to enhance {error_count} videos")

        return {
            "enhanced_videos": enhanced_count,
            "errors": error_count,
            "date": target_date.strftime("%Y-%m-%d"),
            "status": "success"
        }
```

### 4. Implement ReportStage

**File:** `happytube/stages/report.py`

**Purpose:** Generate HTML reports and export analytics to Parquet.

**Key Features:**
- Load enhanced videos
- Generate HTML report using Jinja2
- Export to Parquet for analytics
- Calculate statistics

**Implementation:**
```python
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader

from happytube.stages.base import Stage
from happytube.models.markdown import MarkdownFile
from happytube.models.video import Video
from happytube.utils.logging import get_logger

logger = get_logger()

class ReportStage(Stage):
    """Generates daily HTML reports and exports analytics."""

    def __init__(self, template_dir: Path = Path("templates"), parquet_days_back: int = 7):
        super().__init__("report")
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.parquet_days_back = parquet_days_back

    def _load_enhanced_videos(self, target_date: date) -> List[Dict[str, Any]]:
        """Load all enhanced videos for the target date."""
        enhance_dir = Path("stages") / "enhance" / target_date.strftime("%Y-%m-%d")

        if not enhance_dir.exists():
            return []

        videos = []
        for md_path in enhance_dir.glob("*.md"):
            try:
                md_file = MarkdownFile.load(md_path)

                # Extract enhanced description from content
                content_parts = md_file.content.split("## Enhanced Description")
                enhanced_description = content_parts[1].strip() if len(content_parts) > 1 else ""

                video_data = md_file.frontmatter.copy()
                video_data["enhanced_description"] = enhanced_description
                videos.append(video_data)

            except Exception as e:
                logger.error(f"Error loading {md_path}: {e}")

        return sorted(videos, key=lambda v: v.get("happiness_score", 0), reverse=True)

    def _export_parquet(self, target_date: date) -> None:
        """Export stage data to Parquet for analytics."""
        for stage_name in ["fetch", "assess", "enhance"]:
            try:
                df = Video.df_from_stage_dir(stage_name, days_back=self.parquet_days_back)

                if not df.empty:
                    output_dir = Path("parquet") / stage_name / "by-run-date"
                    output_file = output_dir / f"{target_date.strftime('%Y-%m-%d')}_last_{self.parquet_days_back}_days.parquet"
                    Video.to_parquet(df, output_file)
                    logger.info(f"Exported {stage_name} data to {output_file}")

            except Exception as e:
                logger.warning(f"Error exporting {stage_name} to parquet: {e}")

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Generate report for the date."""
        logger.info(f"[bold cyan]📊 Generating report for {target_date}[/bold cyan]", extra={"markup": True})

        # Load enhanced videos
        videos = self._load_enhanced_videos(target_date)

        if not videos:
            return {
                "videos_reported": 0,
                "date": target_date.strftime("%Y-%m-%d"),
                "status": "no_videos_to_report"
            }

        # Calculate statistics
        avg_happiness = sum(v.get("happiness_score", 0) for v in videos) / len(videos)

        # Generate HTML report
        try:
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

            logger.info(f"[green]✓ Report saved to {report_path}[/green]", extra={"markup": True})

        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return {
                "videos_reported": 0,
                "date": target_date.strftime("%Y-%m-%d"),
                "status": "failed",
                "error": str(e)
            }

        # Export to parquet for analytics
        self._export_parquet(target_date)

        return {
            "videos_reported": len(videos),
            "avg_happiness": round(avg_happiness, 2),
            "report_path": str(report_path),
            "status": "success"
        }
```

### 5. Implement Video Model (for Analytics)

**File:** `happytube/models/video.py`

**Purpose:** Pydantic model for video data with analytics export capabilities.

**Implementation:**
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
                    try:
                        md_file = MarkdownFile.load(md_file_path)
                        video = cls.from_frontmatter(md_file.frontmatter)
                        all_videos.append(video.to_pandas_dict())
                    except Exception:
                        pass  # Skip invalid files

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

**Dependencies to add:**
```bash
poetry add pyarrow  # For parquet support
poetry add jinja2   # For HTML templating
```

### 6. Adapt Existing Claude Functions

**File:** `happytube/claude.py` (update existing file)

Add these wrapper functions to work with the new architecture:

```python
def assess_happiness_csv(csv_content: str, model: str = "claude-3-opus-20240229", max_tokens: int = 4096) -> str:
    """
    Assess happiness for videos in CSV format.
    Returns CSV string with video_id, happiness, reasoning.
    """
    # Use existing implementation, ensure it returns CSV string
    # This should already exist in the codebase
    pass

def enhance_description(title: str, description: str, model: str = "claude-3-opus-20240229", max_tokens: int = 2048) -> str:
    """
    Enhance a video description.
    Returns enhanced description as string.
    """
    # Implement using existing Claude API code
    pass
```

## Testing Phase 2

After completing this phase, test each stage:

```bash
# Test FetchStage
poetry run python -c "
import asyncio
from datetime import date
from happytube.stages.fetch import FetchStage
from happytube.config.config_manager import ConfigManager

cm = ConfigManager()
youtube_config = cm.load_base_config('youtube')['searches']['music_search']['params']
stage = FetchStage(youtube_config, max_videos=5)
result = asyncio.run(stage.run(date.today()))
print(result)
"

# Test AssessStage (after fetch)
poetry run python -c "
import asyncio
from datetime import date
from happytube.stages.assess import AssessStage
from happytube.config.config_manager import ConfigManager

cm = ConfigManager()
prompt_config = cm.load_base_config('prompts')['prompts']['happiness_v2']
stage = AssessStage(prompt_config)
result = asyncio.run(stage.run(date.today()))
print(result)
"

# Test EnhanceStage (after assess)
poetry run python -c "
import asyncio
from datetime import date
from happytube.stages.enhance import EnhanceStage
from happytube.config.config_manager import ConfigManager

cm = ConfigManager()
prompt_config = cm.load_base_config('prompts')['prompts']['enhance_description_v1']
stage = EnhanceStage(prompt_config, happiness_threshold=3)
result = asyncio.run(stage.run(date.today()))
print(result)
"

# Test ReportStage (after enhance)
poetry run python -c "
import asyncio
from datetime import date
from happytube.stages.report import ReportStage

stage = ReportStage()
result = asyncio.run(stage.run(date.today()))
print(result)
"
```

## Dependencies Summary

Add these dependencies in this phase:

```bash
poetry add pyarrow
poetry add jinja2
```

## Success Criteria

- ✅ FetchStage retrieves videos and saves to markdown
- ✅ AssessStage scores happiness and updates files
- ✅ EnhanceStage improves descriptions for happy videos
- ✅ ReportStage generates HTML reports
- ✅ All stages handle errors gracefully
- ✅ Progress logging works with Rich output
- ✅ Parquet exports function correctly
- ✅ Can run full pipeline: fetch → assess → enhance → report

## Next Phase

Phase 3 will create the CLI interface using Typer to make these stages easily accessible from the command line.
