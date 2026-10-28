from datetime import UTC, datetime, timedelta

import pytest
import yaml
from pydantic import ValidationError

from happytube.channels.models import Channel, Review, slugify
from happytube.channels.store import (
    ChannelExistsError,
    ChannelNotFoundError,
    ChannelStore,
    ChannelStoreError,
    derive_status,
    filter_entries,
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _review_yaml(verdict, created_at="2026-10-28T10:15:00Z"):
    return (
        f"reviewer: matous\nrole: human\nverdict: {verdict}\n"
        f"created_at: '{created_at}'\n"
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


def test_latest_human_verdict_wins_regardless_of_input_order():
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


@pytest.mark.parametrize("slug", ["../x", "/abs", "a/b", "..", ""])
def test_slugs_that_are_paths_are_refused(store, tmp_path, slug):
    outside = tmp_path / "x"
    _write(outside / "channel.yaml", "slug: x\n")
    with pytest.raises(ChannelNotFoundError, match="not a valid slug"):
        store.get(slug)
    with pytest.raises(ChannelNotFoundError):
        store.add_review(slug, _review())
    assert not (outside / "reviews").exists()


def test_absolute_path_slug_is_refused(store, tmp_path):
    victim = tmp_path / "victim"
    _write(victim / "channel.yaml", "slug: victim\n")
    with pytest.raises(ChannelNotFoundError):
        store.add_review(str(victim), _review())
    assert not (victim / "reviews").exists()


def test_malformed_channel_yaml_names_the_file(store):
    path = _write(store.root / "bbc-earth" / "channel.yaml", "slug: [unclosed\n")
    with pytest.raises(ChannelStoreError, match="invalid YAML") as exc:
        store.get("bbc-earth")
    assert str(path) in str(exc.value)


def test_malformed_review_yaml_names_the_file(store):
    store.add(_channel())
    path = _write(store.root / "bbc-earth" / "reviews" / "x.yaml", "a: [b\n")
    with pytest.raises(ChannelStoreError, match="invalid YAML") as exc:
        store.reviews("bbc-earth")
    assert str(path) in str(exc.value)


@pytest.mark.parametrize("text", ["- a list\n", "just a string\n", ""])
def test_non_mapping_yaml_names_the_file(store, text):
    path = _write(store.root / "bbc-earth" / "channel.yaml", text)
    with pytest.raises(ChannelStoreError, match="expected a YAML mapping") as exc:
        store.get_channel("bbc-earth")
    assert str(path) in str(exc.value)


def test_invalid_field_on_disk_names_file_and_field(store):
    path = store.add(_channel())
    path.write_text(
        path.read_text(encoding="utf-8").replace("broadcaster", "spaceship"),
        encoding="utf-8",
    )
    with pytest.raises(ChannelStoreError, match="kind") as exc:
        store.get_channel("bbc-earth")
    assert str(path) in str(exc.value)


def test_unknown_key_on_disk_is_refused(store):
    path = store.add(_channel())
    with path.open("a", encoding="utf-8") as f:
        f.write("chanel_id: UCabc\n")
    with pytest.raises(ChannelStoreError, match="chanel_id") as exc:
        store.get_channel("bbc-earth")
    assert str(path) in str(exc.value)


def test_unknown_review_key_is_refused(store):
    store.add(_channel())
    _write(
        store.root / "bbc-earth" / "reviews" / "r.yaml",
        _review_yaml("approve") + "verdikt: approve\n",
    )
    with pytest.raises(ChannelStoreError, match="verdikt"):
        store.reviews("bbc-earth")


def test_slug_must_match_directory(store):
    path = store.add(_channel())
    (store.root / "bbc-earth").rename(store.root / "zlin")
    with pytest.raises(ChannelStoreError, match="does not match its directory") as exc:
        store.get("zlin")
    assert str(store.root / "zlin" / "channel.yaml") in str(exc.value)
    assert not path.exists()


def test_broken_channel_fails_entries_and_add(store):
    store.add(_channel())
    _write(store.root / "broken" / "channel.yaml", "slug: [\n")
    with pytest.raises(ChannelStoreError, match="broken"):
        store.entries()
    with pytest.raises(ChannelStoreError, match="broken"):
        store.add(_channel(slug="other", handle="@x"))
    assert not (store.root / "other").exists()


def test_directory_without_channel_file_does_not_block_add(store):
    (store.root / "bbc-earth" / "reviews").mkdir(parents=True)
    path = store.add(_channel())
    assert store.get_channel("bbc-earth").slug == "bbc-earth"
    assert path.is_file()


def test_review_reviewer_without_letters_falls_back(store):
    store.add(_channel())
    path = store.add_review("bbc-earth", _review(reviewer="!!!"))
    assert path.name == "20261028T101500Z-reviewer.yaml"


def test_tied_reviews_last_written_decides():
    approve, reject = _review(verdict="approve"), _review(verdict="reject")
    assert derive_status([approve, reject]) == "rejected"
    assert derive_status([reject, approve]) == "approved"


def test_tied_reviews_ordered_by_collision_suffix(store):
    store.add(_channel())
    reviews_dir = store.root / "bbc-earth" / "reviews"
    stem = "20261028T101500Z-matous"
    # Written order: base, -2, ..., -10; a lexical sort would misplace -10 and base.
    _write(reviews_dir / f"{stem}-10.yaml", _review_yaml("reject"))
    _write(reviews_dir / f"{stem}-2.yaml", _review_yaml("unsure"))
    _write(reviews_dir / f"{stem}.yaml", _review_yaml("approve"))
    entry = store.get("bbc-earth")
    assert [r.verdict for r in entry.reviews] == ["approve", "unsure", "reject"]
    assert entry.status == "rejected"


def test_reviewer_slug_ending_in_digits_is_not_a_suffix(store):
    store.add(_channel())
    reviews_dir = store.root / "bbc-earth" / "reviews"
    _write(reviews_dir / "20261028T101500Z-bot-9.yaml", _review_yaml("approve"))
    _write(reviews_dir / "20261028T101500Z-bot-9-2.yaml", _review_yaml("reject"))
    assert store.get("bbc-earth").status == "rejected"


@pytest.fixture
def three_entries(store):
    """bbc-earth (en, human-approved), zoo-praha (cs+en, agent-reviewed), zoo-zlin."""
    store.add(_channel())
    store.add(_channel(slug="zoo-zlin", name="Zoo Zlín", kind="zoo", languages=["cs"]))
    store.add(
        _channel(slug="zoo-praha", name="Zoo Praha", kind="zoo", languages=["cs", "en"])
    )
    store.add_review("bbc-earth", _review())
    store.add_review("zoo-praha", _review(role="agent"))
    return store.entries()


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({}, ["bbc-earth", "zoo-praha", "zoo-zlin"]),
        ({"status": "approved"}, ["bbc-earth"]),
        ({"kind": "zoo", "language": "en"}, ["zoo-praha"]),
        ({"needs_human_review": True}, ["zoo-praha", "zoo-zlin"]),
        (
            {"status": "candidate", "language": "cs", "needs_human_review": True},
            ["zoo-praha", "zoo-zlin"],
        ),
    ],
)
def test_filter_entries(three_entries, filters, expected):
    assert [
        e.channel.slug for e in filter_entries(three_entries, **filters)
    ] == expected


def test_add_loses_race_cleanly(store, monkeypatch):
    store.add(_channel())
    # Simulate a writer that created channel.yaml after the duplicate check ran.
    monkeypatch.setattr(store, "_find_duplicate", lambda _channel: None)
    with pytest.raises(ChannelExistsError, match="slug 'bbc-earth'"):
        store.add(_channel(name="Other"))
    assert store.get_channel("bbc-earth").name == "BBC Earth"
