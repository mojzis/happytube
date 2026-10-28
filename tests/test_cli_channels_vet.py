"""``channels vet`` and the vet parts of list and show (fake Claude, no network)."""

import json

import pytest
from click.testing import CliRunner

from happytube.channels.store import ChannelStore
from happytube.channels.vet_run import VetCallError, VetStoppingError
from happytube.cli import channels as channels_cli
from happytube.cli.commands import cli
from tests.vet_helpers import FakeVetClient, make_channel, make_evidence, seed


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A registry with zoo-praha (6 long-form videos) and an unresolved zoo-zlin;
    no API keys in the environment and no ``.env`` in the working directory."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("YTKEY", raising=False)
    monkeypatch.setenv("HAPPYTUBE_CHANNELS_DIR", str(tmp_path / "channels"))
    store = ChannelStore(tmp_path / "channels")
    seed(store, evidence=make_evidence())
    seed(store, make_channel(slug="zoo-zlin", channel_id=None, name="Zoo Zlín"))
    return store


@pytest.fixture
def claude(monkeypatch):
    fake = FakeVetClient(make_evidence())
    monkeypatch.setattr(channels_cli, "make_vet_client", lambda: fake)
    return fake


def _run(*args):
    return CliRunner().invoke(cli, ["channels", *args])


def _json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_vet_json_reports_each_channel_and_totals(store, claude):
    data = _json(_run("vet", "--all", "--json"))
    assert [(r["slug"], r["status"]) for r in data["results"]] == [
        ("zoo-praha", "vetted"),
        ("zoo-zlin", "skipped_unresolved"),
    ]
    assert (data["input_tokens"], data["output_tokens"], data["usd"]) == (
        1000,
        500,
        0.014,
    )


def test_vet_writes_report_and_review(store, claude):
    _run("vet", "zoo-praha")
    assert len(store.vets("zoo-praha")) == 1
    assert [r.reviewer for r in store.reviews("zoo-praha")] == ["claude-vet"]


def test_vet_text_shows_verdict_and_cost(store, claude):
    result = _run("vet", "zoo-praha")
    assert result.exit_code == 0, result.output
    assert "zoo-praha: vetted approve 6/6 suitable" in result.stdout
    assert "tokens: 1000 in, 500 out, est. $0.01 (estimate at Opus 5.5" in result.stdout


def test_second_vet_is_skipped(store, claude):
    _run("vet", "zoo-praha")
    data = _json(_run("vet", "zoo-praha", "--json"))
    assert data["results"][0]["status"] == "skipped_current"
    assert len(claude.prompts) == 1


def test_dry_run_needs_no_key_and_writes_nothing(store):
    data = _json(_run("vet", "--all", "--dry-run", "--json"))
    assert [r["status"] for r in data["results"]] == [
        "would_vet",
        "skipped_unresolved",
    ]
    assert store.vets("zoo-praha") == []


def test_vet_without_key_is_a_clean_error(store):
    result = _run("vet", "zoo-praha")
    assert (result.exit_code, result.stdout) == (1, "")
    assert "ANTHROPIC_API_KEY is not set" in result.stderr
    assert "Traceback" not in result.stderr


def test_stopping_error_exits_non_zero_with_json_on_stdout(store, monkeypatch):
    fake = FakeVetClient(make_evidence(), errors={0: VetStoppingError("401 bad")})
    monkeypatch.setattr(channels_cli, "make_vet_client", lambda: fake)
    result = _run("vet", "--all", "--json")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["aborted"] == "401 bad"
    assert "Stopped early: 401 bad" in result.stderr


def test_vet_needs_slugs_or_all(store):
    assert _run("vet").exit_code == 2


def test_list_and_show_without_vets(store):
    [row] = [r for r in _json(_run("list", "--json")) if r["slug"] == "zoo-praha"]
    assert (row["vetted_at"], row["vet_verdict"]) == (None, None)
    assert "vet: none yet" in _run("show", "zoo-praha").stdout


def test_list_and_show_with_a_vet(store, claude):
    _run("vet", "zoo-praha")
    [row] = [r for r in _json(_run("list", "--json")) if r["slug"] == "zoo-praha"]
    assert row["vet_verdict"] == "approve"
    detail = _json(_run("show", "zoo-praha", "--json"))
    assert (detail["vet"]["suitable_count"], len(detail["vet"]["videos"])) == (6, 6)


def test_show_text_summarises_the_latest_vet(store, claude):
    _run("vet", "zoo-praha")
    text = _run("show", "zoo-praha").stdout
    assert "verdict: approve (model: approve), flags: none" in text
    assert "suitable: 6 of 6 long-form, shorts skipped: 2" in text


@pytest.mark.parametrize(
    ("as_json", "where"),
    [(True, "see the JSON on stdout"), (False, "see the report above")],
)
def test_channel_failure_message_points_to_the_output(
    store, monkeypatch, as_json, where
):
    fake = FakeVetClient(make_evidence(), errors={0: VetCallError("overloaded")})
    monkeypatch.setattr(channels_cli, "make_vet_client", lambda: fake)
    result = _run("vet", "zoo-praha", *(["--json"] if as_json else []))
    assert result.exit_code == 1
    assert f"Some channels failed; {where}" in result.stderr


def test_vet_help_says_force_after_a_prompt_change(store):
    help_text = " ".join(_run("vet", "--help").stdout.split())
    assert "after a prompt or model change, pass --force" in help_text
