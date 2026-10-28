"""Vet channels with Claude: the API call and the run over several channels.

Shared by ``channels vet`` and, later, the web UI; no click or rich here. The call
sits behind ``VetClient`` so tests use a fake (no network). Per-channel problems
become results; an authentication, permission or billing error stops the run
(``VetRun.aborted``), keeping the files already written. Human-rejected channels
(the blocklist, decision 0003) are skipped without a call.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

import anthropic
from anthropic.types.beta import BetaContentBlock, BetaJSONOutputFormatParam
from pydantic import ValidationError

from happytube.channels.models import (
    Channel,
    ChannelFlag,
    Evidence,
    Verdict,
    VetUsage,
)
from happytube.channels.store import ChannelStore, derive_status
from happytube.channels.vet import (
    MODEL,
    Prompt,
    VetOutput,
    VetOutputError,
    build_prompt,
    build_report,
    channel_flags,
    long_form,
    render_report,
    review_for,
)

# Claude Opus 5.5 list prices, USD per million tokens. Estimates only: input is
# counted at the base rate even when served from cache, and a call the refusal
# fallback answered with another model is still priced at Opus 5.5 rates.
USD_PER_MTOK_INPUT = 4.0
USD_PER_MTOK_OUTPUT = 20.0
MAX_TOKENS = 16000
EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Structured output: the SDK moves what the API cannot enforce (score 1-5) into
# the descriptions; ``VetOutput.model_validate_json`` checks it on our side.
OUTPUT_FORMAT = BetaJSONOutputFormatParam(
    type="json_schema", schema=anthropic.transform_schema(VetOutput)
)
_STOPPING_TYPES = frozenset(
    {"authentication_error", "permission_error", "billing_error"}
)
_STOPPING_STATUS = frozenset({401, 402, 403})
_NOT_VETTED = "not vetted: run stopped (Anthropic key, permission or credit problem)"

VetStatus = Literal[
    "vetted",
    "would_vet",
    "skipped_current",
    "skipped_unresolved",
    "skipped_rejected",
    "refused",
    "error",
    "not_vetted",
]
FAILURE_STATUSES: frozenset[str] = frozenset({"refused", "error", "not_vetted"})


def estimate_usd(input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens * USD_PER_MTOK_INPUT + output_tokens * USD_PER_MTOK_OUTPUT)
        / 1_000_000,
        4,
    )


class VetError(Exception):
    """A vet call failed without a response (nothing to bill or record)."""


class VetCallError(VetError):
    """One call failed (after the SDK's retries); the run goes on."""


class VetStoppingError(VetError):
    """The key, its permissions or the credit balance failed; the run stops."""


@dataclass
class VetReply:
    """What one call returned. ``model`` is the model that answered (the refusal
    fallback may have switched it). ``output`` is ``None`` on a refusal (then
    ``refusal_category``) or when the output is unusable (then ``error``); the
    tokens were paid for either way."""

    output: VetOutput | None
    model: str
    usage: VetUsage
    stop_reason: str | None
    refusal_category: str | None = None
    error: str | None = None


class VetClient(Protocol):
    def vet(self, prompt: Prompt) -> VetReply: ...


def _error_detail(error: anthropic.APIStatusError) -> tuple[str, str]:
    """The API's error type and message — never headers or the request."""
    body = error.body if isinstance(error.body, dict) else {}
    detail = body.get("error")
    if not isinstance(detail, dict):
        detail = {}
    kind = detail.get("type") or type(error).__name__
    return str(kind), str(detail.get("message") or "")


def _call_error(error: anthropic.APIStatusError) -> VetError:
    """``VetStoppingError`` for a bad key, missing permission or no credit;
    ``VetCallError`` for anything else (rate limits and 5xx after retries)."""
    kind, message = _error_detail(error)
    text = f"Anthropic API {error.status_code} {kind}: {message}".rstrip(": ")
    # A low credit balance comes back as 400 invalid_request_error, so only its
    # message tells it apart from a bad request.
    stopping = (
        error.status_code in _STOPPING_STATUS
        or kind in _STOPPING_TYPES
        or "credit balance" in message.lower()
    )
    return VetStoppingError(text) if stopping else VetCallError(text)


def _answer_text(content: list[BetaContentBlock]) -> str:
    """The text of the answer: text blocks after the last ``fallback`` block
    (non-streaming responses already drop a declined partial; this is a guard)."""
    texts: list[str] = []
    for block in content:
        if block.type == "fallback":
            texts = []
        elif block.type == "text":
            texts.append(block.text)
    return "".join(texts)


class AnthropicVetClient:
    """``VetClient`` on the Anthropic API: Claude Opus 5.5, adaptive thinking
    (the model's default), effort ``medium``, structured output, and the
    server-side refusal fallback."""

    def __init__(self, api_key: str, client: anthropic.Anthropic | None = None):
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=3)

    def vet(self, prompt: Prompt) -> VetReply:
        try:
            response = self._client.beta.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": prompt.system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt.user}],
                output_config={"effort": EFFORT, "format": OUTPUT_FORMAT},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            raise _call_error(e) from None
        except anthropic.APIConnectionError as e:
            msg = f"Anthropic API unreachable: {type(e).__name__}"
            raise VetCallError(msg) from None
        usage = response.usage
        tokens = VetUsage(
            input_tokens=usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0),
            output_tokens=usage.output_tokens,
        )
        stop = response.stop_reason
        if stop == "refusal":
            details = response.stop_details
            category = details.category if details else None
            return VetReply(None, response.model, tokens, stop, category)
        if stop == "max_tokens":
            error = f"output cut off at max_tokens ({MAX_TOKENS})"
            return VetReply(None, response.model, tokens, stop, error=error)
        try:
            output = VetOutput.model_validate_json(_answer_text(response.content))
        except ValidationError as e:  # not JSON, or e.g. a score outside 1-5
            error = f"model output did not parse ({e.error_count()} problems)"
            return VetReply(None, response.model, tokens, stop, error=error)
        return VetReply(output, response.model, tokens, stop)


