"""Integration tests for the HappyTube pipeline."""

from datetime import date

import pytest
import yaml
from pydantic import ValidationError

from happytube.config.settings import Settings
from happytube.models.markdown import MarkdownFile
from happytube.models.video import Video
from happytube.stages.base import Stage
from happytube.stages.fetch import FetchStage


def _save_assessed(assess_dir, videos: list[dict]) -> None:
    """Write an assessed-stage markdown file for each ``video_id``/score pair."""
    for video in videos:
        video_id = video["video_id"]
        frontmatter = {
            "video_id": video_id,
            "title": f"Video {video_id}",
            "channel": "Test",
            "stage": "assessed",
            "happiness_score": video["happiness_score"],
            "fetched_at": "2025-11-16T10:00:00Z",
            "assessed_at": "2025-11-16T11:00:00Z",
        }
        content = f"# Video {video_id}\n\nTest content"
        MarkdownFile(frontmatter, content).save(assess_dir / f"video_{video_id}.md")


class TestMarkdownFile:
    """Test MarkdownFile reading and writing."""

    def test_create_and_save(self, tmp_path):
        """Test creating and saving a markdown file with frontmatter."""
        frontmatter = {
            "video_id": "test123",
            "title": "Test Video",
            "stage": "fetched",
        }
        content = "# Test Video\n\nThis is a test description."

        md_file = MarkdownFile(frontmatter, content)
        output_path = tmp_path / "test.md"
        md_file.save(output_path)

        assert output_path.exists()

        # Read back and verify
        loaded = MarkdownFile.load(output_path)
        assert loaded.frontmatter["video_id"] == "test123"
        assert loaded.frontmatter["title"] == "Test Video"
        assert loaded.content == content

    def test_load_existing_file(self, tmp_path):
        """Test loading an existing markdown file."""
        file_content = """---
video_id: abc123
title: Happy Cat Video
stage: fetched
happiness_score: 4
---

# Happy Cat Video

A cute cat video that makes everyone smile."""

        test_file = tmp_path / "video.md"
        test_file.write_text(file_content, encoding="utf-8")

        md_file = MarkdownFile.load(test_file)

        assert md_file.frontmatter["video_id"] == "abc123"
        assert md_file.frontmatter["title"] == "Happy Cat Video"
        assert md_file.frontmatter["happiness_score"] == 4
        assert "cute cat video" in md_file.content

    def test_update_frontmatter(self, tmp_path):
        """Test updating frontmatter."""
        frontmatter = {"video_id": "test123", "stage": "fetched"}
        content = "Test content"

        md_file = MarkdownFile(frontmatter, content)
        md_file.update_frontmatter({"stage": "assessed", "happiness_score": 5})

        assert md_file.frontmatter["stage"] == "assessed"
        assert md_file.frontmatter["happiness_score"] == 5
        assert md_file.frontmatter["video_id"] == "test123"

    def test_to_string_format(self):
        """Test the string format of markdown files."""
        frontmatter = {"video_id": "test123", "title": "Test"}
        content = "Content here"

        md_file = MarkdownFile(frontmatter, content)
        string_output = md_file.to_string()

        assert string_output.startswith("---\n")
        assert "video_id: test123" in string_output
        assert "---\n\nContent here" in string_output

    def test_frontmatter_keeps_czech_readable(self, tmp_path):
        path = tmp_path / "v.md"
        MarkdownFile({"title": "Žirafy v zoo Dvůr Králové"}, "Text").save(path)
        assert "title: Žirafy v zoo Dvůr Králové" in path.read_text(encoding="utf-8")
        assert (
            MarkdownFile.load(path).frontmatter["title"] == "Žirafy v zoo Dvůr Králové"
        )


