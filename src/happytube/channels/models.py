"""Pydantic models for registry channels and review records."""

from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from happytube.claude import Usage
from happytube.rubric import Flag, Score
from happytube.utils import as_utc, iso_z, utc_now

Kind = Literal["broadcaster", "zoo", "aquarium", "park", "museum", "other"]
Language = Literal["cs", "en"]
Role = Literal["human", "agent"]
Verdict = Literal["approve", "reject", "unsure"]
Status = Literal["candidate", "approved", "rejected"]

KINDS: tuple[str, ...] = get_args(Kind)
LANGUAGES: tuple[str, ...] = get_args(Language)
ROLES: tuple[str, ...] = get_args(Role)
VERDICTS: tuple[str, ...] = get_args(Verdict)
STATUSES: tuple[str, ...] = get_args(Status)

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
HANDLE_PATTERN = r"^@[\w.\-]+$"
CHANNEL_ID_PATTERN = r"^UC[\w\-]+$"


class Channel(BaseModel):
    """A YouTube channel in the registry (``channels/<slug>/channel.yaml``).

    Status is not stored here: it is derived from the channel's review records.
    Unknown keys are refused so that a typo in a hand-edited file surfaces.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1)
    kind: Kind
    languages: list[Language] = Field(min_length=1)
    handle: str | None = Field(default=None, pattern=HANDLE_PATTERN)
    channel_id: str | None = Field(default=None, pattern=CHANNEL_ID_PATTERN)
    url: str | None = None
    added_by: str = Field(min_length=1)
    added_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None

    @field_validator("languages")
    @classmethod
    def _dedupe_languages(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("added_at")
    @classmethod
    def _added_at_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_serializer("added_at")
    def _dump_added_at(self, value: datetime) -> str:
        return iso_z(value)


class Review(BaseModel):
    """One review of a channel by a human or an agent (append-only file)."""

    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1)
    role: Role
    verdict: Verdict
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_serializer("created_at")
    def _dump_created_at(self, value: datetime) -> str:
        return iso_z(value)


EvidenceMethod = Literal["api", "rss"]
ShortsSource = Literal["uush", "duration"]


class EvidenceVideo(BaseModel):
    """One recent upload in an evidence snapshot."""

    model_config = ConfigDict(extra="forbid")

    video_id: str = Field(min_length=1)
    title: str
    published_at: datetime
    duration_s: int | None = Field(default=None, ge=0)
    is_short: bool
    description: str = ""
    default_language: str | None = None
    made_for_kids: bool | None = None

    @field_validator("published_at")
    @classmethod
    def _published_at_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_serializer("published_at")
    def _dump_published_at(self, value: datetime) -> str:
        return iso_z(value)


class Evidence(BaseModel):
    """A snapshot of a channel's stats and recent uploads (append-only file)."""

    model_config = ConfigDict(extra="forbid")

    fetched_at: datetime = Field(default_factory=utc_now)
    method: EvidenceMethod
    channel_id: str = Field(pattern=CHANNEL_ID_PATTERN)
    title: str
    custom_url: str | None = None
    description: str = ""
    country: str | None = None
    published_at: datetime | None = None
    subscriber_count: int | None = Field(default=None, ge=0)
    view_count: int | None = Field(default=None, ge=0)
    video_count: int | None = Field(default=None, ge=0)
    uploads_playlist_id: str | None = None
    # How ``is_short`` was decided: membership of the channel's ``UUSH…`` Shorts
    # playlist, or the duration fallback (the default, so older snapshots load).
    shorts_source: ShortsSource = "duration"
    videos: list[EvidenceVideo] = Field(default_factory=list)

    @property
    def shorts_count(self) -> int:
        return sum(1 for v in self.videos if v.is_short)

    @field_validator("fetched_at", "published_at")
    @classmethod
    def _times_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else as_utc(value)

    @field_serializer("fetched_at", "published_at")
    def _dump_times(self, value: datetime | None) -> str | None:
        return None if value is None else iso_z(value)


ChannelFlag = Literal["unresolved", "inactive", "mostly_shorts", "identity_doubt"]
IdentityMatch = Literal["yes", "no", "unsure"]


# Tokens one vet call used; the shared ``happytube.claude.Usage`` (vet YAML
# unchanged: the same two fields).
VetUsage = Usage


class VetVideo(BaseModel):
    """One scored long-form video in a vet report."""

    model_config = ConfigDict(extra="forbid")

    video_id: str = Field(min_length=1)
    title: str
    calm: Score
    happy: Score
    flags: list[Flag] = Field(default_factory=list)
    suitable: bool
    note: str = ""


class VetReport(BaseModel):
    """Frontmatter of an agent vet report (``vet/<stamp>.md``, append-only).

    ``verdict`` is final (after the verdict rule); ``model_verdict`` is what the
    model said. ``evidence_at`` is the ``fetched_at`` of the snapshot judged.
    """

    model_config = ConfigDict(extra="forbid")

    vetted_at: datetime = Field(default_factory=utc_now)
    model: str = Field(min_length=1)
    prompt_version: int = Field(ge=1)
    evidence_at: datetime
    verdict: Verdict
    model_verdict: Verdict
    flags: list[ChannelFlag] = Field(default_factory=list)
    identity_match: IdentityMatch
    identity_note: str = ""
    channel_calm: Score
    channel_happy: Score
    summary: str = ""
    concerns: list[str] = Field(default_factory=list)
    usage: VetUsage
    videos: list[VetVideo] = Field(default_factory=list)
    shorts_skipped: int = Field(default=0, ge=0)

    @property
    def suitable_count(self) -> int:
        return sum(1 for v in self.videos if v.suitable)

    @field_validator("vetted_at", "evidence_at")
    @classmethod
    def _times_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_serializer("vetted_at", "evidence_at")
    def _dump_times(self, value: datetime) -> str:
        return iso_z(value)
