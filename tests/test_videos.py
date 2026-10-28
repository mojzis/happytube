from unittest.mock import MagicMock, patch

import pytest

from happytube.videos import Search, Videos, YouTubeAPIError


@pytest.mark.parametrize("query_cls", [Search, Videos])
def test_ytkey_env_lands_in_params(query_cls, monkeypatch):
    monkeypatch.setenv("YTKEY", "env-key")
    query = query_cls()
    assert query.key == "env-key"
    assert query.params["key"] == "env-key"
    # Subclass defaults survive the base __post_init__.
    assert query.params["videoCategoryId"] == 15


def test_explicit_key_wins_over_env(monkeypatch):
    monkeypatch.setenv("YTKEY", "env-key")
    assert Search(key="explicit").params["key"] == "explicit"


def _response(status_code, payload=None):
    response = MagicMock(status_code=status_code, reason="Forbidden", text="quota")
    response.json.return_value = payload
    return response


def test_get_stores_items_on_success():
    query = Search(key="k")
    with patch(
        "happytube.videos.requests.get", return_value=_response(200, {"items": [1]})
    ):
        query.get()
    assert query.data == [1]


def test_get_raises_without_leaking_key_on_http_error():
    query = Search(key="secret-key")
    with (
        patch(
            "happytube.videos.requests.get",
            return_value=_response(403, {"error": {"message": "quotaExceeded"}}),
        ),
        pytest.raises(
            YouTubeAPIError, match="403 Forbidden - quotaExceeded"
        ) as excinfo,
    ):
        query.get()
    assert "secret-key" not in str(excinfo.value)
    assert query.data == []


def test_get_error_without_json_body_keeps_status():
    response = _response(500)
    response.json.side_effect = ValueError("not json")
    with (
        patch("happytube.videos.requests.get", return_value=response),
        pytest.raises(YouTubeAPIError, match=r"500 Forbidden$"),
    ):
        Search(key="k").get()
