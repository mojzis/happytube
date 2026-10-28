"""``happytube trusted`` — the daily pipeline over approved channels (decision 0009).

``fetch`` needs ``YTKEY``; ``assess`` and ``enhance`` need ``ANTHROPIC_API_KEY``,
and only when there is something to send (``--dry-run`` never); ``run`` needs
both; ``status`` none. Files go to ``stages/trusted/`` under the current
directory. ``--json`` prints plain JSON to stdout; errors go to stderr and any
failure (a stopped run, a channel or batch that failed) exits non-zero.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from happytube.channels.store import ChannelStore
from happytube.claude import ClaudeCaller
from happytube.cli.common import (
    channels_dir_option,
    echo_json,
    json_option,
    make_youtube_client,
    print_lines,
    store_errors_as_click,
    with_message,
)
from happytube.config.settings import AnthropicSettings
from happytube.trusted.assess import assess_trusted
from happytube.trusted.enhance import enhance_trusted
from happytube.trusted.fetch import FetchRun, fetch_trusted
from happytube.trusted.runs import ItemRun
from happytube.trusted.stages import status_counts
from happytube.utils import today_local


def _parse_date(
    _ctx: click.Context, _param: click.Parameter, value: str | None
) -> date:
    """``YYYY-MM-DD``, or today (local) when not given — as the legacy commands."""
    if value is None:
        return today_local()
    try:
        return date.fromisoformat(value)
    except ValueError:
        msg = f"{value!r} is not a date; use YYYY-MM-DD"
        raise click.BadParameter(msg) from None


date_option = click.option(
    "--date",
    "target_date",
    callback=_parse_date,
    help="Target date YYYY-MM-DD (default: today).",
)
since_days_option = click.option(
    "--since-days",
    type=click.IntRange(min=0),
    default=14,
    show_default=True,
    help="Keep videos published this many days before --date, up to it.",
)
max_per_channel_option = click.option(
    "--max-per-channel",
    type=click.IntRange(min=1),
    default=50,
    show_default=True,
    help="Newest uploads looked at per channel (50 per quota unit).",
)
force_option = click.option(
    "--force", is_flag=True, help="Redo the date's videos already done."
)
dry_run_option = click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be sent; no call, no key, no files.",
)


def make_claude_caller() -> ClaudeCaller:
    """Caller with ``ANTHROPIC_API_KEY`` from the environment or ``.env``."""
    try:
        settings = AnthropicSettings()
    except ValidationError as e:
        msg = (
            "ANTHROPIC_API_KEY is not set (environment or .env); it is needed to "
            "assess and enhance videos (try --dry-run)"
        )
        raise click.ClickException(msg) from e
    return ClaudeCaller(settings.anthropic_api_key.get_secret_value())


@click.group()
@channels_dir_option
@click.pass_context
def trusted(ctx: click.Context, channels_dir: Path) -> None:
    """Trusted pipeline: fetch approved channels' new videos, assess, enhance."""
    ctx.obj = ChannelStore(channels_dir)


def _fetch_lines(run: FetchRun) -> list[str]:
    out = []
    for r in run.results:
        text = f"{r.slug}: {r.status}"
        if r.status == "fetched":
            text += (
                f" {r.new} new ({r.seen} seen, {r.shorts} shorts by "
                f"{r.shorts_source}, {r.live} live/upcoming, "
                f"{r.outside_window} outside window"
                + (f", {r.unreadable} unreadable" if r.unreadable else "")
                + ")"
            )
        out.append(with_message(text, r.message))
    return [*out, f"new videos: {run.new}, quota units used: {run.quota_units}"]


def _item_lines(run: ItemRun, verb: str) -> list[str]:
    out = []
    for r in run.results:
        text = f"{r.slug}: {r.status} {len(r.video_ids)} video(s)"
        if r.suitable is not None:
            text += f", {r.suitable} suitable"
        if r.model and r.status == "done":
            text += f" ({r.model})"
        out.append(with_message(text, r.message))
    out.append(f"already {verb}: {run.skipped}")
    out.append(
        "dry run: no calls, no files"
        if run.dry_run
        else f"tokens: {run.input_tokens} in, {run.output_tokens} out, "
        f"est. ${run.usd:.2f} (estimate at Opus 5.5 rates)"
    )
    return out


def _failure(run: FetchRun | ItemRun, as_json: bool) -> str | None:
    """Why ``run`` failed (for stderr), or ``None``."""
    if run.aborted:
        return f"Stopped early: {run.aborted}"
    if run.failed:
        where = "the JSON on stdout" if as_json else "the report above"
        return f"Some items failed; see {where}"
    return None


