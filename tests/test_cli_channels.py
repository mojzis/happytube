import json

import pytest
from click.testing import CliRunner

from happytube.cli.commands import cli
from happytube.paths import PROJECT_ROOT


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


def _review(run, slug="zoo-zlin", verdict="approve", *extra, role="human"):
    return run(
        "review",
        slug,
        "--reviewer",
        "matous" if role == "human" else "claude-vetter",
        "--role",
        role,
        "--verdict",
        verdict,
        *extra,
    )


def _no_traceback(result):
    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert isinstance(result.exception, SystemExit)  # click's clean exit, no crash
    return result.stderr


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
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "ct-decko"


def test_add_name_without_letters_needs_slug(run):
    stderr = _no_traceback(_add(run, "!!!"))
    assert "pass --slug" in stderr


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
    _review(run, "bbc-earth")
    approved = _json(run("list", "--status", "approved", "--json"))
    assert [c["slug"] for c in approved] == ["bbc-earth"]
    czech = _json(run("list", "--language", "cs", "--json"))
    assert [c["slug"] for c in czech] == ["zoo-zlin"]


def test_list_needs_human_review_skips_human_reviewed(run):
    _add(run)
    _add(run, "Zoo Praha")
    _review(run, "zoo-praha", role="agent")
    _review(run, "zoo-zlin", "unsure")
    data = _json(run("list", "--needs-human-review", "--json"))
    assert [(c["slug"], c["status"]) for c in data] == [("zoo-praha", "candidate")]


def test_list_table_shows_names(run):
    _add(run)
    result = run("list")
    assert result.exit_code == 0
    assert "Zoo Zlín" in result.stdout


def test_review_agent_approve_keeps_candidate(run):
    _add(run)
    data = _json(_review(run, "zoo-zlin", "approve", "--json", role="agent"))
    assert data["status"] == "candidate"
    assert data["review"]["role"] == "agent"


def test_review_human_reject_prints_status(run):
    _add(run)
    result = _review(run, "zoo-zlin", "reject", "--notes", "too loud")
    assert result.stdout.strip() == "zoo-zlin: rejected"


def test_review_unknown_slug_fails(run):
    stderr = _no_traceback(_review(run, "nope"))
    assert "No channel with slug 'nope'" in stderr


def test_show_json_lists_reviews_chronologically(run):
    _add(run)
    _review(run, "zoo-zlin", "unsure")
    _review(run, "zoo-zlin", "approve")
    data = _json(run("show", "zoo-zlin", "--json"))
    assert data["status"] == "approved"
    assert [r["verdict"] for r in data["reviews"]] == ["unsure", "approve"]


def test_show_text_includes_reviews(run):
    _add(run)
    _review(run, "zoo-zlin", "approve", "--notes", "calm [animals]")
    result = run("show", "zoo-zlin")
    assert result.exit_code == 0
    assert "calm [animals]" in result.stdout


def test_show_unknown_slug_fails(run):
    stderr = _no_traceback(run("show", "nope", "--json"))
    assert "No channel with slug 'nope'" in stderr


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


@pytest.mark.parametrize("slug", ["../outside", "ABS"])
def test_review_and_show_refuse_paths(run, tmp_path, slug):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "channel.yaml").write_text("slug: outside\n", encoding="utf-8")
    target = str(outside) if slug == "ABS" else slug
    assert "not a valid slug" in _no_traceback(_review(run, target))
    assert "not a valid slug" in _no_traceback(run("show", target))
    assert not (outside / "reviews").exists()


def test_malformed_yaml_is_a_clean_error_naming_the_file(run, tmp_path):
    _add(run)
    path = tmp_path / "channels" / "zoo-zlin" / "channel.yaml"
    path.write_text("slug: [unclosed\n", encoding="utf-8")
    for args in (("list",), ("list", "--json"), ("show", "zoo-zlin")):
        stderr = _no_traceback(run(*args))
        assert "invalid YAML" in stderr
        assert "channel.yaml" in stderr
        assert "zoo-zlin" in stderr


def test_broken_channel_blocks_add(run, tmp_path):
    _add(run)
    path = tmp_path / "channels" / "zoo-zlin" / "channel.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("zoo\n", "circus\n"), encoding="utf-8"
    )
    stderr = _no_traceback(_add(run, "Zoo Praha"))
    assert "kind" in stderr
    assert "zoo-zlin" in stderr
    assert not (tmp_path / "channels" / "zoo-praha").exists()


def test_slug_directory_mismatch_is_reported(run, tmp_path):
    _add(run)
    (tmp_path / "channels" / "zoo-zlin").rename(tmp_path / "channels" / "zlin")
    stderr = _no_traceback(run("list", "--json"))
    assert "does not match its directory 'zlin'" in stderr


def test_channels_dir_help_hides_absolute_path():
    result = CliRunner().invoke(cli, ["channels", "--help"])
    assert "channels/ at repo root" in result.stdout
    assert str(PROJECT_ROOT) not in result.stdout
