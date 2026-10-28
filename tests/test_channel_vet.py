"""Rubric, flags, verdict rule, prompt, report and the vet store (no network)."""

from datetime import timedelta

import pytest

from happytube.channels.models import VetReport
from happytube.channels.store import ChannelStore, ChannelStoreError, StoredVet
from happytube.channels.vet import (
    SYSTEM_PROMPT,
    VetOutputError,
    apply_verdict_rule,
    build_prompt,
    build_report,
    channel_flags,
    render_report,
    review_for,
)
from happytube.records import StoreError
from happytube.rubric import FLAGS, is_suitable
from tests.vet_helpers import (
    FETCHED_AT,
    USAGE,
    make_channel,
    make_evidence,
    make_output,
    seed,
)


@pytest.fixture
def store(tmp_path):
    return ChannelStore(tmp_path / "channels")


def _report(evidence=None, flags=(), minutes=0, **output_kwargs):
    evidence = evidence or make_evidence()
    return build_report(
        evidence,
        make_output(evidence, **output_kwargs),
        list(flags),
        model="claude-opus-5-5",
        usage=USAGE,
        vetted_at=FETCHED_AT + timedelta(minutes=minutes),
    )


# --- rubric -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("calm", "happy", "flags", "suitable"),
    [
        (4, 3, [], True),
        (3, 5, [], False),
        (5, 2, [], False),
        (5, 5, ["clickbait", "promo", "loud_fast", "other"], True),
        (5, 5, ["predation"], False),
        (5, 5, ["news"], False),
    ],
)
def test_is_suitable(calm, happy, flags, suitable):
    assert is_suitable(calm, happy, flags) is suitable


def test_every_flag_is_explained_in_the_prompt():
    for flag in FLAGS:
        assert f"  {flag} " in SYSTEM_PROMPT


# --- flags ------------------------------------------------------------------


def test_unresolved_without_channel_id():
    assert channel_flags(make_channel(channel_id=None), make_evidence()) == [
        "unresolved"
    ]


def test_unresolved_without_evidence():
    assert channel_flags(make_channel(), None) == ["unresolved"]


def test_active_channel_with_enough_long_form_has_no_flags():
    assert channel_flags(make_channel(), make_evidence()) == []


def test_inactive_boundary_is_365_days():
    # newest upload is the first Short: newest_days_ago before fetched_at
    assert channel_flags(make_channel(), make_evidence(newest_days_ago=365)) == []
    assert channel_flags(make_channel(), make_evidence(newest_days_ago=366)) == [
        "inactive"
    ]


def test_no_uploads_is_inactive_and_mostly_shorts():
    evidence = make_evidence(n_long=0, n_short=0)
    assert channel_flags(make_channel(), evidence) == ["inactive", "mostly_shorts"]


def test_mostly_shorts_boundary_is_five_long_form():
    assert channel_flags(make_channel(), make_evidence(n_long=5)) == []
    assert channel_flags(make_channel(), make_evidence(n_long=4)) == ["mostly_shorts"]


# --- verdict rule -------------------------------------------------------------


@pytest.mark.parametrize("flag", ["inactive", "mostly_shorts", "identity_doubt"])
def test_approve_with_downgrading_flag_becomes_unsure(flag):
    assert apply_verdict_rule("approve", [flag]) == "unsure"


@pytest.mark.parametrize("verdict", ["approve", "reject", "unsure"])
def test_verdict_passes_through_without_flags(verdict):
    assert apply_verdict_rule(verdict, []) == verdict


@pytest.mark.parametrize("verdict", ["reject", "unsure"])
def test_reject_and_unsure_pass_through_flags(verdict):
    assert apply_verdict_rule(verdict, ["inactive", "identity_doubt"]) == verdict


# --- prompt -----------------------------------------------------------------


def test_prompt_leaves_out_shorts_and_keeps_czech():
    prompt = build_prompt(make_channel(), make_evidence(n_long=6, n_short=2))
    assert "video_id: v0000000005" in prompt.user
    assert "s0" not in prompt.user
    assert "shorts_left_out: 2" in prompt.user
    assert "Score all 6 long-form videos" in prompt.user
    assert "Mládě 0 | žirafa" in prompt.user
    assert "duration: '2:05'" in prompt.user


def test_prompt_is_deterministic_with_a_fixed_system_part():
    one = build_prompt(make_channel(), make_evidence())
    two = build_prompt(make_channel(), make_evidence())
    other = build_prompt(make_channel(name="Zoo Zlín"), make_evidence())
    assert one == two
    assert other.system == one.system
    assert other.user != one.user


# --- output check and report -------------------------------------------------


def test_report_scores_long_form_in_snapshot_order():
    report = _report(make_evidence(n_long=3, n_short=1, newest_days_ago=1))
    assert [v.video_id for v in report.videos] == [
        "v0000000000",
        "v0000000001",
        "v0000000002",
    ]
    assert report.shorts_skipped == 1
    assert report.evidence_at == FETCHED_AT
    assert report.suitable_count == 3


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda videos: videos.pop(), "missing v0000000005"),
        (
            lambda videos: videos.append(videos[0].model_copy()),
            "scored twice v0000000000",
        ),
        (
            lambda videos: videos.append(
                videos[0].model_copy(update={"video_id": "s0"})
            ),
            "unexpected s0",
        ),
    ],
)
def test_output_must_cover_exactly_the_long_form_ids(change, message):
    evidence = make_evidence()
    output = make_output(evidence)
    change(output.videos)
    with pytest.raises(VetOutputError, match=message):
        build_report(evidence, output, [], model="m", usage=USAGE)


