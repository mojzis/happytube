"""Stage directories of the trusted pipeline: ``stages/trusted/<stage>/<date>/``.

One markdown file per video, ``<video_id>.md`` (YAML frontmatter + body), kept
apart from the legacy ``stages/fetch|assess|enhance`` so the two never mix.
"""

import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from happytube.models.markdown import MarkdownFile
from happytube.stages.base import Stage

StageName = Literal["fetch", "assess", "enhance"]
SUFFIX = ".md"
# A YouTube video id; it becomes a file name, so nothing else is written.
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def is_video_id(value: str) -> bool:
    return VIDEO_ID.fullmatch(value) is not None


class TrustedStage(Stage):
    """Files of one trusted stage. The work itself is done by
    ``trusted.fetch`` / ``assess`` / ``enhance`` with explicit clients, so
    ``run`` (the legacy async entry point) is not used here."""

    def __init__(self, name: StageName, base_path: Path = Path("stages")):
        super().__init__(name, base_path / "trusted")

    async def run(self, target_date: date) -> dict[str, Any]:
        msg = "trusted stages run through happytube.trusted (fetch/assess/enhance)"
        raise NotImplementedError(msg)

    def files(self, target_date: date) -> list[Path]:
        """This date's video files, sorted by name."""
        directory = self.get_stage_dir(target_date)
        return sorted(directory.glob(f"*{SUFFIX}")) if directory.is_dir() else []

    def load(self, target_date: date) -> list[MarkdownFile]:
        return [MarkdownFile.load(p) for p in self.files(target_date)]

    def load_until(self, target_date: date) -> list[tuple[date, MarkdownFile]]:
        """Every file dated ``target_date`` or earlier, with its date, oldest
        date first (directories not named ``YYYY-MM-DD`` are ignored)."""
        if not self.stage_path.is_dir():
            return []
        days = []
        for directory in self.stage_path.iterdir():
            try:
                day = date.fromisoformat(directory.name)
            except ValueError:
                continue
            if directory.is_dir() and day <= target_date:
                days.append(day)
        return [(day, md) for day in sorted(days) for md in self.load(day)]

    def remove(self, video_id: str) -> list[Path]:
        """Delete this video's files on every date; the paths removed."""
        paths = sorted(self.stage_path.glob(f"*/{video_id}{SUFFIX}"))
        for path in paths:
            path.unlink()
        return paths

    def video_ids(self) -> set[str]:
        """Ids of every video in this stage, on any date (a plain scan)."""
        if not self.stage_path.is_dir():
            return set()
        return {p.stem for p in self.stage_path.glob(f"*/*{SUFFIX}")}

    def write(self, target_date: date, video_id: str, md: MarkdownFile) -> Path:
        path = self.ensure_stage_dir(target_date) / f"{video_id}{SUFFIX}"
        md.save(path)
        return path


Dated = tuple[date, MarkdownFile]


def pending(
    files: list[Dated], done: set[str], target_date: date, *, force: bool = False
) -> tuple[list[Dated], int]:
    """The files still to process, each video once, and how many of the target
    date's videos were skipped as already done.

    A video is pending when it is not ``done`` on any date, whichever date its
    file is under (so a video left over by a failed run is picked up by a later
    one). ``force`` redoes the target date's videos, nothing earlier.
    """
    redo = (
        {video_id_of(md) for day, md in files if day == target_date} if force else set()
    )
    todo: list[Dated] = []
    picked: set[str] = set()
    skipped = 0
    for day, md in files:
        video_id = video_id_of(md)
        if video_id in picked or (video_id in redo and day != target_date):
            continue
        if video_id in done and video_id not in redo:
            skipped += day == target_date
            continue
        picked.add(video_id)
        todo.append((day, md))
    return todo, skipped


def video_id_of(md: MarkdownFile) -> str:
    return str(md.frontmatter["video_id"])


def status_counts(target_date: date, base_path: Path = Path("stages")) -> dict:
    """Per channel and in total: videos fetched, assessed, suitable and enhanced
    on ``target_date``."""
    keys = ("fetched", "assessed", "suitable", "enhanced")
    per_channel: dict[str, dict[str, int]] = {}

    def bump(md: MarkdownFile, key: str) -> None:
        slug = str(md.frontmatter.get("channel_slug") or "?")
        counts = per_channel.setdefault(slug, dict.fromkeys(keys, 0))
        counts[key] += 1

    for md in TrustedStage("fetch", base_path).load(target_date):
        bump(md, "fetched")
    for md in TrustedStage("assess", base_path).load(target_date):
        bump(md, "assessed")
        if md.frontmatter.get("suitable") is True:
            bump(md, "suitable")
    for md in TrustedStage("enhance", base_path).load(target_date):
        bump(md, "enhanced")
    channels = [{"slug": s, **per_channel[s]} for s in sorted(per_channel)]
    totals = {k: sum(c[k] for c in per_channel.values()) for k in keys}
    return {"date": target_date.isoformat(), "channels": channels, "totals": totals}
