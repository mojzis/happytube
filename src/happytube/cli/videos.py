"""``happytube videos`` — spot-check the trusted pipeline's videos (decision 0011).

The same queue, records and agreement as the review UI's ``/videos``; no API
keys. Reads ``stages/trusted/`` (``--stages-dir``), the channel registry and
``video-reviews/``; ``review`` writes one file there — commit and push it
yourself. With ``--json`` the result goes to stdout as plain JSON; errors go to
stderr with a non-zero exit code.
"""

from dataclasses import dataclass
from pathlib import Path

import click
from rich.markup import escape
from rich.table import Table

from happytube.channels.models import ROLES
from happytube.channels.store import ChannelStore
from happytube.cli.common import (
    channels_dir_option,
    console,
    echo_json,
    json_option,
    print_lines,
    stages_dir_option,
    store_errors_as_click,
    video_reviews_dir_option,
)
from happytube.rubric import FLAGS
from happytube.trusted.spot_checks import (
    SECTION_FILTERS,
    SECTIONS,
    SpotVideo,
    in_section,
    load_spot_checks,
    load_video,
    new_review,
    queue_agreement,
    reload_reviews,
)
from happytube.trusted.video_reviews import (
    VIDEO_VERDICTS,
    WATCHED,
    VideoReviewStore,
)
from happytube.utils import fmt_utc


def _agent(suitable: bool) -> str:
    return "suitable" if suitable else "unsuitable"


def _or_dash(value: object) -> str:
    return "—" if value is None else str(value)


def _version(value: int | None) -> str:
    return "—" if value is None else f"v{value}"


@dataclass(frozen=True)
class _Dirs:
    stages_dir: Path
    channels: ChannelStore
    reviews: VideoReviewStore

    def load(self) -> list[SpotVideo]:
        return load_spot_checks(self.stages_dir, self.channels, self.reviews)

    def get(self, video_id: str) -> SpotVideo:
        return load_video(self.stages_dir, self.channels, self.reviews, video_id)


@click.group()
@channels_dir_option
@stages_dir_option
@video_reviews_dir_option
@click.pass_context
def videos(
    ctx: click.Context, channels_dir: Path, stages_dir: Path, video_reviews_dir: Path
) -> None:
    """Spot-check trusted videos: the queue, one video, a review, agreement."""
    ctx.obj = _Dirs(
        stages_dir, ChannelStore(channels_dir), VideoReviewStore(video_reviews_dir)
    )


@videos.command("list")
@click.option(
    "--section",
    type=click.Choice(SECTION_FILTERS),
    help="shown: in the player, not spot-checked; unreviewed: not shown, not "
    "spot-checked; reviewed; disagree: latest human verdict against the agent.",
)
@json_option
@click.pass_obj
@store_errors_as_click
def list_videos(dirs: _Dirs, section: str | None, as_json: bool) -> None:
    """The spot-check queue: shown-and-unreviewed first, then the other
    unreviewed, then the reviewed videos."""
    current = dirs.load()
    names = [section] if section else list(SECTIONS)
    rows = [v for name in names for v in in_section(current, name)]
    if as_json:
        echo_json([v.summary_dict() for v in rows])
        return
    table = Table(title=f"Videos ({len(rows)})")
    table.add_column("Id", no_wrap=True)  # copied into show/review, keep whole
    for column in ("Section", "Title", "Channel", "Agent", "Player", "Human"):
        table.add_column(column)
    for v in rows:
        s = v.summary_dict()
        human = s["verdict"] or ("unreadable" if s["review_error"] else "-")
        if s["disagrees"]:
            human += " (disagrees)"
        table.add_row(
            s["video_id"],
            s["section"],
            escape(s["title"]),
            escape(s["channel_slug"]),
            "suitable" if s["agent_suitable"] else "unsuitable",
            "shown" if s["shown"] else "-",
            human,
        )
    console.print(table)


