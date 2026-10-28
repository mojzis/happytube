from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import yaml

from happytube.channels.evidence import (
    build_evidence,
    is_short,
    upload_video_ids,
)
from happytube.channels.models import Channel, Evidence
from happytube.channels.store import (
    ChannelIdMismatchError,
    ChannelNotFoundError,
    ChannelStore,
)

T0 = datetime(2026, 10, 28, 19, 0, tzinfo=UTC)

# Shapes as returned by the YouTube Data API v3, trimmed by hand.
CHANNEL_ITEM: dict[str, Any] = {
    "kind": "youtube#channel",
    "id": "UCzoo",
    "snippet": {
        "title": "Zoo Zlín",
        "description": "Oficiální kanál Zoo Zlín. " * 100,
        "customUrl": "@zoozlin",
        "publishedAt": "2009-05-01T10:00:00Z",
        "country": "CZ",
    },
    "contentDetails": {"relatedPlaylists": {"likes": "", "uploads": "UUzoo"}},
    "statistics": {
        "viewCount": "1200000",
        "subscriberCount": "8500",
        "hiddenSubscriberCount": False,
        "videoCount": "412",
    },
}


def _video(video_id, duration, published, **snippet):
    return {
        "id": video_id,
        "snippet": {
            "publishedAt": published,
            "title": f"Video {video_id}",
            "description": "Žirafy " * 100,
            **snippet,
        },
        "contentDetails": {"duration": duration},
        "status": {"madeForKids": False},
    }


VIDEO_ITEMS = [
    _video("old", "PT12M", "2026-09-01T08:00:00Z", defaultLanguage="cs"),
    _video("short", "PT58S", "2026-10-20T08:00:00.5Z", defaultAudioLanguage="cs"),
    _video("live", "P0D", "2026-10-27T08:00:00Z"),
    _video("three-min", "PT3M", "2026-10-10T08:00:00Z"),
]


@pytest.mark.parametrize(
    ("duration_s", "expected"),
    [(58, True), (180, True), (181, False), (0, False), (None, False)],
)
def test_is_short_boundaries(duration_s, expected):
    assert is_short(duration_s) is expected


def test_upload_video_ids_keeps_order():
    items = [
        {"contentDetails": {"videoId": "a"}},
        {"snippet": {"resourceId": {"videoId": "b"}}},
        {"snippet": {"title": "Deleted video"}},
    ]
    assert upload_video_ids(items) == ["a", "b"]


def test_build_evidence_channel_fields():
    evidence = build_evidence(CHANNEL_ITEM, VIDEO_ITEMS, fetched_at=T0)
    fields = evidence.model_dump(exclude={"videos", "description"})
    assert fields == {
        "fetched_at": "2026-10-28T19:00:00Z",
        "method": "api",
        "channel_id": "UCzoo",
        "title": "Zoo Zlín",
        "custom_url": "@zoozlin",
        "country": "CZ",
        "published_at": "2009-05-01T10:00:00Z",
        "subscriber_count": 8500,
        "view_count": 1200000,
        "video_count": 412,
        "uploads_playlist_id": "UUzoo",
    }
    assert len(evidence.description) == 1000


def test_build_evidence_videos_newest_first_with_shorts():
    evidence = build_evidence(CHANNEL_ITEM, VIDEO_ITEMS, fetched_at=T0)
    rows = [(v.video_id, v.duration_s, v.is_short) for v in evidence.videos]
    assert rows == [
        ("live", 0, False),
        ("short", 58, True),
        ("three-min", 180, True),
        ("old", 720, False),
    ]


def test_build_evidence_video_details():
    evidence = build_evidence(CHANNEL_ITEM, VIDEO_ITEMS, fetched_at=T0)
    by_id = {v.video_id: v for v in evidence.videos}
    langs = [by_id[i].default_language for i in ("short", "old", "live")]
    assert langs == ["cs", "cs", None]
    assert by_id["old"].made_for_kids is False
    assert len(by_id["old"].description) == 300


