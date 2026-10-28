"""``happytube serve`` option wiring (``uvicorn.run`` monkeypatched; no server)."""

import socket
import subprocess
import sys

import pytest
import uvicorn
from click.testing import CliRunner
from fastapi.testclient import TestClient

from happytube.channels.store import ChannelStore
from happytube.cli.commands import cli
from happytube.paths import PROJECT_ROOT
from tests.player_helpers import PLAYER_JSON, write_shown
from tests.review_helpers import QUEUE, detail_url, seed_vetted
from tests.trusted_helpers import add_channel

LOCAL_8765 = "http://127.0.0.1:8765"
LOCALHOST = "http://localhost"


@pytest.fixture
def run_calls(monkeypatch):
    """``uvicorn.run`` calls, with a clean environment; the port check is real."""
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append((app, kw)))
    monkeypatch.delenv("HAPPYTUBE_CHANNELS_DIR", raising=False)
    monkeypatch.delenv("HAPPYTUBE_STAGES_DIR", raising=False)
    monkeypatch.delenv("HAPPYTUBE_REVIEWER", raising=False)
    monkeypatch.delenv("YTKEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return calls


@pytest.fixture
def served(run_calls, monkeypatch):
    """As ``run_calls``, with the port check passing: tests don't depend on port
    8000 being free or on this machine having the address."""
    monkeypatch.setattr("happytube.cli.serve._check_port_free", lambda host, port: None)
    return run_calls


def test_serve_help():
    result = CliRunner().invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    for option in ["--host", "--port", "--channels-dir", "--stages-dir", "--reviewer"]:
        assert option in result.output
    assert "HAPPYTUBE_CHANNELS_DIR" in result.output
    assert "HAPPYTUBE_STAGES_DIR" in result.output
    assert "HAPPYTUBE_REVIEWER" in result.output


def test_serve_defaults(served):
    result = CliRunner().invoke(cli, ["serve"])

    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:8000/" in result.output
    assert "Warning" not in result.output
    [(_, kwargs)] = served
    assert kwargs == {"host": "127.0.0.1", "port": 8000}
    assert str(PROJECT_ROOT / "channels") in result.output


def test_serve_options_reach_the_app(served, tmp_path):
    registry = tmp_path / "reg"
    result = CliRunner().invoke(
        cli,
        [
            "serve",
            "--port",
            "8765",
            "--channels-dir",
            str(registry),
            "--reviewer",
            "Matouš",
        ],
    )

    assert result.exit_code == 0, result.output
    [(app, kwargs)] = served
    assert kwargs["port"] == 8765
    page = TestClient(app, base_url=LOCAL_8765).get(QUEUE)
    assert "No channels in the registry." in page.text  # missing dir: starts anyway
    assert not registry.exists()


def test_serve_env_vars(served, tmp_path, monkeypatch):
    seed_vetted(ChannelStore(tmp_path), "zoo-praha", "Zoo Praha")
    monkeypatch.setenv("HAPPYTUBE_CHANNELS_DIR", str(tmp_path))
    monkeypatch.setenv("HAPPYTUBE_REVIEWER", "babička-helper")

    result = CliRunner().invoke(cli, ["serve"])

    assert result.exit_code == 0, result.output
    [(app, _)] = served
    html = TestClient(app, base_url=LOCALHOST).get(detail_url("zoo-praha")).text
    assert 'name="reviewer" value="babička-helper"' in html


def test_serve_prints_player_url_and_stages_dir(served):
    result = CliRunner().invoke(cli, ["serve"])
    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:8000/player/" in result.output
    assert "Stages: stages" in result.output


def test_serve_stages_dir_reaches_the_player(served, tmp_path, monkeypatch):
    registry = tmp_path / "channels"
    add_channel(ChannelStore(registry), "zoo", "UCzoo")
    write_shown(tmp_path / "st", "zoo")
    monkeypatch.setenv("HAPPYTUBE_STAGES_DIR", str(tmp_path / "st"))

    result = CliRunner().invoke(cli, ["serve", "--channels-dir", str(registry)])

    assert result.exit_code == 0, result.output
    [(app, _)] = served
    videos = TestClient(app, base_url=LOCALHOST).get(PLAYER_JSON).json()
    assert [v["channel_slug"] for v in videos] == ["zoo"]


@pytest.mark.parametrize("host", ["192.168.1.5", "fe80::1", "[fe80::1]"])
def test_serve_lan_host_warns_and_accepts_that_host(served, host):
    result = CliRunner().invoke(cli, ["serve", "--host", host])

    assert result.exit_code == 0, result.output
    assert "no authentication" in result.stderr
    [(app, kwargs)] = served
    bare = host.strip("[]")
    assert kwargs["host"] == bare
    url_host = f"[{bare}]" if ":" in bare else bare
    assert f"http://{url_host}:8000/" in result.output
    page = TestClient(app, base_url=f"http://{url_host}:8000").get(QUEUE)
    assert page.status_code == 200


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "[::]"])  # noqa: S104
def test_serve_refuses_wildcard_host(served, host):
    result = CliRunner().invoke(cli, ["serve", "--host", host])

    assert result.exit_code == 2
    assert "bind a concrete address (e.g. your LAN IP); there is no auth" in (
        result.output
    )
    assert "Channel review UI" not in result.output
    assert served == []


def test_serve_ipv6_loopback_url(served):
    result = CliRunner().invoke(cli, ["serve", "--host", "::1"])

    assert result.exit_code == 0, result.output
    assert "http://[::1]:8000/" in result.output
    assert "Warning" not in result.output


def test_serve_port_in_use_is_one_line_error(run_calls):
    with socket.create_server(("127.0.0.1", 0)) as taken:
        port = taken.getsockname()[1]
        result = CliRunner().invoke(cli, ["serve", "--port", str(port)])

    assert result.exit_code == 1
    assert f"Error: cannot listen on 127.0.0.1:{port}:" in result.output
    assert "Channel review UI" not in result.output
    assert run_calls == []


def test_cli_import_leaves_out_the_web_stack():
    code = (
        "import sys, happytube.cli.commands; "
        "print(sorted({'fastapi', 'uvicorn', 'starlette'} & set(sys.modules)))"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
