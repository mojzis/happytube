"""The video spot-check queue and agreement (decision 0011), shared by the review
UI (``/videos``) and ``happytube videos``.

Every assessed trusted video is in the queue, in three sections: unreviewed
videos the player shows now first (a false positive is what hurts her), then the
other unreviewed ones (agent misses, for tuning the rubric), then the reviewed
ones. "Reviewed" means a human review: agent reviews never count. Whether a
video is shown is the player's own rule (``select_videos``), so the queue and
the player can never disagree about it.

Pure over stage records, channel statuses and review states; ``load_spot_checks``
does the reading. A review directory without an assess file (an orphan) is not in
the queue.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import AwareDatetime, Field

from happytube.channels.models import Status
from happytube.channels.store import ChannelStore
from happytube.trusted.player import (
    Assessed,
    StageRecord,
    channel_statuses,
    enhanced_descriptions,
    latest_per_video,
    parse_assessed,
    read_stage,
    select_videos,
)
from happytube.trusted.stages import TrustedStage, is_video_id
from happytube.trusted.video_reviews import (
    NO_REVIEWS,
    Agreement,
    ReviewState,
    VideoNotFoundError,
    VideoReview,
    VideoReviewStore,
    agreement,
    hidden_ids,
)

Section = Literal["shown", "unreviewed", "reviewed"]
SECTIONS: tuple[str, ...] = get_args(Section)
# What ``videos list --section`` and the queue filter accept.
SECTION_FILTERS: tuple[str, ...] = (*SECTIONS, "disagree")


class SpotAssess(Assessed):
    """The assess-file fields a spot-check shows and snapshots."""

    calm: int
    happy: int
    flags: list[str] = Field(default_factory=list)
    note: str = ""
    rubric_version: int = Field(ge=1)
    assessed_at: AwareDatetime


def original_description(body: str, title: str) -> str:
    """The assess file's body without the ``# <title>`` heading fetch puts on it."""
    heading = f"# {title}"
    text = body.strip()
    return text.removeprefix(heading).strip() if text.startswith(heading) else text


@dataclass(frozen=True)
class SpotVideo:
    """One assessed video with what the player does with it and its reviews."""

    assess: SpotAssess
    path: Path
    description: str
    enhanced: str | None
    shown: bool
    state: ReviewState

    @property
    def video_id(self) -> str:
        return self.assess.video_id

    @property
    def latest(self) -> VideoReview | None:
        """The deciding (latest human) review, ``None`` if unreadable."""
        return None if self.state.error else self.state.latest_human

    @property
    def section(self) -> Section:
        if self.state.error is not None or self.latest is not None:
            return "reviewed"
        return "shown" if self.shown else "unreviewed"

    @property
    def disagrees(self) -> bool:
        return self.latest is not None and self.latest.disagrees

    @property
    def assess_changed(self) -> bool:
        """The agent's call was redone since the deciding review was given."""
        latest = self.latest
        return latest is not None and (
            latest.assessed_at != self.assess.assessed_at
            or latest.agent_suitable != self.assess.suitable
            or latest.rubric_version != self.assess.rubric_version
        )

    def summary_dict(self) -> dict[str, Any]:
        a = self.assess
        reviews = self.state.reviews
        humans = sum(1 for r in reviews if r.role == "human")
        return {
            "video_id": a.video_id,
            "title": a.title,
            "channel_slug": a.channel_slug,
            "channel_name": a.channel_name,
            "published_at": a.model_dump(mode="json")["published_at"],
            "duration_s": a.duration_s,
            "agent_suitable": a.suitable,
            "calm": a.calm,
            "happy": a.happy,
            "flags": list(a.flags),
            "shown": self.shown,
            "section": self.section,
            "verdict": self.latest.verdict if self.latest else None,
            "disagrees": self.disagrees,
            "assess_changed": self.assess_changed,
            "human_review_count": humans,
            "agent_review_count": len(reviews) - humans,
            "review_error": self.state.error,
        }

    def detail_dict(self) -> dict[str, Any]:
        """``summary_dict`` plus the whole agent call, both descriptions and every
        review (oldest first)."""
        return {
            **self.summary_dict(),
            "assess": self.assess.model_dump(mode="json"),
            "assess_path": str(self.path),
            "description": self.description,
            "enhanced_description": self.enhanced,
            "reviews": [r.model_dump(mode="json") for r in self.state.reviews],
        }


