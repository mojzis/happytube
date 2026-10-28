"""Human spot-checks of trusted videos (decision 0011).

Layout::

    <root>/<video_id>/<YYYYMMDDTHHMMSSZ>-<reviewer slug>[-N].yaml

One append-only file per review, git-tracked like channel reviews (notes are
public). The video id is the directory, never a field, and is checked with
``is_video_id`` before any path is built. Each review snapshots the agent's call
it was compared with (``agent_suitable``, ``rubric_version``, ``assessed_at``),
since ``trusted assess --force`` can rescore a video later.

The verdict is derived like a channel's status (decision 0003): the latest
*human* review decides; agent reviews are stored but never count. A latest human
``unsuitable`` hides the video from the player; a review file that cannot be read
hides it too (it might be the one saying ``unsuitable``).
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_serializer,
    field_validator,
)

from happytube.channels.models import Role, _as_utc, _iso_z, _now
from happytube.paths import PROJECT_ROOT
from happytube.records import (
    StoreError,
    dump_yaml,
    load_records,
    review_stem,
    write_new,
)
from happytube.rubric import Flag
from happytube.trusted.stages import is_video_id

logger = logging.getLogger(__name__)

VideoVerdict = Literal["suitable", "unsuitable", "unsure"]
Watched = Literal["full", "part", "title"]
VIDEO_VERDICTS: tuple[str, ...] = get_args(VideoVerdict)
WATCHED: tuple[str, ...] = get_args(Watched)
VIDEO_REVIEWS_DIR = PROJECT_ROOT / "video-reviews"


class VideoReview(BaseModel):
    """One spot-check of a video by a human or an agent (append-only file)."""

    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1)
    role: Role
    verdict: VideoVerdict
    flags: list[Flag] = Field(default_factory=list)
    watched: Watched
    notes: str | None = None
    created_at: datetime = Field(default_factory=_now)
    # The agent's call this review was compared with, from the assess file.
    agent_suitable: StrictBool
    rubric_version: int = Field(ge=1)
    assessed_at: datetime

    @field_validator("flags")
    @classmethod
    def _dedupe_flags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("created_at", "assessed_at")
    @classmethod
    def _times_utc(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_serializer("created_at", "assessed_at")
    def _dump_times(self, value: datetime) -> str:
        return _iso_z(value)

    @property
    def disagrees(self) -> bool:
        """A decisive verdict against the agent's call it was compared with."""
        if self.verdict == "unsure":
            return False
        return (self.verdict == "suitable") != self.agent_suitable


class VideoNotFoundError(StoreError):
    """Not a video id, or no such video."""


class VideoReviewsMissingError(StoreError):
    """The video-reviews directory does not exist. Never read as "no reviews":
    a wrong path would silently show videos a human hid."""


def latest_human(reviews: list[VideoReview]) -> VideoReview | None:
    """The deciding review: the last human one in store order (by ``created_at``,
    ties in filename order)."""
    humans = [r for r in reviews if r.role == "human"]
    return humans[-1] if humans else None


@dataclass(frozen=True)
class ReviewState:
    """A video's reviews in store order, or why they could not be read."""

    reviews: list[VideoReview] = field(default_factory=list)
    error: str | None = None

    @property
    def latest_human(self) -> VideoReview | None:
        return latest_human(self.reviews)

    @property
    def hidden(self) -> bool:
        """Kept out of the player: unreadable, or the latest human said
        ``unsuitable``."""
        latest = self.latest_human
        return self.error is not None or (
            latest is not None and latest.verdict == "unsuitable"
        )


NO_REVIEWS = ReviewState()


