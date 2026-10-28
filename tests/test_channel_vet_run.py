"""``vet_channels`` and ``AnthropicVetClient`` with fakes (no network)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx2
import pytest

from happytube.channels.models import VetUsage
from happytube.channels.store import ChannelStore
from happytube.channels.vet import VetOutput, build_prompt
from happytube.channels.vet_run import (
    AnthropicVetClient,
    VetCallError,
    VetReply,
    VetStoppingError,
    vet_channels,
)
from tests.vet_helpers import (
    USAGE,
    FakeVetClient,
    make_channel,
    make_evidence,
    make_output,
    seed,
)


@pytest.fixture
def store(tmp_path):
    return ChannelStore(tmp_path / "channels")


def _files(store, slug, kind):
    directory = store.root / slug / kind
    return sorted(p.name for p in directory.iterdir()) if directory.is_dir() else []


@pytest.fixture
def vetted(store):
    """One channel vetted once by the fake client: (run, store)."""
    evidence = make_evidence()
    seed(store, evidence=evidence)
    return vet_channels(store, FakeVetClient(evidence), ["zoo-praha"]), store


def test_vet_result_names_the_report(vetted):
    run, store = vetted
    [result] = run.results
    assert (result.status, result.verdict, result.suitable) == ("vetted", "approve", 6)
    [name] = _files(store, "zoo-praha", "vet")
    assert (result.path or "").endswith(name)


def test_vet_adds_an_agent_review_that_does_not_decide(vetted):
    _, store = vetted
    [review] = store.reviews("zoo-praha")
    assert (review.reviewer, review.role, review.verdict) == (
        "claude-vet",
        "agent",
        "approve",
    )
    assert store.get("zoo-praha").status == "candidate"


def test_vet_run_totals_tokens_and_cost(vetted):
    run, _ = vetted
    assert (run.input_tokens, run.output_tokens, run.usd) == (1000, 500, 0.014)
    assert not run.failed


def test_current_vet_is_skipped_unless_forced(store):
    evidence = make_evidence()
    seed(store, evidence=evidence)
    client = FakeVetClient(evidence)
    vet_channels(store, client, ["zoo-praha"])
    again = vet_channels(store, client, ["zoo-praha"])
    assert again.results[0].status == "skipped_current"
    assert len(client.prompts) == 1
    forced = vet_channels(store, client, ["zoo-praha"], force=True)
    assert forced.results[0].status == "vetted"
    assert len(store.vets("zoo-praha")) == 2


def test_new_snapshot_makes_the_vet_stale(store):
    evidence = make_evidence()
    seed(store, evidence=evidence)
    client = FakeVetClient(evidence)
    vet_channels(store, client, ["zoo-praha"])
    newer = make_evidence(fetched_at=evidence.fetched_at.replace(day=29))
    store.add_evidence("zoo-praha", newer)
    client.evidence = newer
    assert vet_channels(store, client, ["zoo-praha"]).results[0].status == "vetted"


def test_unresolved_channel_is_skipped_without_files(store):
    seed(store, make_channel(channel_id=None))
    client = FakeVetClient(make_evidence())
    run = vet_channels(store, client, ["zoo-praha"])
    [result] = run.results
    assert (result.status, result.flags) == ("skipped_unresolved", ["unresolved"])
    assert (client.prompts, _files(store, "zoo-praha", "reviews")) == ([], [])
    assert not run.failed


def test_dry_run_calls_nothing_and_writes_nothing(store):
    seed(store, evidence=make_evidence(n_long=3))
    run = vet_channels(store, None, ["zoo-praha"])
    [result] = run.results
    assert (result.status, result.flags, result.long_form) == (
        "would_vet",
        ["mostly_shorts"],
        3,
    )
    assert run.as_dict()["dry_run"] is True
    assert _files(store, "zoo-praha", "vet") == []


def test_refusal_writes_nothing_and_fails(store):
    evidence = make_evidence()
    seed(store, evidence=evidence)
    reply = VetReply(None, "claude-opus-5-5", USAGE, "refusal", "bio")
    run = vet_channels(store, FakeVetClient(evidence, reply=reply), ["zoo-praha"])
    [result] = run.results
    assert (result.status, result.message, result.input_tokens) == (
        "refused",
        "stop_reason refusal (bio); nothing written",
        1000,  # still paid for
    )
    assert (_files(store, "zoo-praha", "vet"), store.reviews("zoo-praha")) == ([], [])
    assert run.failed


def test_output_for_other_videos_is_an_error(store):
    evidence = make_evidence()
    seed(store, evidence=evidence)
    client = FakeVetClient(make_evidence(n_long=2))  # scores only v0, v1
    run = vet_channels(store, client, ["zoo-praha"])
    assert run.results[0].status == "error"
    assert "missing v2, v3, v4, v5" in (run.results[0].message or "")
    assert _files(store, "zoo-praha", "vet") == []


def test_call_error_is_per_channel(store):
    evidence = make_evidence()
    seed(store, evidence=evidence)
    seed(store, make_channel(slug="zoo-zlin", channel_id="UCzlin"), evidence)
    client = FakeVetClient(evidence, errors={0: VetCallError("overloaded")})
    run = vet_channels(store, client, ["zoo-praha", "zoo-zlin"])
    assert [r.status for r in run.results] == ["error", "vetted"]
    assert run.aborted is None
    assert run.failed


def test_stopping_error_stops_the_run_keeping_written_files(store):
    evidence = make_evidence()
    seed(store, make_channel(slug="a", channel_id="UCa"), evidence)
    seed(store, make_channel(slug="b", channel_id="UCb"), evidence)
    seed(store, make_channel(slug="c", channel_id="UCc"), evidence)
    client = FakeVetClient(evidence, errors={1: VetStoppingError("401 bad key")})
    run = vet_channels(store, client, ["a", "b", "c"])
    assert [r.status for r in run.results] == ["vetted", "error", "not_vetted"]
    assert run.aborted == "401 bad key"
    assert len(store.vets("a")) == 1
    assert len(client.prompts) == 2


# --- AnthropicVetClient -----------------------------------------------------


def _sdk_response(stop_reason="end_turn", output=None, category=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        model="claude-opus-5-5",
        parsed_output=output,
        usage=SimpleNamespace(
            input_tokens=900,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=None,
            output_tokens=400,
        ),
    )


def _sdk_client(result):
    sdk = MagicMock()
    if isinstance(result, Exception):
        sdk.beta.messages.parse.side_effect = result
    else:
        sdk.beta.messages.parse.return_value = result
    return sdk


def _prompt():
    return build_prompt(make_channel(), make_evidence())


def test_client_sends_model_effort_schema_and_fallback():
    output = make_output(make_evidence())
    sdk = _sdk_client(_sdk_response(output=output))
    reply = AnthropicVetClient("unused", client=sdk).vet(_prompt())
    kwargs = sdk.beta.messages.parse.call_args.kwargs
    assert {
        k: kwargs[k] for k in sorted(kwargs) if k not in {"system", "messages"}
    } == {
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
        "max_tokens": 16000,
        "model": "claude-opus-5-5",
        "output_config": {"effort": "medium"},
        "output_format": VetOutput,
    }
    assert (reply.output, reply.usage) == (
        output,
        VetUsage(input_tokens=1000, output_tokens=400),
    )


def test_client_reports_refusal_without_output():
    sdk = _sdk_client(_sdk_response("refusal", output=None, category="cyber"))
    reply = AnthropicVetClient("unused", client=sdk).vet(_prompt())
    assert (reply.output, reply.stop_reason, reply.refusal_category) == (
        None,
        "refusal",
        "cyber",
    )


FAKE_URL = "http://fake.invalid/v1/messages"  # never contacted


def _status_error(cls, status, kind, message):
    request = httpx2.Request("POST", FAKE_URL)
    response = httpx2.Response(status, request=request)
    body = {"type": "error", "error": {"type": kind, "message": message}}
    return cls(message, response=response, body=body)


@pytest.mark.parametrize(
    ("error", "stops"),
    [
        (
            _status_error(
                anthropic.AuthenticationError,
                401,
                "authentication_error",
                "invalid x-api-key",
            ),
            True,
        ),
        (
            _status_error(
                anthropic.PermissionDeniedError, 403, "permission_error", "no"
            ),
            True,
        ),
        (
            _status_error(
                anthropic.BadRequestError,
                400,
                "invalid_request_error",
                "Your credit balance is too low",
            ),
            True,
        ),
        (_status_error(anthropic.APIStatusError, 402, "billing_error", "pay"), True),
        (
            _status_error(
                anthropic.RateLimitError, 429, "rate_limit_error", "slow down"
            ),
            False,
        ),
        (
            _status_error(
                anthropic.InternalServerError, 529, "overloaded_error", "busy"
            ),
            False,
        ),
    ],
)
def test_client_maps_api_errors(error, stops):
    client = AnthropicVetClient("unused", client=_sdk_client(error))
    with pytest.raises(VetCallError) as caught:
        client.vet(_prompt())
    assert isinstance(caught.value, VetStoppingError) is stops
    assert str(caught.value).startswith(f"Anthropic API {error.status_code} ")


def test_client_connection_error_names_no_request():
    request = httpx2.Request("POST", FAKE_URL)
    error = anthropic.APIConnectionError(request=request)
    with pytest.raises(VetCallError, match=r"^Anthropic API unreachable"):
        AnthropicVetClient("unused", client=_sdk_client(error)).vet(_prompt())
