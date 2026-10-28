"""A fake YouTube, a fake Claude and a registry for the trusted pipeline tests."""

from typing import Any
from unittest.mock import MagicMock

import yaml

from happytube.channels.models import Channel, Review, VetUsage
from happytube.channels.store import ChannelStore
from happytube.claude import ClaudeError, Prompt, Reply
from happytube.rubric import VideoScore
from happytube.trusted.assess import AssessOutput
from happytube.trusted.enhance import EnhanceOutput

FAKE_KEY = "fake-key-for-tests"
QUOTA_BODY = {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}
NOT_FOUND_BODY = {
    "error": {"message": "gone", "errors": [{"reason": "playlistNotFound"}]}
}
USAGE = VetUsage(input_tokens=1000, output_tokens=200)
RECENT = "2026-10-25T10:00:00Z"  # within 14 days of TARGET
TARGET = "2026-10-28"


def _response(payload, status_code=200, reason="OK"):
    response = MagicMock(status_code=status_code, reason=reason)
    response.json.return_value = payload
    return response


def video(  # noqa: PLR0913 - one keyword per field a test varies
    video_id, duration="PT10M", published=RECENT, live="none", title=None, desc=""
) -> dict[str, Any]:
    """A ``videos.list`` item."""
    return {
        "id": video_id,
        "snippet": {
            "title": title or f"Video {video_id}",
            "description": desc or f"About {video_id}. https://shop.example",
            "publishedAt": published,
            "liveBroadcastContent": live,
        },
        "contentDetails": {"duration": duration},
        "status": {"madeForKids": False},
    }


class FakeYouTube:
    """``playlistItems`` / ``videos`` from in-memory data; can run out of quota.

    ``uploads`` maps a channel id to its videos (newest first); ``shorts`` maps
    a channel id to its Shorts ids (absent: 404, no Shorts); ``broken`` lists
    playlist ids answering 500.
    """

    def __init__(self, quota=1000):
        self.uploads: dict[str, list[dict[str, Any]]] = {}
        self.shorts: dict[str, list[str]] = {}
        self.broken: set[str] = set()
        self.quota = quota
        self.calls: list[str] = []

    def __call__(self, url, params, timeout):
        assert params["key"] == FAKE_KEY
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append(endpoint)
        if len(self.calls) > self.quota:
            return _response(QUOTA_BODY, 403, "Forbidden")
        if endpoint == "videos":
            wanted = params["id"].split(",")
            items = [v for vs in self.uploads.values() for v in vs]
            return _response({"items": [v for v in items if v["id"] in wanted]})
        playlist = params["playlistId"]
        if playlist in self.broken:
            return _response({"error": {"message": "boom"}}, 500, "Server Error")
        channel_id = "UC" + playlist.removeprefix("UUSH").removeprefix("UU")
        if playlist.startswith("UUSH"):
            ids = self.shorts.get(channel_id)
        else:
            ids = [v["id"] for v in self.uploads.get(channel_id, [])] or None
        if ids is None:
            return _response(NOT_FOUND_BODY, 404, "Not Found")
        return _response({"items": [{"contentDetails": {"videoId": i}} for i in ids]})


def add_channel(store: ChannelStore, slug, channel_id, verdict="approve"):
    """A channel with one human review (``None``: no review, a candidate)."""
    store.add(
        Channel(
            slug=slug,
            name=slug.title(),
            kind="zoo",
            languages=["cs"],
            channel_id=channel_id,
            added_by="me",
        )
    )
    if verdict:
        store.add_review(slug, Review(reviewer="me", role="human", verdict=verdict))


def prompt_ids(prompt: Prompt) -> list[str]:
    data = yaml.safe_load(prompt.user.split("\n\n", 1)[1])
    return [v["video_id"] for v in data["videos"]]


class FakeClaude:
    """Scores every video sent (``scores`` overrides per id: (calm, happy,
    flags)) or writes a description; ``errors`` maps a call number to an
    exception; ``drop`` leaves that id out of assess answers; a prompt whose
    first video is in ``refuse`` gets a refusal."""

    def __init__(self, scores=None, errors=None, drop=(), refuse=()):
        self.scores: dict[str, tuple[int, int, list[str]]] = scores or {}
        self.errors: dict[int, ClaudeError] = errors or {}
        self.drop = set(drop)
        self.refuse = set(refuse)
        self.prompts: list[Prompt] = []

    def call(self, prompt, output_type):
        index = len(self.prompts)
        self.prompts.append(prompt)
        if index in self.errors:
            raise self.errors[index]
        if output_type is AssessOutput and prompt_ids(prompt)[0] in self.refuse:
            return Reply(None, "claude-opus-5-5", USAGE, "refusal", "bio")
        if output_type is EnhanceOutput:
            output = EnhanceOutput(description="  Klidné video o žirafách.  ")
        else:
            assert output_type is AssessOutput
            output = AssessOutput(
                videos=[
                    VideoScore.model_validate(
                        {
                            "video_id": i,
                            **dict(
                                zip(
                                    ("calm", "happy", "flags"),
                                    self.scores.get(i, (5, 4, [])),
                                    strict=True,
                                )
                            ),
                            "note": f"Gentle video {i}.",
                        }
                    )
                    for i in prompt_ids(prompt)
                    if i not in self.drop
                ]
            )
        return Reply(output, "claude-opus-5-5", USAGE, "end_turn")
