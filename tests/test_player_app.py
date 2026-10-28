"""The player routes of the local app (TestClient, no server, no network)."""

from fastapi.testclient import TestClient

from happytube.channels.models import Review
from happytube.channels.store import ChannelStore
from happytube.review.app import create_app
from tests.player_helpers import PLAYER, PLAYER_BARE, PLAYER_JSON, vid, write_shown
from tests.review_helpers import BASE_URL
from tests.trusted_helpers import add_channel

FIELDS = {
    "video_id",
    "title",
    "channel_name",
    "channel_slug",
    "published_at",
    "duration_s",
    "description",
}


def _client(tmp_path, base_url=BASE_URL) -> TestClient:
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    add_channel(store, "gone", "UCgone", verdict="reject")
    stages = tmp_path / "stages"
    write_shown(stages, "zoo", 1)
    write_shown(stages, "gone", 2)
    app = create_app(store, default_reviewer=None, stages_dir=stages)
    return TestClient(app, base_url=base_url)


def test_player_page_is_html(tmp_path):
    response = _client(tmp_path).get(PLAYER)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'src="player.js"' in response.text


def test_player_without_slash_redirects_to_page(tmp_path):
    response = _client(tmp_path).get(PLAYER_BARE, follow_redirects=False)
    assert response.headers["location"].endswith(PLAYER)


def test_player_assets_served(tmp_path):
    client = _client(tmp_path)
    assert client.get(PLAYER + "player.js").status_code == 200
    assert client.get(PLAYER + "styles.css").status_code == 200


def test_videos_json_is_the_live_selection(tmp_path):
    response = _client(tmp_path).get(PLAYER_JSON)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    [video] = response.json()
    assert set(video) == FIELDS
    assert (video["video_id"], video["description"]) == (vid(1), "Calm giraffes.")


def test_videos_json_follows_a_later_reject(tmp_path):
    client = _client(tmp_path)
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo2", "UCzoo2")
    write_shown(tmp_path / "stages", "zoo2", 3)
    assert {v["channel_slug"] for v in client.get(PLAYER_JSON).json()} == {
        "zoo",
        "zoo2",
    }
    store.add_review("zoo2", Review(reviewer="me", role="human", verdict="reject"))
    assert [v["channel_slug"] for v in client.get(PLAYER_JSON).json()] == ["zoo"]


def test_videos_json_empty_without_stages(tmp_path):
    store = ChannelStore(tmp_path / "channels")
    app = create_app(store, default_reviewer=None, stages_dir=tmp_path / "none")
    assert TestClient(app, base_url=BASE_URL).get(PLAYER_JSON).json() == []


def test_player_behind_host_guard(tmp_path):
    client = _client(tmp_path, base_url="http://evil.example")
    assert client.get(PLAYER).status_code == 400
    assert client.get(PLAYER_JSON).status_code == 400
