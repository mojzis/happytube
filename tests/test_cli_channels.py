import json

import pytest
from click.testing import CliRunner

from happytube.cli.commands import cli


@pytest.fixture
def run(tmp_path, monkeypatch):
    """Invoke ``happytube channels …`` against a temp registry with no API keys."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("YTKEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HAPPYTUBE_CHANNELS_DIR", str(tmp_path / "channels"))

    def _run(*args):
        return CliRunner().invoke(cli, ["channels", *args])

    return _run


def _add(run, name="Zoo Zlín", *extra):
    return run(
        "add", name, "--kind", "zoo", "--language", "cs", "--added-by", "me", *extra
    )


def _json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_add_prints_slug_and_writes_file(run, tmp_path):
    result = _add(run)
    assert result.exit_code == 0
    assert result.stdout.strip() == "zoo-zlin"
    assert (tmp_path / "channels" / "zoo-zlin" / "channel.yaml").is_file()


def test_add_json_reports_candidate(run):
    data = _json(_add(run, "Zoo Zlín", "--json", "--handle", "@zoozlin"))
    assert (data["slug"], data["status"], data["handle"]) == (
        "zoo-zlin",
        "candidate",
        "@zoozlin",
    )


def test_add_duplicate_fails_on_stderr(run):
    _add(run)
    result = _add(run)
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "already registered" in result.stderr


def test_add_invalid_handle_fails_cleanly(run):
    result = _add(run, "Zoo Zlín", "--handle", "no-at-sign")
    assert result.exit_code != 0
    assert "handle" in result.stderr


def test_add_explicit_slug(run):
    result = _add(run, "ČT :D / Déčko", "--slug", "ct-decko")
    assert result.stdout.strip() == "ct-decko"


def test_list_json_filters_by_status_and_language(run):
    _add(run)
    run(
        "add",
        "BBC Earth",
        "--kind",
        "broadcaster",
        "--language",
        "en",
        "--added-by",
        "me",
    )
    run(
        "review",
        "bbc-earth",
        "--reviewer",
        "matous",
        "--role",
        "human",
        "--verdict",
        "approve",
    )
    approved = _json(run("list", "--status", "approved", "--json"))
    assert [c["slug"] for c in approved] == ["bbc-earth"]
    czech = _json(run("list", "--language", "cs", "--json"))
    assert [c["slug"] for c in czech] == ["zoo-zlin"]


def test_list_needs_human_review_skips_human_reviewed(run):
    _add(run)
    _add(run, "Zoo Praha")
    run(
        "review",
        "zoo-praha",
        "--reviewer",
        "claude",
        "--role",
        "agent",
        "--verdict",
        "approve",
    )
    run(
        "review",
        "zoo-zlin",
        "--reviewer",
        "matous",
        "--role",
        "human",
        "--verdict",
        "unsure",
    )
    data = _json(run("list", "--needs-human-review", "--json"))
    assert [(c["slug"], c["status"]) for c in data] == [("zoo-praha", "candidate")]


def test_list_table_shows_names(run):
    _add(run)
    result = run("list")
    assert result.exit_code == 0
    assert "Zoo Zlín" in result.stdout


def test_review_agent_approve_keeps_candidate(run):
    _add(run)
    data = _json(
        run(
            "review",
            "zoo-zlin",
            "--reviewer",
            "claude-vetter",
            "--role",
            "agent",
            "--verdict",
            "approve",
            "--json",
        )
    )
    assert data["status"] == "candidate"
    assert data["review"]["role"] == "agent"


def test_review_human_reject_prints_status(run):
    _add(run)
    result = run(
        "review",
        "zoo-zlin",
        "--reviewer",
        "matous",
        "--role",
        "human",
        "--verdict",
        "reject",
        "--notes",
        "too loud",
    )
    assert result.stdout.strip() == "zoo-zlin: rejected"


def test_review_unknown_slug_fails(run):
    result = run(
        "review", "nope", "--reviewer", "m", "--role", "human", "--verdict", "approve"
    )
    assert result.exit_code != 0
    assert "No channel" in result.stderr


def test_show_json_lists_reviews_chronologically(run):
    _add(run)
    review = ("review", "zoo-zlin", "--reviewer", "matous", "--role", "human")
    run(*review, "--verdict", "unsure")
    run(*review, "--verdict", "approve")
    data = _json(run("show", "zoo-zlin", "--json"))
    assert data["status"] == "approved"
    assert [r["verdict"] for r in data["reviews"]] == ["unsure", "approve"]


def test_show_text_includes_reviews(run):
    _add(run)
    run(
        "review",
        "zoo-zlin",
        "--reviewer",
        "matous",
        "--role",
        "human",
        "--verdict",
        "approve",
        "--notes",
        "calm [animals]",
    )
    result = run("show", "zoo-zlin")
    assert result.exit_code == 0
    assert "calm [animals]" in result.stdout


def test_show_unknown_slug_fails(run):
    result = run("show", "nope", "--json")
    assert result.exit_code != 0
    assert result.stdout == ""


def test_channels_dir_option_overrides_env(run, tmp_path):
    other = tmp_path / "other"
    result = CliRunner().invoke(
        cli,
        [
            "channels",
            "--channels-dir",
            str(other),
            "add",
            "Zoo Praha",
            "--kind",
            "zoo",
            "--language",
            "cs",
            "--added-by",
            "me",
        ],
    )
    assert result.exit_code == 0
    assert (other / "zoo-praha" / "channel.yaml").is_file()
