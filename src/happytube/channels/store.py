"""File store for the channel registry.

Layout (decision 0003)::

    <root>/<slug>/channel.yaml
    <root>/<slug>/reviews/<YYYYMMDDTHHMMSSZ>-<reviewer slug>[-N].yaml

Files are the source of truth; nothing is cached. Every write creates a new file
exclusively, so concurrent writers never overwrite each other.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from happytube.channels.models import SLUG_PATTERN, Channel, Review, Status, slugify

CHANNEL_FILE = "channel.yaml"
REVIEWS_DIR = "reviews"
DECISIVE_VERDICTS: dict[str, Status] = {"approve": "approved", "reject": "rejected"}
_COLLISION_SUFFIX = re.compile(r"^(?P<base>.+)-(?P<n>\d+)$")


class ChannelStoreError(Exception):
    """Base error for registry operations; the message is user-facing."""


class ChannelExistsError(ChannelStoreError):
    """A channel with the same slug, channel id or handle is already registered."""


class ChannelNotFoundError(ChannelStoreError):
    """No channel with the given slug."""


def derive_status(reviews: list[Review]) -> Status:
    """Status from the latest human approve/reject; agent reviews never count.

    ``reviews`` should be in store order (see ``ChannelStore.reviews``): the sort by
    ``created_at`` is stable, so on a tie the later review in that order decides.
    """
    decisive = [
        r for r in reviews if r.role == "human" and r.verdict in DECISIVE_VERDICTS
    ]
    if not decisive:
        return "candidate"
    latest = sorted(decisive, key=lambda r: r.created_at)[-1]
    return DECISIVE_VERDICTS[latest.verdict]


def _collision_index(name: str, names: set[str]) -> int:
    """Write order of a review file among same-stem files: base is 1, ``-N`` is N.

    A trailing ``-N`` only counts as a collision suffix when the base file exists,
    so a reviewer slug that ends in digits (``bot-2``) is not mistaken for one.
    """
    match = _COLLISION_SUFFIX.match(name.removesuffix(".yaml"))
    if match and f"{match['base']}.yaml" in names:
        return int(match["n"])
    return 1


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
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        msg = f"{path}: invalid YAML: {e}"
        raise ChannelStoreError(msg) from e
    if not isinstance(data, dict):
        msg = f"{path}: expected a YAML mapping"
        raise ChannelStoreError(msg)
    return data


def _load_model[M: BaseModel](path: Path, model: type[M]) -> M:
    """Validate a YAML file as ``model``; errors name the file."""
    try:
        return model.model_validate(_load_yaml(path))
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(file)'}: {err['msg']}"
            for err in e.errors()
        )
        msg = f"{path}: {problems}"
        raise ChannelStoreError(msg) from e


def filter_entries(
    entries: list[ChannelEntry],
    *,
    status: str | None = None,
    kind: str | None = None,
    language: str | None = None,
    needs_human_review: bool = False,
) -> list[ChannelEntry]:
    """Entries matching every given filter; ``None``/``False`` means no filter."""
    return [
        e
        for e in entries
        if (status is None or e.status == status)
        and (kind is None or e.channel.kind == kind)
        and (language is None or language in e.channel.languages)
        and not (needs_human_review and e.has_human_review)
    ]


class ChannelStore:
    """Read and write channels and reviews under a registry directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _channel_dir(self, slug: str) -> Path:
        """Directory of ``slug``; refuses anything that is not a plain slug.

        This is the only place a slug becomes a path, so ``../x`` or ``/abs`` can
        never reach outside the registry.
        """
        if not re.fullmatch(SLUG_PATTERN, slug):
            msg = f"No channel with slug '{slug}' (not a valid slug)"
            raise ChannelNotFoundError(msg)
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
        channel = _load_model(path, Channel)
        if channel.slug != slug:
            msg = (
                f"{path}: slug '{channel.slug}' does not match its directory "
                f"'{slug}'; rename one so they agree"
            )
            raise ChannelStoreError(msg)
        return channel

    def reviews(self, slug: str) -> list[Review]:
        """Reviews of a channel in write order: by ``created_at``, then by the
        filename's collision suffix (base file first, then ``-2``, ``-3`` …)."""
        reviews_dir = self._channel_dir(slug) / REVIEWS_DIR
        if not reviews_dir.is_dir():
            return []
        paths = list(reviews_dir.glob("*.yaml"))
        names = {p.name for p in paths}
        loaded = [(_load_model(p, Review), p.name) for p in paths]
        loaded.sort(
            key=lambda pair: (
                pair[0].created_at,
                _collision_index(pair[1], names),
                pair[1],
            )
        )
        return [review for review, _ in loaded]

    def get(self, slug: str) -> ChannelEntry:
        return ChannelEntry(self.get_channel(slug), self.reviews(slug))

    def entries(self) -> list[ChannelEntry]:
        """Every channel. A broken file raises ``ChannelStoreError`` naming it:
        files are the source of truth, so a broken one should be fixed, not hidden."""
        return [self.get(slug) for slug in self.slugs()]

    def _find_duplicate(self, channel: Channel) -> str | None:
        """Describe an existing channel clashing with ``channel``, if any.

        Reads every channel, so a broken file fails the check instead of letting
        a duplicate through.
        """
        if (self._channel_dir(channel.slug) / CHANNEL_FILE).exists():
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
        channel_dir.mkdir(parents=True, exist_ok=True)
        path = channel_dir / CHANNEL_FILE
        try:
            with path.open("x", encoding="utf-8") as f:
                f.write(_dump_yaml(channel.model_dump(mode="json")))
        except FileExistsError as e:  # another writer won the race
            msg = f"Channel already registered with slug '{channel.slug}'"
            raise ChannelExistsError(msg) from e
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
