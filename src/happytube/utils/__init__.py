"""Utility functions for HappyTube."""

import html
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime

# Below this share of the dominant script the text counts as mixed.
MIXED_SCRIPT_THRESHOLD = 0.5


def utc_now_iso() -> str:
    """Return the current UTC time as naive ISO-8601 with a trailing ``Z``."""
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


def today_local() -> date:
    """Return today's date in the machine's local timezone."""
    return datetime.now().astimezone().date()


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


__all__ = ["determine_text_script", "today_local", "utc_now_iso"]
