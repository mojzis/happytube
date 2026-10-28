"""Small YouTube Data API v3 client for channel evidence.

Every request goes through ``YouTubeClient._call``, which counts quota units and
turns transport and HTTP failures into ``YouTubeError`` subclasses whose message
never contains the request URL — the URL carries the API key as a query parameter.
The HTTP getter is injectable so tests never touch the network.
"""

import re
from collections.abc import Callable, Iterator
from http import HTTPStatus
from typing import Any

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"
REQUEST_TIMEOUT_S = 30
MAX_IDS_PER_CALL = 50  # channels.list / videos.list id limit, playlistItems page size

_DURATION = re.compile(
    r"^P(?:(?P<w>\d+)W)?(?:(?P<d>\d+)D)?"
    r"(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)
_DURATION_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


class YouTubeError(RuntimeError):
    """A YouTube request failed; the message is user-facing and key-free."""


class YouTubeAPIError(YouTubeError):
    """A YouTube Data API request returned a non-200 response."""

    def __init__(
        self,
        endpoint: str,
        status_code: int,
        reason: str,
        detail: str = "",
        error_reason: str = "",
    ):
        # Deliberately no URL: it carries the API key as a query parameter.
        message = f"YouTube {endpoint} request failed: {status_code} {reason}"
        if detail:
            message += f" - {detail}"
        super().__init__(message)
        self.status_code = status_code
        self.error_reason = error_reason


class RunStoppingError(YouTubeAPIError):
    """Every further request would fail the same way; stop the run."""


class QuotaExceededError(RunStoppingError):
    """The daily API quota is used up; nothing more can be fetched today."""


class InvalidKeyError(RunStoppingError):
    """YouTube rejected the API key (wrong, revoked or API not enabled)."""


class YouTubeConnectionError(YouTubeError):
    """The request did not get a usable response (network, timeout, bad JSON)."""


def api_error_detail(response: requests.Response) -> str:
    """Return the ``error.message`` of a YouTube error body, or ``""``."""
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return ""


def _api_error_reason(response: requests.Response) -> str:
    """Machine-readable reason of a YouTube error body, or ``""``.

    ``error.details[].reason`` (``API_KEY_INVALID``, …) wins over the coarser
    ``error.errors[0].reason`` (``quotaExceeded``, ``badRequest``, …).
    """
    try:
        error = response.json()["error"]
    except (ValueError, KeyError, TypeError):
        return ""
    if not isinstance(error, dict):
        return ""
    for detail in error.get("details") or []:
        if isinstance(detail, dict) and detail.get("reason"):
            return str(detail["reason"])
    try:
        return str(error["errors"][0]["reason"])
    except (KeyError, TypeError, IndexError):
        return ""


_STOPPING_REASONS: dict[str, type[YouTubeAPIError]] = {
    "quotaExceeded": QuotaExceededError,
    "API_KEY_INVALID": InvalidKeyError,
    "API_KEY_SERVICE_BLOCKED": InvalidKeyError,
    "SERVICE_DISABLED": InvalidKeyError,
    # Older ``errors[0].reason`` spellings of the same two failures.
    "keyInvalid": InvalidKeyError,
    "accessNotConfigured": InvalidKeyError,
}


def is_playlist_not_found(error: YouTubeError) -> bool:
    """``True`` for a 404 ``playlistNotFound`` — for ``UU…`` / ``UUSH…`` playlists
    YouTube's way of saying the channel has no such uploads."""
    return (
        isinstance(error, YouTubeAPIError)
        and error.status_code == HTTPStatus.NOT_FOUND
        and error.error_reason == "playlistNotFound"
    )


def parse_duration(value: str) -> int:
    """Seconds in an ISO-8601 video duration (``PT1H2M3S``, ``P1DT2H``, ``P0D``)."""
    match = _DURATION.match(value)
    if not match or value in {"P", "PT"} or value.endswith("T"):
        msg = f"Not an ISO-8601 duration: {value!r}"
        raise ValueError(msg)
    return sum(
        int(amount) * _DURATION_UNITS[unit]
        for unit, amount in match.groupdict().items()
        if amount
    )


def _chunks(ids: list[str]) -> Iterator[list[str]]:
    for start in range(0, len(ids), MAX_IDS_PER_CALL):
        yield ids[start : start + MAX_IDS_PER_CALL]


Getter = Callable[..., requests.Response]


class YouTubeClient:
    """The four read calls channel evidence needs; each call costs 1 quota unit."""

    def __init__(self, api_key: str, get: Getter = requests.get):
        self._api_key = api_key
        self._get = get
        self.quota_units = 0

    def _call(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        self.quota_units += 1  # YouTube charges failed requests too
        try:
            response = self._get(
                f"{API_BASE}/{endpoint}",
                params={**params, "key": self._api_key},
                timeout=REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as e:
            # ``from None``: the original exception's text includes the URL + key.
            msg = f"YouTube {endpoint} request failed: {type(e).__name__}"
            raise YouTubeConnectionError(msg) from None
        if response.status_code != HTTPStatus.OK:
            reason = _api_error_reason(response)
            error_cls = _STOPPING_REASONS.get(reason, YouTubeAPIError)
            raise error_cls(
                endpoint,
                response.status_code,
                response.reason,
                api_error_detail(response),
                reason,
            )
        try:
            data = response.json()
        except ValueError:
            msg = f"YouTube {endpoint} returned a non-JSON response"
            raise YouTubeConnectionError(msg) from None
        if not isinstance(data, dict):
            msg = f"YouTube {endpoint} returned an unexpected response"
            raise YouTubeConnectionError(msg)
        return data

    def resolve_handle(self, handle: str) -> str | None:
        """Channel id (``UC…``) for ``@handle``, or ``None`` if no channel has it."""
        data = self._call("channels", {"part": "id", "forHandle": handle})
        items = data.get("items") or []
        return items[0]["id"] if items else None

    def channels(self, channel_ids: list[str]) -> list[dict[str, Any]]:
        """``channels.list`` items (snippet, statistics, contentDetails), batched."""
        items: list[dict[str, Any]] = []
        for chunk in _chunks(channel_ids):
            data = self._call(
                "channels",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(chunk),
                    "maxResults": MAX_IDS_PER_CALL,
                },
            )
            items.extend(data.get("items") or [])
        return items

    def playlist_items(
        self, playlist_id: str, max_results: int = MAX_IDS_PER_CALL
    ) -> list[dict[str, Any]]:
        """Up to ``max_results`` items of a playlist, following pages as needed."""
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while len(items) < max_results:
            params: dict[str, Any] = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": min(MAX_IDS_PER_CALL, max_results - len(items)),
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._call("playlistItems", params)
            items.extend(data.get("items") or [])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return items[:max_results]

    def videos(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """``videos.list`` items (contentDetails, snippet, status), batched."""
        items: list[dict[str, Any]] = []
        for chunk in _chunks(video_ids):
            data = self._call(
                "videos",
                {
                    "part": "contentDetails,snippet,status",
                    "id": ",".join(chunk),
                    "maxResults": MAX_IDS_PER_CALL,
                },
            )
            items.extend(data.get("items") or [])
        return items
