"""``happytube serve`` — the local channel review UI (decision 0007).

Needs no API keys. Writes review files into the registry like
``happytube channels review``; committing them is up to the user.
"""

from pathlib import Path

import click
import uvicorn

from happytube.channels.store import ChannelStore
from happytube.cli.channels import channels_dir_option
from happytube.review.app import create_app, is_loopback


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=click.IntRange(1, 65535))
@channels_dir_option
@click.option(
    "--reviewer",
    envvar="HAPPYTUBE_REVIEWER",
    help="Name prefilled in the review form when the browser has none remembered "
    "(env: HAPPYTUBE_REVIEWER).",
)
def serve(host: str, port: int, channels_dir: Path, reviewer: str | None) -> None:
    """Serve the channel review UI on HOST:PORT (local only, no auth)."""
    if not is_loopback(host):
        click.secho(
            f"Warning: serving on non-loopback host {host!r} — the review UI has "
            "no authentication and writes into the registry.",
            fg="yellow",
            err=True,
        )
    url_host = f"[{host}]" if ":" in host else host
    click.echo(f"Channel review UI: http://{url_host}:{port}/")
    click.echo(f"Registry: {channels_dir}")
    app = create_app(
        ChannelStore(channels_dir), default_reviewer=reviewer, bind_host=host
    )
    uvicorn.run(app, host=host, port=port)
