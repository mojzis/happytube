"""Stage directories of the trusted pipeline: ``stages/trusted/<stage>/<date>/``.

One markdown file per video, ``<video_id>.md`` (YAML frontmatter + body), kept
apart from the legacy ``stages/fetch|assess|enhance`` so the two never mix.
"""

from datetime import date
from pathlib import Path
from typing import Any, Literal

from happytube.models.markdown import MarkdownFile
from happytube.stages.base import Stage

StageName = Literal["fetch", "assess", "enhance"]
SUFFIX = ".md"


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

    def video_ids(self) -> set[str]:
        """Ids of every video in this stage, on any date (a plain scan)."""
        if not self.stage_path.is_dir():
            return set()
        return {p.stem for p in self.stage_path.glob(f"*/*{SUFFIX}")}

    def write(self, target_date: date, video_id: str, md: MarkdownFile) -> Path:
        path = self.ensure_stage_dir(target_date) / f"{video_id}{SUFFIX}"
        md.save(path)
        return path


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
