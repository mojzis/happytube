"""The one Claude call shape shared by ``channels vet`` and the trusted pipeline.

Claude Opus 5.5, adaptive thinking (the model's default), effort ``medium``,
structured output, the server-side refusal fallback and the error mapping: an
authentication, permission or billing problem is a ``ClaudeStoppingError`` (stop
the run), anything else a ``ClaudeCallError`` (this call failed, go on). Refusals
and ``max_tokens`` cut-offs are not errors but replies without output — the
tokens were paid for. Messages never carry headers, the request or the key.
"""

from dataclasses import dataclass
from functools import cache

import anthropic
from anthropic.types.beta import BetaContentBlock, BetaJSONOutputFormatParam
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MODEL = "claude-opus-5-5"
# Claude Opus 5.5 list prices, USD per million tokens. Estimates only: input is
# counted at the base rate even when served from cache, and a call the refusal
# fallback answered with another model is still priced at Opus 5.5 rates.
USD_PER_MTOK_INPUT = 4.0
USD_PER_MTOK_OUTPUT = 20.0
MAX_TOKENS = 16000
EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_STOPPING_TYPES = frozenset(
    {"authentication_error", "permission_error", "billing_error"}
)
_STOPPING_STATUS = frozenset({401, 402, 403})


class Usage(BaseModel):
    """Tokens one call used (input includes any cache reads and writes)."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


def estimate_usd(input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens * USD_PER_MTOK_INPUT + output_tokens * USD_PER_MTOK_OUTPUT)
        / 1_000_000,
        4,
    )


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str


class ClaudeError(Exception):
    """A call failed without a response (nothing to bill or record)."""


class ClaudeCallError(ClaudeError):
    """One call failed (after the SDK's retries); the run goes on."""


class ClaudeStoppingError(ClaudeError):
    """The key, its permissions or the credit balance failed; the run stops."""


@dataclass
class Reply[T: BaseModel]:
    """What one call returned. ``model`` is the model that answered (the refusal
    fallback may have switched it). ``output`` is ``None`` on a refusal (then
    ``refusal_category``) or when the output is unusable (then ``error``); the
    tokens were paid for either way."""

    output: T | None
    model: str
    usage: Usage
    stop_reason: str | None
    refusal_category: str | None = None
    error: str | None = None


@cache
def output_format(output_type: type[BaseModel]) -> BetaJSONOutputFormatParam:
    """Structured-output format for ``output_type``. The SDK moves what the API
    cannot enforce (e.g. score 1-5) into the descriptions; ``model_validate_json``
    checks it on our side."""
    return BetaJSONOutputFormatParam(
        type="json_schema", schema=anthropic.transform_schema(output_type)
    )


def _error_detail(error: anthropic.APIStatusError) -> tuple[str, str]:
    """The API's error type and message — never headers or the request."""
    body = error.body if isinstance(error.body, dict) else {}
    detail = body.get("error")
    if not isinstance(detail, dict):
        detail = {}
    kind = detail.get("type") or type(error).__name__
    return str(kind), str(detail.get("message") or "")


def call_error(error: anthropic.APIStatusError) -> ClaudeError:
    """``ClaudeStoppingError`` for a bad key, missing permission or no credit;
    ``ClaudeCallError`` for anything else (rate limits and 5xx after retries)."""
    kind, message = _error_detail(error)
    text = f"Anthropic API {error.status_code} {kind}: {message}".rstrip(": ")
    # A low credit balance comes back as 400 invalid_request_error, so only its
    # message tells it apart from a bad request.
    stopping = (
        error.status_code in _STOPPING_STATUS
        or kind in _STOPPING_TYPES
        or "credit balance" in message.lower()
    )
    return ClaudeStoppingError(text) if stopping else ClaudeCallError(text)


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


class ClaudeCaller:
    """Structured-output calls on the Anthropic API, one request per call."""

    def __init__(self, api_key: str, client: anthropic.Anthropic | None = None):
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=3)

    def call[T: BaseModel](self, prompt: Prompt, output_type: type[T]) -> Reply[T]:
        """Send ``prompt``; parse the answer as ``output_type``. Raises
        ``ClaudeStoppingError`` / ``ClaudeCallError``."""
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
                output_config={
                    "effort": EFFORT,
                    "format": output_format(output_type),
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            raise call_error(e) from None
        except anthropic.APIConnectionError as e:
            msg = f"Anthropic API unreachable: {type(e).__name__}"
            raise ClaudeCallError(msg) from None
        usage = response.usage
        tokens = Usage(
            input_tokens=usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0),
            output_tokens=usage.output_tokens,
        )
        stop = response.stop_reason
        if stop == "refusal":
            details = response.stop_details
            category = details.category if details else None
            return Reply(None, response.model, tokens, stop, category)
        if stop == "max_tokens":
            error = f"output cut off at max_tokens ({MAX_TOKENS})"
            return Reply(None, response.model, tokens, stop, error=error)
        try:
            output = output_type.model_validate_json(_answer_text(response.content))
        except ValidationError as e:  # not JSON, or e.g. a score outside 1-5
            error = f"model output did not parse ({e.error_count()} problems)"
            return Reply(None, response.model, tokens, stop, error=error)
        return Reply(output, response.model, tokens, stop)
