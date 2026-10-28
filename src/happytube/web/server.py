"""
Simple Flask server for HappyTube video player.
Serves curated YouTube videos with controlled playback interface.
"""

import json
import logging

from flask import Flask, jsonify, render_template

from happytube.paths import LEGACY_FETCHED_DIR
from happytube.web.export import extract_video_info

app = Flask(__name__)
logger = logging.getLogger(__name__)


def load_video_data():
    """
    Load video data from the HappyTube data directory.
    Returns a list of videos with happiness scores >= 3.
    """
    # This is a placeholder - we'll need to adapt based on actual data structure
    # For now, return sample data structure
    videos = []

    # Try to load from data directory if it exists
    data_dir = LEGACY_FETCHED_DIR

    if data_dir.exists():
        # Look for video JSON files
        video_files = list(data_dir.glob("**/*.json"))

        for video_file in video_files:
            try:
                with video_file.open() as f:
                    data = json.load(f)
                    # Adapt to YouTube API response format
                    if isinstance(data, list):
                        for item in data:
                            video_info = extract_video_info(item)
                            if video_info:
                                videos.append(video_info)
            except Exception as e:
                logger.warning("Error loading %s: %s", video_file, e)

    return videos


@app.route("/")
def index():
    """Serve the main player page."""
    return render_template("player.html")


@app.route("/api/videos")
def get_videos():
    """API endpoint to get the list of curated videos."""
    videos = load_video_data()
    return jsonify(videos)


@app.route("/api/videos/<video_id>")
def get_video(video_id):
    """Get details for a specific video."""
    videos = load_video_data()
    video = next((v for v in videos if v["video_id"] == video_id), None)

    if video:
        return jsonify(video)
    else:
        return jsonify({"error": "Video not found"}), 404


def run_server(host="127.0.0.1", port=5000, debug=True):
    """Run the Flask development server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server()
