"""``happytube trusted`` against a fake YouTube and a fake Claude (no network)."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from happytube.channels.store import ChannelStore
from happytube.claude import ClaudeCallError, ClaudeStoppingError
from happytube.cli import trusted as trusted_cli
from happytube.cli.commands import cli
from happytube.models.markdown import MarkdownFile
from happytube.youtube import YouTubeClient
from tests.trusted_helpers import (
    FAKE_KEY,
    TARGET,
    FakeClaude,
    FakeYouTube,
    add_channel,
    video,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ("YTKEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HAPPYTUBE_CHANNELS_DIR", str(tmp_path / "channels"))
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    add_channel(store, "earth", "UCearth")
    add_channel(store, "maybe", "UCmaybe", verdict=None)  # candidate
    add_channel(store, "bad", "UCbad", verdict="reject")
    return store


@pytest.fixture
def youtube(monkeypatch):
    fake = FakeYouTube()
    fake.uploads = {
        "UCzoo": [
            video("zoo-video-1"),
            video("zoo-video-2", "PT45S"),
            video("zoo-video-3"),
        ],
        "UCearth": [video("earth-vid-1", "PT1H")],
        "UCmaybe": [video("maybe-vid-1")],
        "UCbad": [video("bad-video-1")],
    }
    fake.shorts = {"UCzoo": ["zoo-video-2"]}
    monkeypatch.setattr(
        trusted_cli, "make_youtube_client", lambda: YouTubeClient(FAKE_KEY, get=fake)
    )
    return fake


@pytest.fixture
def claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(trusted_cli, "make_claude_caller", lambda: fake)
    return fake


def _run(*args):
    return CliRunner().invoke(cli, ["trusted", *args])


def _json(result):
    return json.loads(result.stdout)


def _stage_dir(stage, day=TARGET):
    return Path("stages") / "trusted" / stage / day  # under the test's tmp_path


def _ids(stage):
    return sorted(p.stem for p in _stage_dir(stage).glob("*.md"))


def _by_slug(data):
    return {r["slug"]: r for r in data["results"]}


# --- fetch ------------------------------------------------------------------


def test_fetch_writes_only_approved_long_form_videos(store, youtube):
    result = _run("fetch", "--date", TARGET, "--json")
    assert result.exit_code == 0, result.stderr
    data = _json(result)
    assert sorted(_by_slug(data)) == ["earth", "zoo"]  # no candidate, no rejected
    assert _ids("fetch") == ["earth-vid-1", "zoo-video-1", "zoo-video-3"]
    zoo = _by_slug(data)["zoo"]
    assert (zoo["new"], zoo["shorts"], zoo["shorts_source"]) == (2, 1, "uush")
    assert data["quota_units"] == 6  # uploads, UUSH, videos per channel


def test_fetch_file_has_the_frontmatter_and_full_description(store, youtube):
    long_text = "Žirafa. " * 200
    youtube.uploads["UCearth"] = [video("earth-vid-1", desc=long_text)]
    _run("fetch", "--date", TARGET)
    md = MarkdownFile.load(_stage_dir("fetch") / "earth-vid-1.md")
    assert md.frontmatter == md.frontmatter | {
        "video_id": "earth-vid-1",
        "channel_slug": "earth",
        "channel_id": "UCearth",
        "channel_name": "Earth",
        "languages": ["cs"],
        "published_at": "2026-10-25T10:00:00Z",
        "duration_s": 600,
        "shorts_source": "uush",  # no UUSH playlist (404): no Shorts
        "stage": "trusted_fetch",
    }
    assert md.content == f"# Video earth-vid-1\n\n{long_text.strip()}"


def test_shorts_by_duration_when_uush_unreadable(store, youtube):
    youtube.broken.add("UUSHzoo")
    data = _json(_run("fetch", "zoo", "--date", TARGET, "--json"))
    zoo = _by_slug(data)["zoo"]
    assert (zoo["shorts"], zoo["shorts_source"]) == (1, "duration")
    assert _ids("fetch") == ["zoo-video-1", "zoo-video-3"]


def test_window_live_and_upcoming_are_left_out(store, youtube):
    youtube.uploads["UCearth"] = [
        video("old-video-1", published="2026-10-13T10:00:00Z"),  # 15 days back
        video("edge-video1", published="2026-10-14T10:00:00Z"),  # 14 days back
        video("future-vid1", published="2026-10-29T10:00:00Z"),
        video("live-video1", "P0D", live="live"),
        video("soon-video1", "P0D", live="upcoming"),
    ]
    data = _json(_run("fetch", "earth", "--date", TARGET, "--json"))
    earth = _by_slug(data)["earth"]
    assert (earth["outside_window"], earth["live"], earth["new"]) == (2, 2, 1)
    assert _ids("fetch") == ["edge-video1"]
    narrow = _json(
        _run("fetch", "zoo", "--date", TARGET, "--since-days", "2", "--json")
    )
    assert _by_slug(narrow)["zoo"]["outside_window"] == 2


def test_rerun_same_date_is_idempotent(store, youtube):
    _run("fetch", "--date", TARGET)
    before = {p: p.read_text() for p in _stage_dir("fetch").glob("*.md")}
    again = _json(_run("fetch", "--date", TARGET, "--json"))
    zoo = _by_slug(again)["zoo"]
    assert (again["new"], zoo["seen"], zoo["shorts"]) == (0, 2, 1)
    assert {p: p.read_text() for p in _stage_dir("fetch").glob("*.md")} == before


def test_later_date_skips_videos_seen_on_earlier_dates(store, youtube):
    _run("fetch", "--date", TARGET)
    youtube.uploads["UCzoo"].insert(
        0, video("zoo-video-0", published="2026-10-29T08:00:00Z")
    )
    later = _json(_run("fetch", "--date", "2026-10-29", "--json"))
    written = sorted(p.stem for p in _stage_dir("fetch", "2026-10-29").glob("*.md"))
    assert (later["new"], written) == (1, ["zoo-video-0"])


def test_named_channel_must_be_approved(store, youtube):
    result = _run("fetch", "maybe", "--date", TARGET, "--json")
    assert result.exit_code == 1
    assert "'maybe' is candidate, not approved" in result.stderr
    assert youtube.calls == []
    assert "'bad' is rejected" in _run("fetch", "zoo", "bad").stderr


def test_unresolved_approved_channel_is_reported(store, youtube):
    add_channel(store, "nameless", None)
    result = _run("fetch", "nameless", "--date", TARGET, "--json")
    assert result.exit_code == 0
    assert _json(result)["results"][0]["status"] == "skipped_unresolved"
    assert youtube.calls == []


def test_quota_stop_keeps_files_and_fails(store, youtube):
    youtube.quota = 4  # earth (3 calls) done, zoo stops on its UUSH call
    result = _run("fetch", "--date", TARGET, "--json")
    data = _json(result)
    assert (result.exit_code, [r["status"] for r in data["results"]]) == (
        1,
        ["fetched", "error"],
    )
    assert data["aborted"].startswith("YouTube playlistItems request failed: 403")
    assert _ids("fetch") == ["earth-vid-1"]


def test_quota_stop_message_is_on_stderr_without_the_key(store, youtube):
    youtube.quota = 4
    result = _run("fetch", "--date", TARGET)
    assert "Stopped early: YouTube playlistItems request failed" in result.stderr
    assert FAKE_KEY not in result.output


def test_quota_stop_lists_unreached_channels_as_not_fetched(store, youtube):
    youtube.quota = 0
    data = _json(_run("fetch", "--date", TARGET, "--json"))
    assert [(r["status"], r["channel_id"]) for r in data["results"]] == [
        ("error", "UCearth"),
        ("not_fetched", "UCzoo"),
    ]


def test_channel_error_fails_the_run_but_others_are_written(store, youtube):
    youtube.broken.add("UUearth")
    result = _run("fetch", "--date", TARGET)
    assert result.exit_code == 1
    assert "earth: error — YouTube playlistItems request failed: 500" in result.stdout
    assert "Some items failed; see the report above" in result.stderr
    assert _ids("fetch") == ["zoo-video-1", "zoo-video-3"]


def test_channel_with_no_uploads_is_zero_new(store, youtube):
    youtube.uploads["UCearth"] = []
    result = _run("fetch", "earth", "--date", TARGET, "--json")
    assert result.exit_code == 0
    assert _json(result)["new"] == 0


def test_unknown_slug_is_reported_before_the_missing_key(store):
    result = _run("fetch", "nope", "--date", TARGET)
    assert result.exit_code == 1
    assert "nope" in result.stderr
    assert "YTKEY" not in result.stderr


def test_video_with_a_bad_id_is_unreadable_not_written(store, youtube):
    youtube.uploads["UCearth"] = [video("../../evil1"), video("earth-vid-1")]
    data = _json(_run("fetch", "earth", "--date", TARGET, "--json"))
    assert (_by_slug(data)["earth"]["unreadable"], _ids("fetch")) == (
        1,
        ["earth-vid-1"],
    )
    assert not list(Path("stages").rglob("evil1*"))


def test_fetch_needs_ytkey(store):
    result = _run("fetch", "--date", TARGET)
    assert result.exit_code == 1
    assert "YTKEY is not set" in result.stderr


def test_bad_date_is_a_usage_error(store):
    result = _run("status", "--date", "28.10.2026")
    assert result.exit_code == 2
    assert "is not a date; use YYYY-MM-DD" in result.stderr


# --- assess / enhance via the CLI -------------------------------------------


def test_assess_dry_run_needs_no_key(store, youtube):
    _run("fetch", "--date", TARGET)
    result = _run("assess", "--date", TARGET, "--dry-run", "--json")
    assert result.exit_code == 0, result.stderr
    data = _json(result)
    assert (data["dry_run"], [r["status"] for r in data["results"]]) == (
        True,
        ["would_run", "would_run"],
    )
    assert not _stage_dir("assess").exists()


def test_nothing_to_assess_needs_no_key(store):
    result = _run("assess", "--date", TARGET, "--json")
    assert result.exit_code == 0, result.stderr
    assert _json(result)["results"] == []


def test_assess_without_key_is_a_clean_error(store, youtube):
    _run("fetch", "--date", TARGET)
    result = _run("assess", "--date", TARGET)
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY is not set" in result.stderr
    assert "Traceback" not in result.stderr


def test_assess_then_enhance_report_tokens_and_cost(store, youtube, claude):
    claude.scores = {"zoo-video-3": (3, 4, [])}
    _run("fetch", "--date", TARGET)
    assess = _run("assess", "--date", TARGET)
    assert assess.exit_code == 0, assess.stderr
    assert "zoo: done 2 video(s), 1 suitable (claude-opus-5-5)" in assess.stdout
    assert "tokens: 2000 in, 400 out, est. $0.02" in assess.stdout
    enhance = _json(_run("enhance", "--date", TARGET, "--json"))
    assert [r["video_ids"] for r in enhance["results"]] == [
        ["earth-vid-1"],
        ["zoo-video-1"],
    ]
    assert (enhance["input_tokens"], enhance["usd"]) == (2000, 0.016)


def test_stopping_error_exits_non_zero_with_json(store, youtube, monkeypatch):
    _run("fetch", "--date", TARGET)
    fake = FakeClaude(errors={0: ClaudeStoppingError("Anthropic API 401 nope")})
    monkeypatch.setattr(trusted_cli, "make_claude_caller", lambda: fake)
    result = _run("assess", "--date", TARGET, "--json")
    assert result.exit_code == 1
    data = _json(result)
    assert data["aborted"] == "Anthropic API 401 nope"
    assert [r["status"] for r in data["results"]] == ["error", "not_run"]
    assert "Stopped early: Anthropic API 401 nope" in result.stderr


# --- run / status -----------------------------------------------------------


def test_run_chains_fetch_assess_enhance(store, youtube, claude):
    result = _run("run", "--date", TARGET, "--json")
    assert result.exit_code == 0, result.stderr
    data = _json(result)
    assert (data["fetch"]["new"], len(data["assess"]["results"])) == (3, 2)
    assert len(data["enhance"]["results"]) == 3
    status = _json(_run("status", "--date", TARGET, "--json"))
    assert status["totals"] == {
        "fetched": 3,
        "assessed": 3,
        "suitable": 3,
        "enhanced": 3,
    }


def test_run_goes_on_past_a_channel_error(store, youtube, claude):
    youtube.broken.add("UUearth")
    result = _run("run", "--date", TARGET, "--json")
    assert result.exit_code == 1
    data = _json(result)
    assert [r["video_ids"] for r in data["assess"]["results"]] == [
        ["zoo-video-1", "zoo-video-3"]
    ]
    assert _ids("enhance") == ["zoo-video-1", "zoo-video-3"]
    assert "Some items failed in fetch; see the JSON on stdout" in result.stderr


def test_video_left_by_a_failed_day_is_assessed_the_next_day(store, youtube, claude):
    youtube.broken.add("UUearth")
    _run("fetch", "--date", TARGET)  # zoo written, earth failed: exit 1
    youtube.broken.clear()
    result = _run("run", "--date", "2026-10-29", "--json")
    assert result.exit_code == 0, result.stderr
    assessed = _json(result)["assess"]["results"]
    assert sorted(i for r in assessed for i in r["video_ids"]) == [
        "earth-vid-1",
        "zoo-video-1",
        "zoo-video-3",
    ]
    # zoo's videos land under the date they were fetched on
    assert _ids("assess") == _ids("enhance") == ["zoo-video-1", "zoo-video-3"]
    assert _json(_run("status", "--date", TARGET, "--json"))["totals"] == {
        "fetched": 2,
        "assessed": 2,
        "suitable": 2,
        "enhanced": 2,
    }


def test_run_stops_on_a_quota_stop(store, youtube, claude):
    youtube.quota = 0
    result = _run("run", "--date", TARGET, "--json")
    assert result.exit_code == 1
    data = _json(result)
    assert (data["assess"], data["enhance"]) == (None, None)
    assert claude.prompts == []
    assert "fetch stopped, chain stopped. Stopped early:" in result.stderr


def test_run_stops_on_an_anthropic_stop(store, youtube, monkeypatch):
    fake = FakeClaude(errors={0: ClaudeStoppingError("Anthropic API 402 no credit")})
    monkeypatch.setattr(trusted_cli, "make_claude_caller", lambda: fake)
    result = _run("run", "--date", TARGET, "--json")
    assert result.exit_code == 1
    assert _json(result)["enhance"] is None
    assert "assess stopped, chain stopped" in result.stderr
    assert not _stage_dir("enhance").exists()


def test_run_goes_on_past_a_failed_batch(store, youtube, monkeypatch):
    fake = FakeClaude(errors={0: ClaudeCallError("Anthropic API 529 busy")})
    monkeypatch.setattr(trusted_cli, "make_claude_caller", lambda: fake)
    result = _run("run", "--date", TARGET)
    assert result.exit_code == 1
    assert "assess: earth: error 1 video(s) — Anthropic API 529 busy" in result.stdout
    assert "Some items failed in assess; see the report above" in result.stderr
    assert _ids("enhance") == ["zoo-video-1", "zoo-video-3"]


def test_run_without_anthropic_key_fetches_nothing(store, youtube):
    result = _run("run", "--date", TARGET, "--json")
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY is not set" in result.stderr
    assert (youtube.calls, result.stdout) == ([], "")
    assert not Path("stages").exists()


def test_status_counts_per_channel(store, youtube, claude):
    claude.scores = {"zoo-video-1": (5, 4, ["war"])}
    _run("run", "--date", TARGET)
    text = _run("status", "--date", TARGET).stdout
    assert "zoo: fetched 2, assessed 2, suitable 1, enhanced 1" in text
    assert "total 2026-10-28: fetched 3, assessed 3, suitable 2, enhanced 2" in text
