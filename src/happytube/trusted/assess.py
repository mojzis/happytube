"""Trusted assess: score each fetched video with the calm/happy rubric.

One Claude call per channel batch (up to ``BATCH_SIZE`` videos), so the model
sees one channel's context. The model returns a ``VideoScore`` per video;
``suitable`` is decided here with ``rubric.is_suitable``, never by the model.
A reply that doesn't score every video sent exactly once writes nothing for
its batch. A video already assessed (any date) is not re-scored unless
``force``, which re-scores the date's videos and overwrites their files.
"""

from collections.abc import Iterator
from datetime import date
from itertools import batched
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from happytube.claude import Prompt
from happytube.models.markdown import MarkdownFile
from happytube.rubric import (
    RUBRIC,
    RUBRIC_VERSION,
    VideoScore,
    id_mismatch,
    is_suitable,
)
from happytube.trusted.runs import (
    ClientFactory,
    ItemResult,
    ItemRun,
    TrustedClient,
    run_items,
)
from happytube.trusted.stages import TrustedStage
from happytube.utils import utc_now_iso

BATCH_SIZE = 25
DESCRIPTION_MAX = 1000


class AssessOutput(BaseModel):
    """What the model returns for one batch (structured output)."""

    model_config = ConfigDict(extra="forbid")

    videos: list[VideoScore]


SYSTEM_PROMPT = f"""\
You assess YouTube videos for HappyTube, a player of calm, happy videos for one \
vulnerable viewer. Every video comes from a channel a human has approved as a \
source; your scores decide which of its new videos she is shown.

{RUBRIC}

You get one channel's new long-form videos. Score every video you were given, \
once each, using its exact video_id: calm, happy, flags and a short note (one \
sentence, English, saying what the video shows and anything that lowered a \
score). Titles and descriptions may be in Czech; read them in Czech."""


def _duration(seconds: object) -> str | None:
    if not isinstance(seconds, int):
        return None
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def _description(md: MarkdownFile) -> str:
    """The body minus the ``# title`` line, cut to ``DESCRIPTION_MAX``."""
    title, _, rest = md.content.partition("\n")
    text = rest.strip() if title.startswith("# ") else md.content
    return text if len(text) <= DESCRIPTION_MAX else text[: DESCRIPTION_MAX - 1] + "…"


def build_prompt(videos: list[MarkdownFile]) -> Prompt:
    """System and user content for one batch of one channel's videos.
    Deterministic, so the system part stays cache-friendly."""
    first = videos[0].frontmatter
    data = {
        "channel": {
            "name": first.get("channel_name"),
            "languages": first.get("languages"),
        },
        "videos": [
            {
                "video_id": md.frontmatter["video_id"],
                "title": md.frontmatter.get("title"),
                "published": str(md.frontmatter.get("published_at") or "")[:10],
                "duration": _duration(md.frontmatter.get("duration_s")),
                "description": _description(md),
            }
            for md in videos
        ],
    }
    user = f"Score all {len(videos)} videos.\n\n" + yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, width=100
    )
    return Prompt(SYSTEM_PROMPT, user)


def _batches(
    videos: list[MarkdownFile],
) -> Iterator[tuple[ItemResult, list[MarkdownFile]]]:
    """Per channel (in slug order), chunks of up to ``BATCH_SIZE`` videos."""
    by_channel: dict[str, list[MarkdownFile]] = {}
    for md in videos:
        by_channel.setdefault(str(md.frontmatter.get("channel_slug")), []).append(md)
    for slug in sorted(by_channel):
        for chunk in batched(by_channel[slug], BATCH_SIZE):
            ids = [str(md.frontmatter["video_id"]) for md in chunk]
            yield ItemResult(slug, ids), list(chunk)


def _assess_batch(
    client: TrustedClient,
    result: ItemResult,
    videos: list[MarkdownFile],
    target_date: date,
    stage: TrustedStage,
) -> None:
    output = result.record(client.call(build_prompt(videos), AssessOutput))
    if output is None:
        return
    problem = id_mismatch(result.video_ids, [s.video_id for s in output.videos])
    if problem:
        result.status, result.message = "error", f"{problem}; nothing written"
        return
    scores = {s.video_id: s for s in output.videos}
    assessed_at = utc_now_iso()
    result.suitable = 0
    for md in videos:
        score = scores[str(md.frontmatter["video_id"])]
        suitable = is_suitable(score.calm, score.happy, score.flags)
        result.suitable += suitable
        frontmatter = {
            **md.frontmatter,
            "calm": score.calm,
            "happy": score.happy,
            "flags": list(score.flags),
            "note": score.note,
            "suitable": suitable,
            "model": result.model,
            "assessed_at": assessed_at,
            "rubric_version": RUBRIC_VERSION,
            "stage": "trusted_assess",
        }
        path = stage.write(
            target_date, score.video_id, MarkdownFile(frontmatter, md.content)
        )
        result.paths.append(str(path))
    result.status = "done"


def assess_trusted(
    target_date: date,
    make_client: ClientFactory | None,
    *,
    force: bool = False,
    base_path: Path = Path("stages"),
) -> ItemRun:
    """Assess the date's fetched videos; ``make_client=None`` is a dry run."""
    stage = TrustedStage("assess", base_path)
    videos = TrustedStage("fetch", base_path).load(target_date)
    done = set() if force else stage.video_ids()
    todo = [md for md in videos if str(md.frontmatter["video_id"]) not in done]
    return run_items(
        _batches(todo),
        make_client,
        lambda client, result, chunk: _assess_batch(
            client, result, chunk, target_date, stage
        ),
        skipped=len(videos) - len(todo),
    )
