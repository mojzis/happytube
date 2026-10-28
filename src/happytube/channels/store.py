"""File store for the channel registry.

Layout (decision 0003)::

    <root>/<slug>/channel.yaml
    <root>/<slug>/reviews/<YYYYMMDDTHHMMSSZ>-<reviewer slug>[-N].yaml
    <root>/<slug>/evidence/<YYYYMMDDTHHMMSSZ>[-N].yaml          (decision 0004)
    <root>/<slug>/vet/<YYYYMMDDTHHMMSSZ>[-N].md                 (decision 0005)

Files are the source of truth; nothing is cached. Every write creates a new file
exclusively, so concurrent writers never overwrite each other — except
``set_channel_id``, which fills a null ``channel_id`` in ``channel.yaml`` once.
"""

import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import yaml
from pydantic import BaseModel, ValidationError

from happytube.channels.models import (
    SLUG_PATTERN,
    Channel,
    Evidence,
    Review,
    Status,
    VetReport,
    slugify,
)

CHANNEL_FILE = "channel.yaml"
REVIEWS_DIR = "reviews"
EVIDENCE_DIR = "evidence"
VET_DIR = "vet"
YAML_SUFFIX = ".yaml"
MARKDOWN_SUFFIX = ".md"
DECISIVE_VERDICTS: dict[str, Status] = {"approve": "approved", "reject": "rejected"}
_COLLISION_SUFFIX = re.compile(r"^(?P<base>.+)-(?P<n>\d+)$")


class ChannelStoreError(Exception):
    """Base error for registry operations; the message is user-facing."""


class ChannelExistsError(ChannelStoreError):
    """A channel with the same slug, channel id or handle is already registered."""


class ChannelNotFoundError(ChannelStoreError):
    """No channel with the given slug."""


class ChannelIdMismatchError(ChannelStoreError):
    """``channel.yaml`` already holds a different channel id; never overwritten."""


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


def _collision_index(name: str, names: set[str], suffix: str = YAML_SUFFIX) -> int:
    """Write order of a record file among same-stem files: base is 1, ``-N`` is N.

    A trailing ``-N`` only counts as a collision suffix when the base file exists,
    so a reviewer slug that ends in digits (``bot-2``) is not mistaken for one.
    """
    match = _COLLISION_SUFFIX.match(name.removesuffix(suffix))
    if match and f"{match['base']}{suffix}" in names:
        return int(match["n"])
    return 1


@dataclass
class StoredVet:
    """A vet report's frontmatter and the file it was read from."""

    report: VetReport
    path: Path

    def summary_dict(self) -> dict[str, Any]:
        """Verdict, flags, scores and suitable count — no per-video detail."""
        r = self.report
        return {
            "vetted_at": r.model_dump(mode="json")["vetted_at"],
            "verdict": r.verdict,
            "model_verdict": r.model_verdict,
            "flags": list(r.flags),
            "channel_calm": r.channel_calm,
            "channel_happy": r.channel_happy,
            "long_form_scored": len(r.videos),
            "suitable_count": r.suitable_count,
            "path": str(self.path),
        }

    def detail_dict(self) -> dict[str, Any]:
        """The whole report plus its suitable count and path."""
        return {
            **self.report.model_dump(mode="json"),
            "suitable_count": self.report.suitable_count,
            "path": str(self.path),
        }


@dataclass
class ChannelEntry:
    """A channel with its reviews (chronological), derived status, the latest
    evidence snapshot and the latest vet report (``None`` if it has none)."""

    channel: Channel
    reviews: list[Review]
    latest_evidence: Evidence | None = None
    latest_vet: StoredVet | None = None

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
            "evidence_at": (
                self.latest_evidence.model_dump(mode="json")["fetched_at"]
                if self.latest_evidence
                else None
            ),
            "vetted_at": (
                self.latest_vet.summary_dict()["vetted_at"] if self.latest_vet else None
            ),
            "vet_verdict": self.latest_vet.report.verdict if self.latest_vet else None,
        }

    def detail_dict(self) -> dict[str, Any]:
        """``summary_dict`` plus every review (oldest first), the latest evidence
        snapshot in full with its shorts count, and the latest vet report in full."""
        evidence = None
        if self.latest_evidence:
            evidence = {
                **self.latest_evidence.model_dump(mode="json"),
                "shorts_count": self.latest_evidence.shorts_count,
            }
        return {
            **self.summary_dict(),
            "reviews": [r.model_dump(mode="json") for r in self.reviews],
            "evidence": evidence,
            "vet": self.latest_vet.detail_dict() if self.latest_vet else None,
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


def _validate[M: BaseModel](path: Path, data: dict[str, Any], model: type[M]) -> M:
    """Validate data read from ``path`` as ``model``; errors name the file."""
    try:
        return model.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(file)'}: {err['msg']}"
            for err in e.errors()
        )
        msg = f"{path}: {problems}"
        raise ChannelStoreError(msg) from e


