"""Helpers for reading Claude API responses in the assess and enhance stages."""

from collections.abc import Iterable

from anthropic.types import ContentBlock


def first_text(content: Iterable[ContentBlock], default: str = "") -> str:
    """Return the text of the first text block in a Claude response.

    Non-text blocks (tool use, thinking, ...) are skipped; ``default`` is
    returned when there is no text block at all.
    """
    return next((block.text for block in content if block.type == "text"), default)
