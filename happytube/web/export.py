"""
Export HappyTube videos to static JSON for GitHub Pages deployment.

This script processes video data from the HappyTube pipeline and exports
it to a static JSON file that can be served from GitHub Pages or other
static hosting services.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_video_info(item: dict) -> dict | None:
    """Extract video information from YouTube API response."""
    try:
        # Handle both search results and video details format
        if "id" in item:
            video_id = item["id"].get("videoId") if isinstance(item["id"], dict) else item["id"]
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
        logger.warning(f"Error extracting video info: {e}")
        return None


def load_videos_from_data_dir(data_dir: Path) -> List[Dict[str, Any]]:
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
        logger.warning(f"Data directory not found: {data_dir}")
        return videos

    # Look for JSON files in the data directory
    video_files = list(data_dir.glob("**/*.json"))
    logger.info(f"Found {len(video_files)} JSON files to process")

    for video_file in video_files:
        try:
            with open(video_file, "r") as f:
                data = json.load(f)

                # Handle both list and single item formats
                items = data if isinstance(data, list) else [data]

                for item in items:
                    video_info = extract_video_info(item)
                    if video_info and video_info["video_id"] not in seen_ids:
                        videos.append(video_info)
                        seen_ids.add(video_info["video_id"])

        except Exception as e:
            logger.warning(f"Error loading {video_file}: {e}")

    logger.info(f"Loaded {len(videos)} unique videos")
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
        # Assume script is run from project root
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "data" / "fetched"

    # Load videos
    videos = load_videos_from_data_dir(data_dir)

    if not videos:
        logger.warning("No videos found to export!")
        logger.info("Make sure to run 'poetry run python -m happytube.main' first to fetch videos")
        # Create empty file for consistency
        videos = []

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to JSON file
    with open(output_path, "w") as f:
        json.dump(videos, f, indent=2)

    logger.info(f"Exported {len(videos)} videos to {output_path}")


def main():
    """Main export function - run this to generate static build."""
    # Determine paths
    script_dir = Path(__file__).parent
    output_file = script_dir / "static" / "videos.json"

    logger.info("Starting HappyTube static export...")
    export_to_static(output_file)
    logger.info("Export complete!")
    logger.info(f"Static files ready for deployment in: {script_dir / 'static'}")


if __name__ == "__main__":
    main()
