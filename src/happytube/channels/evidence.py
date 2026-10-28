"""Build an ``Evidence`` snapshot from YouTube Data API responses (pure functions)."""

from datetime import datetime
from typing import Any

from happytube.channels.models import Evidence, EvidenceVideo
from happytube.youtube import parse_duration

SHORTS_MAX_S = 180  # Shorts can be up to 3 minutes since October 2024
CHANNEL_DESCRIPTION_MAX = 1000
VIDEO_DESCRIPTION_MAX = 300


def is_short(duration_s: int | None) -> bool:
    """Shorts rule: up to 3 minutes. ``0`` (live or upcoming streams report
    ``P0D``) and unknown durations are not Shorts."""
    return duration_s is not None and 0 < duration_s <= SHORTS_MAX_S


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


def evidence_video(video: dict[str, Any]) -> EvidenceVideo:
    """One ``videos.list`` item as an ``EvidenceVideo``."""
    snippet = video.get("snippet", {})
    duration_s = _duration_s(video)
    return EvidenceVideo(
        video_id=video["id"],
        title=snippet.get("title", ""),
        published_at=snippet["publishedAt"],
        duration_s=duration_s,
        is_short=is_short(duration_s),
        description=_truncate(snippet.get("description"), VIDEO_DESCRIPTION_MAX),
        default_language=snippet.get("defaultAudioLanguage")
        or snippet.get("defaultLanguage"),
        made_for_kids=video.get("status", {}).get("madeForKids"),
    )


def build_evidence(
    channel: dict[str, Any],
    videos: list[dict[str, Any]],
    fetched_at: datetime | None = None,
) -> Evidence:
    """Snapshot from a ``channels.list`` item and its ``videos.list`` items.

    Videos are stored newest first. Videos the API no longer returns (private,
    deleted) are simply absent from ``videos``.
    """
    snippet = channel.get("snippet", {})
    statistics = channel.get("statistics", {})
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {})
    hidden = statistics.get("hiddenSubscriberCount", False)
    entries = sorted(
        (evidence_video(v) for v in videos),
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
        "videos": entries,
    }
    if fetched_at is not None:
        fields["fetched_at"] = fetched_at
    return Evidence.model_validate(fields)
