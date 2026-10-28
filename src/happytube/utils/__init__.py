"""Utility functions for HappyTube."""

import html
import re
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime

# Below this share of the dominant script the text counts as mixed.
MIXED_SCRIPT_THRESHOLD = 0.5


def as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC and convert an aware one to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_z(value: datetime) -> str:
    """Format a datetime in UTC as ISO-8601 with a trailing ``Z``."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def utc_now() -> datetime:
    return datetime.now(UTC)


def slugify(text: str) -> str:
    """Kebab-case ASCII slug: strip diacritics, lowercase, non-alphanumerics to ``-``.

    Returns an empty string when nothing alphanumeric is left.
    """
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


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