@videos.command("show")
@click.argument("video_id")
@json_option
@click.pass_obj
@store_errors_as_click
def show_video(dirs: _Dirs, video_id: str, as_json: bool) -> None:
    """Show a video: the agent's call, what the player does, every review."""
    video = dirs.get(video_id)
    detail = video.detail_dict()
    if as_json:
        echo_json(detail)
        return
    a = video.assess
    lines = [
        f"{a.video_id}: {a.title}",
        f"channel: {a.channel_name} ({a.channel_slug})",
        f"https://www.youtube.com/watch?v={a.video_id}",
        f"agent: {_agent(a.suitable)} — calm {_or_dash(a.calm)}, happy "
        f"{_or_dash(a.happy)}, flags {', '.join(a.flags) or 'none'}, rubric "
        f"{_version(a.rubric_version)}, assessed {fmt_utc(a.assessed_at)}",
        f"note: {a.note or '—'}",
        f"player: {'shown' if video.shown else 'not shown'}",
        f"section: {video.section}",
    ]
    if a.incomplete:
        lines.append(f"incomplete assess: lacks {', '.join(a.missing())}")
    if video.state.error:
        lines.append(f"unreadable review (video hidden): {video.state.error}")
    lines.append(f"\nreviews ({len(video.state.reviews)})")
    lines.extend(
        f"  {fmt_utc(r.created_at)}  {r.reviewer} ({r.role}): {r.verdict}, "
        f"watched {r.watched}"
        + (f", flags {', '.join(r.flags)}" if r.flags else "")
        + f" — vs agent {_agent(r.agent_suitable)}"
        + (" (rescored since)" if video.rescored(r) else "")
        + (f" — {r.notes}" if r.notes else "")
        for r in video.state.reviews
    )
    print_lines(lines)


@videos.command("review")
@click.argument("video_id")
@click.option("--reviewer", required=True)
@click.option("--role", type=click.Choice(ROLES), required=True)
@click.option("--verdict", type=click.Choice(VIDEO_VERDICTS), required=True)
@click.option(
    "--flag",
    "flags",
    type=click.Choice(FLAGS),
    multiple=True,
    help="Rubric flag; repeat for several.",
)
@click.option(
    "--watched",
    type=click.Choice(WATCHED),
    required=True,
    help="How much you watched: the full video, part of it, or the title only.",
)
@click.option("--notes", help="Public: the repo is public.")
@json_option
@click.pass_obj
@store_errors_as_click
def review_video(  # noqa: PLR0913 - one parameter per CLI option
    dirs: _Dirs,
    video_id: str,
    reviewer: str,
    role: str,
    verdict: str,
    flags: tuple[str, ...],
    watched: str,
    notes: str | None,
    as_json: bool,
) -> None:
    """Record a spot-check of VIDEO_ID. A human "unsuitable" hides it from the
    player; agent reviews are stored but never count."""
    video = dirs.get(video_id)
    review = new_review(
        video,
        reviewer=reviewer,
        role=role,
        verdict=verdict,
        flags=flags,
        watched=watched,
        notes=notes,
    )
    path = dirs.reviews.add_review(video_id, review)
    after = reload_reviews(video, dirs.reviews)
    if as_json:
        echo_json(
            {
                "video_id": video_id,
                "shown": after.shown,
                "verdict": after.latest.verdict if after.latest else None,
                "review": review.model_dump(mode="json"),
                "path": str(path),
            }
        )
    else:
        click.echo(f"{video_id}: {'shown' if after.shown else 'not shown'}")


@videos.command("stats")
@json_option
@click.pass_obj
@store_errors_as_click
def video_stats(dirs: _Dirs, as_json: bool) -> None:
    """How often the latest human verdict agrees with the agent's call it was
    shown (agent reviews never count)."""
    current = dirs.load()
    stats = queue_agreement(current)
    data = {"assessed": len(current), **stats.as_dict()}
    if as_json:
        echo_json(data)
        return
    rate = "—" if stats.rate is None else f"{stats.rate:.0%}"
    lines = [
        f"spot-checked {stats.reviewed} of {len(current)} assessed videos",
        f"agreement {rate}: {stats.agree} agree, {stats.disagree} disagree, "
        f"{stats.unsure} unsure",
    ]
    lines.extend(
        f"  human {verdict}: agent suitable {stats.count(verdict, True)}, "
        f"agent unsuitable {stats.count(verdict, False)}"
        for verdict in VIDEO_VERDICTS
    )
    print_lines(lines)
