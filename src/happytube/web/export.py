"""
Export HappyTube videos to static JSON for GitHub Pages deployment.

This script processes video data from the HappyTube pipeline and exports
it to a static JSON file that can be served from GitHub Pages or other
static hosting services.
"""

import json
import logging
from pathlib import Path
from typing import Any

from happytube.paths import LEGACY_FETCHED_DIR

logger = logging.getLogger(__name__)


def extract_video_info(item: dict) -> dict | None:
    """Extract video information from YouTube API response."""
    try:
        # Handle both search results and video details format
        if "id" in item:
            video_id = (
                item["id"].get("videoId")
                if isinstance(item["id"], dict)
                else item["id"]
            )
        else:
            return None

        snippet = item.get("snippet", {})

        return {
            "video_id": video_id,
            "title": snippet.get("title", "Unknown Title"),
            "description": snippet.get("description", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "published_at": snippet.get("publishedAt", ""),
        }
    except Exception as e:
        logger.warning("Error extracting video info: %s", e)
        return None


def load_videos_from_data_dir(data_dir: Path) -> list[dict[str, Any]]:
    """
    Load video data from the HappyTube data directory.

    Args:
        data_dir: Path to the data/fetched directory

    Returns:
        List of video dictionaries
    """
    videos = []
    seen_ids = set()

    if not data_dir.exists():
        # Debug: the server calls this per request and data/fetched has no writer.
        logger.debug("Data directory not found: %s", data_dir)
        return videos

    # Look for JSON files in the data directory
    video_files = list(data_dir.glob("**/*.json"))
    logger.info("Found %d JSON files to process", len(video_files))

    for video_file in video_files:
        try:
            with video_file.open() as f:
                data = json.load(f)

                # Handle both list and single item formats
                items = data if isinstance(data, list) else [data]

                for item in items:
                    video_info = extract_video_info(item)
                    if video_info and video_info["video_id"] not in seen_ids:
                        videos.append(video_info)
                        seen_ids.add(video_info["video_id"])

        except Exception as e:
            logger.warning("Error loading %s: %s", video_file, e)

    logger.info("Loaded %d unique videos", len(videos))
    return videos


def export_to_static(output_path: Path, data_dir: Path | None = None) -> None:
    """
    Export videos to a static JSON file for deployment.

    Args:
        output_path: Path where the videos.json file should be written
        data_dir: Path to the data/fetched directory (auto-detected if None)
    """
    # Auto-detect data directory if not provided
    if data_dir is None:
        data_dir = LEGACY_FETCHED_DIR

    # Load videos
    videos = load_videos_from_data_dir(data_dir)

    if not videos:
        logger.warning("No videos found to export!")
        logger.info(
            "No video JSON found under %s (legacy data/fetched layout)", data_dir
        )
        # Create empty file for consistency
        videos = []

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to JSON file
    with output_path.open("w") as f:
        json.dump(videos, f, indent=2)

    logger.info("Exported %d videos to %s", len(videos), output_path)


def main():
    """Main export function - run this to generate static build."""
    logging.basicConfig(level=logging.INFO)
    # Determine paths
    script_dir = Path(__file__).parent
    output_file = script_dir / "static" / "videos.json"

    logger.info("Starting HappyTube static export...")
    export_to_static(output_file)
    logger.info("Export complete!")
    logger.info("Static files ready for deployment in: %s", script_dir / "static")


if __name__ == "__main__":
    main()
