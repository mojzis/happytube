"""
Simple Flask server for HappyTube video player.
Serves curated YouTube videos with controlled playback interface.
"""

from flask import Flask, jsonify, render_template

from happytube.paths import LEGACY_FETCHED_DIR
from happytube.web.export import load_videos_from_data_dir

app = Flask(__name__)


def load_video_data():
    """Load videos from the legacy data/fetched directory (same loader as export)."""
    return load_videos_from_data_dir(LEGACY_FETCHED_DIR)


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
