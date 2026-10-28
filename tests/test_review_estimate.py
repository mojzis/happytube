"""Watchable-video estimate over approved channels (pure)."""

from happytube.channels.store import ChannelStore
from happytube.review.estimate import channel_watchable, watchable_estimate
from tests.review_helpers import chan, review, seed_vetted
from tests.vet_helpers import make_evidence, seed


def test_channel_estimate_is_uploads_times_long_form_and_suitable_share(tmp_path):
    store = ChannelStore(tmp_path)
    seed_vetted(store, "zoo", "Zoo")  # 1045 uploads, 6 of 8 long-form, 1 of 2 suitable
    assert channel_watchable(store.get("zoo")) == 392  # round(1045 * 6/8 * 1/2)


def test_channel_without_vet_or_evidence_is_not_estimated(tmp_path):
    store = ChannelStore(tmp_path)
    seed(store, chan("bare"))
    seed(store, chan("unvetted"), make_evidence())
    assert channel_watchable(store.get("bare")) is None
    assert channel_watchable(store.get("unvetted")) is None


def test_estimate_counts_only_approved_channels(tmp_path):
    store = ChannelStore(tmp_path)
    seed_vetted(store, "a", "A")
    seed_vetted(store, "b", "B")
    seed_vetted(store, "pending", "Pending")
    store.add_review("a", review("approve"))
    store.add_review("b", review("approve"))
    seed(store, chan("c"), make_evidence())
    store.add_review("c", review("approve"))

    estimate = watchable_estimate(store.entries())

    assert estimate.channels == 3
    assert estimate.estimated_channels == 2
    assert estimate.videos == 2 * 392
    assert estimate.sampled_suitable == 2
