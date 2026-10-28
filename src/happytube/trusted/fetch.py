"""Trusted fetch: new long-form videos from approved channels only (decision 0009).

Per approved channel (decision 0004 method, ~3 quota units): the newest uploads
from its ``UU…`` playlist, its Shorts from ``UUSH…`` (duration rule when that
can't be read), then ``videos.list`` for the candidates. Kept: long-form, not
live or upcoming, published within ``since_days`` of the date, and never fetched
before on any date. Same run shape as ``channels/collect.py``: a used-up quota
or rejected key stops the run (files written stay, the rest ``not_fetched``);
any other per-channel error is that channel's ``error``; both fail the run.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from happytube.channels.collect import fetch_short_ids
from happytube.channels.evidence import (
    evidence_video,
    upload_video_ids,
    uploads_playlist_id,
)
from happytube.channels.models import Channel, EvidenceVideo
from happytube.channels.store import ChannelStore, ChannelStoreError
from happytube.models.markdown import MarkdownFile
from happytube.trusted.stages import TrustedStage, is_video_id
from happytube.utils import utc_now_iso
from happytube.youtube import (
    RunStoppingError,
    YouTubeClient,
    YouTubeError,
    is_playlist_not_found,
)

FetchStatus = Literal["fetched", "skipped_unresolved", "error", "not_fetched"]
FAILURE_STATUSES: frozenset[str] = frozenset({"error", "not_fetched"})
_NOT_FETCHED = "not fetched: run stopped (quota used up or key rejected)"
_LIVE = frozenset({"live", "upcoming"})


class NotApprovedError(ChannelStoreError):
    """A channel named for the trusted fetch is not approved."""


@dataclass
class FetchResult:
    slug: str
    status: FetchStatus
    channel_id: str | None = None
    message: str | None = None
    shorts_source: str | None = None
    new: int = 0  # files written
    seen: int = 0  # fetched on an earlier run (any date)
    shorts: int = 0
    live: int = 0  # live, upcoming or without a duration
    outside_window: int = 0
    unreadable: int = 0  # no valid id or no publish date in videos.list
    paths: list[str] = field(default_factory=list)


@dataclass
class FetchRun:
    """Outcome of a trusted fetch over several channels."""

    results: list[FetchResult] = field(default_factory=list)
    aborted: str | None = None
    quota_units: int = 0

    @property
    def failed(self) -> bool:
        return self.aborted is not None or any(
            r.status in FAILURE_STATUSES for r in self.results
        )

    @property
    def new(self) -> int:
        return sum(r.new for r in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "results": [asdict(r) for r in self.results],
            "aborted": self.aborted,
            "quota_units": self.quota_units,
            "new": self.new,
        }


def approved_channels(store: ChannelStore, slugs: list[str]) -> list[Channel]:
    """Channels to fetch: every approved one, or exactly ``slugs`` — each of which
    must exist and be approved (``NotApprovedError`` names its status)."""
    if not slugs:
        return [e.channel for e in store.entries() if e.status == "approved"]
    channels = []
    for slug in dict.fromkeys(slugs):
        entry = store.get(slug)  # raises ChannelNotFoundError
        if entry.status != "approved":
            msg = f"Channel '{slug}' is {entry.status}, not approved; not fetched"
            raise NotApprovedError(msg)
        channels.append(entry.channel)
    return channels


@dataclass(frozen=True)
class Window:
    """Publication dates kept: ``since_days`` before ``target_date`` up to it."""

    target_date: date
    since_days: int

    def __contains__(self, published: date) -> bool:
        start = self.target_date - timedelta(days=self.since_days)
        return start <= published <= self.target_date


def _frontmatter(
    channel: Channel, video: EvidenceVideo, shorts_source: str
) -> dict[str, Any]:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "channel_slug": channel.slug,
        "channel_id": channel.channel_id,
        "channel_name": channel.name,
        "languages": list(channel.languages),
        "published_at": video.model_dump(mode="json")["published_at"],
        "duration_s": video.duration_s,
        "shorts_source": shorts_source,
        "fetched_at": utc_now_iso(),
        "stage": "trusted_fetch",
    }


def _upload_ids(client: YouTubeClient, channel_id: str, limit: int) -> list[str]:
    """Newest ``limit`` upload ids; 404 on ``UU…`` means no uploads."""
    try:
        items = client.playlist_items(uploads_playlist_id(channel_id), limit)
    except YouTubeError as e:
        if is_playlist_not_found(e):
            return []
        raise
    return upload_video_ids(items)


@dataclass
class _Fetch:
    """What one fetch needs besides the channel."""

    client: YouTubeClient
    stage: TrustedStage
    window: Window
    max_per_channel: int
    seen: set[str]


def _classify(
    fetch: _Fetch, result: FetchResult, raw: dict[str, Any], video: EvidenceVideo
) -> bool:
    """Count why a video is left out; ``True`` when it is kept."""
    live = raw.get("snippet", {}).get("liveBroadcastContent") in _LIVE
    if video.is_short:
        result.shorts += 1
    elif live or not video.duration_s:  # P0D: live or upcoming stream
        result.live += 1
    elif video.published_at.date() not in fetch.window:
        result.outside_window += 1
    else:
        return True
    return False


def _fetch_channel(fetch: _Fetch, channel: Channel) -> FetchResult:
    """Write new videos of one channel. Raises ``RunStoppingError``; other
    YouTube errors propagate as ``YouTubeError`` for the caller to record."""
    result = FetchResult(channel.slug, "fetched", channel.channel_id)
    if channel.channel_id is None:
        result.status = "skipped_unresolved"
        result.message = "approved but no channel_id; run channels resolve"
        return result
    ids = _upload_ids(fetch.client, channel.channel_id, fetch.max_per_channel)
    short_ids = (
        fetch_short_ids(fetch.client, channel.channel_id, fetch.max_per_channel)
        if ids
        else set()
    )
    result.shorts_source = "duration" if short_ids is None else "uush"
    unseen = [i for i in ids if i not in fetch.seen]
    result.seen = len(ids) - len(unseen)
    # UUSH Shorts need no videos.list lookup; the duration rule needs one.
    candidates = [i for i in unseen if not short_ids or i not in short_ids]
    result.shorts = len(unseen) - len(candidates)
    for raw in fetch.client.videos(candidates) if candidates else []:
        video = evidence_video(raw, short_ids, description_max=None)
        if video is None or not is_video_id(video.video_id):
            result.unreadable += 1
        elif _classify(fetch, result, raw, video):
            md = MarkdownFile(
                _frontmatter(channel, video, result.shorts_source),
                f"# {video.title}\n\n{video.description}",
            )
            path = fetch.stage.write(fetch.window.target_date, video.video_id, md)
            fetch.seen.add(video.video_id)
            result.paths.append(str(path))
            result.new += 1
    return result


def fetch_trusted(  # noqa: PLR0913 - the run's inputs, all keyword
    channels: list[Channel],
    client: YouTubeClient,
    target_date: date,
    *,
    since_days: int = 14,
    max_per_channel: int = 50,
    base_path: Path = Path("stages"),
) -> FetchRun:
    """Fetch new long-form videos of ``channels`` (from ``approved_channels``)
    into ``stages/trusted/fetch/<date>/``.

    Re-running for the same date writes nothing new: every video already in
    the fetch stage, on any date, is ``seen``.
    """
    stage = TrustedStage("fetch", base_path)
    fetch = _Fetch(
        client,
        stage,
        Window(target_date, since_days),
        max_per_channel,
        stage.video_ids(),
    )
    run = FetchRun(
        [
            FetchResult(c.slug, "not_fetched", c.channel_id, _NOT_FETCHED)
            for c in channels
        ]
    )
    for index, channel in enumerate(channels):
        try:
            run.results[index] = _fetch_channel(fetch, channel)
        except RunStoppingError as e:
            run.results[index].status = "error"
            run.results[index].message = str(e)
            run.aborted = str(e)
            break
        except YouTubeError as e:
            run.results[index] = FetchResult(
                channel.slug, "error", channel.channel_id, str(e)
            )
    run.quota_units = client.quota_units
    return run
