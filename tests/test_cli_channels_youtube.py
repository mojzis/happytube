"""``channels resolve`` / ``channels evidence`` against a fake YouTube (no network)."""

import json
from unittest.mock import MagicMock

import pytest
import yaml
from click.testing import CliRunner

from happytube.cli import channels as channels_cli
from happytube.cli.commands import cli
from happytube.youtube import YouTubeClient

FAKE_KEY = "fake-key-for-tests"
QUOTA_BODY = {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}


def _response(payload, status_code=200, reason="OK"):
    response = MagicMock(status_code=status_code, reason=reason)
    response.json.return_value = payload
    return response


class FakeYouTube:
    """Answers the four endpoints from in-memory data; can run out of quota."""

    def __init__(self, quota=1000):
        self.handles = {"@zoozlin": "UCzoo", "@bbcearth": "UCbbc"}
        self.uploads = {
            "UUzoo": [("v1", "PT45S"), ("v2", "PT12M")],
            "UUbbc": [("b1", "PT1H")],
        }
        self.quota = quota
        self.calls: list[str] = []

    def __call__(self, url, params, timeout):
        assert params["key"] == FAKE_KEY
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append(endpoint)
        if len(self.calls) > self.quota:
            return _response(QUOTA_BODY, 403, "Forbidden")
        if endpoint == "playlistItems" and params["playlistId"] not in self.uploads:
            return _response({"error": {"message": "gone"}}, 404, "Not Found")
        return _response(getattr(self, f"_{endpoint}")(params))

    def _channels(self, params):
        if "forHandle" in params:
            found = self.handles.get(params["forHandle"])
            return {"items": [{"id": found}]} if found else {"pageInfo": {}}
        return {
            "items": [
                {
                    "id": cid,
                    "snippet": {"title": f"Title {cid}", "customUrl": "@x"},
                    "statistics": {"subscriberCount": "10", "videoCount": "2"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}},
                }
                for cid in params["id"].split(",")
            ]
        }

    def _playlistItems(self, params):
        videos = self.uploads[params["playlistId"]]
        return {"items": [{"contentDetails": {"videoId": v}} for v, _ in videos]}

    def _videos(self, params):
        durations = dict(v for vs in self.uploads.values() for v in vs)
        return {
            "items": [
                {
                    "id": vid,
                    "snippet": {"title": vid, "publishedAt": "2026-10-01T00:00:00Z"},
                    "contentDetails": {"duration": durations[vid]},
                    "status": {"madeForKids": False},
                }
                for vid in params["id"].split(",")
            ]
        }


@pytest.fixture
def youtube(monkeypatch):
    fake = FakeYouTube()
    monkeypatch.setattr(
        channels_cli,
        "make_youtube_client",
        lambda: YouTubeClient(FAKE_KEY, get=fake),
    )
    return fake


@pytest.fixture
def root(tmp_path):
    return tmp_path / "channels"


