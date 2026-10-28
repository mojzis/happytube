"""What the player shows (decision 0010): one rule, used by the live
``/player/videos.json`` route and the static export alike.

A video is shown iff its assess file says ``suitable: true``, it has an enhance
file with a non-empty ``enhanced_description``, its channel is *currently*
``approved`` in the registry, and no human spot-check hides it (decision 0011:
the latest human verdict is ``unsuitable``, or a review file is unreadable).
Every field but the description comes from the assess file (an enhance file can
carry stale scores after a re-score). Newest ``published_at`` first.

Reading is forgiving per file and strict about the result: a file that cannot
be read or lacks a field is skipped with a warning naming it and never shown;
nothing here raises on bad data. A missing video-reviews directory is the one
exception: ``player_videos`` raises rather than show what a human may have hidden.
"""

import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import AwareDatetime, BaseModel, StrictBool, ValidationError

from happytube.channels.models import Status
from happytube.channels.store import ChannelStore, derive_status
from happytube.models.markdown import MarkdownFile
from happytube.records import StoreError
from happytube.trusted.stages import TrustedStage, is_video_id
from happytube.trusted.video_reviews import VideoReviewStore, hidden_ids

logger = logging.getLogger(__name__)


class PlayerVideo(BaseModel):
    """One record of ``videos.json`` (no scores: the player doesn't need them)."""

    video_id: str
    title: str
    channel_name: str
    channel_slug: str
    published_at: AwareDatetime
    duration_s: int | None
    description: str


class Assessed(BaseModel):
    """The assess-file fields the player reads; anything else is ignored."""

    video_id: str
    title: str
    channel_name: str
    channel_slug: str
    published_at: AwareDatetime
    duration_s: int | None = None
    suitable: StrictBool


@dataclass(frozen=True)
class StageRecord:
    """One stage file's frontmatter and body, its date dir and path (for
    warnings)."""

    day: date
    path: Path
    frontmatter: Mapping[str, Any]
    body: str = ""


def latest_per_video(records: list[StageRecord]) -> dict[str, StageRecord]:
    """By file name (= video id): the record in the latest date dir. That copy
    is the truth even if broken — an older one may be stale."""
    latest: dict[str, StageRecord] = {}
    for record in sorted(records, key=lambda r: (r.day, str(r.path))):
        latest[record.path.stem] = record
    return latest


def parse_assessed[A: Assessed](record: StageRecord, model: type[A]) -> A | None:
    """The record as ``model``, or ``None`` with a warning naming the file when a
    field is bad or missing or the id does not match the file."""
    try:
        assessed = model.model_validate(record.frontmatter)
    except ValidationError as e:
        fields = ", ".join(".".join(map(str, err["loc"])) for err in e.errors())
        logger.warning("Skipping %s: bad or missing %s", record.path, fields)
        return None
    if assessed.video_id != record.path.stem or not is_video_id(assessed.video_id):
        logger.warning("Skipping %s: video_id does not match the file", record.path)
        return None
    return assessed


def _description(record: StageRecord) -> str | None:
    value = record.frontmatter.get("enhanced_description")
    if not isinstance(value, str):
        if value is not None:
            logger.warning("Skipping %s: enhanced_description is not text", record.path)
        return None
    return value.strip() or None


def enhanced_descriptions(enhance: list[StageRecord]) -> dict[str, str | None]:
    """Per video id, its latest enhance file's non-empty description or ``None``."""
    return {
        video_id: _description(record)
        for video_id, record in latest_per_video(enhance).items()
    }


def eligible(
    assessed: Assessed | None, description: str | None, statuses: Mapping[str, Status]
) -> bool:
    """Rules 1 to 3: scored suitable, enhanced, channel approved now. Rule 4 (not
    hidden by a human) is ``select_videos``'s; the spot-check queue shares this
    predicate, so it and the player never disagree about what is shown."""
    return (
        assessed is not None
        and assessed.suitable is True
        and description is not None
        and statuses.get(assessed.channel_slug) == "approved"
    )


def select_videos(
    assess: list[StageRecord],
    enhance: list[StageRecord],
    statuses: Mapping[str, Status],
    hidden: Collection[str],
) -> list[PlayerVideo]:
    """The videos the player shows, newest ``published_at`` first (then by id,
    so the order is deterministic). ``statuses`` maps a channel slug to its
    current status; a slug not in it is not shown. ``hidden`` are the ids human
    spot-checks keep out (``video_reviews.hidden_ids``)."""
    descriptions = enhanced_descriptions(enhance)
    shown: list[PlayerVideo] = []
    for video_id, record in latest_per_video(assess).items():
        assessed = parse_assessed(record, Assessed)
        description = descriptions.get(video_id)
        if (
            video_id in hidden
            or assessed is None
            or description is None  # narrows for ty; eligible checks it too
            or not eligible(assessed, description, statuses)
        ):
            continue
        shown.append(
            PlayerVideo(
                **assessed.model_dump(exclude={"suitable"}), description=description
            )
        )
    shown.sort(key=lambda v: v.video_id)
    shown.sort(key=lambda v: v.published_at, reverse=True)
    return shown


def read_stage(stage: TrustedStage) -> list[StageRecord]:
    """Every file of a stage, on every date; an unreadable one is skipped with
    a warning naming it."""
    records = []
    for day in stage.days():
        for path in stage.files(day):
            try:
                md = MarkdownFile.load(path)
                frontmatter = md.frontmatter
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
                logger.warning("Skipping %s: cannot read it (%s)", path, e)
                continue
            if not isinstance(frontmatter, dict):
                logger.warning("Skipping %s: no frontmatter mapping", path)
                continue
            records.append(StageRecord(day, path, frontmatter, md.content))
    return records


def channel_statuses(store: ChannelStore) -> dict[str, Status]:
    """Current status per registered channel. A channel whose reviews cannot be
    read is left out (so its videos are hidden), with a warning."""
    statuses: dict[str, Status] = {}
    for slug in store.slugs():
        try:
            statuses[slug] = derive_status(store.reviews(slug))
        except StoreError as e:
            logger.warning("Hiding channel %s: %s", slug, e)
    return statuses


def player_videos(
    stages_dir: Path, store: ChannelStore, reviews: VideoReviewStore
) -> list[PlayerVideo]:
    """The selection from ``<stages_dir>/trusted/``, the registry and the video
    reviews; a missing reviews directory raises ``VideoReviewsMissingError``."""
    hidden = hidden_ids(reviews.states())
    return select_videos(
        read_stage(TrustedStage("assess", stages_dir)),
        read_stage(TrustedStage("enhance", stages_dir)),
        channel_statuses(store),
        hidden,
    )


def videos_json(videos: list[PlayerVideo]) -> list[dict[str, Any]]:
    """Plain JSON records (``published_at`` as ISO 8601 text)."""
    return [v.model_dump(mode="json") for v in videos]