def spot_videos(
    assess: list[StageRecord],
    enhance: list[StageRecord],
    statuses: Mapping[str, Status],
    states: Mapping[str, ReviewState],
) -> list[SpotVideo]:
    """Every readable assessed video (latest copy per id), newest published
    first. An assess file the player cannot read is skipped with its warning."""
    shown = {
        v.video_id for v in select_videos(assess, enhance, statuses, hidden_ids(states))
    }
    descriptions = enhanced_descriptions(enhance)
    videos = []
    for video_id, record in latest_per_video(assess).items():
        parsed = parse_assessed(record, SpotAssess)
        if parsed is None:
            continue
        videos.append(
            SpotVideo(
                assess=parsed,
                path=record.path,
                description=original_description(record.body, parsed.title),
                enhanced=descriptions.get(video_id),
                shown=video_id in shown,
                state=states.get(video_id, NO_REVIEWS),
            )
        )
    return _newest_first(videos)


def _newest_first(videos: Iterable[SpotVideo]) -> list[SpotVideo]:
    ordered = sorted(videos, key=lambda v: v.video_id)
    return sorted(ordered, key=lambda v: v.assess.published_at, reverse=True)


def _reviewed_key(video: SpotVideo) -> tuple[int, int, float]:
    """Unreadable first, then disagreements, then the latest review newest first."""
    latest = video.latest
    when = latest.created_at.timestamp() if latest else 0.0
    return (0 if video.state.error else 1, 0 if video.disagrees else 1, -when)


def sections(videos: list[SpotVideo]) -> dict[str, list[SpotVideo]]:
    """The queue: shown-and-unreviewed, other unreviewed (both newest published
    first, as given), reviewed (see ``_reviewed_key``)."""
    split: dict[str, list[SpotVideo]] = {"shown": [], "unreviewed": []}
    for video in videos:
        if video.section != "reviewed":
            split[video.section].append(video)
    split["reviewed"] = sorted(
        (v for v in videos if v.section == "reviewed"), key=_reviewed_key
    )
    return split


def in_section(videos: list[SpotVideo], name: str) -> list[SpotVideo]:
    """One section of the queue in its order; ``disagree`` is the reviewed videos
    whose latest human verdict goes against the agent's call it was shown."""
    if name == "disagree":
        return [v for v in sections(videos)["reviewed"] if v.disagrees]
    return sections(videos)[name]


def queue_agreement(videos: list[SpotVideo]) -> Agreement:
    """Agreement over the queue's videos (orphan reviews never count)."""
    return agreement(v.state for v in videos)


def find(videos: list[SpotVideo], video_id: str) -> SpotVideo | None:
    return next((v for v in videos if v.video_id == video_id), None)


def new_review(  # noqa: PLR0913 - one parameter per review field
    video: SpotVideo,
    *,
    reviewer: str,
    role: str,
    verdict: str,
    flags: Iterable[str],
    watched: str,
    notes: str | None,
) -> VideoReview:
    """A review of ``video`` with the snapshot of the agent's current call;
    ``ValidationError`` on bad input."""
    return VideoReview.model_validate(
        {
            "reviewer": reviewer,
            "role": role,
            "verdict": verdict,
            "flags": list(flags),
            "watched": watched,
            "notes": notes,
            "agent_suitable": video.assess.suitable,
            "rubric_version": video.assess.rubric_version,
            "assessed_at": video.assess.assessed_at,
        }
    )


def load_spot_checks(
    stages_dir: Path, channels: ChannelStore, reviews: VideoReviewStore
) -> list[SpotVideo]:
    """The queue's videos from ``<stages_dir>/trusted/``, the registry and the
    video reviews (a missing reviews dir raises ``VideoReviewsMissingError``)."""
    states = reviews.states()
    return spot_videos(
        read_stage(TrustedStage("assess", stages_dir)),
        read_stage(TrustedStage("enhance", stages_dir)),
        channel_statuses(channels),
        states,
    )


def load_video(
    stages_dir: Path,
    channels: ChannelStore,
    reviews: VideoReviewStore,
    video_id: str,
) -> SpotVideo:
    """One queue video. An invalid id is refused before any file is read; an
    unknown or not-assessed one (an orphan review dir) is ``VideoNotFoundError``."""
    if not is_video_id(video_id):
        msg = f"No video '{video_id}' (not a valid video id)"
        raise VideoNotFoundError(msg)
    video = find(load_spot_checks(stages_dir, channels, reviews), video_id)
    if video is None:
        msg = f"No assessed video '{video_id}' in the trusted stages"
        raise VideoNotFoundError(msg)
    return video
