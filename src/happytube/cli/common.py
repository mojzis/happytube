"""Pieces shared by the ``channels``, ``trusted`` and ``serve`` commands: the
``--channels-dir`` and ``--json`` options, JSON and plain-line output, the
store-error wrapper and the YouTube client from ``YTKEY``."""

import json
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError
from rich.console import Console

from happytube.channels.store import ChannelStoreError
from happytube.config.settings import YouTubeSettings
from happytube.paths import PROJECT_ROOT
from happytube.youtube import YouTubeClient

console = Console()

json_option = click.option(
    "--json", "as_json", is_flag=True, help="Print machine-readable JSON to stdout."
)

channels_dir_option = click.option(
    "--channels-dir",
    type=click.Path(file_okay=False, path_type=Path),
    envvar="HAPPYTUBE_CHANNELS_DIR",
    default=PROJECT_ROOT / "channels",
    show_default="channels/ at repo root",
    help="Registry directory (env: HAPPYTUBE_CHANNELS_DIR).",
)


def echo_json(data: Any) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def print_lines(lines: list[str]) -> None:
    """Plain lines (no rich markup or highlighting: names may contain ``[``)."""
    for line in lines:
        console.print(line, highlight=False, markup=False, soft_wrap=True)


def with_message(text: str, message: str | None) -> str:
    if not message:
        return text.rstrip()
    return f"{text.rstrip()} — {message}"


def store_errors_as_click(f: Callable) -> Callable:
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


def make_youtube_client() -> YouTubeClient:
    """Client with ``YTKEY`` from the environment or ``.env``; clean error if unset."""
    try:
        settings = YouTubeSettings()
    except ValidationError as e:
        msg = "YTKEY is not set (environment or .env); it is needed to call YouTube"
        raise click.ClickException(msg) from e
    return YouTubeClient(settings.youtube_api_key.get_secret_value())