def _load_model[M: BaseModel](path: Path, model: type[M]) -> M:
    """Validate a YAML file as ``model``; errors name the file."""
    return _validate(path, _load_yaml(path), model)


def _read_frontmatter(path: Path) -> dict[str, Any]:
    """The YAML frontmatter mapping of a markdown file (the body is for people)."""
    text = path.read_text(encoding="utf-8")
    # The closing delimiter is a line that is exactly ``---``; inside the YAML a
    # longer dash run or an indented continuation line never matches it.
    head, sep, _body = text.removeprefix("---\n").partition("\n---\n")
    if not text.startswith("---\n") or not sep:
        msg = f"{path}: expected YAML frontmatter between '---' lines"
        raise ChannelStoreError(msg)
    try:
        data = yaml.safe_load(head)
    except yaml.YAMLError as e:
        msg = f"{path}: invalid YAML frontmatter: {e}"
        raise ChannelStoreError(msg) from e
    if not isinstance(data, dict):
        msg = f"{path}: expected a YAML mapping in the frontmatter"
        raise ChannelStoreError(msg)
    return data


def _load_frontmatter[M: BaseModel](path: Path, model: type[M]) -> M:
    """Validate a markdown file's frontmatter as ``model``; errors name the file."""
    return _validate(path, _read_frontmatter(path), model)


def _load_records[M: BaseModel](
    directory: Path,
    model: type[M],
    timestamp: Callable[[M], datetime],
    suffix: str = YAML_SUFFIX,
) -> list[M]:
    """Every record file in ``directory`` in write order: by ``timestamp``, then by
    the filename's collision suffix (base file first, then ``-2``, ``-3`` …).
    ``.md`` records are read by their frontmatter."""
    if not directory.is_dir():
        return []
    load = _load_frontmatter if suffix == MARKDOWN_SUFFIX else _load_model
    paths = list(directory.glob(f"*{suffix}"))
    names = {p.name for p in paths}
    loaded = [(load(p, model), p.name) for p in paths]
    loaded.sort(
        key=lambda pair: (
            timestamp(pair[0]),
            _collision_index(pair[1], names, suffix),
            pair[1],
        )
    )
    return [record for record, _ in loaded]


def _latest_by_name(directory: Path, suffix: str = YAML_SUFFIX) -> Path | None:
    """The newest record file by name alone: its timestamp stem, then the same
    collision-suffix rule as ``_load_records``. Valid for files named by
    ``_stamp`` of the record's own timestamp (evidence snapshots, vet reports),
    so only one file needs parsing."""
    if not directory.is_dir():
        return None
    paths = list(directory.glob(f"*{suffix}"))
    names = {p.name for p in paths}

    def key(path: Path) -> tuple[str, int, str]:
        index = _collision_index(path.name, names, suffix)
        stem = path.stem
        if index > 1:
            stem = stem.rsplit("-", 1)[0]
        return (stem, index, path.name)

    return max(paths, key=key, default=None)


