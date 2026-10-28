"""``python -m happytube.web.export`` over temp dirs (no network)."""

import json
import logging
import subprocess
import sys

from happytube.channels.store import ChannelStore
from happytube.web.export import main
from tests.player_helpers import review_store, vid, vreview, write_shown
from tests.trusted_helpers import add_channel


def _args(tmp_path):
    return [
        "--stages-dir",
        str(tmp_path / "stages"),
        "--channels-dir",
        str(tmp_path / "channels"),
        "--video-reviews-dir",
        str(tmp_path / "video-reviews"),
        "--output",
        str(tmp_path / "out" / "videos.json"),
    ]


def test_export_writes_the_selection(tmp_path, caplog):
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    add_channel(store, "gone", "UCgone", verdict="reject")
    write_shown(tmp_path / "stages", "zoo", 1, text="Žirafy.")
    write_shown(tmp_path / "stages", "gone", 2)
    review_store(tmp_path)

    with caplog.at_level(logging.INFO):
        assert main(_args(tmp_path)) == 0

    data = json.loads((tmp_path / "out" / "videos.json").read_text(encoding="utf-8"))
    assert [(v["video_id"], v["description"]) for v in data] == [(vid(1), "Žirafy.")]
    assert "Exported 1 videos" in caplog.text


def test_export_missing_stages_dir_fails(tmp_path, caplog):
    ChannelStore(tmp_path / "channels").root.mkdir()
    assert main(_args(tmp_path)) == 1
    assert "trusted not found" in caplog.text
    assert not (tmp_path / "out").exists()


def test_export_missing_registry_fails(tmp_path):
    (tmp_path / "stages" / "trusted").mkdir(parents=True)
    assert main(_args(tmp_path)) == 1


def test_export_empty_selection_warns_and_succeeds(tmp_path, caplog):
    (tmp_path / "stages" / "trusted").mkdir(parents=True)
    (tmp_path / "channels").mkdir()
    review_store(tmp_path)
    with caplog.at_level(logging.WARNING):
        assert main(_args(tmp_path)) == 0
    assert json.loads((tmp_path / "out" / "videos.json").read_text()) == []
    assert "Exported 0 videos" in caplog.text


def _two_shown(tmp_path):
    add_channel(ChannelStore(tmp_path / "channels"), "zoo", "UCzoo")
    write_shown(tmp_path / "stages", "zoo", 1)
    write_shown(tmp_path / "stages", "zoo", 2)


def _exported_ids(tmp_path):
    data = json.loads((tmp_path / "out" / "videos.json").read_text(encoding="utf-8"))
    return [v["video_id"] for v in data]


def test_export_leaves_out_a_video_a_human_hid(tmp_path):
    _two_shown(tmp_path)
    review_store(tmp_path).add_review(vid(1), vreview("unsuitable"))
    assert main(_args(tmp_path)) == 0
    assert _exported_ids(tmp_path) == [vid(2)]


def test_export_missing_reviews_dir_fails(tmp_path, caplog):
    _two_shown(tmp_path)
    assert main(_args(tmp_path)) == 1
    assert "video-reviews not found" in caplog.text
    assert not (tmp_path / "out").exists()


def test_web_package_needs_no_flask():
    code = (
        "import sys, happytube.web, happytube.web.export, happytube.review.app; "
        "print('flask' in sys.modules)"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"
