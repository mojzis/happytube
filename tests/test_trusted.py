"""Trusted assess and enhance on hand-made fetch files (fake Claude, no network)."""

import asyncio
from datetime import date

import pytest

from happytube.claude import ClaudeCallError
from happytube.models.markdown import MarkdownFile
from happytube.rubric import RUBRIC_VERSION
from happytube.trusted import assess as assess_module
from happytube.trusted.assess import assess_trusted, build_prompt
from happytube.trusted.enhance import enhance_trusted
from happytube.trusted.stages import TrustedStage
from tests.trusted_helpers import FakeClaude, prompt_ids

DAY = date(2026, 10, 28)


@pytest.fixture
def base(tmp_path):
    return tmp_path / "stages"


def _fetched(base, slug, *ids, day=DAY):
    stage = TrustedStage("fetch", base)
    for video_id in ids:
        frontmatter = {
            "video_id": video_id,
            "title": f"Video {video_id}",
            "channel_slug": slug,
            "channel_name": slug.title(),
            "languages": ["cs"],
            "published_at": "2026-10-25T10:00:00Z",
            "duration_s": 754,
            "stage": "trusted_fetch",
        }
        md = MarkdownFile(frontmatter, f"# Video {video_id}\n\n{'Popis. ' * 300}")
        stage.write(day, video_id, md)


def _front(base, stage, video_id, day=DAY):
    return MarkdownFile.load(
        TrustedStage(stage, base).get_stage_dir(day) / f"{video_id}.md"
    ).frontmatter


def _assess(base, client, **kwargs):
    return assess_trusted(DAY, lambda: client, base_path=base, **kwargs)


def test_prompt_has_rubric_and_truncated_description(base):
    _fetched(base, "zoo", "a")
    [md] = TrustedStage("fetch", base).load(DAY)
    prompt = build_prompt([md])
    assert "calm\n  5 = gentle and slow" in prompt.system
    assert "duration: '12:34'" in prompt.user
    assert len(prompt.user) < 1300  # description cut to 1000 characters


def test_one_call_per_channel_chunked(base, monkeypatch):
    monkeypatch.setattr(assess_module, "BATCH_SIZE", 2)
    _fetched(base, "zoo", "z1", "z2", "z3")
    _fetched(base, "earth", "e1")
    client = FakeClaude()
    run = _assess(base, client)
    assert [prompt_ids(p) for p in client.prompts] == [["e1"], ["z1", "z2"], ["z3"]]
    assert [(r.slug, r.status) for r in run.results] == [
        ("earth", "done"),
        ("zoo", "done"),
        ("zoo", "done"),
    ]
    assert (run.input_tokens, run.usd, run.failed) == (3000, 0.024, False)


def test_suitable_is_decided_in_code(base):
    _fetched(base, "zoo", "calm", "busy", "war", "sad")
    scores = {"busy": (3, 5, []), "war": (5, 5, ["war"]), "sad": (5, 2, [])}
    run = _assess(base, FakeClaude(scores=scores))
    assert run.results[0].suitable == 1
    front = _front(base, "assess", "calm")
    assert (
        front
        | {
            "suitable": True,
            "calm": 5,
            "happy": 4,
            "flags": [],
            "note": "Gentle video calm.",
            "model": "claude-opus-5-5",
            "rubric_version": RUBRIC_VERSION,
            "stage": "trusted_assess",
            "channel_slug": "zoo",
            "duration_s": 754,
        }
        == front
    )
    assert [_front(base, "assess", v)["suitable"] for v in ("busy", "war", "sad")] == [
        False,
        False,
        False,
    ]


def test_reply_missing_a_video_writes_nothing_for_that_batch(base):
    _fetched(base, "zoo", "z1", "z2")
    _fetched(base, "earth", "e1")
    run = _assess(base, FakeClaude(drop=["z2"]))
    statuses = {r.slug: (r.status, r.message) for r in run.results}
    assert statuses["zoo"] == (
        "error",
        "model output does not match the videos sent: missing z2; nothing written",
    )
    assert statuses["earth"][0] == "done"
    assert TrustedStage("assess", base).video_ids() == {"e1"}
    # failed, and the bad batch was still paid for
    assert (run.failed, run.input_tokens) == (True, 2000)


