from datetime import datetime

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from happytube.stages.claude_response import first_text
from happytube.utils import determine_text_script, today_local, utc_now_iso


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello, world!", "LATIN"),
        ("IT&#39;S ALIVE! Pac-Man of the Sea?", "LATIN"),
        ("こんにちは", "HIRAGANA"),
        ("안녕하세요", "HANGUL"),
        ("你好", "CJK"),
        ("مرحبا", "ARABIC"),
        ("Привет", "CYRILLIC"),
        ("Привіт", "CYRILLIC"),
        ("Hello こんにちは", "LATIN"),
        ("안녕하세요 你好", "HANGUL"),
        ("مرحبا こんにちは", "ARABIC"),
    ],
    ids=[
        "Latin",
        "Latin with HTML entities",
        "Hiragana",
        "Hangul",
        "CJK",
        "Arabic",
        "Cyrillic",
        "Cyrillic",
        "Latin with Hiragana",
        "Hangul with CJK",
        "Arabic with Hiragana",
    ],
)
def test_determine_text_script(text, expected):
    result = determine_text_script(text)
    assert result == expected


def test_utc_now_iso_format():
    stamp = utc_now_iso()
    assert stamp.endswith("Z")
    parsed = datetime.fromisoformat(stamp.removesuffix("Z"))
    assert parsed.tzinfo is None


def test_today_local_is_local_date():
    assert today_local() == datetime.now().astimezone().date()


_TOOL = ToolUseBlock(id="t1", input={}, name="tool", type="tool_use")


@pytest.mark.parametrize(
    "content, expected",
    [
        ([TextBlock(text="hi", type="text")], "hi"),
        ([_TOOL, TextBlock(text="after tool", type="text")], "after tool"),
        (
            [TextBlock(text="one", type="text"), TextBlock(text="two", type="text")],
            "one",
        ),
        ([_TOOL], "fallback"),
        ([], "fallback"),
    ],
    ids=["single text", "skips non-text", "first wins", "no text", "empty"],
)
def test_first_text(content, expected):
    assert first_text(content, default="fallback") == expected
