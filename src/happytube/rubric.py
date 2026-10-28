"""The calm/happy rubric shared by channel vetting and (later) video assessment.

One place for the definitions, so the channel vet (phase 3) and per-video assessment
(phase 5) score the same way. Audience and principles: ``docs/constitution.md`` —
calm matters as much as happy.
"""

from collections.abc import Collection
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Flag = Literal[
    "war",
    "disaster",
    "violence",
    "predation",
    "death_sadness",
    "scary",
    "loud_fast",
    "news",
    "clickbait",
    "promo",
    "other",
]
FLAGS: tuple[str, ...] = get_args(Flag)

# A video with any of these is never suitable, whatever its scores.
BLOCKING_FLAGS: frozenset[str] = frozenset(
    {"war", "disaster", "violence", "predation", "death_sadness", "scary", "news"}
)
MIN_CALM = 4
MIN_HAPPY = 3

Score = Annotated[int, Field(ge=1, le=5)]

RUBRIC = """\
Audience: an elderly viewer with early dementia. She is easily frightened, \
confused by fast or loud content, and scared by war news. She watches in Czech \
or English. Calm matters as much as happy.

Score each video on two scales, 1 to 5:

calm
  5 = gentle and slow; quiet narration or soft music; no tension at all
  4 = mostly calm; an occasional livelier moment
  3 = neutral pace; some energy or mild tension
  2 = busy or tense; quick cuts, raised voices, suspense
  1 = alarming; loud, fast cuts, suspense, shouting

happy
  5 = joyful, warm, cute, uplifting
  4 = pleasant and positive
  3 = neutral, informative
  2 = somewhat sad or worrying
  1 = sad, grim or distressing

flags (zero or more per video, only when they apply):
  war            war, armed conflict, military
  disaster       natural or man-made disasters, accidents
  violence       fighting, cruelty, weapons
  predation      predators hunting or killing, injured animals
  death_sadness  death, illness, loss, rescue of suffering animals
  scary          creepy, horror, dangerous animals framed as a threat
  loud_fast      hype editing, shouting, countdowns
  news           news, current affairs, politics
  clickbait      misleading or sensational title or framing
  promo          ads, merchandise or fundraising appeals dominate
  other          anything else she should not see; say what in the note

Judge from the title, description, duration and publication date you are given; \
you cannot watch the video. When the text leaves real doubt, score lower rather \
than higher: a false "calm" is worse than a missed good video."""


class VideoScore(BaseModel):
    """The model's score of one long-form video."""

    model_config = ConfigDict(extra="forbid")

    video_id: str
    calm: Score
    happy: Score
    flags: list[Flag]
    note: str


def is_suitable(calm: int, happy: int, flags: Collection[str]) -> bool:
    """Whether a scored video may be shown: calm, at least neutral-happy, and no
    blocking flag. Decided here in code, never by the model."""
    return (
        calm >= MIN_CALM
        and happy >= MIN_HAPPY
        and not BLOCKING_FLAGS.intersection(flags)
    )
