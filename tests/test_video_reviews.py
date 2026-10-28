"""Video review store, derived verdict and agreement (decision 0011)."""

import logging

import pytest
import yaml

from happytube.trusted.video_reviews import (
    NO_REVIEWS,
    ReviewState,
    VideoNotFoundError,
    VideoReviewsMissingError,
    VideoReviewStore,
    agreement,
    hidden_ids,
)
from tests.player_helpers import vid, vreview


@pytest.fixture
def store(tmp_path):
    (tmp_path / "video-reviews").mkdir()
    return VideoReviewStore(tmp_path / "video-reviews")


def _stored(store):
    review = vreview(
        "unsuitable", flags=["scary", "scary", "loud_fast"], notes="Jumpy start."
    )
    return review, store.add_review(vid(1), review)


def test_round_trip(store):
    review, _ = _stored(store)
    assert (store.reviews(vid(1)), store.video_ids()) == ([review], [vid(1)])


def test_file_name_is_stamp_and_reviewer(store):
    _, path = _stored(store)
    relative = path.relative_to(store.root).as_posix()
    assert relative == f"{vid(1)}/20261028T120000Z-mojzis.yaml"


def test_file_fields(store):
    _, path = _stored(store)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "created_at": "2026-10-28T12:00:00Z",
        "assessed_at": "2026-10-27T12:00:00Z",
        "flags": ["scary", "loud_fast"],
        "video_id": None,
    }
    assert {k: data.get(k) for k in expected} == expected


def test_same_second_never_overwrites(store):
    first = store.add_review(vid(1), vreview("unsuitable"))
    second = store.add_review(vid(1), vreview("suitable"))
    assert first != second
    assert second.name == "20261028T120000Z-mojzis-2.yaml"
    # Tie on created_at: filename order decides, so the later write wins.
    assert store.reviews(vid(1))[-1].verdict == "suitable"
    assert not store.states()[vid(1)].hidden


@pytest.mark.parametrize("bad", ["../x", "short", f"{vid(1)}/..", "a" * 12, ""])
def test_invalid_id_refused_before_any_path(store, bad):
    with pytest.raises(VideoNotFoundError):
        store.add_review(bad, vreview())
    with pytest.raises(VideoNotFoundError):
        store.reviews(bad)
    assert list(store.root.iterdir()) == []


def test_missing_root_is_an_error_not_empty(tmp_path):
    store = VideoReviewStore(tmp_path / "nope")
    for call in (store.states, lambda: store.add_review(vid(1), vreview())):
        with pytest.raises(VideoReviewsMissingError, match="nope"):
            call()
    assert not (tmp_path / "nope").exists()


@pytest.mark.parametrize(
    ("reviews", "hidden"),
    [
        ([], False),
        ([vreview("unsuitable")], True),
        ([vreview("unsuitable"), vreview("suitable", minutes=1)], False),
        ([vreview("suitable"), vreview("unsuitable", minutes=1)], True),
        ([vreview("unsuitable"), vreview("unsure", minutes=1)], False),
        ([vreview("unsuitable", role="agent")], False),
        ([vreview("unsuitable"), vreview("suitable", role="agent", minutes=1)], True),
    ],
)
def test_latest_human_decides(reviews, hidden):
    assert ReviewState(reviews).hidden is hidden


def test_out_of_order_files_sorted_by_created_at(store):
    store.add_review(vid(1), vreview("unsuitable", minutes=5))
    store.add_review(vid(1), vreview("suitable", minutes=1))
    assert store.states()[vid(1)].latest_human.verdict == "unsuitable"


def test_malformed_file_hides_with_warning(store, caplog):
    store.add_review(vid(1), vreview("suitable"))
    bad = store.root / vid(1) / "20261028T130000Z-x.yaml"
    bad.write_text("verdict: [", encoding="utf-8")
    (store.root / vid(2)).mkdir()
    (store.root / vid(2) / "20261028T130000Z-x.yaml").write_text(
        "reviewer: x\nverdikt: suitable\n", encoding="utf-8"
    )
    (store.root / "README.md").write_text("docs", encoding="utf-8")
    (store.root / "not-an-id").mkdir()
    with caplog.at_level(logging.WARNING):
        states = store.states()
    assert hidden_ids(states) == {vid(1), vid(2)}
    assert str(bad) in caplog.text
    assert "not-an-id" in caplog.text
    assert states[vid(1)].error is not None


def test_agreement_uses_snapshot_and_latest_human():
    states = [
        ReviewState([vreview("suitable", agent=True)]),
        ReviewState([vreview("unsuitable", agent=False)]),
        ReviewState([vreview("suitable", agent=False)]),
        ReviewState([vreview("unsuitable", agent=True)]),
        ReviewState([vreview("unsure", agent=True)]),
        ReviewState([vreview("unsuitable"), vreview("suitable", minutes=1)]),
        ReviewState([vreview("unsuitable", role="agent", agent=True)]),
        ReviewState(error="broken"),
        NO_REVIEWS,
    ]
    stats = agreement(states)
    assert (stats.reviewed, stats.agree, stats.disagree, stats.unsure) == (6, 3, 2, 1)
    assert stats.rate == pytest.approx(0.6)
    assert stats.as_dict()["matrix"]["suitable"] == {
        "agent_suitable": 2,
        "agent_unsuitable": 1,
    }
    assert agreement([]).rate is None


@pytest.mark.parametrize(
    ("verdict", "agent", "disagrees"),
    [
        ("suitable", True, False),
        ("suitable", False, True),
        ("unsuitable", True, True),
        ("unsure", False, False),
    ],
)
def test_disagrees(verdict, agent, disagrees):
    assert vreview(verdict, agent=agent).disagrees is disagrees


def test_model_refuses_unknown_keys_and_flags():
    with pytest.raises(ValueError, match="extra"):
        vreview(extra="x")
    with pytest.raises(ValueError, match="flags"):
        vreview(flags=["kittens"])
    with pytest.raises(ValueError, match="agent_suitable"):
        vreview(agent="yes")