def test_build_evidence_hidden_subscribers_and_bad_duration():
    channel = {
        **CHANNEL_ITEM,
        "statistics": {"viewCount": "1", "hiddenSubscriberCount": True},
    }
    evidence = build_evidence(channel, [_video("x", "nonsense", "2026-01-01T00:00Z")])
    assert evidence.subscriber_count is None
    assert evidence.videos[0].duration_s is None
    assert not evidence.videos[0].is_short


@pytest.fixture
def store(tmp_path):
    s = ChannelStore(tmp_path)
    s.add(
        Channel(
            slug="zoo-zlin",
            name="Zoo Zlín",
            kind="zoo",
            languages=["cs"],
            handle="@zoozlin",
            added_by="me",
        )
    )
    return s


def _evidence(fetched_at=T0, title="Zoo Zlín"):
    return build_evidence(
        {**CHANNEL_ITEM, "snippet": {**CHANNEL_ITEM["snippet"], "title": title}},
        VIDEO_ITEMS,
        fetched_at=fetched_at,
    )


def test_add_evidence_writes_readable_yaml(store, tmp_path):
    path = store.add_evidence("zoo-zlin", _evidence())
    assert path == tmp_path / "zoo-zlin" / "evidence" / "20261028T190000Z.yaml"
    text = path.read_text(encoding="utf-8")
    assert "Zoo Zlín" in text  # unicode stays literal
    data = yaml.safe_load(text)
    assert list(data)[:3] == ["fetched_at", "method", "channel_id"]
    assert Evidence.model_validate(data) == store.latest_evidence("zoo-zlin")


def test_add_evidence_is_append_only(store):
    first = store.add_evidence("zoo-zlin", _evidence(title="first"))
    second = store.add_evidence("zoo-zlin", _evidence(title="second"))
    assert first != second
    assert second.name == "20261028T190000Z-2.yaml"
    assert [e.title for e in store.evidence("zoo-zlin")] == ["first", "second"]
    assert store.latest_evidence("zoo-zlin").title == "second"


def test_latest_evidence_is_newest_fetched_at(store):
    store.add_evidence("zoo-zlin", _evidence(T0 + timedelta(hours=1), "newer"))
    store.add_evidence("zoo-zlin", _evidence(T0, "older"))
    assert store.latest_evidence("zoo-zlin").title == "newer"


def test_no_evidence(store):
    assert store.evidence("zoo-zlin") == []
    assert store.latest_evidence("zoo-zlin") is None
    entry = store.get("zoo-zlin")
    assert entry.summary_dict()["evidence_at"] is None
    assert entry.detail_dict()["evidence"] is None


def test_entry_dicts_carry_latest_evidence(store):
    store.add_evidence("zoo-zlin", _evidence())
    entry = store.get("zoo-zlin")
    assert entry.summary_dict()["evidence_at"] == "2026-10-28T19:00:00Z"
    detail = entry.detail_dict()["evidence"]
    assert detail["shorts_count"] == 2
    assert len(detail["videos"]) == 4


def test_add_evidence_unknown_channel(store):
    with pytest.raises(ChannelNotFoundError):
        store.add_evidence("nope", _evidence())


def test_set_channel_id_fills_null_once(store, tmp_path):
    before = (tmp_path / "zoo-zlin" / "channel.yaml").read_text(encoding="utf-8")
    written = [store.set_channel_id("zoo-zlin", "UCzoo") for _ in range(2)]
    after = (tmp_path / "zoo-zlin" / "channel.yaml").read_text(encoding="utf-8")
    assert written == [True, False]
    assert before.replace("channel_id: null", "channel_id: UCzoo") == after
    assert not list((tmp_path / "zoo-zlin").glob(".*tmp"))


def test_set_channel_id_refuses_to_overwrite(store):
    store.set_channel_id("zoo-zlin", "UCzoo")
    with pytest.raises(ChannelIdMismatchError, match="not overwriting"):
        store.set_channel_id("zoo-zlin", "UCother")
    assert store.get_channel("zoo-zlin").channel_id == "UCzoo"
