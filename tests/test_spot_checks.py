"""The spot-check queue: sections, order, snapshot vs current call (no I/O
except ``load_spot_checks``)."""

from pathlib import Path

import pytest

from happytube.channels.models import Status
from happytube.channels.store import ChannelStore
from happytube.trusted.player import StageRecord
from happytube.trusted.spot_checks import (
    in_section,
    load_spot_checks,
    new_review,
    original_description,
    queue_agreement,
    sections,
    spot_videos,
)
from happytube.trusted.video_reviews import NO_REVIEWS, ReviewState
from tests.player_helpers import (
    DAY,
    assess_fm,
    review_store,
    vid,
    vreview,
    write_shown,
)
from tests.trusted_helpers import add_channel

STATUSES: dict[str, Status] = {"zoo": "approved"}


def rec(fm: dict, body: str = "") -> StageRecord:
    return StageRecord(DAY, Path(f"a/{fm['video_id']}.md"), fm, body)


def enh(n: int) -> StageRecord:
    return rec(assess_fm(n) | {"enhanced_description": f"Calm {n}."})


def videos(states=None, *, unsuitable=(), assess_over=None):
    """Videos 1 to 4, all enhanced; ``unsuitable`` ones scored unsuitable."""
    assess = [
        rec(
            assess_fm(n, suitable=n not in unsuitable) | (assess_over or {}).get(n, {}),
            f"# Title {n}\n\nOriginal {n}.",
        )
        for n in (1, 2, 3, 4)
    ]
    return spot_videos(assess, [enh(n) for n in (1, 2, 3, 4)], STATUSES, states or {})


def ids(rows) -> list[str]:
    return [v.video_id for v in rows]


def test_sections_shown_first_then_other_unreviewed_then_reviewed():
    states = {vid(4): ReviewState([vreview()])}
    split = sections(videos(states, unsuitable={1}))
    got = {name: ids(rows) for name, rows in split.items()}
    assert got == {
        "shown": [vid(3), vid(2)],  # newest published first
        "unreviewed": [vid(1)],
        "reviewed": [vid(4)],
    }


def test_agent_review_alone_leaves_it_unreviewed():
    states = {vid(2): ReviewState([vreview("unsuitable", role="agent")])}
    by_id = {v.video_id: v for v in videos(states)}
    assert (by_id[vid(2)].section, by_id[vid(2)].shown) == ("shown", True)


def test_reviewed_order_unreadable_then_disagreements_then_newest():
    states = {
        vid(1): ReviewState([vreview("suitable", minutes=9)]),
        vid(2): ReviewState(error="broken"),
        vid(3): ReviewState([vreview("unsuitable", agent=True, minutes=1)]),
        vid(4): ReviewState([vreview("suitable", minutes=5)]),
    }
    assert ids(sections(videos(states))["reviewed"]) == [vid(2), vid(3), vid(1), vid(4)]


def test_unreadable_review_is_hidden_and_marked():
    [video] = [
        v for v in videos({vid(1): ReviewState(error="x")}) if v.video_id == vid(1)
    ]
    assert (video.shown, video.section, video.latest) == (False, "reviewed", None)


def test_human_suitable_on_agent_unsuitable_stays_hidden_and_disagrees():
    states = {vid(1): ReviewState([vreview("suitable", agent=False)])}
    video = videos(states, unsuitable={1})[-1]
    assert (video.video_id, video.shown, video.disagrees) == (vid(1), False, True)
    assert ids(in_section(videos(states, unsuitable={1}), "disagree")) == [vid(1)]


def test_rescore_after_review_keeps_the_snapshot_in_stats():
    # Reviewed "suitable" when the agent said suitable; since rescored unsuitable.
    states = {vid(1): ReviewState([vreview("suitable", agent=True)])}
    rescored = {1: {"suitable": False, "assessed_at": "2026-10-29T08:00:00Z"}}
    current = videos(states, unsuitable={1}, assess_over=rescored)
    video = next(v for v in current if v.video_id == vid(1))
    stats = queue_agreement(current)
    assert (video.assess_changed, video.disagrees) == (True, False)
    assert (stats.agree, stats.disagree) == (1, 0)


def test_same_call_is_not_rescored():
    states = {vid(1): ReviewState([vreview("suitable")])}
    assert not next(v for v in videos(states) if v.video_id == vid(1)).assess_changed


def test_orphan_reviews_are_not_in_the_queue_or_stats():
    states = {vid(9): ReviewState([vreview("unsuitable", agent=True)])}
    current = videos(states)
    assert vid(9) not in ids(current)
    assert queue_agreement(current).reviewed == 0


def test_assess_file_lacking_review_fields_is_skipped():
    fm = assess_fm(1)
    del fm["rubric_version"]
    assert spot_videos([rec(fm)], [], STATUSES, {}) == []


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("# Title 1\n\nGiraffes.\nMore.", "Giraffes.\nMore."),
        ("Giraffes.", "Giraffes."),
        ("# Other\n\nGiraffes.", "# Other\n\nGiraffes."),
        ("", ""),
    ],
)
def test_original_description_drops_the_title_heading(body, expected):
    assert original_description(body, "Title 1") == expected


def test_new_review_snapshots_the_current_call():
    video = videos(unsuitable={1})[-1]
    review = new_review(
        video,
        reviewer="mojzis",
        role="human",
        verdict="suitable",
        flags=["promo"],
        watched="part",
        notes=None,
    )
    snapshot = (review.agent_suitable, review.rubric_version, review.assessed_at)
    assert snapshot == (False, 1, video.assess.assessed_at)


def test_summary_and_detail_dicts():
    states = {vid(1): ReviewState([vreview("unsuitable", agent=True)])}
    video = next(v for v in videos(states) if v.video_id == vid(1))
    detail = video.detail_dict()
    picked = {k: detail[k] for k in ("section", "verdict", "disagrees", "shown")}
    assert picked == {
        "section": "reviewed",
        "verdict": "unsuitable",
        "disagrees": True,
        "shown": False,
    }
    assert (detail["description"], detail["enhanced_description"]) == (
        "Original 1.",
        "Calm 1.",
    )


def test_load_spot_checks_over_files(tmp_path):
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    write_shown(tmp_path / "stages", "zoo", 1)
    reviews = review_store(tmp_path)
    reviews.add_review(vid(1), vreview("unsuitable"))
    [video] = load_spot_checks(tmp_path / "stages", store, reviews)
    assert (video.shown, video.section, video.state is NO_REVIEWS) == (
        False,
        "reviewed",
        False,
    )
