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

from happytube.channels.models import (
    Channel,
    ChannelFlag,
    Evidence,
    Verdict,
)
from happytube.channels.store import ChannelStore, derive_status
from happytube.channels.vet import (
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
from happytube.claude import (
    MODEL,
    ClaudeCaller,
    ClaudeCallError,
    ClaudeError,
    ClaudeStoppingError,
    Reply,
    estimate_usd,
    output_format,
)

# The shared call (``happytube.claude``) under the names vet has always used.
OUTPUT_FORMAT = output_format(VetOutput)
VetError = ClaudeError
VetCallError = ClaudeCallError
VetStoppingError = ClaudeStoppingError
VetReply = Reply[VetOutput]
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


class VetClient(Protocol):
    def vet(self, prompt: Prompt) -> VetReply: ...


class AnthropicVetClient:
    """``VetClient`` on the shared Claude call (``happytube.claude``)."""

    def __init__(self, api_key: str, client: anthropic.Anthropic | None = None):
        self._caller = ClaudeCaller(api_key, client)

    def vet(self, prompt: Prompt) -> VetReply:
        return self._caller.call(prompt, VetOutput)


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
