"""The run shape shared by trusted assess and enhance (one Claude call per item).

An item is a batch of one channel's videos (assess) or one video (enhance).
Per-item problems (call error, refusal, unusable output) become results and
fail the run; a ``ClaudeStoppingError`` (key, permission, credit) stops it,
keeping files already written, and every item not reached is ``not_run``.
"""

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from happytube.claude import (
    MODEL,
    ClaudeCallError,
    ClaudeStoppingError,
    Prompt,
    Reply,
    estimate_usd,
)

ItemStatus = Literal["done", "would_run", "refused", "error", "not_run"]
FAILURE_STATUSES: frozenset[str] = frozenset({"refused", "error", "not_run"})
_NOT_RUN = "not run: run stopped (Anthropic key, permission or credit problem)"


class TrustedClient(Protocol):
    """``happytube.claude.ClaudeCaller``, or a fake in tests."""

    def call[T: BaseModel](self, prompt: Prompt, output_type: type[T]) -> Reply[T]: ...


ClientFactory = Callable[[], TrustedClient]


@dataclass
class ItemResult:
    slug: str  # channel
    video_ids: list[str]
    status: ItemStatus = "would_run"
    model: str | None = None  # the model that answered
    message: str | None = None
    suitable: int | None = None  # assess: how many of the batch are suitable
    paths: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def usd(self) -> float:
        return estimate_usd(self.input_tokens, self.output_tokens)

    def record[T: BaseModel](self, reply: Reply[T]) -> T | None:
        """Tokens and model of ``reply``; its output, or ``None`` after marking
        this item refused / error (nothing is written for it then)."""
        self.model = reply.model
        self.input_tokens = reply.usage.input_tokens
        self.output_tokens = reply.usage.output_tokens
        if reply.stop_reason == "refusal":
            category = f" ({reply.refusal_category})" if reply.refusal_category else ""
            self.status = "refused"
            self.message = f"stop_reason refusal{category}; nothing written"
            return None
        if reply.output is None:
            problem = reply.error or f"no output (stop_reason {reply.stop_reason})"
            self.status, self.message = "error", f"{problem}; nothing written"
            return None
        return reply.output


@dataclass
class ItemRun:
    """Outcome of an assess or enhance run."""

    results: list[ItemResult] = field(default_factory=list)
    aborted: str | None = None
    dry_run: bool = False
    skipped: int = 0  # videos already done (no call)

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
            "skipped": self.skipped,
            "requested_model": MODEL,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": self.usd,
        }


def run_items[I](
    items: Iterable[tuple[ItemResult, I]],
    make_client: ClientFactory | None,
    work: Callable[[TrustedClient, ItemResult, I], None],
    *,
    skipped: int = 0,
) -> ItemRun:
    """Call ``work`` per item; ``make_client=None`` is a dry run. The client is
    made only when there is an item, so a run with nothing to do needs no key."""
    pairs = list(items)
    run = ItemRun([r for r, _ in pairs], dry_run=make_client is None, skipped=skipped)
    if make_client is None or not pairs:
        return run
    client = make_client()
    for index, (result, item) in enumerate(pairs):
        try:
            work(client, result, item)
        except ClaudeCallError as e:
            result.status, result.message = "error", str(e)
        except ClaudeStoppingError as e:
            result.status, result.message = "error", str(e)
            run.aborted = str(e)
            for rest, _ in pairs[index + 1 :]:
                rest.status, rest.message = "not_run", _NOT_RUN
            break
    return run