def _write_new(
    directory: Path, stem: str, content: str, suffix: str = YAML_SUFFIX
) -> Path:
    """Create ``<stem><suffix>`` exclusively, or ``<stem>-2<suffix>``, ``-3`` …
    if taken."""
    directory.mkdir(exist_ok=True)
    n = 1
    while True:
        name = f"{stem}{suffix}" if n == 1 else f"{stem}-{n}{suffix}"
        try:
            with (directory / name).open("x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            n += 1
            continue
        return directory / name


def _stamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


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
        return _load_records(
            self._channel_dir(slug) / REVIEWS_DIR, Review, lambda r: r.created_at
        )

    def evidence(self, slug: str) -> list[Evidence]:
        """Evidence snapshots of a channel in write order (by ``fetched_at``, same
        tie rule as reviews); the last one is the latest."""
        return _load_records(
            self._channel_dir(slug) / EVIDENCE_DIR, Evidence, lambda e: e.fetched_at
        )

    def latest_evidence(self, slug: str) -> Evidence | None:
        """The newest snapshot, parsing only its file (picked by name: the stem
        is the snapshot's ``fetched_at``)."""
        path = _latest_by_name(self._channel_dir(slug) / EVIDENCE_DIR)
        return None if path is None else _load_model(path, Evidence)

    def vets(self, slug: str) -> list[VetReport]:
        """Vet reports of a channel in write order (by ``vetted_at``, same tie rule
        as reviews); the last one is the latest."""
        return _load_records(
            self._channel_dir(slug) / VET_DIR,
            VetReport,
            lambda v: v.vetted_at,
            MARKDOWN_SUFFIX,
        )

    def latest_vet(self, slug: str) -> StoredVet | None:
        """The newest vet report and its path, parsing only its file (picked by
        name: the stem is the report's ``vetted_at``)."""
        path = _latest_by_name(self._channel_dir(slug) / VET_DIR, MARKDOWN_SUFFIX)
        if path is None:
            return None
        return StoredVet(_load_frontmatter(path, VetReport), path)

    def get(self, slug: str) -> ChannelEntry:
        return ChannelEntry(
            self.get_channel(slug),
            self.reviews(slug),
            self.latest_evidence(slug),
            self.latest_vet(slug),
        )

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
        stem = f"{_stamp(review.created_at)}-{slugify(review.reviewer) or 'reviewer'}"
        return _write_new(
            self._channel_dir(slug) / REVIEWS_DIR,
            stem,
            _dump_yaml(review.model_dump(mode="json")),
        )

    def add_evidence(self, slug: str, evidence: Evidence) -> Path:
        """Write a new evidence snapshot for ``slug``; never overwrites."""
        self.get_channel(slug)  # raises ChannelNotFoundError
        return _write_new(
            self._channel_dir(slug) / EVIDENCE_DIR,
            _stamp(evidence.fetched_at),
            _dump_yaml(evidence.model_dump(mode="json")),
        )

    def add_vet(self, slug: str, report: VetReport, body: str) -> Path:
        """Write a new vet report (YAML frontmatter + markdown ``body``) for
        ``slug``; never overwrites. Returns its path."""
        self.get_channel(slug)  # raises ChannelNotFoundError
        content = f"---\n{_dump_yaml(report.model_dump(mode='json'))}---\n\n{body}"
        return _write_new(
            self._channel_dir(slug) / VET_DIR,
            _stamp(report.vetted_at),
            content,
            MARKDOWN_SUFFIX,
        )

    def set_channel_id(self, slug: str, channel_id: str) -> bool:
        """Fill a null ``channel_id`` in ``channel.yaml`` (the one machine write to
        it, decision 0004). Returns ``True`` if written, ``False`` if it already
        held ``channel_id``; a different id raises ``ChannelIdMismatchError``, an
        id another channel holds raises ``ChannelExistsError``.

        Only ``channel_id`` changes: the rest of the mapping is kept as loaded, in
        its key order (YAML comments are not preserved). The write is atomic.
        """
        channel = self.get_channel(slug)
        if channel.channel_id == channel_id:
            return False
        if channel.channel_id is not None:
            self._mismatch(slug, channel.channel_id, channel_id)
        for other in self.slugs():
            if other != slug and self.get_channel(other).channel_id == channel_id:
                msg = f"{slug}: channel id '{channel_id}' is already slug '{other}'"
                raise ChannelExistsError(msg)
        path = self._channel_dir(slug) / CHANNEL_FILE
        raw = _load_yaml(path)
        raw["channel_id"] = channel_id
        Channel.model_validate(raw)  # refuse to write a file that won't load
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{CHANNEL_FILE}.", suffix=".tmp", dir=path.parent
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(_dump_yaml(raw))
            current = _load_yaml(path).get("channel_id")
            if current is not None:  # another writer got there first
                if current == channel_id:
                    return False
                self._mismatch(slug, current, channel_id)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
        return True

    @staticmethod
    def _mismatch(slug: str, current: str, resolved: str) -> NoReturn:
        msg = (
            f"{slug}: channel.yaml has channel_id '{current}' but the handle "
            f"resolves to '{resolved}'; not overwriting"
        )
        raise ChannelIdMismatchError(msg)