def test_identity_doubt_downgrades_approve():
    report = _report(identity="unsure")
    assert report.flags == ["identity_doubt"]
    assert (report.model_verdict, report.verdict) == ("approve", "unsure")


def test_channel_flags_do_not_touch_video_suitability():
    report = _report(flags=["inactive"])
    assert report.verdict == "unsure"
    assert report.suitable_count == len(report.videos)


def test_predation_video_is_not_suitable():
    evidence = make_evidence()
    output = make_output(evidence)
    output.videos[0].flags = ["predation"]
    report = build_report(evidence, output, [], model="m", usage=USAGE)
    assert not report.videos[0].suitable
    assert report.suitable_count == len(report.videos) - 1


def test_rendered_report_has_summary_table_and_unicode():
    channel = make_channel()
    evidence = make_evidence(n_long=2, n_short=0)
    output = make_output(evidence, verdict="reject")
    output.concerns = ["Lion | hunt video"]
    report = build_report(evidence, output, ["mostly_shorts"], model="m", usage=USAGE)
    body = render_report(channel, report)
    assert body.startswith("# Zoo Praha — vet\n")
    assert "**Verdict: reject**" in body
    assert "- Lion | hunt video" in body
    assert "| Mládě 0 \\| žirafa | 5 | 4 |  | yes |" in body


def test_review_explains_a_downgrade():
    report = _report(flags=["inactive"])
    review = review_for(report, "20261028T191618Z.md")
    assert (review.reviewer, review.role, review.verdict) == (
        "claude-vet",
        "agent",
        "unsure",
    )
    assert review.notes == (
        "Calm zoo videos. Flags: inactive. Model said approve; unsure because "
        "inactive. Report: vet/20261028T191618Z.md"
    )


# --- store --------------------------------------------------------------------


@pytest.fixture
def two_vets(store):
    """The same report written twice for one channel."""
    channel = seed(store, evidence=make_evidence())
    report = _report()
    paths = [store.add_vet(channel.slug, report, "# body\n") for _ in range(2)]
    return channel.slug, report, paths


def test_vet_files_never_collide(two_vets):
    _, _, paths = two_vets
    assert [p.name for p in paths] == ["20261028T191618Z.md", "20261028T191618Z-2.md"]


def test_vet_file_is_frontmatter_with_unicode(two_vets):
    text = two_vets[2][0].read_text(encoding="utf-8")
    assert text.startswith("---\nvetted_at: ")
    assert "Mládě 0 | žirafa" in text


def test_vets_round_trip_in_write_order(store, two_vets):
    slug, report, paths = two_vets
    assert store.vets(slug) == [report, report]
    assert store.latest_vet(slug) == StoredVet(report, paths[1])


def test_latest_vet_is_newest_by_time(store):
    channel = seed(store, evidence=make_evidence())
    store.add_vet(channel.slug, _report(minutes=5, verdict="reject"), "")
    store.add_vet(channel.slug, _report(minutes=1), "")
    latest = store.latest_vet(channel.slug)
    assert latest is not None
    assert latest.report.verdict == "reject"
    assert [v.verdict for v in store.vets(channel.slug)] == ["approve", "reject"]


def test_no_vets(store):
    channel = seed(store)
    assert store.vets(channel.slug) == []
    assert store.latest_vet(channel.slug) is None
    assert store.get(channel.slug).summary_dict()["vet_verdict"] is None


def test_frontmatter_survives_dash_lines_in_text(store):
    channel = seed(store, evidence=make_evidence())
    evidence = make_evidence()
    output = make_output(evidence)
    output.summary = "Line one\n---\nline three ------"
    report = build_report(evidence, output, [], model="m", usage=USAGE)
    store.add_vet(channel.slug, report, "body\n---\nmore\n")
    assert store.vets(channel.slug)[0].summary == output.summary


@pytest.mark.parametrize(
    "text",
    [
        "no frontmatter",
        "---\nverdict: approve\n",
        "---\n- a list\n---\n",
        "---\n: :\n---\n",
    ],
)
def test_broken_vet_file_names_the_file(store, text):
    channel = seed(store)
    path = store.root / channel.slug / "vet" / "20261028T191618Z.md"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ChannelStoreError, match=r"20261028T191618Z\.md"):
        store.latest_vet(channel.slug)


def test_unknown_key_in_vet_frontmatter_is_refused(store):
    channel = seed(store, evidence=make_evidence())
    path = store.add_vet(channel.slug, _report(), "")
    path.write_text(
        path.read_text(encoding="utf-8").replace("---\n", "---\nextra: 1\n", 1),
        encoding="utf-8",
    )
    with pytest.raises(StoreError, match="extra"):
        store.vets(channel.slug)


def test_entry_dicts_include_latest_vet(store):
    channel = seed(store, evidence=make_evidence())
    store.add_vet(channel.slug, _report(), "")
    entry = store.get(channel.slug)
    summary = entry.summary_dict()
    assert (summary["vetted_at"], summary["vet_verdict"]) == (
        "2026-10-28T19:16:18Z",
        "approve",
    )
    vet = entry.detail_dict()["vet"]
    path = vet.pop("path")
    assert path.endswith("vet/20261028T191618Z.md")
    assert vet.pop("suitable_count") == 6
    assert VetReport.model_validate(vet) == _report()
