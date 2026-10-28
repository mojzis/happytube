from datetime import UTC, datetime, timedelta

import pytest
import yaml
from pydantic import ValidationError

from happytube.channels.models import Channel, Review, slugify
from happytube.channels.store import (
    ChannelExistsError,
    ChannelNotFoundError,
    ChannelStore,
    derive_status,
)

T0 = datetime(2026, 10, 28, 10, 15, tzinfo=UTC)


def _channel(slug="bbc-earth", **overrides):
    fields = {
        "slug": slug,
        "name": "BBC Earth",
        "kind": "broadcaster",
        "languages": ["en"],
        "added_by": "matous",
    }
    return Channel.model_validate(fields | overrides)


def _review(role="human", verdict="approve", minutes=0, reviewer="matous"):
    return Review(
        reviewer=reviewer,
        role=role,
        verdict=verdict,
        created_at=T0 + timedelta(minutes=minutes),
    )


@pytest.fixture
def store(tmp_path):
    return ChannelStore(tmp_path / "channels")


def test_no_reviews_is_candidate():
    assert derive_status([]) == "candidate"


def test_agent_approve_does_not_change_status():
    assert derive_status([_review(role="agent", verdict="approve")]) == "candidate"


def test_agent_reject_after_human_approve_keeps_approved():
    reviews = [_review(minutes=0), _review(role="agent", verdict="reject", minutes=5)]
    assert derive_status(reviews) == "approved"


def test_latest_human_verdict_wins_regardless_of_order():
    reviews = [_review(verdict="reject", minutes=10), _review(minutes=0)]
    assert derive_status(reviews) == "rejected"


def test_human_unsure_does_not_override_decision():
    reviews = [_review(minutes=0), _review(verdict="unsure", minutes=5)]
    assert derive_status(reviews) == "approved"


def test_review_filenames_never_collide(store):
    store.add(_channel())
    paths = [store.add_review("bbc-earth", _review()) for _ in range(3)]
    assert [p.name for p in paths] == [
        "20261028T101500Z-matous.yaml",
        "20261028T101500Z-matous-2.yaml",
        "20261028T101500Z-matous-3.yaml",
    ]
    assert len(store.reviews("bbc-earth")) == 3


def test_review_filename_uses_reviewer_slug(store):
    store.add(_channel())
    path = store.add_review("bbc-earth", _review(reviewer="Claude Vetter"))
    assert path.name == "20261028T101500Z-claude-vetter.yaml"


def test_reviews_are_chronological(store):
    store.add(_channel())
    store.add_review("bbc-earth", _review(verdict="reject", minutes=10))
    store.add_review("bbc-earth", _review(verdict="approve", minutes=0))
    entry = store.get("bbc-earth")
    assert [r.verdict for r in entry.reviews] == ["approve", "reject"]
    assert entry.status == "rejected"


def test_review_for_unknown_channel_fails(store):
    with pytest.raises(ChannelNotFoundError):
        store.add_review("nope", _review())


def test_duplicate_slug_is_refused(store):
    store.add(_channel())
    with pytest.raises(ChannelExistsError, match="slug 'bbc-earth'"):
        store.add(_channel())


def test_duplicate_channel_id_is_refused(store):
    store.add(_channel(channel_id="UCabc"))
    with pytest.raises(ChannelExistsError, match="channel id"):
        store.add(_channel(slug="other", channel_id="UCabc"))


def test_duplicate_handle_is_refused_case_insensitively(store):
    store.add(_channel(handle="@BBCEarth"))
    with pytest.raises(ChannelExistsError, match="handle"):
        store.add(_channel(slug="other", handle="@bbcearth"))


def test_unicode_round_trip(store):
    channel = _channel(
        slug="zoo-dvur-kralove", name="ZOO Dvůr Králové", kind="zoo", languages=["cs"]
    )
    path = store.add(channel)
    assert "Dvůr Králové" in path.read_text(encoding="utf-8")
    assert store.get_channel("zoo-dvur-kralove") == channel


def test_channel_yaml_keeps_field_order(store):
    path = store.add(_channel())
    keys = list(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert keys[:3] == ["slug", "name", "kind"]


def test_slugs_ignore_stray_directories(store):
    store.add(_channel())
    (store.root / "not-a-channel").mkdir()
    assert store.slugs() == ["bbc-earth"]


def test_missing_root_lists_nothing(tmp_path):
    assert ChannelStore(tmp_path / "missing").entries() == []


def test_summary_counts_reviews(store):
    store.add(_channel())
    store.add_review("bbc-earth", _review(role="agent", verdict="approve"))
    summary = store.get("bbc-earth").summary_dict()
    assert summary["status"] == "candidate"
    assert (summary["human_review_count"], summary["agent_review_count"]) == (0, 1)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Zoo Zlín", "zoo-zlin"),
        ("ZOO Dvůr Králové", "zoo-dvur-kralove"),
        ("ČT :D / Déčko", "ct-d-decko"),
        ("explore.org", "explore-org"),
    ],
)
def test_slugify(name, slug):
    assert slugify(name) == slug


@pytest.mark.parametrize(
    "overrides",
    [
        {"languages": ["de"]},
        {"languages": []},
        {"kind": "circus"},
        {"handle": "noat"},
        {"channel_id": "XYZ"},
        {"slug": "Not A Slug"},
    ],
)
def test_channel_validation_rejects_bad_fields(overrides):
    with pytest.raises(ValidationError):
        _channel(**overrides)
