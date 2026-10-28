"""``channels resolve`` / ``channels evidence`` against a fake YouTube (no network)."""

import json
from unittest.mock import MagicMock

import pytest
import yaml
from click.testing import CliRunner

from happytube.channels.models import Evidence, EvidenceVideo
from happytube.channels.store import ChannelStore
from happytube.cli import channels as channels_cli
from happytube.cli.commands import cli
from happytube.youtube import YouTubeClient

FAKE_KEY = "fake-key-for-tests"
QUOTA_BODY = {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}
NOT_FOUND_BODY = {
    "error": {"message": "gone", "errors": [{"reason": "playlistNotFound"}]}
}


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
        # Shorts playlists; a channel without one gets 404 playlistNotFound.
        self.shorts = {"UUSHzoo": ["v1"]}
        self.broken: set[str] = set()  # playlists answering 500
        self.quota = quota
        self.stop_body = QUOTA_BODY  # error once the quota is used up
        self.calls: list[str] = []

    def __call__(self, url, params, timeout):
        assert params["key"] == FAKE_KEY
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append(endpoint)
        if len(self.calls) > self.quota:
            return _response(self.stop_body, 403, "Forbidden")
        if endpoint == "playlistItems":
            playlist = params["playlistId"]
            if playlist in self.broken:
                return _response({"error": {"message": "boom"}}, 500, "Server Error")
            if playlist not in self.uploads and playlist not in self.shorts:
                return _response(NOT_FOUND_BODY, 404, "Not Found")
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
        playlist = params["playlistId"]
        if playlist in self.shorts:
            ids = self.shorts[playlist]
        else:
            ids = [v for v, _ in self.uploads[playlist]]
        return {"items": [{"contentDetails": {"videoId": v}} for v in ids]}

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


def test_resolve_skips_resolved_channels_at_no_cost(registry, youtube):
    registry("resolve", "zoo-zlin")
    youtube.calls.clear()
    result = registry("resolve", "zoo-zlin", "wrong", "--json")
    assert _statuses(result) == {"zoo-zlin": "already", "wrong": "not_found"}
    assert json.loads(result.stdout)["quota_units"] == 1
    assert youtube.calls == ["channels"]


def test_resolve_verify_same_id_is_already(registry, youtube):
    registry("resolve", "zoo-zlin")
    assert _statuses(registry("resolve", "zoo-zlin", "--verify", "--json")) == {
        "zoo-zlin": "already"
    }
    assert youtube.calls == ["channels", "channels"]


def test_resolve_mismatch_only_seen_with_verify(registry, youtube):
    registry("resolve", "zoo-zlin")
    youtube.handles["@zoozlin"] = "UCimpostor"
    assert _statuses(registry("resolve", "zoo-zlin", "--json")) == {
        "zoo-zlin": "already"
    }
    result = registry("resolve", "zoo-zlin", "--verify", "--json")
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
    # 3 resolves + 1 channels + 2 x (uploads + shorts playlist + videos)
    assert data["quota_units"] == 10
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
    assert "quota units used: 6" in result.stdout


def test_evidence_quota_exceeded_keeps_written_snapshots(registry, youtube, root):
    youtube.quota = 7  # 3 resolves, channels, zoo's 3 calls; bbc's first fails
    result = registry("evidence", "zoo-zlin", "bbc-earth", "wrong", "--json")
    assert result.exit_code == 1
    assert "quota" in result.stderr
    assert _statuses(result) == {
        "zoo-zlin": "written",
        "bbc-earth": "error",
        "wrong": "not_found",
    }
    assert list((root / "zoo-zlin" / "evidence").glob("*.yaml"))


def test_evidence_quota_at_channels_call_lists_every_channel(registry, youtube):
    youtube.quota = 2  # both resolves pass, the batched channels call fails
    result = registry("evidence", "zoo-zlin", "bbc-earth", "--json")
    assert result.exit_code == 1
    assert _statuses(result) == {"zoo-zlin": "not_fetched", "bbc-earth": "not_fetched"}


