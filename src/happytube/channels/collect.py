"""Resolve channel handles and collect evidence snapshots via ``YouTubeClient``.

Shared by the ``channels resolve`` / ``channels evidence`` commands and, later, by
scheduled refreshes. No click or rich here. Per-channel problems become results;
only a used-up quota stops a run early (``Run.aborted``), keeping what was written.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from happytube.channels.evidence import build_evidence, upload_video_ids
from happytube.channels.store import ChannelIdMismatchError, ChannelStore
from happytube.youtube import QuotaExceededError, YouTubeClient, YouTubeError

ResultStatus = Literal[
    "resolved", "already", "not_found", "no_handle", "mismatch", "error", "written"
]
FAILURE_STATUSES: frozenset[str] = frozenset({"mismatch", "error"})
_NOT_FETCHED = "not fetched: YouTube quota exceeded"


@dataclass
class ChannelResult:
    slug: str
    status: ResultStatus
    handle: str | None = None
    channel_id: str | None = None
    message: str | None = None
    path: str | None = None
    video_count: int | None = None
    shorts_count: int | None = None


@dataclass
class Run:
    """Outcome of a resolve or evidence run over several channels."""

    results: list[ChannelResult] = field(default_factory=list)
    aborted: str | None = None  # set when the quota ran out mid-run
    quota_units: int = 0

    @property
    def failed(self) -> bool:
        return self.aborted is not None or any(
            r.status in FAILURE_STATUSES for r in self.results
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "results": [asdict(r) for r in self.results],
            "aborted": self.aborted,
            "quota_units": self.quota_units,
        }


def _resolve(
    store: ChannelStore, client: YouTubeClient, slug: str, *, verify: bool
) -> ChannelResult:
    """Resolve one channel's handle; ``verify`` re-checks an already set id.

    Raises ``QuotaExceededError``; other API errors become an ``error`` result.
    """
    channel = store.get_channel(slug)
    result = ChannelResult(slug, "already", channel.handle, channel.channel_id)
    if channel.channel_id and not (verify and channel.handle):
        return result
    if not channel.handle:
        result.status = "no_handle"
        result.message = "no handle in channel.yaml; add one or a channel_id"
        return result
    try:
        found = client.resolve_handle(channel.handle)
    except QuotaExceededError:
        raise
    except YouTubeError as e:
        result.status, result.message = "error", str(e)
        return result
    if found is None:
        result.status = "not_found"
        result.message = f"no YouTube channel has handle {channel.handle}"
        return result
    try:
        written = store.set_channel_id(slug, found)
    except ChannelIdMismatchError as e:
        result.status, result.message = "mismatch", str(e)
        return result
    result.channel_id = found
    result.status = "resolved" if written else "already"
    return result


def resolve_channels(
    store: ChannelStore, client: YouTubeClient, slugs: list[str]
) -> Run:
    """Resolve handles of ``slugs``; a set ``channel_id`` is verified against the
    handle (a different one is a ``mismatch``, never overwritten)."""
    run = Run()
    for slug in slugs:
        try:
            run.results.append(_resolve(store, client, slug, verify=True))
        except QuotaExceededError as e:
            run.results.append(ChannelResult(slug, "error", message=str(e)))
            run.aborted = str(e)
            break
    run.quota_units = client.quota_units
    return run


def _snapshot(
    store: ChannelStore,
    client: YouTubeClient,
    result: ChannelResult,
    item: dict[str, Any],
    max_videos: int,
) -> None:
    """Fetch recent uploads for one channel item and write its snapshot."""
    uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    videos: list[dict[str, Any]] = []
    if uploads:
        ids = upload_video_ids(client.playlist_items(uploads, max_videos))
        videos = client.videos(ids)
    evidence = build_evidence(item, videos)
    result.path = str(store.add_evidence(result.slug, evidence))
    result.status = "written"
    result.video_count = len(evidence.videos)
    result.shorts_count = evidence.shorts_count


def _fetch_channels(
    client: YouTubeClient, ready: list[ChannelResult]
) -> dict[str, dict[str, Any]]:
    ids = list(dict.fromkeys(r.channel_id for r in ready if r.channel_id))
    return {item["id"]: item for item in client.channels(ids)}


def collect_evidence(
    store: ChannelStore, client: YouTubeClient, slugs: list[str], max_videos: int
) -> Run:
    """Resolve where ``channel_id`` is missing, then write one snapshot per channel.

    If the quota runs out, snapshots already written stay; every channel not yet
    fetched is reported as an ``error``.
    """
    run = Run()
    try:
        for slug in slugs:
            run.results.append(ChannelResult(slug, "error", message=_NOT_FETCHED))
            run.results[-1] = _resolve(store, client, slug, verify=False)
        ready = [r for r in run.results if r.status in {"resolved", "already"}]
        try:
            items = _fetch_channels(client, ready)
        except QuotaExceededError:
            raise
        except YouTubeError as e:
            items = {}
            for result in ready:
                result.status, result.message = "error", str(e)
            ready = []
        for result in ready:
            item = items.get(result.channel_id or "")
            if item is None:
                result.status = "error"
                result.message = f"YouTube returned no channel {result.channel_id}"
                continue
            try:
                _snapshot(store, client, result, item, max_videos)
            except QuotaExceededError:
                raise
            except YouTubeError as e:
                result.status, result.message = "error", str(e)
    except QuotaExceededError as e:
        run.aborted = str(e)
        for result in run.results:
            if result.status in {"resolved", "already"} or (
                result.message == _NOT_FETCHED
            ):
                result.status, result.message = "error", _NOT_FETCHED
    run.quota_units = client.quota_units
    return run
