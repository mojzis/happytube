import json
import os
from collections import namedtuple

from anthropic import Anthropic
from dotenv import load_dotenv

from happytube.prompts import get_prompt

ClaudeConfig = namedtuple("ClaudeConfig", ["claude_model_version", "claude_max_tokens"])


def default_settings():
    claude_config = ClaudeConfig(
        claude_model_version="claude-3-opus-20240229", claude_max_tokens=4096
    )

    return claude_config


def create_client() -> Anthropic:
    _ = load_dotenv()
    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    return client


def get_response(
    client: Anthropic, message: dict, settings: ClaudeConfig | None = None
) -> str:
    settings = settings or default_settings()
    response = client.messages.create(
        model=settings.claude_model_version,
        messages=[message],
        max_tokens=settings.claude_max_tokens,
    )
    return response


def do_with_videos(
    client: Anthropic,
    videos: list,
    prompt_definitions: list,
    prompt_name: str | None = None,
    prompt_version: int | None = None,
    settings: ClaudeConfig | None = None,
    debug=False,
) -> str:
    prompt_name = prompt_name or "rate_video_happiness"
    prompt_version = prompt_version or 2
    return range_video_happiness(
        client, videos, prompt_definitions, prompt_name, prompt_version, settings, debug
    )


def range_video_happiness(
    client: Anthropic,
    videos: list,
    # TODO: refactor to combine definitions and config
    prompt_definitions: list,
    prompt_name: str | None = None,
    prompt_version: int | None = None,
    settings: ClaudeConfig | None = None,
    debug=False,
) -> str:
    settings = settings or default_settings()
    prompt_name = prompt_name or "rate_video_happiness"
    prompt_version = prompt_version or 2
    prompt = get_prompt(prompt_definitions, prompt_name, prompt_version)
    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "text", "text": json.dumps(videos)},
        ],
    }
    if debug:
        return message
    return get_response(client, message, settings)
