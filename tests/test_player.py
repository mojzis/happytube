"""The player's selection rule (decision 0010), pure and over real files."""

import logging
from datetime import date
from pathlib import Path

import pytest

from happytube.channels.models import Status
from happytube.channels.store import ChannelStore
from happytube.trusted.player import (
    StageRecord,
    channel_statuses,
    player_videos,
    read_stage,
    select_videos,
    videos_json,
)
from happytube.trusted.stages import TrustedStage
from happytube.trusted.video_reviews import VideoReviewsMissingError, VideoReviewStore
from tests.player_helpers import DAY, assess_fm, review_store, vid, vreview, write
from tests.trusted_helpers import add_channel

LATER = date(2026, 10, 27)
APPROVED: dict[str, Status] = {
    "zoo": "approved",
    "gone": "rejected",
    "maybe": "candidate",
}


def rec(frontmatter: dict, day: date = DAY, name: str | None = None) -> StageRecord:
    stem = name or str(frontmatter.get("video_id"))
    return StageRecord(day, Path(f"stages/trusted/x/{day}/{stem}.md"), frontmatter)


def enh(n: int, text: object = "Calm giraffes.", day: date = DAY) -> StageRecord:
    return rec(
        {**assess_fm(n, calm=1, happy=1, title="stale"), "enhanced_description": text},
        day,
        vid(n),
    )


def shown_ids(assess, enhance, statuses=APPROVED, hidden=()) -> list[str]:
    return [v.video_id for v in select_videos(assess, enhance, statuses, hidden)]


@pytest.mark.parametrize(
    ("case", "assess", "enhance", "expected"),
    [
        ("suitable + enhanced", [rec(assess_fm(1))], [enh(1)], [vid(1)]),
        ("unsuitable", [rec(assess_fm(1, suitable=False))], [enh(1)], []),
        ("suitable as text", [rec(assess_fm(1, suitable="true"))], [enh(1)], []),
        ("enhance missing", [rec(assess_fm(1))], [], []),
        ("enhance empty", [rec(assess_fm(1))], [enh(1, "  ")], []),
        ("enhance not text", [rec(assess_fm(1))], [enh(1, ["x"])], []),
        ("rejected channel", [rec(assess_fm(1, channel_slug="gone"))], [enh(1)], []),
        ("candidate", [rec(assess_fm(1, channel_slug="maybe"))], [enh(1)], []),
        ("unknown channel", [rec(assess_fm(1, channel_slug="nope"))], [enh(1)], []),
        ("missing title", [rec(assess_fm(1, title=None))], [enh(1)], []),
        ("naive time", [rec(assess_fm(1, published_at="2026-10-11"))], [enh(1)], []),
        ("id != file", [rec(assess_fm(1), name=vid(2))], [enh(2)], []),
        ("bad id", [rec(assess_fm(1, video_id="x/y"), name="x")], [enh(1)], []),
        (
            "latest assess wins (now unsuitable)",
            [rec(assess_fm(1)), rec(assess_fm(1, suitable=False), LATER)],
            [enh(1)],
            [],
        ),
        (
            "latest assess wins (now suitable)",
            [rec(assess_fm(1, suitable=False)), rec(assess_fm(1), LATER)],
            [enh(1)],
            [vid(1)],
        ),
        (
            "broken latest copy hides it",
            [rec(assess_fm(1)), rec({"video_id": vid(1)}, LATER)],
            [enh(1)],
            [],
        ),
        (
            "latest enhance wins",
            [rec(assess_fm(1))],
            [enh(1), enh(1, "", LATER)],
            [],
        ),
        (
            "newest published first, one bad file skipped",
            [rec(assess_fm(1)), rec(assess_fm(3)), rec({"x": 1}, name=vid(9))],
            [enh(1), enh(3), enh(9)],
            [vid(3), vid(1)],
        ),
    ],
)
def test_selection_rule(case, assess, enhance, expected):
    assert shown_ids(assess, enhance) == expected, case


def test_fields_from_assess_and_description_from_enhance():
    [video] = select_videos(
        [rec(assess_fm(1))], [enh(1, "  Calm giraffes.\n")], APPROVED, ()
    )
    assert videos_json([video]) == [
        {
            "video_id": vid(1),
            "title": "Title 1",
            "channel_name": "Zoo",
            "channel_slug": "zoo",
            "published_at": "2026-10-11T10:00:00Z",
            "duration_s": 600,
            "description": "Calm giraffes.",
        }
    ]


def test_equal_published_at_sorted_by_id():
    same = "2026-10-11T10:00:00Z"
    assess = [rec(assess_fm(n, published_at=same)) for n in (2, 1)]
    assert shown_ids(assess, [enh(1), enh(2)]) == [vid(1), vid(2)]


