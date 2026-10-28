"""Static ``videos.json`` for the GitHub Pages player (decision 0010).

``python -m happytube.web.export`` writes the same selection the local
``/player/videos.json`` serves (``happytube.trusted.player``), from
``stages/trusted/``, the channel registry and ``video-reviews/`` (a human
``unsuitable`` hides a video, decision 0011), into ``web/static/``. The deploy
workflow runs it from the repo root.

Fails loudly: a missing ``stages/trusted/``, registry or video-reviews directory
exits non-zero, so a wrong path in CI never deploys an empty player nor one
showing videos a human hid. Present but selecting
nothing is a warning and exit 0.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from happytube.channels.store import ChannelStore
from happytube.paths import PROJECT_ROOT
from happytube.trusted.player import player_videos, videos_json
from happytube.trusted.video_reviews import VIDEO_REVIEWS_DIR, VideoReviewStore

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class ExportError(Exception):
    """The export's input is not where it should be; nothing was written."""


def export_videos(
    stages_dir: Path, channels_dir: Path, output: Path, video_reviews_dir: Path
) -> int:
    """Write the selection to ``output``; the number of videos written."""
    for directory in (stages_dir / "trusted", channels_dir, video_reviews_dir):
        if not directory.is_dir():
            msg = f"{directory} not found (run from the repo root, or pass the path)"
            raise ExportError(msg)
    videos = player_videos(
        stages_dir, ChannelStore(channels_dir), VideoReviewStore(video_reviews_dir)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(videos_json(videos), ensure_ascii=False, indent=2)
    output.write_text(text + "\n", encoding="utf-8")
    if videos:
        logger.info("Exported %d videos to %s", len(videos), output)
    else:
        logger.warning(
            "Exported 0 videos to %s: nothing suitable and enhanced "
            "from an approved channel yet",
            output,
        )
    return len(videos)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m happytube.web.export", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "--stages-dir",
        type=Path,
        default=Path(os.environ.get("HAPPYTUBE_STAGES_DIR", "stages")),
        help="Stage data directory to read trusted/ from (env: "
        "HAPPYTUBE_STAGES_DIR; default: stages/ in the current directory). Only "
        "where the export reads; the trusted commands write stages/ in the cwd.",
    )
    parser.add_argument(
        "--channels-dir",
        type=Path,
        default=Path(
            os.environ.get("HAPPYTUBE_CHANNELS_DIR", PROJECT_ROOT / "channels")
        ),
        help="Registry directory (env: HAPPYTUBE_CHANNELS_DIR; default: channels/ "
        "at the repo root).",
    )
    parser.add_argument(
        "--video-reviews-dir",
        type=Path,
        default=Path(os.environ.get("HAPPYTUBE_VIDEO_REVIEWS_DIR", VIDEO_REVIEWS_DIR)),
        help="Video spot-check reviews (env: HAPPYTUBE_VIDEO_REVIEWS_DIR; "
        "default: video-reviews/ at the repo root). Must exist.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=STATIC_DIR / "videos.json",
        help="Where to write (default: the player's static dir).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parser().parse_args(argv)
    try:
        export_videos(
            args.stages_dir, args.channels_dir, args.output, args.video_reviews_dir
        )
    except ExportError as e:
        logger.error("Export failed: %s", e)  # noqa: TRY400 — message, no traceback
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
