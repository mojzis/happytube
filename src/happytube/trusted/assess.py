"""Trusted assess: score each fetched video with the calm/happy rubric.

One Claude call per channel batch (up to ``BATCH_SIZE`` videos), so the model
sees one channel's context. The model returns a ``VideoScore`` per video;
``suitable`` is decided here with ``rubric.is_suitable``, never by the model.
A reply that doesn't score every video sent exactly once writes nothing for
its batch. Every fetched video not yet assessed, on any date up to the target,
is picked up (a video left over by a failed run is not stranded) and written
under its fetch file's date; one already assessed is not re-scored unless
``force``, which re-scores the target date's videos. A video scored unsuitable
loses any enhance file it had.
"""

from collections.abc import Iterator
from dataclasses import dataclass
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
from happytube.trusted.stages import Dated, TrustedStage, pending, video_id_of
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
    videos: list[Dated],
) -> Iterator[tuple[ItemResult, list[Dated]]]:
    """Per channel (in slug order), chunks of up to ``BATCH_SIZE`` videos."""
    by_channel: dict[str, list[Dated]] = {}
    for day, md in videos:
        slug = str(md.frontmatter.get("channel_slug"))
        by_channel.setdefault(slug, []).append((day, md))
    for slug in sorted(by_channel):
        for chunk in batched(by_channel[slug], BATCH_SIZE):
            ids = [video_id_of(md) for _, md in chunk]
            yield ItemResult(slug, ids), list(chunk)


@dataclass(frozen=True)
class _Stages:
    assess: TrustedStage
    enhance: TrustedStage


def _assess_batch(
    client: TrustedClient,
    result: ItemResult,
    videos: list[Dated],
    stages: _Stages,
) -> None:
    prompt = build_prompt([md for _, md in videos])
    output = result.record(client.call(prompt, AssessOutput))
    if output is None:
        return
    problem = id_mismatch(result.video_ids, [s.video_id for s in output.videos])
    if problem:
        result.status, result.message = "error", f"{problem}; nothing written"
        return
    scores = {s.video_id: s for s in output.videos}
    assessed_at = utc_now_iso()
    result.suitable = 0
    for day, md in videos:
        score = scores[video_id_of(md)]
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
        # Written under the fetch file's date, so each date's stages line up.
        path = stages.assess.write(
            day, score.video_id, MarkdownFile(frontmatter, md.content)
        )
        result.paths.append(str(path))
        if not suitable:  # no longer shown: drop an earlier enhanced version
            removed = stages.enhance.remove(score.video_id)
            result.unenhanced.extend(str(p) for p in removed)
    result.status = "done"


def assess_trusted(
    target_date: date,
    make_client: ClientFactory | None,
    *,
    force: bool = False,
    base_path: Path = Path("stages"),
) -> ItemRun:
    """Assess every fetched video (dated ``target_date`` or earlier) not yet
    assessed; ``force`` re-scores the date's videos. ``make_client=None`` is a
    dry run. A video that turns out unsuitable loses its enhance file."""
    stages = _Stages(
        TrustedStage("assess", base_path), TrustedStage("enhance", base_path)
    )
    todo, skipped = pending(
        TrustedStage("fetch", base_path).load_until(target_date),
        stages.assess.video_ids(),
        target_date,
        force=force,
    )
    return run_items(
        _batches(todo),
        make_client,
        lambda client, result, chunk: _assess_batch(client, result, chunk, stages),
        skipped=skipped,
    )
