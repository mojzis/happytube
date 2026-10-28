"""Vet channels with Claude: the API call and the run over several channels.

Shared by ``channels vet`` and, later, the web UI; no click or rich here. The call
sits behind ``VetClient`` so tests use a fake (no network). Per-channel problems
become results; an authentication, permission or billing error stops the run
(``VetRun.aborted``), keeping the files already written.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

import anthropic
from pydantic import ValidationError

from happytube.channels.models import Channel, ChannelFlag, Evidence, VetUsage
from happytube.channels.store import ChannelStore
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
# counted at the base rate even when served from cache.
USD_PER_MTOK_INPUT = 4.0
USD_PER_MTOK_OUTPUT = 20.0
MAX_TOKENS = 16000
EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
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


class VetCallError(Exception):
    """One call failed (after the SDK's retries); the run goes on."""


class VetStoppingError(VetCallError):
    """The key, its permissions or the credit balance failed; the run stops."""


@dataclass
class VetReply:
    """What one call returned. ``output`` is ``None`` on a refusal."""

    output: VetOutput | None
    model: str
    usage: VetUsage
    stop_reason: str | None
    refusal_category: str | None = None


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


def _call_error(error: anthropic.APIStatusError) -> VetCallError:
    """``VetStoppingError`` for a bad key, missing permission or no credit;
    ``VetCallError`` for anything else (rate limits and 5xx after retries)."""
    kind, message = _error_detail(error)
    text = f"Anthropic API {error.status_code} {kind}: {message}".rstrip(": ")
    stopping = (
        error.status_code in _STOPPING_STATUS
        or kind in _STOPPING_TYPES
        or "credit balance" in message.lower()
    )
    return VetStoppingError(text) if stopping else VetCallError(text)


class AnthropicVetClient:
    """``VetClient`` on the Anthropic API: Claude Opus 5.5, adaptive thinking
    (the model's default), effort ``medium``, structured output, and the
    server-side refusal fallback."""

    def __init__(self, api_key: str, client: anthropic.Anthropic | None = None):
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=3)

    def vet(self, prompt: Prompt) -> VetReply:
        try:
            response = self._client.beta.messages.parse(
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
                output_config={"effort": EFFORT},
                output_format=VetOutput,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            raise _call_error(e) from None
        except anthropic.APIConnectionError as e:
            msg = f"Anthropic API unreachable: {type(e).__name__}"
            raise VetCallError(msg) from None
        except ValidationError as e:  # JSON cut short or not matching VetOutput
            msg = f"model output did not parse ({e.error_count()} problems)"
            raise VetCallError(msg) from None
        usage = response.usage
        tokens = VetUsage(
            input_tokens=usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0),
            output_tokens=usage.output_tokens,
        )
        if response.stop_reason == "refusal":
            details = response.stop_details
            return VetReply(
                None,
                response.model,
                tokens,
                response.stop_reason,
                details.category if details else None,
            )
        return VetReply(
            response.parsed_output, response.model, tokens, response.stop_reason
        )


@dataclass
class VetResult:
    slug: str
    status: VetStatus
    flags: list[ChannelFlag] = field(default_factory=list)
    verdict: str | None = None
    model_verdict: str | None = None
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
            "model": MODEL,
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
    except VetStoppingError:
        raise
    except VetCallError as e:
        result.status, result.message = "error", str(e)
        return
    result.input_tokens = reply.usage.input_tokens
    result.output_tokens = reply.usage.output_tokens
    if reply.stop_reason == "refusal" or reply.output is None:
        result.status = "refused" if reply.stop_reason == "refusal" else "error"
        result.message = (
            f"stop_reason {reply.stop_reason}"
            + (f" ({reply.refusal_category})" if reply.refusal_category else "")
            + "; nothing written"
        )
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
