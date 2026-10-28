"""``happytube channels`` — manage the trusted-channel registry.

Only ``resolve`` and ``evidence`` call the YouTube API (they need ``YTKEY``);
``vet`` calls Claude (it needs only ``ANTHROPIC_API_KEY``); the rest need no
keys. With ``--json`` the result goes to stdout as plain JSON (no rich markup);
errors go to stderr with a non-zero exit code.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError
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
    filter_entries,
)
from happytube.channels.vet_run import AnthropicVetClient, VetRun, vet_channels
from happytube.cli.common import (
    channels_dir_option,
    console,
    echo_json,
    json_option,
    make_youtube_client,
    print_lines,
    store_errors_as_click,
    with_message,
)
from happytube.config.settings import AnthropicSettings


@click.group()
@channels_dir_option
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
@store_errors_as_click
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
        echo_json(store.get(slug).summary_dict())
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
@store_errors_as_click
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
        echo_json([e.summary_dict() for e in entries])
        return
    _print_table(entries)


def _print_table(entries: list[ChannelEntry]) -> None:
    table = Table(title=f"Channels ({len(entries)})")
    table.add_column("Slug", no_wrap=True)  # copied into show/review, keep whole
    for column in (
        "Name",
        "Kind",
        "Lang",
        "Status",
        "Reviews (h/a)",
        "Evidence",
        "Vet",
    ):
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
            s["vet_verdict"] or "-",
        )
    console.print(table)


@channels.command("show")
@click.argument("slug")
@json_option
@click.pass_obj
@store_errors_as_click
def show_channel(store: ChannelStore, slug: str, as_json: bool) -> None:
    """Show a channel, its derived status and all reviews (oldest first)."""
    detail = store.get(slug).detail_dict()
    if as_json:
        echo_json(detail)
        return
    reviews = detail.pop("reviews")
    evidence = detail.pop("evidence")
    vet = detail.pop("vet")
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
    _print_vet(vet)


def _print_vet(vet: dict[str, Any] | None) -> None:
    if vet is None:
        console.print("\n[bold]vet[/bold]: none yet (run channels vet)")
        return
    console.print("\n[bold]vet[/bold] (latest; full report with --json)")
    print_lines(
        [
            f"  vetted_at: {vet['vetted_at']} (snapshot {vet['evidence_at']})",
            f"  verdict: {vet['verdict']} (model: {vet['model_verdict']}), "
            f"flags: {', '.join(vet['flags']) or 'none'}",
            f"  calm {vet['channel_calm']}/5, happy {vet['channel_happy']}/5, "
            f"suitable: {vet['suitable_count']} of {len(vet['videos'])} long-form, "
            f"shorts skipped: {vet['shorts_skipped']}",
            f"  summary: {vet['summary']}",
            f"  report: {vet['path']}",
        ]
    )


def _or(value: Any, missing: str) -> Any:
    """``value``, or ``missing`` when it is ``None`` (``0`` stays ``0``)."""
    return missing if value is None else value


def _print_evidence(evidence: dict[str, Any] | None, recent: int = 5) -> None:
    if evidence is None:
        console.print("\n[bold]evidence[/bold]: none yet (run channels evidence)")
        return
    videos = evidence["videos"]
    lines = [
        f"fetched_at: {evidence['fetched_at']}",
        f"resolved to: {evidence['title']} ({evidence['custom_url'] or '-'}, "
        f"{evidence['channel_id']})",
        f"subscribers: {_or(evidence['subscriber_count'], 'hidden')}, "
        f"videos on channel: {evidence['video_count']}",
        f"recent uploads stored: {len(videos)}, shorts: {evidence['shorts_count']} "
        f"(by {evidence['shorts_source']})",
    ]
    lines += [
        f"  {v['published_at'][:10]}  "
        + ("?" if v["duration_s"] is None else f"{v['duration_s']}s")
        + (" short" if v["is_short"] else "")
        + f"  {v['title']}"
        for v in videos[:recent]
    ]
    console.print("\n[bold]evidence[/bold] (latest; full list with --json)")
    print_lines([f"  {line}" for line in lines])


@channels.command("review")
@click.argument("slug")
@click.option("--reviewer", required=True)
@click.option("--role", type=click.Choice(ROLES), required=True)
@click.option("--verdict", type=click.Choice(VERDICTS), required=True)
@click.option("--notes")
@json_option
@click.pass_obj
@store_errors_as_click
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
        echo_json(
            {
                "slug": slug,
                "status": status,
                "review": review.model_dump(mode="json"),
                "path": str(path),
            }
        )
    else:
        click.echo(f"{slug}: {status}")


def _select_slugs(store: ChannelStore, slugs: tuple[str, ...], all_: bool) -> list[str]:
    """Slugs to process, each checked to exist before any quota is spent."""
    if all_ == bool(slugs):
        msg = "Give one or more SLUGs or --all (not both)"
        raise click.UsageError(msg)
    selected = store.slugs() if all_ else list(dict.fromkeys(slugs))
    for slug in selected:
        store.get_channel(slug)  # raises ChannelNotFoundError / broken file
    return selected


def _finish(run: Run | VetRun, as_json: bool, lines: Callable[[], list[str]]) -> None:
    """Print a run as JSON or as ``lines()``, then exit 1 (message on stderr) if
    anything failed."""
    if as_json:
        echo_json(run.as_dict())
    else:
        print_lines(lines())
    if run.aborted:
        msg = f"Stopped early: {run.aborted}"
        raise click.ClickException(msg)
    if run.failed:
        where = "the JSON on stdout" if as_json else "the report above"
        msg = f"Some channels failed; see {where}"
        raise click.ClickException(msg)


def _report(run: Run, as_json: bool) -> None:
    """Print a resolve or evidence run; exit 1 if anything failed."""

    def lines() -> list[str]:
        out = []
        for r in run.results:
            detail = r.path or r.channel_id or ""
            if r.video_count is not None:
                detail += f" ({r.video_count} videos, {r.shorts_count} shorts)"
            out.append(with_message(f"{r.slug}: {r.status} {detail}", r.message))
        return [*out, f"quota units used: {run.quota_units}"]

    _finish(run, as_json, lines)


def _report_vet(run: VetRun, as_json: bool) -> None:
    """Print a vet run with token and cost totals; exit 1 if anything failed."""

    def lines() -> list[str]:
        out = []
        for r in run.results:
            text = f"{r.slug}: {r.status}"
            if r.verdict:
                text += f" {r.verdict}"
            if r.model_verdict and r.model_verdict != r.verdict:
                text += f" (model: {r.model_verdict})"
            if r.flags:
                text += f" [{', '.join(r.flags)}]"
            if r.suitable is not None:
                text += f" {r.suitable}/{r.long_form} suitable"
            elif r.long_form is not None:
                text += f" ({r.long_form} long-form)"
            if r.path:
                text += f" {r.path}"
            out.append(with_message(text, r.message))
        total = (
            "dry run: no calls, no files"
            if run.dry_run
            else f"tokens: {run.input_tokens} in, {run.output_tokens} out, "
            f"est. ${run.usd:.2f} (estimate at Opus 5.5 rates)"
        )
        return [*out, total]

    _finish(run, as_json, lines)


slug_args = click.argument("slugs", nargs=-1)
all_option = click.option(
    "--all", "all_", is_flag=True, help="Every channel in the registry."
)


@channels.command("resolve")
@slug_args
@all_option
@click.option(
    "--verify",
    is_flag=True,
    help="Also re-check channels that already have a channel_id (1 unit each).",
)
@json_option
@click.pass_obj
@store_errors_as_click
def resolve_command(
    store: ChannelStore,
    slugs: tuple[str, ...],
    all_: bool,
    verify: bool,
    as_json: bool,
) -> None:
    """Resolve handles to channel ids via YouTube (1 quota unit per handle).

    Fills a missing channel_id in channel.yaml. Channels that already have one are
    'already' at no cost; with --verify their handle is re-checked and a different
    id is a mismatch, never overwritten. not_found / no_handle are reported, not
    failures.
    """
    selected = _select_slugs(store, slugs, all_)
    client = make_youtube_client()
    _report(resolve_channels(store, client, selected, verify=verify), as_json)


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
@store_errors_as_click
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


def make_vet_client() -> AnthropicVetClient:
    """Client with ``ANTHROPIC_API_KEY`` from the environment or ``.env``."""
    try:
        settings = AnthropicSettings()
    except ValidationError as e:
        msg = (
            "ANTHROPIC_API_KEY is not set (environment or .env); it is needed to "
            "vet channels (try --dry-run)"
        )
        raise click.ClickException(msg) from e
    return AnthropicVetClient(settings.anthropic_api_key.get_secret_value())


@channels.command("vet")
@slug_args
@all_option
@click.option(
    "--force", is_flag=True, help="Re-vet channels whose latest vet is current."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show flags and what would be vetted; no Claude call, no key, no files.",
)
@json_option
@click.pass_obj
@store_errors_as_click
def vet_command(  # noqa: PLR0913 - one parameter per CLI option
    store: ChannelStore,
    slugs: tuple[str, ...],
    all_: bool,
    force: bool,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Vet channels with Claude from their latest evidence snapshot.

    Writes an append-only vet report (vet/<time>.md) and an agent review per
    channel; agent reviews never change status. Channels whose latest vet used
    the latest snapshot are skipped unless --force; after a prompt or model
    change, pass --force to re-vet them. Unresolved channels (no channel_id or
    no snapshot) and channels a human rejected are skipped without a call.
    """
    selected = _select_slugs(store, slugs, all_)
    client = None if dry_run else make_vet_client()
    _report_vet(vet_channels(store, client, selected, force=force), as_json)
