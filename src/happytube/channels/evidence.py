"""Build an ``Evidence`` snapshot from YouTube Data API responses (pure functions)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from happytube.channels.models import Evidence, EvidenceVideo
from happytube.youtube import parse_duration

# Duration fallback, used only when the channel's UUSH playlist can't be read.
SHORTS_MAX_S = 180  # Shorts can be up to 3 minutes since 2024-10-15 …
SHORTS_MAX_S_BEFORE = 60  # … and were up to 60 s before
SHORTS_3MIN_SINCE = datetime(2024, 10, 15, tzinfo=UTC)
CHANNEL_DESCRIPTION_MAX = 1000
VIDEO_DESCRIPTION_MAX = 300


def shorts_playlist_id(channel_id: str) -> str:
    """The ``UUSH…`` playlist holding a channel's Shorts (``UC…`` → ``UUSH…``)."""
    return "UUSH" + channel_id.removeprefix("UC")


def is_short(duration_s: int | None, published_at: datetime | None = None) -> bool:
    """Duration fallback: up to 60 s before 2024-10-15, up to 3 min since (and when
    the date is unknown). ``0`` (live or upcoming streams report ``P0D``) and
    unknown durations are not Shorts."""
    if duration_s is None or duration_s <= 0:
        return False
    limit = SHORTS_MAX_S
    if published_at is not None and published_at < SHORTS_3MIN_SINCE:
        limit = SHORTS_MAX_S_BEFORE
    return duration_s <= limit


def _truncate(text: str | None, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _count(statistics: dict[str, Any], key: str) -> int | None:
    value = statistics.get(key)
    return None if value is None else int(value)


def _duration_s(video: dict[str, Any]) -> int | None:
    raw = video.get("contentDetails", {}).get("duration")
    if not raw:
        return None
    try:
        return parse_duration(raw)
    except ValueError:
        return None


def upload_video_ids(playlist_items: list[dict[str, Any]]) -> list[str]:
    """Video ids of ``playlistItems.list`` items, in playlist order."""
    ids = []
    for item in playlist_items:
        video_id = item.get("contentDetails", {}).get("videoId") or (
            item.get("snippet", {}).get("resourceId", {}).get("videoId")
        )
        if video_id:
            ids.append(video_id)
    return ids


def evidence_video(
    video: dict[str, Any], short_ids: set[str] | None = None
) -> EvidenceVideo | None:
    """One ``videos.list`` item as an ``EvidenceVideo``, or ``None`` if it lacks
    an id or a valid ``publishedAt`` (skipped rather than failing the channel).

    ``short_ids`` (from the ``UUSH…`` playlist) decides ``is_short``; ``None``
    falls back to the duration rule.
    """
    snippet = video.get("snippet", {})
    duration_s = _duration_s(video)
    try:
        entry = EvidenceVideo(
            video_id=video.get("id", ""),
            title=snippet.get("title", ""),
            published_at=snippet.get("publishedAt"),
            duration_s=duration_s,
            is_short=False,
            description=_truncate(snippet.get("description"), VIDEO_DESCRIPTION_MAX),
            default_language=snippet.get("defaultAudioLanguage")
            or snippet.get("defaultLanguage"),
            made_for_kids=video.get("status", {}).get("madeForKids"),
        )
    except ValidationError:
        return None
    entry.is_short = (
        is_short(duration_s, entry.published_at)
        if short_ids is None
        else entry.video_id in short_ids
    )
    return entry


def build_evidence(
    channel: dict[str, Any],
    videos: list[dict[str, Any]],
    fetched_at: datetime | None = None,
    short_ids: set[str] | None = None,
) -> Evidence:
    """Snapshot from a ``channels.list`` item and its ``videos.list`` items.

    ``short_ids`` are the ids in the channel's ``UUSH…`` Shorts playlist (empty
    set: the channel has no Shorts); ``None`` means it couldn't be read and the
    duration rule decides. Videos are stored newest first. Videos the API no
    longer returns (private, deleted) or without a publish date are absent.
    """
    snippet = channel.get("snippet", {})
    statistics = channel.get("statistics", {})
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {})
    hidden = statistics.get("hiddenSubscriberCount", False)
    parsed = (evidence_video(v, short_ids) for v in videos)
    entries = sorted(
        (v for v in parsed if v is not None),
        key=lambda v: v.published_at,
        reverse=True,
    )
    fields: dict[str, Any] = {
        "method": "api",
        "channel_id": channel["id"],
        "title": snippet.get("title", ""),
        "custom_url": snippet.get("customUrl"),
        "description": _truncate(snippet.get("description"), CHANNEL_DESCRIPTION_MAX),
        "country": snippet.get("country"),
        "published_at": snippet.get("publishedAt"),
        "subscriber_count": None if hidden else _count(statistics, "subscriberCount"),
        "view_count": _count(statistics, "viewCount"),
        "video_count": _count(statistics, "videoCount"),
        "uploads_playlist_id": uploads.get("uploads") or None,
        "shorts_source": "duration" if short_ids is None else "uush",
        "videos": entries,
    }
    if fetched_at is not None:
        fields["fetched_at"] = fetched_at
    return Evidence.model_validate(fields)
