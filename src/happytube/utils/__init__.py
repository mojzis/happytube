"""Utility functions for HappyTube."""

import html
import unicodedata
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime

from anthropic.types import ContentBlock

# Below this share of the dominant script the text counts as mixed.
MIXED_SCRIPT_THRESHOLD = 0.5


def first_text(content: Iterable[ContentBlock], default: str = "") -> str:
    """Return the text of the first text block in a Claude response."""
    return next((block.text for block in content if block.type == "text"), default)


def utc_now_iso() -> str:
    """Return the current UTC time as naive ISO-8601 with a trailing ``Z``."""
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


def determine_text_script(text: str) -> str:
    """
    Determine the script of the text.
    """
    text = html.unescape(text)
    beginning = text[:10]
    script_counter = Counter()
    for char in beginning:
        if char.isalpha():  # Check only alphabetic characters
            script = unicodedata.name(char).split()[0]
            script_counter[script] += 1
    most_common = script_counter.most_common(1)
    num_occurrences = most_common[0][1] if most_common else 0
    if num_occurrences / len(beginning) < MIXED_SCRIPT_THRESHOLD:
        return "MIXED"
    return most_common[0][0]


__all__ = ["determine_text_script"]
