"""The review queue: which channels a human should look at first (pure, no I/O)."""

import unicodedata
from dataclasses import dataclass

from happytube.channels.store import ChannelEntry, filter_entries
from happytube.channels.vet import channel_flags

# Latest vet verdict, most in need of a human first; not vetted comes last.
_VERDICT_RANK = {"unsure": 0, "reject": 1, "approve": 2}
_NOT_VETTED_RANK = len(_VERDICT_RANK)
_STATUS_RANK = {"candidate": 0, "approved": 1, "rejected": 2}


@dataclass(frozen=True)
class QueueSections:
    """Channels with no human review yet, and the ones that have one."""

    needs_review: list[ChannelEntry]
    reviewed: list[ChannelEntry]


def is_unresolved(entry: ChannelEntry) -> bool:
    """Nothing to judge yet: no ``channel_id`` or no evidence snapshot (the vet's
    ``unresolved`` rule)."""
    return "unresolved" in channel_flags(entry.channel, entry.latest_evidence)


def needs_attention(entry: ChannelEntry) -> bool:
    """The latest vet raised a flag, or the channel is unresolved."""
    if entry.latest_vet and entry.latest_vet.report.flags:
        return True
    return is_unresolved(entry)


def _name_key(entry: ChannelEntry) -> tuple[str, str]:
    """Name without diacritics, case-folded (``ČT`` sorts with ``C``), then slug."""
    decomposed = unicodedata.normalize("NFKD", entry.channel.name)
    base = "".join(c for c in decomposed if not unicodedata.combining(c))
    return (base.casefold(), entry.channel.slug)


def _needs_review_key(entry: ChannelEntry) -> tuple[int, int, tuple[str, str]]:
    verdict = entry.latest_vet.report.verdict if entry.latest_vet else ""
    rank = _VERDICT_RANK.get(verdict, _NOT_VETTED_RANK)
    return (0 if needs_attention(entry) else 1, rank, _name_key(entry))


def _reviewed_key(entry: ChannelEntry) -> tuple[int, tuple[str, str]]:
    return (_STATUS_RANK[entry.status], _name_key(entry))


def queue_sections(entries: list[ChannelEntry]) -> QueueSections:
    """Split into *needs human review* — attention first, then latest vet verdict
    ``unsure`` → ``reject`` → ``approve`` → not vetted, then name — and *reviewed*,
    by status (candidate, approved, rejected), then name."""
    pending = filter_entries(entries, needs_human_review=True)
    done = [e for e in entries if e.has_human_review]
    return QueueSections(
        needs_review=sorted(pending, key=_needs_review_key),
        reviewed=sorted(done, key=_reviewed_key),
    )
