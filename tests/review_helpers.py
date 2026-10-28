"""Fixture registry for the review UI tests (no network, no server)."""

from datetime import timedelta

from fastapi.testclient import TestClient

from happytube.channels.models import Review, VetReport, VetVideo
from happytube.channels.store import ChannelStore
from happytube.review import create_app
from tests.vet_helpers import FETCHED_AT, USAGE, make_channel, make_evidence, seed

BASE_URL = "http://127.0.0.1:8000"
QUEUE = "/channels"


def detail_url(slug):
    return f"{QUEUE}/{slug}"


def missing(text, *snippets):
    """The snippets not found in ``text`` (``[]`` when all are there)."""
    return [s for s in snippets if s not in text]


def make_vet(evidence, verdict="approve", flags=(), title="Mládě | žirafa"):
    """A vet report scoring two videos, the first suitable."""
    videos = [
        VetVideo(
            video_id="v0000000000",
            title=title,
            calm=5,
            happy=4,
            suitable=True,
            note="Klidné.",
        ),
        VetVideo(
            video_id="v0000000001",
            title="Krmení",
            calm=2,
            happy=3,
            flags=["predation"],
            suitable=False,
        ),
    ]
    return VetReport(
        vetted_at=evidence.fetched_at + timedelta(hours=1),
        model="claude-opus-5-5",
        prompt_version=1,
        evidence_at=evidence.fetched_at,
        verdict=verdict,
        model_verdict="approve" if flags else verdict,
        flags=list(flags),
        identity_match="yes",
        identity_note="Official channel.",
        channel_calm=5,
        channel_happy=4,
        summary="Calm zoo videos.",
        concerns=["one feeding clip"],
        usage=USAGE,
        videos=videos,
        shorts_skipped=2,
    )


def review(verdict="approve", role="human", reviewer=None, hours=2, notes=None):
    return Review(
        reviewer=reviewer or ("matous" if role == "human" else "claude-vet"),
        role=role,
        verdict=verdict,
        notes=notes,
        created_at=FETCHED_AT + timedelta(hours=hours),
    )


def chan(slug, **overrides):
    """``make_channel`` with a channel id unique to the slug."""
    return make_channel(slug, **({"channel_id": f"UC{slug}"} | overrides))


def seed_vetted(store: ChannelStore, slug, name, verdict="approve", flags=()):
    """A resolved channel with evidence, a vet report and the vet's agent review."""
    evidence = make_evidence()
    seed(store, chan(slug, name=name), evidence)
    store.add_vet(slug, make_vet(evidence, verdict, flags), "body")
    store.add_review(slug, review(verdict, role="agent"))


def client(store: ChannelStore, default_reviewer=None, **kwargs) -> TestClient:
    app = create_app(store, default_reviewer=default_reviewer, **kwargs)
    return TestClient(app, base_url=BASE_URL)
