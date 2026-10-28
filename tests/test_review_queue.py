"""The review queue order (pure ``queue_sections``)."""

from happytube.channels.store import ChannelStore
from happytube.review.queue import is_unresolved, needs_attention, queue_sections
from tests.review_helpers import chan, review, seed_vetted
from tests.vet_helpers import make_evidence, seed


def _slugs(entries):
    return [e.channel.slug for e in entries]


def test_needs_review_order_attention_then_verdict_then_name(tmp_path):
    store = ChannelStore(tmp_path)
    seed_vetted(store, "approve-b", "B approve")
    seed_vetted(store, "approve-a", "A approve")
    seed_vetted(store, "reject-z", "Z reject", verdict="reject")
    seed_vetted(store, "unsure-y", "Y unsure", verdict="unsure")
    seed_vetted(store, "flagged", "Flagged", verdict="unsure", flags=["inactive"])
    seed(store, chan("not-vetted", name="Not vetted"), make_evidence())
    seed(store, chan("ct-decko", name="ČT Déčko", channel_id=None))
    seed(store, chan("zoo-zlin", name="Zoo Zlín", channel_id=None))

    sections = queue_sections(store.entries())

    assert _slugs(sections.needs_review) == [
        "flagged",  # attention, unsure
        "ct-decko",  # attention (unresolved), not vetted; Č sorts with C
        "zoo-zlin",
        "unsure-y",
        "reject-z",
        "approve-a",
        "approve-b",
        "not-vetted",
    ]
    assert sections.reviewed == []


def _seed_reviewed(store, *channels):
    """Vetted channels, each with one human review: (slug, name, verdict)."""
    for slug, name, verdict in channels:
        seed_vetted(store, slug, name)
        store.add_review(slug, review(verdict))


def test_reviewed_section_by_status_then_name(tmp_path):
    store = ChannelStore(tmp_path)
    _seed_reviewed(
        store,
        ("rej", "A rejected", "reject"),
        ("app", "B approved", "approve"),
        ("cand", "C unsure", "unsure"),
        ("app2", "A approved", "approve"),
    )
    seed_vetted(store, "pending", "Pending")

    sections = queue_sections(store.entries())

    assert _slugs(sections.reviewed) == ["cand", "app2", "app", "rej"]
    assert _slugs(sections.needs_review) == ["pending"]


def test_agent_review_alone_keeps_channel_in_needs_review(tmp_path):
    store = ChannelStore(tmp_path)
    seed_vetted(store, "zoo-praha", "Zoo Praha")  # has a claude-vet agent review

    sections = queue_sections(store.entries())

    assert _slugs(sections.needs_review) == ["zoo-praha"]


def test_attention_rules(tmp_path):
    store = ChannelStore(tmp_path)
    seed(store, chan("no-evidence"))
    seed(store, chan("no-id", channel_id=None), make_evidence())
    seed(store, chan("resolved"), make_evidence())
    seed_vetted(store, "clean", "Clean")
    seed_vetted(store, "flagged", "Flagged", flags=["mostly_shorts"])
    entries = {e.channel.slug: e for e in store.entries()}

    assert {s for s, e in entries.items() if is_unresolved(e)} == {
        "no-evidence",
        "no-id",
    }
    assert {s for s, e in entries.items() if needs_attention(e)} == {
        "no-evidence",
        "no-id",
        "flagged",
    }
