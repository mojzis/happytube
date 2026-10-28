from unittest.mock import MagicMock

import pytest
import requests
from pydantic import ValidationError

from happytube.config.settings import YouTubeSettings
from happytube.youtube import (
    API_BASE,
    InvalidKeyError,
    QuotaExceededError,
    RunStoppingError,
    YouTubeAPIError,
    YouTubeClient,
    YouTubeConnectionError,
    is_playlist_not_found,
    parse_duration,
)

KEY = "fake-test-key-123"


def _response(status_code=200, payload=None, reason="OK"):
    response = MagicMock(status_code=status_code, reason=reason)
    response.json.return_value = payload if payload is not None else {}
    return response


class FakeGet:
    """Records calls and replies with queued responses (or raises queued errors)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, params, timeout):
        assert timeout > 0
        self.calls.append((url, params))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("PT0S", 0),
        ("P0D", 0),
        ("PT45S", 45),
        ("PT3M", 180),
        ("PT1H2M3S", 3723),
        ("P1DT2H", 93600),
        ("P1W", 604800),
    ],
)
def test_parse_duration(value, seconds):
    assert parse_duration(value) == seconds


@pytest.mark.parametrize("value", ["", "P", "PT", "P1DT", "1H", "PT1.5S", "garbage"])
def test_parse_duration_rejects_garbage(value):
    with pytest.raises(ValueError, match="ISO-8601"):
        parse_duration(value)


def test_resolve_handle_found_and_counts_quota():
    get = FakeGet(_response(payload={"items": [{"id": "UCabc"}]}))
    client = YouTubeClient(KEY, get=get)
    assert client.resolve_handle("@zoo") == "UCabc"
    url, params = get.calls[0]
    assert url == f"{API_BASE}/channels"
    assert params == {"part": "id", "forHandle": "@zoo", "key": KEY}
    assert client.quota_units == 1


def test_resolve_handle_not_found_is_none():
    client = YouTubeClient(KEY, get=FakeGet(_response(payload={"pageInfo": {}})))
    assert client.resolve_handle("@nobody") is None


def test_channels_batches_by_50():
    ids = [f"UC{i}" for i in range(120)]
    get = FakeGet(
        *[_response(payload={"items": [{"id": "x"}] * n}) for n in (50, 50, 20)]
    )
    client = YouTubeClient(KEY, get=get)
    assert len(client.channels(ids)) == 120
    batches = [params["id"].split(",") for _, params in get.calls]
    assert [len(b) for b in batches] == [50, 50, 20]
    assert [i for b in batches for i in b] == ids
    assert client.quota_units == 3


def test_videos_batches_by_50():
    get = FakeGet(_response(payload={"items": [1]}), _response(payload={"items": [2]}))
    client = YouTubeClient(KEY, get=get)
    assert client.videos([f"v{i}" for i in range(51)]) == [1, 2]
    assert "contentDetails" in get.calls[0][1]["part"]


def test_videos_empty_list_makes_no_call():
    client = YouTubeClient(KEY, get=FakeGet())
    assert client.videos([]) == []
    assert client.quota_units == 0


def test_playlist_items_follows_pages_up_to_max():
    get = FakeGet(
        _response(payload={"items": [1] * 50, "nextPageToken": "p2"}),
        _response(payload={"items": [2] * 50, "nextPageToken": "p3"}),
    )
    client = YouTubeClient(KEY, get=get)
    items = client.playlist_items("UUx", max_results=70)
    assert len(items) == 70
    assert get.calls[1][1]["pageToken"] == "p2"
    assert get.calls[1][1]["maxResults"] == 20
    assert client.quota_units == 2


def test_playlist_items_stops_without_next_page():
    get = FakeGet(_response(payload={"items": [1, 2]}))
    assert YouTubeClient(KEY, get=get).playlist_items("UUx") == [1, 2]


def test_non_200_raises_api_error_without_key():
    get = FakeGet(
        _response(
            404,
            {"error": {"message": "Not found", "errors": [{"reason": "notFound"}]}},
            reason="Not Found",
        )
    )
    with pytest.raises(YouTubeAPIError, match="404 Not Found - Not found") as exc:
        YouTubeClient(KEY, get=get).playlist_items("UUx")
    assert not isinstance(exc.value, QuotaExceededError)
    assert exc.value.error_reason == "notFound"
    assert KEY not in str(exc.value)


def test_quota_exceeded_has_own_error():
    body = {
        "error": {
            "message": "The request cannot be completed because you have exceeded "
            "your quota.",
            "errors": [{"reason": "quotaExceeded"}],
        }
    }
    get = FakeGet(_response(403, body, reason="Forbidden"))
    with pytest.raises(QuotaExceededError, match="403 Forbidden"):
        YouTubeClient(KEY, get=get).resolve_handle("@x")


def test_error_body_without_json_still_raises():
    response = _response(500, reason="Server Error")
    response.json.side_effect = ValueError("not json")
    with pytest.raises(YouTubeAPIError, match=r"500 Server Error$"):
        YouTubeClient(KEY, get=FakeGet(response)).videos(["v"])


@pytest.mark.parametrize(
    "error",
    [
        requests.ConnectionError(
            f"HTTPSConnectionPool: Max retries exceeded with url: /channels?key={KEY}"
        ),
        requests.Timeout(f"Read timed out. url=https://x/?key={KEY}"),
    ],
)
def test_request_exception_never_leaks_key(error):
    with pytest.raises(YouTubeConnectionError) as exc:
        YouTubeClient(KEY, get=FakeGet(error)).resolve_handle("@x")
    assert KEY not in str(exc.value)
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__
    assert type(error).__name__ in str(exc.value)


def test_non_json_success_body_is_a_connection_error():
    response = _response()
    response.json.side_effect = ValueError("bad")
    with pytest.raises(YouTubeConnectionError, match="non-JSON"):
        YouTubeClient(KEY, get=FakeGet(response)).resolve_handle("@x")


def test_youtube_settings_needs_only_ytkey(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("YTKEY", raising=False)
    with pytest.raises(ValidationError):
        YouTubeSettings()
    (tmp_path / ".env").write_text("YTKEY=from-env-file\nOTHER=1\n")
    settings = YouTubeSettings()
    assert settings.youtube_api_key.get_secret_value() == "from-env-file"
    assert "from-env-file" not in repr(settings)


def test_invalid_key_is_run_stopping():
    body = {
        "error": {
            "message": "API key not valid. Please pass a valid API key.",
            "errors": [{"reason": "badRequest"}],
            "details": [{"reason": "API_KEY_INVALID"}],
        }
    }
    get = FakeGet(_response(400, body, reason="Bad Request"))
    with pytest.raises(InvalidKeyError, match="API key not valid") as exc:
        YouTubeClient(KEY, get=get).resolve_handle("@x")
    assert isinstance(exc.value, RunStoppingError)


@pytest.mark.parametrize("reason", ["keyInvalid", "accessNotConfigured"])
def test_legacy_key_reasons_are_run_stopping(reason):
    body = {"error": {"message": "nope", "errors": [{"reason": reason}]}}
    get = FakeGet(_response(403, body, reason="Forbidden"))
    with pytest.raises(InvalidKeyError):
        YouTubeClient(KEY, get=get).resolve_handle("@x")


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    [
        (404, "playlistNotFound", True),
        (404, "", False),
        (403, "playlistNotFound", False),
    ],
)
def test_is_playlist_not_found(status, reason, expected):
    body = {"error": {"message": "m", "errors": [{"reason": reason}]}}
    get = FakeGet(_response(status, body, reason="x"))
    with pytest.raises(YouTubeAPIError) as exc:
        YouTubeClient(KEY, get=get).playlist_items("UUSHabc")
    assert is_playlist_not_found(exc.value) is expected