@dataclass
class VetResult:
    slug: str
    status: VetStatus
    flags: list[ChannelFlag] = field(default_factory=list)
    verdict: Verdict | None = None
    model_verdict: Verdict | None = None
    model: str | None = None  # the model that answered, when one was called
    message: str | None = None
    path: str | None = None
    review_path: str | None = None
    long_form: int | None = None
    suitable: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def usd(self) -> float:
        return estimate_usd(self.input_tokens, self.output_tokens)


@dataclass
class VetRun:
    """Outcome of a vet run over several channels."""

    results: list[VetResult] = field(default_factory=list)
    aborted: str | None = None
    dry_run: bool = False

    @property
    def input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.results)

    @property
    def output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.results)

    @property
    def usd(self) -> float:
        return estimate_usd(self.input_tokens, self.output_tokens)

    @property
    def failed(self) -> bool:
        return self.aborted is not None or any(
            r.status in FAILURE_STATUSES for r in self.results
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "results": [{**asdict(r), "usd": r.usd} for r in self.results],
            "aborted": self.aborted,
            "dry_run": self.dry_run,
            "requested_model": MODEL,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": self.usd,
        }


def _vet_one(
    store: ChannelStore,
    client: VetClient | None,
    slug: str,
    *,
    force: bool,
) -> VetResult:
    """Vet one channel; ``client=None`` is a dry run. Raises
    ``VetStoppingError``; other call errors become an ``error`` result."""
    channel = store.get_channel(slug)
    if derive_status(store.reviews(slug)) == "rejected":
        message = "rejected by a human (blocklist); not vetted"
        return VetResult(slug, "skipped_rejected", message=message)
    evidence = store.latest_evidence(slug)
    result = VetResult(slug, "skipped_unresolved", channel_flags(channel, evidence))
    if evidence is None or "unresolved" in result.flags:
        result.message = "no channel_id or no evidence snapshot; nothing to judge"
        return result
    result.long_form = len(long_form(evidence))
    latest = store.latest_vet(slug)
    if not force and latest and latest.report.evidence_at == evidence.fetched_at:
        result.status, result.path = "skipped_current", str(latest.path)
        result.verdict = latest.report.verdict
        result.message = "latest vet already used the latest snapshot (--force)"
        return result
    if client is None:
        result.status = "would_vet"
    else:
        _call_and_write(store, client, channel, evidence, result)
    return result


def _call_and_write(
    store: ChannelStore,
    client: VetClient,
    channel: Channel,
    evidence: Evidence,
    result: VetResult,
) -> None:
    """Call the model and, if its output fits, write the report and the agent
    review; fills ``result``. Raises ``VetStoppingError``."""
    try:
        reply = client.vet(build_prompt(channel, evidence))
    except VetCallError as e:  # VetStoppingError is not one: it stops the run
        result.status, result.message = "error", str(e)
        return
    result.model = reply.model
    result.input_tokens = reply.usage.input_tokens
    result.output_tokens = reply.usage.output_tokens
    if reply.stop_reason == "refusal":
        category = f" ({reply.refusal_category})" if reply.refusal_category else ""
        result.status = "refused"
        result.message = f"stop_reason refusal{category}; nothing written"
        return
    if reply.output is None:
        problem = reply.error or f"no output (stop_reason {reply.stop_reason})"
        result.status, result.message = "error", f"{problem}; nothing written"
        return
    try:
        report = build_report(
            evidence, reply.output, result.flags, model=reply.model, usage=reply.usage
        )
    except VetOutputError as e:
        result.status, result.message = "error", f"{e}; nothing written"
        return
    path = store.add_vet(result.slug, report, render_report(channel, report))
    review_path = store.add_review(result.slug, review_for(report, path.name))
    result.status, result.flags = "vetted", list(report.flags)
    result.verdict, result.model_verdict = report.verdict, report.model_verdict
    result.path, result.review_path = str(path), str(review_path)
    result.suitable = report.suitable_count


def vet_channels(
    store: ChannelStore,
    client: VetClient | None,
    slugs: list[str],
    *,
    force: bool = False,
) -> VetRun:
    """Vet ``slugs`` in order; ``client=None`` is a dry run (no call, no files).

    A channel whose latest vet used its latest snapshot is ``skipped_current``
    unless ``force``. If the run stops, files already written stay and every
    channel not reached is ``not_vetted``.
    """
    run = VetRun(dry_run=client is None)
    for index, slug in enumerate(slugs):
        try:
            run.results.append(_vet_one(store, client, slug, force=force))
        except VetStoppingError as e:
            run.aborted = str(e)
            run.results.append(VetResult(slug, "error", message=str(e)))
            run.results += [
                VetResult(s, "not_vetted", message=_NOT_VETTED)
                for s in slugs[index + 1 :]
            ]
            break
    return run