class VideoReviewStore:
    """Read and write video reviews under a ``video-reviews/`` directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def require_root(self) -> None:
        if not self.root.is_dir():
            msg = (
                f"{self.root} not found: the video reviews directory must exist "
                "(check --video-reviews-dir / HAPPYTUBE_VIDEO_REVIEWS_DIR)"
            )
            raise VideoReviewsMissingError(msg)

    def _video_dir(self, video_id: str) -> Path:
        """Directory of ``video_id``; refuses anything that is not a video id, so
        ``../x`` can never reach outside the store."""
        if not is_video_id(video_id):
            msg = f"No video '{video_id}' (not a valid video id)"
            raise VideoNotFoundError(msg)
        return self.root / video_id

    def video_ids(self) -> list[str]:
        """Ids with a review directory, sorted; other entries are skipped with a
        warning naming them."""
        self.require_root()
        ids = []
        for path in self.root.iterdir():
            if not path.is_dir():
                continue
            if not is_video_id(path.name):
                logger.warning("Skipping %s: not a video id", path)
                continue
            ids.append(path.name)
        return sorted(ids)

    def reviews(self, video_id: str) -> list[VideoReview]:
        """Reviews of a video in write order; ``StoreError`` names a broken file."""
        self.require_root()
        return load_records(
            self._video_dir(video_id), VideoReview, lambda r: r.created_at
        )

    def add_review(self, video_id: str, review: VideoReview) -> Path:
        """Write a new review file; never overwrites. Returns its path."""
        directory = self._video_dir(video_id)
        self.require_root()
        return write_new(
            directory,
            review_stem(review.created_at, review.reviewer),
            dump_yaml(review.model_dump(mode="json")),
        )

    def states(self) -> dict[str, ReviewState]:
        """Every reviewed video's state. A video whose reviews cannot be read is
        kept with its error (so it is hidden), with a warning naming the file."""
        states = {}
        for video_id in self.video_ids():
            try:
                states[video_id] = ReviewState(self.reviews(video_id))
            except StoreError as e:
                logger.warning("Hiding video %s: %s", video_id, e)
                states[video_id] = ReviewState(error=str(e))
        return states


def hidden_ids(states: dict[str, ReviewState]) -> frozenset[str]:
    """Videos a human review keeps out of the player (selection rule 4)."""
    return frozenset(video_id for video_id, s in states.items() if s.hidden)


@dataclass(frozen=True)
class Agreement:
    """How often the latest human verdict agrees with the agent's call it was
    compared with (the review's snapshot, not today's assess file). Agent reviews
    and unreadable states never count."""

    counts: dict[tuple[str, bool], int]

    def count(self, verdict: str, agent_suitable: bool) -> int:
        return self.counts.get((verdict, agent_suitable), 0)

    @property
    def reviewed(self) -> int:
        return sum(self.counts.values())

    @property
    def agree(self) -> int:
        return self.count("suitable", True) + self.count("unsuitable", False)

    @property
    def disagree(self) -> int:
        return self.count("suitable", False) + self.count("unsuitable", True)

    @property
    def unsure(self) -> int:
        return self.count("unsure", True) + self.count("unsure", False)

    @property
    def rate(self) -> float | None:
        """Share of decisive verdicts agreeing with the agent; ``None`` without
        any."""
        decisive = self.agree + self.disagree
        return self.agree / decisive if decisive else None

    def as_dict(self) -> dict:
        return {
            "reviewed": self.reviewed,
            "agree": self.agree,
            "disagree": self.disagree,
            "unsure": self.unsure,
            "rate": self.rate,
            "matrix": {
                verdict: {
                    "agent_suitable": self.count(verdict, True),
                    "agent_unsuitable": self.count(verdict, False),
                }
                for verdict in VIDEO_VERDICTS
            },
        }


def agreement(states: Iterable[ReviewState]) -> Agreement:
    """Latest human verdict against the agent's ``suitable`` at review time."""
    counts: dict[tuple[str, bool], int] = {}
    for state in states:
        latest = state.latest_human
        if state.error is None and latest is not None:
            key = (latest.verdict, latest.agent_suitable)
            counts[key] = counts.get(key, 0) + 1
    return Agreement(counts)
