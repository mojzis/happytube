from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from happytube.channels.evidence import (
    build_evidence,
    is_short,
    shorts_playlist_id,
    upload_video_ids,
)
from happytube.channels.models import Channel, Evidence
from happytube.channels.store import (
    ChannelExistsError,
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


NEW = datetime(2024, 10, 15, tzinfo=UTC)  # Shorts up to 3 min from here on
OLD = NEW - timedelta(seconds=1)


@pytest.mark.parametrize(
    ("duration_s", "published_at", "expected"),
    [
        (58, NEW, True),
        (180, NEW, True),
        (181, NEW, False),
        (60, OLD, True),
        (61, OLD, False),
        (129, OLD, False),
        (180, None, True),
        (0, NEW, False),
        (None, NEW, False),
    ],
)
def test_is_short_duration_fallback(duration_s, published_at, expected):
    assert is_short(duration_s, published_at) is expected


def test_shorts_playlist_id():
    assert shorts_playlist_id("UCabc-123") == "UUSHabc-123"


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
        "shorts_source": "duration",
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


def test_build_evidence_shorts_from_uush_ids():
    evidence = build_evidence(CHANNEL_ITEM, VIDEO_ITEMS, short_ids={"three-min"})
    assert evidence.shorts_source == "uush"
    assert [v.video_id for v in evidence.videos if v.is_short] == ["three-min"]


def test_build_evidence_empty_uush_means_no_shorts():
    evidence = build_evidence(CHANNEL_ITEM, VIDEO_ITEMS, short_ids=set())
    assert (evidence.shorts_source, evidence.shorts_count) == ("uush", 0)


def test_build_evidence_skips_video_without_publish_date():
    broken = _video("broken", "PT1M", "2026-01-01T00:00:00Z")
    del broken["snippet"]["publishedAt"]
    evidence = build_evidence(CHANNEL_ITEM, [*VIDEO_ITEMS, broken, {"snippet": {}}])
    assert len(evidence.videos) == len(VIDEO_ITEMS)


def test_old_snapshot_without_shorts_source_loads():
    data = _evidence().model_dump(mode="json")
    del data["shorts_source"]
    assert Evidence.model_validate(data).shorts_source == "duration"


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


def test_set_channel_id_keeps_hand_edited_file(store, tmp_path):
    path = tmp_path / "zoo-zlin" / "channel.yaml"
    path.write_text(
        "name: Zoo Zlín\nslug: zoo-zlin\nkind: zoo\nlanguages: [cs]\n"
        "handle: '@zoozlin'\nadded_by: me\nadded_at: '2026-01-01T00:00:00Z'\n",
        encoding="utf-8",
    )
    assert store.set_channel_id("zoo-zlin", "UCzoo")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert list(data) == [
        "name",
        "slug",
        "kind",
        "languages",
        "handle",
        "added_by",
        "added_at",
        "channel_id",
    ]
    assert data["added_at"] == "2026-01-01T00:00:00Z"
    assert "Zoo Zlín" in path.read_text(encoding="utf-8")


def test_set_channel_id_does_not_invent_added_at(store, tmp_path):
    path = tmp_path / "zoo-zlin" / "channel.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["added_at"]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    store.set_channel_id("zoo-zlin", "UCzoo")
    assert "added_at" not in yaml.safe_load(path.read_text(encoding="utf-8"))


def test_set_channel_id_refuses_id_of_another_channel(store, tmp_path):
    store.add(
        Channel(
            slug="other",
            name="Other",
            kind="zoo",
            languages=["cs"],
            channel_id="UCzoo",
            added_by="me",
        )
    )
    with pytest.raises(ChannelExistsError, match="already slug 'other'"):
        store.set_channel_id("zoo-zlin", "UCzoo")
    assert store.get_channel("zoo-zlin").channel_id is None


def test_set_channel_id_refuses_invalid_result(store):
    with pytest.raises(ValidationError):
        store.set_channel_id("zoo-zlin", "not-a-channel-id")
    assert store.get_channel("zoo-zlin").channel_id is None


def test_latest_evidence_reads_only_newest_file(store, tmp_path):
    store.add_evidence("zoo-zlin", _evidence(T0, "first"))
    store.add_evidence("zoo-zlin", _evidence(T0, "second"))
    store.add_evidence("zoo-zlin", _evidence(T0 - timedelta(days=1), "older"))
    (tmp_path / "zoo-zlin" / "evidence" / "20200101T000000Z.yaml").write_text(
        "not: [valid", encoding="utf-8"
    )
    assert store.latest_evidence("zoo-zlin").title == "second"


def test_set_channel_id_refuses_to_overwrite(store):
    store.set_channel_id("zoo-zlin", "UCzoo")
    with pytest.raises(ChannelIdMismatchError, match="not overwriting"):
        store.set_channel_id("zoo-zlin", "UCother")
    assert store.get_channel("zoo-zlin").channel_id == "UCzoo"