def test_skipped_file_is_named_in_a_warning(caplog):
    bad = rec({"video_id": vid(1)})
    with caplog.at_level(logging.WARNING):
        assert shown_ids([bad], [enh(1)]) == []
    assert str(bad.path) in caplog.text


def test_read_stage_skips_unreadable_files(tmp_path, caplog):
    stages = tmp_path / "stages"
    good = write(stages, "assess", 1, assess_fm(1))
    broken = good.with_name(f"{vid(2)}.md")
    broken.write_text("---\nkey: [unclosed\n---\n", encoding="utf-8")
    plain = good.with_name(f"{vid(3)}.md")
    plain.write_text("---\n- a list\n---\n", encoding="utf-8")
    (stages / "trusted" / "assess" / "notes").mkdir()
    with caplog.at_level(logging.WARNING):
        records = read_stage(TrustedStage("assess", stages))
    assert [r.path for r in records] == [good]
    assert str(broken) in caplog.text
    assert str(plain) in caplog.text


def test_player_videos_over_files_and_registry(tmp_path):
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    add_channel(store, "gone", "UCgone", verdict="reject")
    add_channel(store, "maybe", "UCmaybe", verdict=None)
    stages = tmp_path / "stages"
    write(stages, "assess", 1, assess_fm(1))
    write(stages, "assess", 2, assess_fm(2, channel_slug="gone"))
    write(stages, "assess", 3, assess_fm(3, channel_slug="maybe"))
    write(stages, "assess", 4, assess_fm(4))  # suitable, not enhanced yet
    write(stages, "enhance", 1, dict(enh(1).frontmatter))
    write(stages, "enhance", 2, dict(enh(2).frontmatter))
    write(stages, "enhance", 3, dict(enh(3).frontmatter))
    assert channel_statuses(store) == {
        "gone": "rejected",
        "maybe": "candidate",
        "zoo": "approved",
    }
    reviews = review_store(tmp_path)
    assert [v.video_id for v in player_videos(stages, store, reviews)] == [vid(1)]


def test_channel_with_broken_reviews_is_hidden(tmp_path, caplog):
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    (store.root / "zoo" / "reviews" / "20990101T000000Z-x.yaml").write_text(
        "verdict: [", encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING):
        assert channel_statuses(store) == {}
    assert "zoo" in caplog.text


def test_missing_stage_dirs_mean_nothing_shown(tmp_path):
    store = ChannelStore(tmp_path / "channels")
    assert player_videos(tmp_path / "stages", store, review_store(tmp_path)) == []


def test_rule4_hidden_ids_never_shown():
    assess = [rec(assess_fm(1)), rec(assess_fm(2))]
    assert shown_ids(assess, [enh(1), enh(2)], hidden={vid(1)}) == [vid(2)]


def _shown_with_reviews(tmp_path, *reviews):
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    stages = tmp_path / "stages"
    write(stages, "assess", 1, assess_fm(1))
    write(stages, "enhance", 1, dict(enh(1).frontmatter))
    write(stages, "assess", 2, assess_fm(2, suitable=False))
    write(stages, "enhance", 2, dict(enh(2).frontmatter))
    videos = review_store(tmp_path)
    for n, review in reviews:
        videos.add_review(vid(n), review)
    return [v.video_id for v in player_videos(stages, store, videos)]


@pytest.mark.parametrize(
    ("case", "reviews", "expected"),
    [
        ("no reviews", [], [vid(1)]),
        ("human unsuitable hides", [(1, vreview("unsuitable"))], []),
        (
            "agent unsuitable ignored",
            [(1, vreview("unsuitable", role="agent"))],
            [vid(1)],
        ),
        ("unsure changes nothing", [(1, vreview("unsure"))], [vid(1)]),
        (
            "later human suitable shows again",
            [(1, vreview("unsuitable")), (1, vreview("suitable", minutes=1))],
            [vid(1)],
        ),
        ("suitable never overrides agent", [(2, vreview("suitable"))], [vid(1)]),
        ("orphan review hides nothing", [(9, vreview("unsuitable"))], [vid(1)]),
    ],
)
def test_rule4_over_review_files(tmp_path, case, reviews, expected):
    assert _shown_with_reviews(tmp_path, *reviews) == expected, case


def test_unreadable_review_hides_with_warning(tmp_path, caplog):
    bad = tmp_path / "video-reviews" / vid(1) / "20261028T120000Z-x.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text("verdict: [", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert _shown_with_reviews(tmp_path) == []
    assert str(bad) in caplog.text


def test_missing_reviews_dir_raises(tmp_path):
    store = ChannelStore(tmp_path / "channels")
    with pytest.raises(VideoReviewsMissingError):
        player_videos(tmp_path / "stages", store, VideoReviewStore(tmp_path / "no"))
