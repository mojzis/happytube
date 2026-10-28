"""Trusted stage files for the player tests (selection, app, export)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from happytube.models.markdown import MarkdownFile
from happytube.trusted.stages import StageName, TrustedStage
from happytube.trusted.video_reviews import VideoReview, VideoReviewStore

DAY = date(2026, 10, 20)
PLAYER_BARE = "/player"
PLAYER = PLAYER_BARE + "/"
PLAYER_JSON = PLAYER + "videos.json"
ASSESSED_AT = "2026-10-27T12:00:00Z"


def vid(n: int) -> str:
    return f"vid{n:08d}"


def assess_fm(n: int, **over) -> dict:
    """Assess frontmatter of a suitable video of channel ``zoo``."""
    return {
        "video_id": vid(n),
        "title": f"Title {n}",
        "channel_slug": "zoo",
        "channel_name": "Zoo",
        "published_at": f"2026-10-{10 + n:02d}T10:00:00Z",
        "duration_s": 600,
        "calm": 5,
        "happy": 4,
        "flags": [],
        "note": "Calm.",
        "suitable": True,
        "rubric_version": 1,
        "assessed_at": ASSESSED_AT,
    } | over


def write(stages: Path, stage: StageName, n: int, fm: dict, day: date = DAY) -> Path:
    body = f"# {fm.get('title')}\n\nOriginal text {n}."
    return TrustedStage(stage, stages).write(day, vid(n), MarkdownFile(fm, body))


def write_shown(stages: Path, slug: str, n: int = 1, text="Calm giraffes.") -> None:
    """Assess + enhance files of a suitable, enhanced video of ``slug``."""
    fm = assess_fm(n, channel_slug=slug)
    write(stages, "assess", n, fm)
    write(stages, "enhance", n, fm | {"enhanced_description": text})


def review_store(tmp_path: Path) -> VideoReviewStore:
    """An empty, existing ``video-reviews/`` under ``tmp_path``."""
    root = tmp_path / "video-reviews"
    root.mkdir(exist_ok=True)
    return VideoReviewStore(root)


T0 = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def vreview(verdict="suitable", role="human", minutes=0, agent=True, **over):
    fields = {
        "reviewer": "mojzis" if role == "human" else "claude",
        "role": role,
        "verdict": verdict,
        "watched": "full",
        "created_at": T0 + timedelta(minutes=minutes),
        "agent_suitable": agent,
        "rubric_version": 1,
        "assessed_at": T0 - timedelta(days=1),
    }
    return VideoReview.model_validate(fields | over)