@pytest.fixture
def registry(root, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("YTKEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HAPPYTUBE_CHANNELS_DIR", str(root))

    def _run(*args):
        return CliRunner().invoke(cli, ["channels", *args])

    for name, handle in [
        ("Zoo Zlín", "@zoozlin"),
        ("BBC Earth", "@bbcearth"),
        ("Wrong", "@nobody"),
        ("No Handle", None),
    ]:
        extra = ["--handle", handle] if handle else []
        args = ["add", name, "--kind", "zoo", "--language", "cs", "--added-by", "me"]
        assert _run(*args, *extra).exit_code == 0
    return _run


def _statuses(result):
    return {r["slug"]: r["status"] for r in json.loads(result.stdout)["results"]}


def test_resolve_all_reports_statuses_and_writes_ids(registry, youtube, root):
    result = registry("resolve", "--all", "--json")
    assert result.exit_code == 0, result.stderr
    assert _statuses(result) == {
        "bbc-earth": "resolved",
        "no-handle": "no_handle",
        "wrong": "not_found",
        "zoo-zlin": "resolved",
    }
    saved = yaml.safe_load((root / "zoo-zlin" / "channel.yaml").read_text())
    assert saved["channel_id"] == "UCzoo"


def test_resolve_twice_is_already_and_mismatch_fails(registry, youtube):
    registry("resolve", "zoo-zlin")
    assert _statuses(registry("resolve", "zoo-zlin", "--json")) == {
        "zoo-zlin": "already"
    }
    youtube.handles["@zoozlin"] = "UCimpostor"
    result = registry("resolve", "zoo-zlin", "--json")
    assert result.exit_code == 1
    assert _statuses(result) == {"zoo-zlin": "mismatch"}
    assert "Some channels failed" in result.stderr


def test_resolve_needs_slugs_or_all(registry, youtube):
    assert registry("resolve").exit_code == 2
    assert registry("resolve", "zoo-zlin", "--all").exit_code == 2
    assert youtube.calls == []


def test_resolve_unknown_slug_spends_no_quota(registry, youtube):
    result = registry("resolve", "zoo-zlin", "ghost")
    assert result.exit_code == 1
    assert "No channel with slug 'ghost'" in result.stderr
    assert youtube.calls == []


def test_resolve_without_key_is_clean_error(registry):
    result = registry("resolve", "--all")
    assert result.exit_code == 1
    assert "YTKEY is not set" in result.stderr
    assert "Traceback" not in result.stderr


def test_evidence_all_writes_snapshots(registry, youtube, root):
    result = registry("evidence", "--all", "--json")
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    by_slug = {r["slug"]: r for r in data["results"]}
    zoo = by_slug["zoo-zlin"]
    assert (zoo["status"], zoo["video_count"], zoo["shorts_count"]) == (
        "written",
        2,
        1,
    )
    # 2 resolves + 1 for the unknown handle + 1 channels + 2 x (playlist + videos)
    assert data["quota_units"] == 8
    assert by_slug["wrong"]["status"] == "not_found"
    assert list((root / "zoo-zlin" / "evidence").glob("*.yaml"))


def test_evidence_shows_up_in_list_and_show(registry, youtube):
    registry("evidence", "zoo-zlin")
    listed = json.loads(registry("list", "--json").stdout)
    evidence_at = {c["slug"]: c["evidence_at"] for c in listed}
    assert evidence_at["zoo-zlin"] is not None
    assert evidence_at["bbc-earth"] is None
    shown = registry("show", "zoo-zlin")
    assert "resolved to: Title UCzoo" in shown.stdout
    assert "shorts: 1" in shown.stdout


def test_show_json_has_full_evidence(registry, youtube):
    registry("evidence", "zoo-zlin")
    data = json.loads(registry("show", "zoo-zlin", "--json").stdout)
    assert [v["video_id"] for v in data["evidence"]["videos"]] == ["v1", "v2"]


def test_evidence_human_output(registry, youtube):
    result = registry("evidence", "zoo-zlin", "wrong")
    assert result.exit_code == 0
    assert "zoo-zlin: written" in result.stdout
    assert "(2 videos, 1 shorts)" in result.stdout
    assert "quota units used: 5" in result.stdout


def test_evidence_quota_exceeded_keeps_written_snapshots(registry, youtube, root):
    youtube.quota = 5  # 2 resolves, channels, zoo's playlist + videos; bbc fails
    result = registry("evidence", "zoo-zlin", "bbc-earth", "--json")
    assert result.exit_code == 1
    assert "quota" in result.stderr
    assert _statuses(result) == {"zoo-zlin": "written", "bbc-earth": "error"}
    assert list((root / "zoo-zlin" / "evidence").glob("*.yaml"))


def test_evidence_quota_exceeded_while_resolving(registry, youtube):
    youtube.quota = 0
    result = registry("evidence", "zoo-zlin", "--json")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["aborted"]
    assert _statuses(result) == {"zoo-zlin": "error"}


def test_evidence_playlist_error_is_reported(registry, youtube):
    youtube.uploads.pop("UUbbc")
    result = registry("evidence", "bbc-earth", "zoo-zlin", "--json")
    assert result.exit_code == 1
    results = {r["slug"]: r for r in json.loads(result.stdout)["results"]}
    assert results["bbc-earth"]["message"].endswith("404 Not Found - gone")
    assert results["zoo-zlin"]["status"] == "written"


def test_list_and_show_work_without_keys(registry):
    assert registry("list", "--json").exit_code == 0
    assert registry("show", "zoo-zlin").exit_code == 0
