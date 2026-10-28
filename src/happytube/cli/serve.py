"""``happytube serve`` — the local channel review UI (decision 0007).

Needs no API keys. Writes review files into the registry like
``happytube channels review``; committing them is up to the user. FastAPI and
uvicorn are imported inside ``serve`` so other commands don't pay for them.
"""

import socket
from pathlib import Path

import click

from happytube.channels.store import ChannelStore
from happytube.cli.channels import channels_dir_option


def _check_port_free(host: str, port: int) -> None:
    """Bind ``host:port`` once and let go, so a port in use is a one-line error
    before the banner, not a uvicorn traceback after it."""
    try:
        family = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][0]
        with socket.create_server((host, port), family=family):
            pass
    except OSError as e:
        msg = f"cannot listen on {host}:{port}: {e.strerror or e}"
        raise click.ClickException(msg) from e


@click.command()
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Address to listen on. A LAN address works too (there is no auth); "
    "0.0.0.0 / :: are refused.",
)
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
    import uvicorn  # noqa: PLC0415 — heavy, only this command needs it

    from happytube.review.app import (  # noqa: PLC0415
        create_app,
        is_loopback,
        is_wildcard,
    )

    host = host.strip("[]")
    if is_wildcard(host):
        msg = f"{host}: bind a concrete address (e.g. your LAN IP); there is no auth"
        raise click.BadParameter(msg, param_hint="--host")
    _check_port_free(host, port)
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