def test_refusal_and_call_error_are_per_batch(base):
    _fetched(base, "a", "a1")
    _fetched(base, "b", "b1")
    _fetched(base, "c", "c1")
    client = FakeClaude(
        errors={0: ClaudeCallError("Anthropic API 529 busy")}, refuse=["b1"]
    )
    run = _assess(base, client)
    assert [(r.status, r.message) for r in run.results] == [
        ("error", "Anthropic API 529 busy"),
        ("refused", "stop_reason refusal (bio); nothing written"),
        ("done", None),
    ]
    assert TrustedStage("assess", base).video_ids() == {"c1"}


def test_already_assessed_is_skipped_unless_forced(base):
    _fetched(base, "zoo", "z1")
    _assess(base, FakeClaude())
    _fetched(base, "zoo", "z2")
    client = FakeClaude()
    run = _assess(base, client)
    assert ([prompt_ids(p) for p in client.prompts], run.skipped) == ([["z2"]], 1)
    forced = FakeClaude(scores={"z1": (2, 2, [])})
    _assess(base, forced, force=True)
    assert [prompt_ids(p) for p in forced.prompts] == [["z1", "z2"]]
    assert _front(base, "assess", "z1")["suitable"] is False


def test_assessed_on_an_earlier_date_is_not_rescored(base):
    _fetched(base, "zoo", "z1", day=date(2026, 10, 27))
    assess_trusted(date(2026, 10, 27), lambda: FakeClaude(), base_path=base)
    _fetched(base, "zoo", "z1")  # e.g. a hand-copied file
    client = FakeClaude()
    assert _assess(base, client).skipped == 1
    assert client.prompts == []


def test_dry_run_makes_no_client(base):
    _fetched(base, "zoo", "z1")
    run = assess_trusted(DAY, None, base_path=base)
    assert (run.dry_run, run.results[0].status, run.failed) == (
        True,
        "would_run",
        False,
    )
    assert TrustedStage("assess", base).video_ids() == set()


@pytest.fixture
def assessed(base):
    """Two assessed videos: ``good`` suitable, ``bad`` not."""
    _fetched(base, "zoo", "good", "bad")
    _assess(base, FakeClaude(scores={"bad": (2, 2, [])}))
    return base


def test_enhance_only_suitable(assessed):
    run = enhance_trusted(DAY, FakeClaude, base_path=assessed)
    assert [r.video_ids for r in run.results] == [["good"]]
    assert TrustedStage("enhance", assessed).video_ids() == {"good"}


def test_enhance_file_keeps_assess_fields(assessed):
    enhance_trusted(DAY, FakeClaude, base_path=assessed)
    front = _front(assessed, "enhance", "good")
    assert {
        k: front[k] for k in ("enhanced_description", "enhance_model", "stage")
    } == {
        "enhanced_description": "Klidné video o žirafách.",
        "enhance_model": "claude-opus-5-5",
        "stage": "trusted_enhance",
    }
    assert (front["suitable"], front["calm"]) == (True, 5)


def test_enhance_skips_existing_unless_forced(assessed):
    client = FakeClaude()
    enhance_trusted(DAY, lambda: client, base_path=assessed)
    again = enhance_trusted(DAY, lambda: client, base_path=assessed)
    assert (again.results, again.skipped, len(client.prompts)) == ([], 1, 1)
    forced = enhance_trusted(DAY, lambda: client, base_path=assessed, force=True)
    assert [r.status for r in forced.results] == ["done"]


def test_enhance_with_nothing_suitable_makes_no_client(base):
    made = []

    def factory():
        made.append(1)
        return FakeClaude()

    run = enhance_trusted(DAY, factory, base_path=base)
    assert (run.results, made) == ([], [])


def test_stage_run_is_not_the_entry_point(base):
    with pytest.raises(NotImplementedError):
        asyncio.run(TrustedStage("fetch", base).run(DAY))
