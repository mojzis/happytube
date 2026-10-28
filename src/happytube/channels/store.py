"""File store for the channel registry.

Layout (decision 0003)::

    <root>/<slug>/channel.yaml
    <root>/<slug>/reviews/<YYYYMMDDTHHMMSSZ>-<reviewer slug>[-N].yaml

Files are the source of truth; nothing is cached. Every write creates a new file
exclusively, so concurrent writers never overwrite each other.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from happytube.channels.models import Channel, Review, Status, slugify

CHANNEL_FILE = "channel.yaml"
REVIEWS_DIR = "reviews"
DECISIVE_VERDICTS = {"approve": "approved", "reject": "rejected"}


class ChannelStoreError(Exception):
    """Base error for registry operations; the message is user-facing."""


class ChannelExistsError(ChannelStoreError):
    """A channel with the same slug, channel id or handle is already registered."""


class ChannelNotFoundError(ChannelStoreError):
    """No channel with the given slug."""


def derive_status(reviews: list[Review]) -> Status:
    """Status from the latest human approve/reject; agent reviews never count."""
    decisive = [
        r for r in reviews if r.role == "human" and r.verdict in DECISIVE_VERDICTS
    ]
    if not decisive:
        return "candidate"
    latest = max(decisive, key=lambda r: r.created_at)
    return "approved" if latest.verdict == "approve" else "rejected"


@dataclass
class ChannelEntry:
    """A channel with its reviews (chronological) and derived status."""

    channel: Channel
    reviews: list[Review]

    @property
    def status(self) -> Status:
        return derive_status(self.reviews)

    @property
    def has_human_review(self) -> bool:
        return any(r.role == "human" for r in self.reviews)

    def summary_dict(self) -> dict[str, Any]:
        """JSON-ready channel fields plus derived status and review counts."""
        human = sum(1 for r in self.reviews if r.role == "human")
        return {
            **self.channel.model_dump(mode="json"),
            "status": self.status,
            "review_count": len(self.reviews),
            "human_review_count": human,
            "agent_review_count": len(self.reviews) - human,
        }

    def detail_dict(self) -> dict[str, Any]:
        """``summary_dict`` plus every review, oldest first."""
        return {
            **self.summary_dict(),
            "reviews": [r.model_dump(mode="json") for r in self.reviews],
        }


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path}: expected a YAML mapping"
        raise ChannelStoreError(msg)
    return data


class ChannelStore:
    """Read and write channels and reviews under a registry directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _channel_dir(self, slug: str) -> Path:
        return self.root / slug

    def slugs(self) -> list[str]:
        """Slugs of all registered channels, sorted."""
        if not self.root.is_dir():
            return []
        return sorted(
            p.name for p in self.root.iterdir() if (p / CHANNEL_FILE).is_file()
        )

    def get_channel(self, slug: str) -> Channel:
        path = self._channel_dir(slug) / CHANNEL_FILE
        if not path.is_file():
            msg = f"No channel with slug '{slug}'"
            raise ChannelNotFoundError(msg)
        return Channel.model_validate(_load_yaml(path))

    def reviews(self, slug: str) -> list[Review]:
        """Reviews of a channel, oldest first (ties broken by filename)."""
        reviews_dir = self._channel_dir(slug) / REVIEWS_DIR
        if not reviews_dir.is_dir():
            return []
        loaded = [
            (Review.model_validate(_load_yaml(p)), p.name)
            for p in reviews_dir.glob("*.yaml")
        ]
        loaded.sort(key=lambda pair: (pair[0].created_at, pair[1]))
        return [review for review, _ in loaded]

    def get(self, slug: str) -> ChannelEntry:
        return ChannelEntry(self.get_channel(slug), self.reviews(slug))

    def entries(self) -> list[ChannelEntry]:
        return [self.get(slug) for slug in self.slugs()]

    def _find_duplicate(self, channel: Channel) -> str | None:
        """Describe an existing channel clashing with ``channel``, if any."""
        if self._channel_dir(channel.slug).exists():
            return f"slug '{channel.slug}'"
        handle = channel.handle.lower() if channel.handle else None
        for slug in self.slugs():
            other = self.get_channel(slug)
            if channel.channel_id and other.channel_id == channel.channel_id:
                return f"channel id '{channel.channel_id}' (slug '{slug}')"
            if handle and other.handle and other.handle.lower() == handle:
                return f"handle '{channel.handle}' (slug '{slug}')"
        return None

    def add(self, channel: Channel) -> Path:
        """Register a new channel; refuse duplicates. Returns the channel.yaml path."""
        duplicate = self._find_duplicate(channel)
        if duplicate:
            msg = f"Channel already registered with {duplicate}"
            raise ChannelExistsError(msg)
        channel_dir = self._channel_dir(channel.slug)
        try:
            channel_dir.mkdir(parents=True)
        except FileExistsError as e:
            msg = f"Channel already registered with slug '{channel.slug}'"
            raise ChannelExistsError(msg) from e
        path = channel_dir / CHANNEL_FILE
        path.write_text(_dump_yaml(channel.model_dump(mode="json")), encoding="utf-8")
        return path

    def add_review(self, slug: str, review: Review) -> Path:
        """Write a new review file for ``slug``; never overwrites. Returns its path."""
        self.get_channel(slug)  # raises ChannelNotFoundError
        reviews_dir = self._channel_dir(slug) / REVIEWS_DIR
        reviews_dir.mkdir(exist_ok=True)
        stamp = review.created_at.strftime("%Y%m%dT%H%M%SZ")
        stem = f"{stamp}-{slugify(review.reviewer) or 'reviewer'}"
        content = _dump_yaml(review.model_dump(mode="json"))
        suffix = 1
        while True:
            name = f"{stem}.yaml" if suffix == 1 else f"{stem}-{suffix}.yaml"
            try:
                with (reviews_dir / name).open("x", encoding="utf-8") as f:
                    f.write(content)
            except FileExistsError:
                suffix += 1
                continue
            return reviews_dir / name
