"""``happytube serve`` option wiring (``uvicorn.run`` monkeypatched; no server)."""

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from happytube.channels.store import ChannelStore
from happytube.cli import serve as serve_module
from happytube.cli.commands import cli
from happytube.paths import PROJECT_ROOT
from tests.review_helpers import QUEUE, detail_url, seed_vetted

LOCAL_8765 = "http://127.0.0.1:8765"
LOCALHOST = "http://localhost"
ALL_INTERFACES = "http://0.0.0.0:8000"


@pytest.fixture
def served(monkeypatch):
    calls = []
    monkeypatch.setattr(
        serve_module.uvicorn, "run", lambda app, **kw: calls.append((app, kw))
    )
    monkeypatch.delenv("HAPPYTUBE_CHANNELS_DIR", raising=False)
    monkeypatch.delenv("HAPPYTUBE_REVIEWER", raising=False)
    monkeypatch.delenv("YTKEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return calls


def test_serve_help():
    result = CliRunner().invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    for option in ["--host", "--port", "--channels-dir", "--reviewer"]:
        assert option in result.output
    assert "HAPPYTUBE_CHANNELS_DIR" in result.output
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


def test_serve_non_loopback_host_warns_and_accepts_that_host(served):
    result = CliRunner().invoke(cli, ["serve", "--host", "0.0.0.0"])  # noqa: S104

    assert result.exit_code == 0, result.output
    assert "no authentication" in result.stderr
    [(app, kwargs)] = served
    assert kwargs["host"] == "0.0.0.0"  # noqa: S104
    assert TestClient(app, base_url=ALL_INTERFACES).get(QUEUE).status_code == 200


def test_serve_ipv6_url(served):
    result = CliRunner().invoke(cli, ["serve", "--host", "::1"])
    assert "http://[::1]:8000/" in result.output
    assert "Warning" not in result.output
