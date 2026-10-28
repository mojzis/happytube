"""Pydantic models for registry channels and review records."""

import re
import unicodedata
from datetime import UTC, datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

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


def _as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC and convert an aware one to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_z(value: datetime) -> str:
    """Format a UTC datetime as ISO-8601 with a trailing ``Z``."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _now() -> datetime:
    return datetime.now(UTC)


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
    added_at: datetime = Field(default_factory=_now)
    notes: str | None = None

    @field_validator("languages")
    @classmethod
    def _dedupe_languages(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("added_at")
    @classmethod
    def _added_at_utc(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_serializer("added_at")
    def _dump_added_at(self, value: datetime) -> str:
        return _iso_z(value)


class Review(BaseModel):
    """One review of a channel by a human or an agent (append-only file)."""

    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1)
    role: Role
    verdict: Verdict
    notes: str | None = None
    created_at: datetime = Field(default_factory=_now)

    @field_validator("created_at")
    @classmethod
    def _created_at_utc(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_serializer("created_at")
    def _dump_created_at(self, value: datetime) -> str:
        return _iso_z(value)


def slugify(text: str) -> str:
    """Kebab-case ASCII slug: strip diacritics, lowercase, non-alphanumerics to ``-``.

    Returns an empty string when nothing alphanumeric is left.
    """
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
