"""``happytube channels`` — manage the trusted-channel registry.

Only ``resolve`` and ``evidence`` call the YouTube API (they need ``YTKEY``); the
rest need no keys. With ``--json`` the result goes to stdout as plain JSON (no rich
markup); errors go to stderr with a non-zero exit code.
"""

import json
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from happytube.channels.collect import Run, collect_evidence, resolve_channels
from happytube.channels.models import (
    KINDS,
    LANGUAGES,
    ROLES,
    STATUSES,
    VERDICTS,
    Channel,
    Review,
    slugify,
)
from happytube.channels.store import (
    ChannelEntry,
    ChannelStore,
    ChannelStoreError,
    filter_entries,
)
from happytube.config.settings import YouTubeSettings
from happytube.paths import PROJECT_ROOT
from happytube.youtube import YouTubeClient

console = Console()

json_option = click.option(
    "--json", "as_json", is_flag=True, help="Print machine-readable JSON to stdout."
)


def _echo_json(data: Any) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _store_errors_as_click(f: Callable) -> Callable:
    """Turn store and input-validation errors into a clean stderr message, exit 1.

    Problems in files on disk arrive as ``ChannelStoreError`` naming the file; a
    ``ValidationError`` here comes from command-line input.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ChannelStoreError as e:
            raise click.ClickException(str(e)) from e
        except ValidationError as e:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in e.errors()
            )
            msg = f"Invalid input: {problems}"
            raise click.ClickException(msg) from e

    return wrapper


@click.group()
@click.option(
    "--channels-dir",
    type=click.Path(file_okay=False, path_type=Path),
    envvar="HAPPYTUBE_CHANNELS_DIR",
    default=PROJECT_ROOT / "channels",
    show_default="channels/ at repo root",
    help="Registry directory (env: HAPPYTUBE_CHANNELS_DIR).",
)
@click.pass_context
def channels(ctx: click.Context, channels_dir: Path) -> None:
    """Trusted-channel registry: add candidates, list, show and review them."""
    ctx.obj = ChannelStore(channels_dir)


@channels.command("add")
@click.argument("name")
@click.option("--kind", type=click.Choice(KINDS), required=True)
@click.option(
    "--language",
    "languages",
    type=click.Choice(LANGUAGES),
    multiple=True,
    required=True,
    help="Repeat for several languages.",
)
@click.option("--handle", help="YouTube handle, starting with @.")
@click.option("--channel-id", help="YouTube channel id (UC…).")
@click.option("--url")
@click.option("--slug", help="Defaults to a kebab-case slug of NAME.")
@click.option("--notes")
@click.option("--added-by", required=True)
@json_option
@click.pass_obj
@_store_errors_as_click
def add_channel(  # noqa: PLR0913 - one parameter per CLI option
    store: ChannelStore,
    name: str,
    kind: str,
    languages: tuple[str, ...],
    handle: str | None,
    channel_id: str | None,
    url: str | None,
    slug: str | None,
    notes: str | None,
    added_by: str,
    as_json: bool,
) -> None:
    """Register NAME as a candidate channel."""
    slug = slug or slugify(name)
    if not slug:
        msg = f"Cannot derive a slug from '{name}'; pass --slug"
        raise click.ClickException(msg)
    channel = Channel.model_validate(
        {
            "slug": slug,
            "name": name,
            "kind": kind,
            "languages": list(languages),
            "handle": handle,
            "channel_id": channel_id,
            "url": url,
            "added_by": added_by,
            "notes": notes,
        }
    )
    store.add(channel)
    if as_json:
        _echo_json(store.get(slug).summary_dict())
    else:
        click.echo(slug)


@channels.command("list")
@click.option("--status", type=click.Choice(STATUSES))
@click.option("--kind", type=click.Choice(KINDS))
@click.option("--language", type=click.Choice(LANGUAGES))
@click.option(
    "--needs-human-review", is_flag=True, help="Only channels with no human review."
)
@json_option
@click.pass_obj
@_store_errors_as_click
def list_channels(  # noqa: PLR0913 - one parameter per CLI option
    store: ChannelStore,
    status: str | None,
    kind: str | None,
    language: str | None,
    needs_human_review: bool,
    as_json: bool,
) -> None:
    """List registered channels with their derived status."""
    entries = filter_entries(
        store.entries(),
        status=status,
        kind=kind,
        language=language,
        needs_human_review=needs_human_review,
    )
    if as_json:
        _echo_json([e.summary_dict() for e in entries])
        return
    _print_table(entries)


def _print_table(entries: list[ChannelEntry]) -> None:
    table = Table(title=f"Channels ({len(entries)})")
    table.add_column("Slug", no_wrap=True)  # copied into show/review, keep whole
    for column in ("Name", "Kind", "Lang", "Status", "Reviews (h/a)", "Evidence"):
        table.add_column(column)
    for e in entries:
        s = e.summary_dict()
        table.add_row(
            s["slug"],
            escape(s["name"]),
            s["kind"],
            ",".join(s["languages"]),
            s["status"],
            f"{s['human_review_count']}/{s['agent_review_count']}",
            (s["evidence_at"] or "-")[:10],
        )
    console.print(table)


@channels.command("show")
@click.argument("slug")
@json_option
@click.pass_obj
@_store_errors_as_click
def show_channel(store: ChannelStore, slug: str, as_json: bool) -> None:
    """Show a channel, its derived status and all reviews (oldest first)."""
    detail = store.get(slug).detail_dict()
    if as_json:
        _echo_json(detail)
        return
    reviews = detail.pop("reviews")
    evidence = detail.pop("evidence")
    for key, value in detail.items():
        if value is not None:
            shown = ", ".join(value) if isinstance(value, list) else value
            console.print(f"[bold]{key}[/bold]: {escape(str(shown))}", highlight=False)
    console.print(f"\n[bold]reviews[/bold] ({len(reviews)})")
    for r in reviews:
        console.print(
            f"  {r['created_at']}  {r['reviewer']} ({r['role']}): {r['verdict']}"
            + (f" — {r['notes']}" if r["notes"] else ""),
            highlight=False,
            markup=False,
        )
    _print_evidence(evidence)


def _print_evidence(evidence: dict[str, Any] | None, recent: int = 5) -> None:
    if evidence is None:
        console.print("\n[bold]evidence[/bold]: none yet (run channels evidence)")
        return
    videos = evidence["videos"]
    lines = [
        f"fetched_at: {evidence['fetched_at']}",
        f"resolved to: {evidence['title']} ({evidence['custom_url'] or '-'}, "
        f"{evidence['channel_id']})",
        f"subscribers: {evidence['subscriber_count'] or 'hidden'}, "
        f"videos on channel: {evidence['video_count']}",
        f"recent uploads stored: {len(videos)}, shorts: {evidence['shorts_count']}",
    ]
    lines += [
        f"  {v['published_at'][:10]}  {v['duration_s']}s"
        + (" short" if v["is_short"] else "")
        + f"  {v['title']}"
        for v in videos[:recent]
    ]
    console.print("\n[bold]evidence[/bold] (latest; full list with --json)")
    for line in lines:
        console.print(f"  {line}", highlight=False, markup=False, soft_wrap=True)


@channels.command("review")
@click.argument("slug")
@click.option("--reviewer", required=True)
@click.option("--role", type=click.Choice(ROLES), required=True)
@click.option("--verdict", type=click.Choice(VERDICTS), required=True)
@click.option("--notes")
@json_option
@click.pass_obj
@_store_errors_as_click
def review_channel(  # noqa: PLR0913 - one parameter per CLI option
    store: ChannelStore,
    slug: str,
    reviewer: str,
    role: str,
    verdict: str,
    notes: str | None,
    as_json: bool,
) -> None:
    """Record a review of SLUG. Only human approve/reject changes the status."""
    review = Review.model_validate(
        {"reviewer": reviewer, "role": role, "verdict": verdict, "notes": notes}
    )
    path = store.add_review(slug, review)
    status = store.get(slug).status
    if as_json:
        _echo_json(
            {
                "slug": slug,
                "status": status,
                "review": review.model_dump(mode="json"),
                "path": str(path),
            }
        )
    else:
        click.echo(f"{slug}: {status}")


def make_youtube_client() -> YouTubeClient:
    """Client with ``YTKEY`` from the environment or ``.env``; clean error if unset."""
    try:
        settings = YouTubeSettings()
    except ValidationError as e:
        msg = "YTKEY is not set (environment or .env); it is needed to call YouTube"
        raise click.ClickException(msg) from e
    return YouTubeClient(settings.youtube_api_key)


def _select_slugs(store: ChannelStore, slugs: tuple[str, ...], all_: bool) -> list[str]:
    """Slugs to process, each checked to exist before any quota is spent."""
    if all_ == bool(slugs):
        msg = "Give one or more SLUGs or --all (not both)"
        raise click.UsageError(msg)
    selected = store.slugs() if all_ else list(dict.fromkeys(slugs))
    for slug in selected:
        store.get_channel(slug)  # raises ChannelNotFoundError / broken file
    return selected


def _report(run: Run, as_json: bool) -> None:
    """Print a run, then exit 1 (message on stderr) if anything failed."""
    if as_json:
        _echo_json(run.as_dict())
    else:
        for r in run.results:
            detail = r.path or r.channel_id or ""
            if r.video_count is not None:
                detail += f" ({r.video_count} videos, {r.shorts_count} shorts)"
            if r.message:
                detail += f" — {r.message}" if detail else r.message
            console.print(
                f"{r.slug}: {r.status} {detail}".rstrip(),
                highlight=False,
                markup=False,
                soft_wrap=True,
            )
        console.print(f"quota units used: {run.quota_units}", highlight=False)
    if run.aborted:
        msg = f"Stopped early: {run.aborted}"
        raise click.ClickException(msg)
    if run.failed:
        msg = "Some channels failed; see the report above"
        raise click.ClickException(msg)


slug_args = click.argument("slugs", nargs=-1)
all_option = click.option(
    "--all", "all_", is_flag=True, help="Every channel in the registry."
)


@channels.command("resolve")
@slug_args
@all_option
@json_option
@click.pass_obj
@_store_errors_as_click
def resolve_command(
    store: ChannelStore, slugs: tuple[str, ...], all_: bool, as_json: bool
) -> None:
    """Resolve handles to channel ids via YouTube (1 quota unit per handle).

    Fills a missing channel_id in channel.yaml; a set one is verified and never
    overwritten. not_found / no_handle are reported, not failures.
    """
    selected = _select_slugs(store, slugs, all_)
    _report(resolve_channels(store, make_youtube_client(), selected), as_json)


@channels.command("evidence")
@slug_args
@all_option
@click.option(
    "--max-videos",
    type=click.IntRange(min=1),
    default=50,
    show_default=True,
    help="Recent uploads per channel (50 per quota unit).",
)
@json_option
@click.pass_obj
@_store_errors_as_click
def evidence_command(
    store: ChannelStore,
    slugs: tuple[str, ...],
    all_: bool,
    max_videos: int,
    as_json: bool,
) -> None:
    """Fetch stats and recent uploads; write one evidence snapshot per channel.

    Resolves missing channel ids first. Snapshots are append-only.
    """
    selected = _select_slugs(store, slugs, all_)
    run = collect_evidence(store, make_youtube_client(), selected, max_videos)
    _report(run, as_json)
