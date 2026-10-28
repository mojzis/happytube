"""``happytube videos`` over temp dirs (no network, no keys)."""

import json
import logging
import re

import pytest
from click.testing import CliRunner

from happytube.channels.store import ChannelStore
from happytube.cli.commands import cli
from tests.player_helpers import (
    assess_fm,
    review_store,
    vid,
    vreview,
    write,
    write_shown,
)
from tests.trusted_helpers import add_channel


@pytest.fixture
def run(tmp_path, monkeypatch):
    """``happytube videos …`` with video 1 shown and 2 scored unsuitable."""
    for env in (
        "HAPPYTUBE_CHANNELS_DIR",
        "HAPPYTUBE_STAGES_DIR",
        "HAPPYTUBE_VIDEO_REVIEWS_DIR",
    ):
        monkeypatch.delenv(env, raising=False)
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    write_shown(tmp_path / "stages", "zoo", 1)
    write(tmp_path / "stages", "assess", 2, assess_fm(2, suitable=False))
    review_store(tmp_path)
    dirs = [
        "--channels-dir",
        str(tmp_path / "channels"),
        "--stages-dir",
        str(tmp_path / "stages"),
        "--video-reviews-dir",
        str(tmp_path / "video-reviews"),
    ]

    def _run(*args):
        return CliRunner().invoke(cli, ["videos", *dirs, *args])

    return _run


def _json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _review(run, n=1, verdict="unsuitable", *extra):
    return run(
        "review",
        vid(n),
        "--reviewer",
        "mojzis",
        "--role",
        "human",
        "--verdict",
        verdict,
        "--watched",
        "full",
        "--json",
        *extra,
    )


def test_list_json_in_queue_order(run):
    rows = _json(run("list", "--json"))
    assert [(r["video_id"], r["section"], r["shown"]) for r in rows] == [
        (vid(1), "shown", True),
        (vid(2), "unreviewed", False),
    ]


def test_list_section_filter(run):
    assert [
        r["video_id"] for r in _json(run("list", "--section", "unreviewed", "--json"))
    ] == [vid(2)]


def test_list_plain_table(run):
    result = run("list")
    assert result.exit_code == 0
    assert vid(1) in result.output


def test_review_json_writes_and_hides(run, tmp_path):
    data = _json(_review(run, 1, "unsuitable", "--flag", "scary", "--notes", "Jumpy."))
    review = data["review"]
    assert (data["shown"], data["verdict"]) == (False, "unsuitable")
    assert (review["flags"], review["agent_suitable"]) == (["scary"], True)
    assert data["path"].startswith(str(tmp_path / "video-reviews" / vid(1)))


def test_reviewed_video_moves_to_reviewed(run):
    _review(run, 1)
    rows = _json(run("list", "--section", "reviewed", "--json"))
    assert [r["video_id"] for r in rows] == [vid(1)]


def test_review_agent_role_changes_nothing(run):
    result = run(
        "review", vid(1), "--reviewer", "claude", "--role", "agent",
        "--verdict", "unsuitable", "--watched", "title", "--json",
    )  # fmt: skip
    assert (_json(result)["shown"], _json(result)["verdict"]) == (True, None)


def test_show_json_has_reviews_and_both_descriptions(run):
    _review(run, 2, "suitable")
    detail = _json(run("show", vid(2), "--json"))
    assert (detail["disagrees"], detail["shown"], len(detail["reviews"])) == (
        True,
        False,
        1,
    )
    assert (detail["description"], detail["enhanced_description"]) == (
        "Original text 2.",
        None,
    )


def test_show_plain(run):
    _review(run, 1)
    result = run("show", vid(1))
    assert result.exit_code == 0
    assert "mojzis (human): unsuitable" in result.output
    assert "assessed 2026-10-27 12:00 UTC" in result.output


def test_show_plain_times_are_minutes_not_microseconds(run):
    _review(run, 1)
    output = run("show", vid(1)).output
    assert re.search(r"^  \d{4}-\d\d-\d\d \d\d:\d\d UTC  mojzis", output, re.M)
    assert not re.search(r"\d\d:\d\d:\d\d\.\d+", output)


def test_stats_json(run):
    _review(run, 1, "unsuitable")
    _review(run, 2, "unsuitable")
    stats = _json(run("stats", "--json"))
    picked = {
        k: stats[k] for k in ("assessed", "reviewed", "agree", "disagree", "rate")
    }
    assert picked == {
        "assessed": 2,
        "reviewed": 2,
        "agree": 1,
        "disagree": 1,
        "rate": 0.5,
    }


def test_stats_plain(run):
    result = run("stats")
    assert result.exit_code == 0
    assert "spot-checked 0 of 2" in result.output


@pytest.mark.parametrize("bad", ["../x", "short"])
def test_invalid_id_is_a_clean_error(run, bad, tmp_path):
    result = run("show", bad)
    assert result.exit_code == 1
    assert "not a valid video id" in result.stderr
    assert "Traceback" not in result.output


def test_unknown_id_is_an_error(run):
    result = _review(run, 9)
    assert result.exit_code == 1
    assert "No assessed video" in result.stderr


def test_watched_is_required(run):
    result = run(
        "review", vid(1), "--reviewer", "m", "--role", "human", "--verdict", "unsure"
    )
    assert result.exit_code == 2
    assert "--watched" in result.stderr


def test_missing_reviews_dir_fails(tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "videos",
            "--video-reviews-dir",
            str(tmp_path / "nope"),
            "--stages-dir",
            str(tmp_path),
            "list",
        ],
    )
    assert result.exit_code == 1
    assert "nope" in result.stderr


def test_malformed_review_listed_as_unreadable(run, tmp_path):
    bad = tmp_path / "video-reviews" / vid(1) / "20261028T120000Z-x.yaml"
    bad.parent.mkdir()
    bad.write_text("verdict: [", encoding="utf-8")
    [row] = _json(run("list", "--section", "reviewed", "--json"))
    assert (row["video_id"], row["shown"]) == (vid(1), False)
    assert str(bad) in row["review_error"]


def test_orphan_review_does_not_crash(run, tmp_path):
    review_store(tmp_path).add_review(vid(9), vreview())
    assert len(_json(run("list", "--json"))) == 2


def test_bad_assess_file_warned_once_per_command(run, tmp_path, caplog):
    write(tmp_path / "stages", "assess", 3, assess_fm(3, suitable="maybe"))
    with caplog.at_level(logging.WARNING):
        _json(_review(run))
    assert caplog.text.count(f"{vid(3)}.md") == 1