@pytest.mark.parametrize("command", ["resolve", "evidence"])
def test_quota_while_resolving_lists_every_channel(registry, youtube, command):
    youtube.quota = 1  # zoo resolves, bbc's resolve fails, wrong is never reached
    result = registry(command, "zoo-zlin", "bbc-earth", "wrong", "--json")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["aborted"]
    first = "resolved" if command == "resolve" else "not_fetched"
    assert _statuses(result) == {
        "zoo-zlin": first,
        "bbc-earth": "error",
        "wrong": "not_fetched",
    }


def test_evidence_missing_uploads_playlist_is_zero_videos(registry, youtube):
    youtube.uploads.pop("UUbbc")
    result = registry("evidence", "bbc-earth", "--json")
    assert result.exit_code == 0, result.stderr
    (bbc,) = json.loads(result.stdout)["results"]
    assert (bbc["status"], bbc["video_count"]) == ("written", 0)


def test_evidence_playlist_error_is_reported(registry, youtube):
    youtube.broken.add("UUbbc")
    result = registry("evidence", "bbc-earth", "zoo-zlin", "--json")
    assert result.exit_code == 1
    results = {r["slug"]: r for r in json.loads(result.stdout)["results"]}
    assert results["bbc-earth"]["message"].endswith("500 Server Error - boom")
    assert results["zoo-zlin"]["status"] == "written"


def test_evidence_no_uush_playlist_means_no_shorts(registry, youtube):
    youtube.uploads["UUbbc"] = [("b1", "PT30S")]  # short by duration, not a Short
    result = registry("evidence", "bbc-earth", "--json")
    (bbc,) = json.loads(result.stdout)["results"]
    assert (bbc["status"], bbc["shorts_count"]) == ("written", 0)


def test_evidence_shorts_from_uush(registry, youtube):
    youtube.uploads["UUzoo"] = [("v1", "PT10M"), ("v2", "PT45S")]  # v1 is a Short
    registry("evidence", "zoo-zlin")
    data = json.loads(registry("show", "zoo-zlin", "--json").stdout)["evidence"]
    assert data["shorts_source"] == "uush"
    assert [v["video_id"] for v in data["videos"] if v["is_short"]] == ["v1"]


def test_evidence_uush_error_falls_back_to_duration(registry, youtube):
    youtube.broken.add("UUSHzoo")
    result = registry("evidence", "zoo-zlin", "--json")
    assert result.exit_code == 0, result.stderr
    data = json.loads(registry("show", "zoo-zlin", "--json").stdout)["evidence"]
    assert data["shorts_source"] == "duration"
    assert [v["video_id"] for v in data["videos"] if v["is_short"]] == ["v1"]


def test_list_and_show_work_without_keys(registry):
    assert registry("list", "--json").exit_code == 0
    assert registry("show", "zoo-zlin").exit_code == 0


def test_invalid_key_stops_after_first_call(registry, youtube):
    youtube.quota = 0
    youtube.stop_body = {
        "error": {
            "message": "API key not valid.",
            "details": [{"reason": "API_KEY_INVALID"}],
        }
    }
    result = registry("resolve", "--all", "--json")
    assert result.exit_code == 1
    assert "API key not valid" in result.stderr
    assert youtube.calls == ["channels"]


def test_show_zero_subscribers_and_unknown_duration(registry, root):
    snapshot = Evidence(
        method="api",
        channel_id="UCzoo",
        title="Zoo",
        subscriber_count=0,
        videos=[
            EvidenceVideo(
                video_id="v",
                title="clip",
                published_at="2026-10-01T00:00:00Z",
                is_short=False,
            )
        ],
    )
    ChannelStore(root).add_evidence("zoo-zlin", snapshot)
    shown = registry("show", "zoo-zlin").stdout
    assert "subscribers: 0," in shown
    assert "2026-10-01  ?  clip" in shown
    assert "Nones" not in shown
