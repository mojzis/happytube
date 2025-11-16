"""Utility functions for HappyTube."""

import html
import unicodedata
from collections import Counter


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
    if num_occurrences / len(beginning) < 0.5:
        return "MIXED"
    return most_common[0][0]


__all__ = ["determine_text_script"]
