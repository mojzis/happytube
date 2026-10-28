"""Trusted stage files for the player tests (selection, app, export)."""

from datetime import date
from pathlib import Path

from happytube.models.markdown import MarkdownFile
from happytube.trusted.stages import StageName, TrustedStage

DAY = date(2026, 10, 20)
PLAYER_BARE = "/player"
PLAYER = PLAYER_BARE + "/"
PLAYER_JSON = PLAYER + "videos.json"


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
        "suitable": True,
    } | over


def write(stages: Path, stage: StageName, n: int, fm: dict, day: date = DAY) -> Path:
    return TrustedStage(stage, stages).write(day, vid(n), MarkdownFile(fm, "body"))


def write_shown(stages: Path, slug: str, n: int = 1, text="Calm giraffes.") -> None:
    """Assess + enhance files of a suitable, enhanced video of ``slug``."""
    fm = assess_fm(n, channel_slug=slug)
    write(stages, "assess", n, fm)
    write(stages, "enhance", n, fm | {"enhanced_description": text})
