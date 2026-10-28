from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from happytube.cli.commands import cli


def _forbidden():
    response = MagicMock(status_code=403, reason="Forbidden")
    response.json.return_value = {"error": {"message": "quotaExceeded"}}
    return response


def test_fetch_exits_nonzero_on_youtube_api_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YTKEY", "secret-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    with patch("happytube.videos.requests.get", return_value=_forbidden()):
        result = CliRunner().invoke(cli, ["fetch", "--date", "2026-01-01"])
    assert result.exit_code == 1
    assert "403 Forbidden - quotaExceeded" in result.output
    assert "secret-key" not in result.output


def test_run_all_exits_nonzero_on_youtube_api_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YTKEY", "secret-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    with patch("happytube.videos.requests.get", return_value=_forbidden()):
        result = CliRunner().invoke(cli, ["run-all", "--date", "2026-01-01"])
    assert result.exit_code == 1
    assert "Pipeline failed" in result.output
    # The config message is printed under the stage header, not above it.
    assert result.output.index("Stage 1/4: Fetch") < result.output.index(
        "No config found"
    )
