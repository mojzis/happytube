import pytest

from happytube.utils import determine_text_script


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
    # pytest.fail(f"{result=}, {expected=}")
    assert result == expected