class TestSettings:
    """Test Settings configuration."""

    def test_settings_validation(self, monkeypatch):
        """Test that settings validates API keys."""
        monkeypatch.setenv("YTKEY", "test_youtube_key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_anthropic_key")

        settings = Settings()
        assert settings.youtube_api_key == "test_youtube_key"
        assert settings.anthropic_api_key == "test_anthropic_key"
        assert settings.has_all_credentials is True

    def test_log_level_validation(self, monkeypatch):
        """Test log level validation."""
        monkeypatch.setenv("YTKEY", "test_key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        settings = Settings()
        assert settings.log_level == "DEBUG"

    def test_invalid_log_level(self, monkeypatch):
        """Test that invalid log level raises error."""
        monkeypatch.setenv("YTKEY", "test_key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
        monkeypatch.setenv("LOG_LEVEL", "invalid")

        with pytest.raises(ValidationError):
            Settings()

    def test_missing_credentials(self, monkeypatch, tmp_path):
        """Test detection of missing credentials."""
        monkeypatch.chdir(tmp_path)  # a real .env in the repo root would fill them
        # Only set one key
        monkeypatch.setenv("YTKEY", "test_key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ValidationError):
            Settings()


class TestVideoModel:
    """Test Video model functionality."""

    def test_video_from_frontmatter(self):
        """Test creating Video from frontmatter."""
        frontmatter = {
            "video_id": "abc123",
            "title": "Test Video",
            "channel": "Test Channel",
            "fetched_at": "2025-11-16T10:00:00Z",
            "stage": "fetched",
        }

        video = Video.from_frontmatter(frontmatter)
        assert video.video_id == "abc123"
        assert video.title == "Test Video"
        assert video.stage == "fetched"

    def test_video_to_pandas_dict(self):
        """Test converting video to pandas dictionary."""
        frontmatter = {
            "video_id": "abc123",
            "title": "Test Video",
            "channel": "Test Channel",
            "fetched_at": "2025-11-16T10:00:00Z",
            "stage": "assessed",
            "happiness_score": 4,
        }

        video = Video.from_frontmatter(frontmatter)
        data_dict = video.to_pandas_dict()

        assert data_dict["video_id"] == "abc123"
        assert data_dict["happiness_score"] == 4
        assert "title" in data_dict


class TestStageBase:
    """Test Stage base class functionality."""

    def test_stage_directory_creation(self, tmp_path):
        """Test that stages create directories correctly."""

        # Create a simple test stage
        class TestStage(Stage):
            async def run(self, target_date: date):
                return {"test": "result"}

        stage = TestStage("test_stage", base_path=tmp_path)
        target_date = date(2025, 11, 16)

        stage_dir = stage.ensure_stage_dir(target_date)

        assert stage_dir.exists()
        assert stage_dir == tmp_path / "test_stage" / "2025-11-16"

    def test_get_stage_dir(self, tmp_path):
        """Test getting stage directory path."""

        class TestStage(Stage):
            async def run(self, target_date: date):
                return {}

        stage = TestStage("fetch", base_path=tmp_path)
        target_date = date(2025, 11, 16)

        stage_dir = stage.get_stage_dir(target_date)

        assert stage_dir == tmp_path / "fetch" / "2025-11-16"


class TestFetchStageIntegration:
    """Test FetchStage integration (without actual API calls)."""

    def test_fetch_stage_initialization(self):
        """Test FetchStage can be initialized."""
        config = {"regionCode": "US", "maxResults": 10}
        stage = FetchStage(youtube_config=config, max_videos=10)

        assert stage.youtube_config == config
        assert stage.max_videos == 10
        assert stage.stage_name == "fetch"

    def test_fetch_stage_directory_structure(self, tmp_path):
        """Test that fetch stage creates proper directory structure."""
        # Note: FetchStage uses default base_path from Stage class
        # This test verifies the directory naming pattern
        stage = FetchStage()
        target_date = date(2025, 11, 16)

        # Get the stage directory path (without creating it yet)
        stage_dir = stage.get_stage_dir(target_date)

        # Verify it follows the expected pattern
        expected_suffix = "stages/fetch/2025-11-16"
        assert str(stage_dir).endswith(expected_suffix)


class TestPipelineDataFlow:
    """Test data flow through the pipeline stages."""

    def test_fetch_to_assess_data_flow(self, tmp_path):
        """Test that data flows correctly from fetch to assess stage."""
        # Create stages directory
        stages_dir = tmp_path / "stages"
        fetch_dir = stages_dir / "fetch" / "2025-11-16"
        fetch_dir.mkdir(parents=True)

        # Create a mock fetched video
        frontmatter = {
            "video_id": "test123",
            "title": "Happy Test Video",
            "channel": "Test Channel",
            "fetched_at": "2025-11-16T10:00:00Z",
            "stage": "fetched",
        }
        content = "# Happy Test Video\n\nThis is a test video about happiness."

        md_file = MarkdownFile(frontmatter, content)
        md_file.save(fetch_dir / "video_test123.md")

        # Load it back as the assess stage would (raises if the file is missing)
        loaded = MarkdownFile.load(fetch_dir / "video_test123.md")
        assert loaded.frontmatter["video_id"] == "test123"
        assert loaded.frontmatter["stage"] == "fetched"

        # Simulate assess stage updating the file
        assess_dir = stages_dir / "assess" / "2025-11-16"
        assess_dir.mkdir(parents=True)

        loaded.update_frontmatter(
            {
                "stage": "assessed",
                "happiness_score": 4,
                "happiness_reasoning": "Test reasoning",
                "assessed_at": "2025-11-16T11:00:00Z",
            }
        )

        loaded.save(assess_dir / "video_test123.md")

        # Verify assessed file
        assessed = MarkdownFile.load(assess_dir / "video_test123.md")
        assert assessed.frontmatter["stage"] == "assessed"
        assert assessed.frontmatter["happiness_score"] == 4

    def test_assess_to_enhance_filtering(self, tmp_path):
        """Test that only happy videos flow to enhance stage."""
        # Create assess stage with multiple videos
        stages_dir = tmp_path / "stages"
        assess_dir = stages_dir / "assess" / "2025-11-16"
        assess_dir.mkdir(parents=True)

        # Create videos with different happiness scores
        videos = [
            {"video_id": "happy1", "happiness_score": 5},
            {"video_id": "happy2", "happiness_score": 4},
            {"video_id": "neutral", "happiness_score": 3},
            {"video_id": "sad", "happiness_score": 1},
        ]

        _save_assessed(assess_dir, videos)

        # Load videos that meet threshold (>= 3)
        threshold = 3
        loaded = [MarkdownFile.load(p) for p in assess_dir.glob("video_*.md")]
        eligible_videos = [
            m for m in loaded if m.frontmatter.get("happiness_score", 0) >= threshold
        ]

        # Should have 3 videos (scores 5, 4, 3)
        assert len(eligible_videos) == 3

        # Verify they're the right ones
        video_ids = [v.frontmatter["video_id"] for v in eligible_videos]
        assert sorted(video_ids) == ["happy1", "happy2", "neutral"]


class TestErrorHandling:
    """Test error handling across the pipeline."""

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading a file that doesn't exist raises error."""
        nonexistent = tmp_path / "doesnt_exist.md"

        with pytest.raises(FileNotFoundError):
            MarkdownFile.load(nonexistent)

    def test_malformed_frontmatter(self, tmp_path):
        """Test handling of malformed frontmatter."""
        # Create file with broken YAML
        broken_file = tmp_path / "broken.md"
        broken_file.write_text(
            """---
video_id: test
title: [unclosed bracket
---

Content"""
        )

        with pytest.raises(yaml.YAMLError):
            MarkdownFile.load(broken_file)

    def test_stage_with_empty_directory(self, tmp_path):
        """Test stage behavior with empty source directory."""
        # Create empty fetch directory
        fetch_dir = tmp_path / "stages" / "fetch" / "2025-11-16"
        fetch_dir.mkdir(parents=True)

        # Try to load videos (should return empty list, not error)
        videos = [MarkdownFile.load(p) for p in fetch_dir.glob("video_*.md")]

        assert len(videos) == 0
