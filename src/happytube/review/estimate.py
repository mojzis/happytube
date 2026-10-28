"""How many watchable videos the approved channels hold — a rough estimate (pure).

Per channel: total uploads * long-form share of the latest snapshot * suitable share
of the latest vet. Shorts are never watchable (the vet never scores them). A channel
without evidence, an upload count or a vet with scored videos is not estimated.
"""

from dataclasses import dataclass

from happytube.channels.store import ChannelEntry
from happytube.channels.vet import long_form


@dataclass(frozen=True)
class WatchableEstimate:
    """Totals over the approved channels."""

    channels: int  # approved channels
    estimated_channels: int  # of those, with enough data for an estimate
    videos: int  # estimated watchable videos over the estimated channels
    sampled_suitable: int  # videos the vets actually judged suitable


def channel_watchable(entry: ChannelEntry) -> int | None:
    """Estimated watchable videos of one channel, ``None`` without enough data."""
    evidence = entry.latest_evidence
    vet = entry.latest_vet.report if entry.latest_vet else None
    if evidence is None or not evidence.video_count or not evidence.videos:
        return None
    if vet is None or not vet.videos:
        return None
    long_share = len(long_form(evidence)) / len(evidence.videos)
    suitable_share = vet.suitable_count / len(vet.videos)
    return round(evidence.video_count * long_share * suitable_share)


def watchable_estimate(entries: list[ChannelEntry]) -> WatchableEstimate:
    """The estimate over the ``approved`` entries."""
    approved = [e for e in entries if e.status == "approved"]
    per_channel = [channel_watchable(e) for e in approved]
    known = [n for n in per_channel if n is not None]
    sampled = sum(e.latest_vet.report.suitable_count for e in approved if e.latest_vet)
    return WatchableEstimate(
        channels=len(approved),
        estimated_channels=len(known),
        videos=sum(known),
        sampled_suitable=sampled,
    )
