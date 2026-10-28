"""``happytube channels`` — manage the trusted-channel registry.

No command here needs API keys. With ``--json`` the result goes to stdout as plain
JSON (no rich markup); errors go to stderr with a non-zero exit code.
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
from happytube.channels.store import ChannelEntry, ChannelStore, ChannelStoreError
from happytube.paths import PROJECT_ROOT

console = Console()

json_option = click.option(
    "--json", "as_json", is_flag=True, help="Print machine-readable JSON to stdout."
)


def _echo_json(data: Any) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _store_errors_as_click(f: Callable) -> Callable:
    """Turn store and validation errors into a clean stderr message and exit 1."""

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
    show_default=True,
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
    entries = [
        e
        for e in store.entries()
        if (status is None or e.status == status)
        and (kind is None or e.channel.kind == kind)
        and (language is None or language in e.channel.languages)
        and not (needs_human_review and e.has_human_review)
    ]
    if as_json:
        _echo_json([e.summary_dict() for e in entries])
        return
    _print_table(entries)


def _print_table(entries: list[ChannelEntry]) -> None:
    table = Table(title=f"Channels ({len(entries)})")
    table.add_column("Slug", no_wrap=True)  # copied into show/review, keep whole
    for column in ("Name", "Kind", "Lang", "Status", "Reviews (h/a)"):
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
