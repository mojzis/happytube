"""Builders and a fake Claude client for the vetting tests (no network)."""

from datetime import UTC, datetime, timedelta

from happytube.channels.models import Channel, Evidence, EvidenceVideo, VetUsage
from happytube.channels.store import ChannelStore
from happytube.channels.vet import Prompt, VetOutput, long_form
from happytube.channels.vet_run import VetError, VetReply
from happytube.rubric import VideoScore

FETCHED_AT = datetime(2026, 10, 28, 19, 16, 18, tzinfo=UTC)
USAGE = VetUsage(input_tokens=1000, output_tokens=500)


def make_channel(slug="zoo-praha", channel_id="UCzoo", **overrides):
    fields = {
        "slug": slug,
        "name": "Zoo Praha",
        "kind": "zoo",
        "languages": ["cs"],
        "handle": "@" + slug.replace("-", ""),
        "channel_id": channel_id,
        "added_by": "matous",
    }
    return Channel.model_validate(fields | overrides)


def make_evidence(n_long=6, n_short=2, newest_days_ago=3, fetched_at=FETCHED_AT):
    """Shorts first (newest), then long-form videos one day apart."""
    videos = [
        EvidenceVideo(
            video_id=f"s{i}",
            title=f"Short {i}",
            published_at=fetched_at - timedelta(days=newest_days_ago + i),
            duration_s=30,
            is_short=True,
        )
        for i in range(n_short)
    ]
    videos += [
        EvidenceVideo(
            video_id=f"v{i}",
            title=f"Mládě {i} | žirafa",
            published_at=fetched_at - timedelta(days=newest_days_ago + n_short + i),
            duration_s=125,
            is_short=False,
            description=f"Popis {i}",
            default_language="cs",
        )
        for i in range(n_long)
    ]
    return Evidence(
        fetched_at=fetched_at,
        method="api",
        channel_id="UCzoo",
        title="Zoologická zahrada hl. m. Prahy",
        custom_url="@zoopraha",
        country="CZ",
        subscriber_count=39800,
        video_count=1045,
        shorts_source="uush",
        videos=videos,
    )


def make_output(  # noqa: PLR0913 - one keyword per output field tests vary
    evidence, verdict="approve", identity="yes", calm=5, happy=4, flags=()
):
    """A model output scoring every long-form video alike."""
    return VetOutput(
        identity_match=identity,
        identity_note="Official Zoo Praha channel.",
        channel_calm=5,
        channel_happy=4,
        verdict=verdict,
        summary="Calm zoo videos.",
        concerns=[],
        videos=[
            VideoScore(
                video_id=v.video_id,
                calm=calm,
                happy=happy,
                flags=list(flags),
                note="Gentle zoo clip.",
            )
            for v in long_form(evidence)
        ],
    )


def seed(store: ChannelStore, channel=None, evidence=None):
    channel = channel or make_channel()
    store.add(channel)
    if evidence is not None:
        store.add_evidence(channel.slug, evidence)
    return channel


class FakeVetClient:
    """Answers with ``make_output`` for the evidence it is given; ``errors`` maps
    a call number (0-based) to an exception to raise instead."""

    def __init__(self, evidence, *, errors=None, reply=None, **output_kwargs):
        self.evidence = evidence
        self.errors: dict[int, VetError] = errors or {}
        self.reply = reply
        self.output_kwargs = output_kwargs
        self.prompts: list[Prompt] = []

    def vet(self, prompt):
        index = len(self.prompts)
        self.prompts.append(prompt)
        if index in self.errors:
            raise self.errors[index]
        if self.reply is not None:
            return self.reply
        output = make_output(self.evidence, **self.output_kwargs)
        return VetReply(output, "claude-opus-5-5", USAGE, "end_turn")
