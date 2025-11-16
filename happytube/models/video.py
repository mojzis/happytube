"""Video model with analytics export capabilities."""

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import BaseModel, Field


class Video(BaseModel):
    """Video model with analytics export capabilities.

    This model represents a YouTube video with various metadata fields
    that are populated as the video moves through different processing stages.
    """

    # Core fields (populated during fetch)
    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    channel: str = Field(..., description="Channel name/title")
    category: Optional[str] = Field(None, description="Video category")
    duration: Optional[int] = Field(None, description="Video duration in seconds")
    fetched_at: datetime = Field(..., description="When the video was fetched")
    stage: str = Field(..., description="Current processing stage")
    script_type: Optional[str] = Field(None, description="Script type (e.g., LATIN)")

    # Additional metadata fields
    channel_id: Optional[str] = Field(None, description="YouTube channel ID")
    published_at: Optional[str] = Field(None, description="When video was published")

    # Assessment fields (populated during assess stage)
    happiness_score: Optional[int] = Field(
        None, ge=1, le=5, description="Happiness score (1-5)"
    )
    happiness_reasoning: Optional[str] = Field(
        None, description="Reasoning for happiness score"
    )
    assessed_at: Optional[datetime] = Field(None, description="When assessed")
    prompt_version: Optional[str] = Field(None, description="Prompt version used")

    # Enhancement fields (populated during enhance stage)
    enhanced_description: Optional[str] = Field(
        None, description="Enhanced video description"
    )
    enhanced_at: Optional[datetime] = Field(None, description="When enhanced")

    @classmethod
    def from_frontmatter(cls, frontmatter: dict) -> "Video":
        """Create Video from markdown frontmatter.

        Args:
            frontmatter: Dictionary containing video metadata from markdown file

        Returns:
            Video instance populated from frontmatter data
        """
        return cls.model_validate(frontmatter)

    def to_pandas_dict(self) -> dict:
        """Convert to dict suitable for pandas DataFrame.

        Returns:
            Dictionary representation of the video
        """
        return self.model_dump()

    @classmethod
    def df_from_stage_dir(cls, stage_name: str, days_back: int = 7) -> pd.DataFrame:
        """Load videos from stage directory into DataFrame.

        Args:
            stage_name: Name of the stage (fetch, assess, enhance)
            days_back: Number of days to look back from today

        Returns:
            DataFrame containing all videos from the specified stage and date range
        """
        from happytube.models.markdown import MarkdownFile

        base_path = Path("stages") / stage_name
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back - 1)

        all_videos = []
        current_date = start_date

        while current_date <= end_date:
            date_dir = base_path / current_date.strftime("%Y-%m-%d")
            if date_dir.exists():
                for md_file_path in date_dir.glob("video_*.md"):
                    try:
                        md_file = MarkdownFile.load(md_file_path)
                        video = cls.from_frontmatter(md_file.frontmatter)
                        all_videos.append(video.to_pandas_dict())
                    except Exception:
                        # Skip files that can't be parsed
                        pass
            current_date += timedelta(days=1)

        return pd.DataFrame(all_videos) if all_videos else pd.DataFrame()

    @classmethod
    def to_parquet(cls, df: pd.DataFrame, output_path: Path) -> None:
        """Export DataFrame to Parquet format.

        Args:
            df: DataFrame to export
            output_path: Path where the parquet file should be saved
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, engine="pyarrow", compression="snappy", index=False)
