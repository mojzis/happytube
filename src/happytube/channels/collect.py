"""Resolve channel handles and collect evidence snapshots via ``YouTubeClient``.

Shared by the ``channels resolve`` / ``channels evidence`` commands and, later, by
scheduled refreshes. No click or rich here. Per-channel problems become results;
only a used-up quota or a rejected key stops a run early (``Run.aborted``), keeping
what was written.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from happytube.channels.evidence import (
    build_evidence,
    shorts_playlist_id,
    upload_video_ids,
)
from happytube.channels.store import ChannelIdMismatchError, ChannelStore
from happytube.youtube import (
    RunStoppingError,
    YouTubeClient,
    YouTubeError,
    is_playlist_not_found,
)

ResultStatus = Literal[
    "resolved",
    "already",
    "not_found",
    "no_handle",
    "mismatch",
    "error",
    "written",
    "not_fetched",
]
FAILURE_STATUSES: frozenset[str] = frozenset({"mismatch", "error", "not_fetched"})
_NOT_FETCHED = "not fetched: run stopped (quota used up or key rejected)"


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
    aborted: str | None = None  # set when quota or key failed mid-run
    quota_units: int = 0

    @classmethod
    def for_slugs(cls, slugs: list[str]) -> "Run":
        """A run listing every requested slug as ``not_fetched`` until reached, so
        a run that stops early still reports each channel it was asked for."""
        return cls(
            [ChannelResult(s, "not_fetched", message=_NOT_FETCHED) for s in slugs]
        )

    def stop(self, index: int | None, error: RunStoppingError) -> None:
        """Record a run-stopping error, hit by the channel at ``index`` if any."""
        if index is not None:
            result = self.results[index]
            result.status, result.message = "error", str(error)
        self.aborted = str(error)

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

    Raises ``RunStoppingError``; other API errors become an ``error`` result.
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
    except RunStoppingError:
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
    store: ChannelStore,
    client: YouTubeClient,
    slugs: list[str],
    *,
    verify: bool = False,
) -> Run:
    """Resolve handles of ``slugs`` whose ``channel_id`` is null (1 unit each).

    A set ``channel_id`` is ``already`` at no cost; with ``verify`` it is
    re-checked against the handle (a different one is a ``mismatch``, never
    overwritten).
    """
    run = Run.for_slugs(slugs)
    for index, slug in enumerate(slugs):
        try:
            run.results[index] = _resolve(store, client, slug, verify=verify)
        except RunStoppingError as e:
            run.stop(index, e)
            break
    run.quota_units = client.quota_units
    return run


def fetch_short_ids(
    client: YouTubeClient, channel_id: str, max_videos: int
) -> set[str] | None:
    """Ids in the channel's ``UUSH…`` Shorts playlist (1 unit).

    The Shorts among the newest ``max_videos`` uploads are the newest Shorts, so
    one page of ``max_videos`` is enough. 404 ``playlistNotFound`` means the
    channel has no Shorts; any other non-stopping error returns ``None`` (the
    duration rule decides).
    """
    try:
        items = client.playlist_items(shorts_playlist_id(channel_id), max_videos)
    except RunStoppingError:
        raise
    except YouTubeError as e:
        return set() if is_playlist_not_found(e) else None
    return set(upload_video_ids(items))


def _snapshot(
    store: ChannelStore,
    client: YouTubeClient,
    result: ChannelResult,
    item: dict[str, Any],
    max_videos: int,
) -> None:
    """Fetch recent uploads for one channel item and write its snapshot.

    A 404 on the uploads playlist means the channel has no uploads (0 videos).
    """
    uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    ids: list[str] = []
    if uploads:
        try:
            ids = upload_video_ids(client.playlist_items(uploads, max_videos))
        except YouTubeError as e:
            if not is_playlist_not_found(e):
                raise
    short_ids = fetch_short_ids(client, item["id"], max_videos) if ids else set()
    evidence = build_evidence(item, client.videos(ids), short_ids=short_ids)
    result.path = str(store.add_evidence(result.slug, evidence))
    result.status = "written"
    result.message = None
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

    If the run stops (quota, bad key), snapshots already written stay; the channel
    that hit the stop is an ``error`` and every channel not reached is
    ``not_fetched``.
    """
    run = Run.for_slugs(slugs)
    for index, slug in enumerate(slugs):
        try:
            run.results[index] = _resolve(store, client, slug, verify=False)
        except RunStoppingError as e:
            run.stop(index, e)
            break
    if not run.aborted:
        _collect_ready(store, client, run, max_videos)
    if run.aborted:
        for result in run.results:
            if result.status in {"resolved", "already"}:
                result.status, result.message = "not_fetched", _NOT_FETCHED
    run.quota_units = client.quota_units
    return run


def _collect_ready(
    store: ChannelStore, client: YouTubeClient, run: Run, max_videos: int
) -> None:
    """Fetch channel items for resolved channels and write their snapshots."""
    ready = [
        (index, r)
        for index, r in enumerate(run.results)
        if r.status in {"resolved", "already"}
    ]
    try:
        items = _fetch_channels(client, [r for _, r in ready])
    except RunStoppingError as e:
        run.stop(None, e)  # a batched call: no single channel hit it
        return
    except YouTubeError as e:
        for _, result in ready:
            result.status, result.message = "error", str(e)
        return
    for index, result in ready:
        item = items.get(result.channel_id or "")
        if item is None:
            result.status = "error"
            result.message = f"YouTube returned no channel {result.channel_id}"
            continue
        try:
            _snapshot(store, client, result, item, max_videos)
        except RunStoppingError as e:
            run.stop(index, e)
            return
        except YouTubeError as e:
            result.status, result.message = "error", str(e)