def _finish(
    run: FetchRun | ItemRun, as_json: bool, lines: Callable[[], list[str]]
) -> None:
    if as_json:
        echo_json(run.as_dict())
    else:
        print_lines(lines())
    if problem := _failure(run, as_json):
        raise click.ClickException(problem)


def _claude(dry_run: bool) -> Callable[[], ClaudeCaller] | None:
    return None if dry_run else make_claude_caller


@trusted.command("fetch")
@click.argument("slugs", nargs=-1)
@date_option
@since_days_option
@max_per_channel_option
@json_option
@click.pass_obj
@store_errors_as_click
def fetch_command(  # noqa: PLR0913 - one parameter per CLI option
    store: ChannelStore,
    slugs: tuple[str, ...],
    target_date: date,
    since_days: int,
    max_per_channel: int,
    as_json: bool,
) -> None:
    """Fetch new long-form videos of approved channels (all, or SLUGs).

    A named channel that is not approved is an error. Videos already fetched
    on any date are skipped, so a rerun for the same date writes nothing new.
    """
    run = fetch_trusted(
        store,
        make_youtube_client(),
        target_date,
        slugs=list(slugs),
        since_days=since_days,
        max_per_channel=max_per_channel,
    )
    _finish(run, as_json, lambda: _fetch_lines(run))


@trusted.command("assess")
@date_option
@force_option
@dry_run_option
@json_option
def assess_command(
    target_date: date, force: bool, dry_run: bool, as_json: bool
) -> None:
    """Score the date's fetched videos with the calm/happy rubric (Claude).

    One call per channel batch; already assessed videos are skipped unless
    --force.
    """
    run = assess_trusted(target_date, _claude(dry_run), force=force)
    _finish(run, as_json, lambda: _item_lines(run, "assessed"))


@trusted.command("enhance")
@date_option
@force_option
@dry_run_option
@json_option
def enhance_command(
    target_date: date, force: bool, dry_run: bool, as_json: bool
) -> None:
    """Rewrite descriptions of the date's suitable videos (Claude).

    Unsuitable videos are never enhanced; already enhanced ones are skipped
    unless --force.
    """
    run = enhance_trusted(target_date, _claude(dry_run), force=force)
    _finish(run, as_json, lambda: _item_lines(run, "enhanced"))


@trusted.command("run")
@date_option
@since_days_option
@max_per_channel_option
@json_option
@click.pass_obj
@store_errors_as_click
def run_command(
    store: ChannelStore,
    target_date: date,
    since_days: int,
    max_per_channel: int,
    as_json: bool,
) -> None:
    """Fetch, assess and enhance for the date; any failing step stops the chain.

    Every step is idempotent, so rerunning after a failure is cheap.
    """
    steps: dict[str, Any] = {"fetch": None, "assess": None, "enhance": None}
    fetch = fetch_trusted(
        store,
        make_youtube_client(),
        target_date,
        since_days=since_days,
        max_per_channel=max_per_channel,
    )
    chain: list[tuple[str, FetchRun | ItemRun, list[str]]] = [
        ("fetch", fetch, _fetch_lines(fetch))
    ]
    if not fetch.failed:
        assess = assess_trusted(target_date, make_claude_caller)
        chain.append(("assess", assess, _item_lines(assess, "assessed")))
        if not assess.failed:
            enhance = enhance_trusted(target_date, make_claude_caller)
            chain.append(("enhance", enhance, _item_lines(enhance, "enhanced")))
    for name, run, _ in chain:
        steps[name] = run.as_dict()
    if as_json:
        echo_json(steps)
    else:
        print_lines([f"{name}: {line}" for name, _, lines in chain for line in lines])
    name, last, _ = chain[-1]
    if problem := _failure(last, as_json):
        msg = f"{name} failed, chain stopped. {problem}"
        raise click.ClickException(msg)


@trusted.command("status")
@date_option
@json_option
def status_command(target_date: date, as_json: bool) -> None:
    """Videos fetched, assessed, suitable and enhanced on the date, per channel."""
    counts = status_counts(target_date)
    if as_json:
        echo_json(counts)
        return
    rows = [
        f"{c['slug']}: fetched {c['fetched']}, assessed {c['assessed']}, "
        f"suitable {c['suitable']}, enhanced {c['enhanced']}"
        for c in counts["channels"]
    ]
    t = counts["totals"]
    rows.append(
        f"total {counts['date']}: fetched {t['fetched']}, assessed {t['assessed']}, "
        f"suitable {t['suitable']}, enhanced {t['enhanced']}"
    )
    print_lines(rows)
