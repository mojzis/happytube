"""Trusted enhance: a clean description for every *suitable* assessed video.

One Claude call per video: volume is a handful a day, and one bad reply then
costs only its own video. Unsuitable videos are never sent and never reach
``stages/trusted/enhance/``. Every suitable video not yet enhanced, on any date
up to the target, is picked up; ``force`` redoes the target date's.
"""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from happytube.claude import Prompt
from happytube.models.markdown import MarkdownFile
from happytube.prompts import TRUSTED_ENHANCE_PROMPT
from happytube.trusted.runs import (
    ClientFactory,
    ItemResult,
    ItemRun,
    TrustedClient,
    run_items,
)
from happytube.trusted.stages import Dated, TrustedStage, pending, video_id_of
from happytube.utils import utc_now_iso

DESCRIPTION_MAX = 5000


class EnhanceOutput(BaseModel):
    """What the model returns for one video (structured output)."""

    model_config = ConfigDict(extra="forbid")

    description: str


def build_prompt(md: MarkdownFile) -> Prompt:
    _, _, body = md.content.partition("\n")
    data = {
        "channel": md.frontmatter.get("channel_name"),
        "title": md.frontmatter.get("title"),
        "description": body.strip()[:DESCRIPTION_MAX],
    }
    user = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    return Prompt(TRUSTED_ENHANCE_PROMPT, user)


def _enhance_one(
    client: TrustedClient,
    result: ItemResult,
    item: Dated,
    stage: TrustedStage,
) -> None:
    day, md = item
    output = result.record(client.call(build_prompt(md), EnhanceOutput))
    if output is None:
        return
    description = output.description.strip()
    if not description:
        result.status, result.message = "error", "empty description; nothing written"
        return
    frontmatter = {
        **md.frontmatter,
        "enhanced_description": description,
        "enhanced_at": utc_now_iso(),
        "enhance_model": result.model,
        "stage": "trusted_enhance",
    }
    # Under the assess (= fetch) file's date, so each date's stages line up.
    path = stage.write(day, result.video_ids[0], MarkdownFile(frontmatter, md.content))
    result.paths.append(str(path))
    result.status = "done"


def enhance_trusted(
    target_date: date,
    make_client: ClientFactory | None,
    *,
    force: bool = False,
    base_path: Path = Path("stages"),
) -> ItemRun:
    """Enhance every suitable assessed video (dated ``target_date`` or earlier)
    not yet enhanced; ``force`` redoes the date's. ``make_client=None`` is a dry
    run. ``skipped`` counts the date's suitable videos already enhanced."""
    stage = TrustedStage("enhance", base_path)
    suitable = [
        (day, md)
        for day, md in TrustedStage("assess", base_path).load_until(target_date)
        if md.frontmatter.get("suitable") is True
    ]
    todo, skipped = pending(suitable, stage.video_ids(), target_date, force=force)
    items = [
        (
            ItemResult(str(md.frontmatter.get("channel_slug")), [video_id_of(md)]),
            (day, md),
        )
        for day, md in todo
    ]
    return run_items(
        items,
        make_client,
        lambda client, result, item: _enhance_one(client, result, item, stage),
        skipped=skipped,
    )
