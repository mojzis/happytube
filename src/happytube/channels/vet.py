"""Agent vetting of a channel: the pure parts (decision 0005).

Flags, prompt, output check, verdict rule and report rendering — no network, no
click. The Claude call and the run over several channels live in
``channels/vet_run.py``.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import yaml
from pydantic import BaseModel, ConfigDict

from happytube.channels.models import (
    Channel,
    ChannelFlag,
    Evidence,
    EvidenceVideo,
    IdentityMatch,
    Review,
    Verdict,
    VetReport,
    VetUsage,
    VetVideo,
)
from happytube.rubric import RUBRIC, Score, VideoScore, is_suitable

MODEL = "claude-opus-5-5"
PROMPT_VERSION = 1
REVIEWER = "claude-vet"
INACTIVE_AFTER = timedelta(days=365)
MIN_LONG_FORM = 5
# Any of these turns a model ``approve`` into ``unsure``.
DOWNGRADING_FLAGS: frozenset[str] = frozenset(
    {"inactive", "mostly_shorts", "identity_doubt"}
)


class VetOutput(BaseModel):
    """What the model returns for one channel (structured output)."""

    model_config = ConfigDict(extra="forbid")

    identity_match: IdentityMatch
    identity_note: str
    channel_calm: Score
    channel_happy: Score
    verdict: Verdict
    summary: str
    concerns: list[str]
    videos: list[VideoScore]


class VetOutputError(ValueError):
    """The model's output does not fit the videos it was sent."""


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str


def long_form(evidence: Evidence) -> list[EvidenceVideo]:
    """Videos that are not Shorts, in snapshot order (newest first)."""
    return [v for v in evidence.videos if not v.is_short]


def channel_flags(channel: Channel, evidence: Evidence | None) -> list[ChannelFlag]:
    """Deterministic flags, computed before any model call.

    ``unresolved`` alone when there is nothing to judge (no ``channel_id`` or no
    snapshot). ``inactive`` when the newest upload is more than a year older than
    the snapshot (or there are none); ``mostly_shorts`` when fewer than
    ``MIN_LONG_FORM`` long-form videos remain. ``identity_doubt`` comes later,
    from the model.
    """
    if channel.channel_id is None or evidence is None:
        return ["unresolved"]
    flags: list[ChannelFlag] = []
    newest = max((v.published_at for v in evidence.videos), default=None)
    if newest is None or evidence.fetched_at - newest > INACTIVE_AFTER:
        flags.append("inactive")
    if len(long_form(evidence)) < MIN_LONG_FORM:
        flags.append("mostly_shorts")
    return flags


def apply_verdict_rule(model_verdict: Verdict, flags: list[ChannelFlag]) -> Verdict:
    """Final verdict: ``approve`` becomes ``unsure`` when a downgrading flag is
    set; ``reject`` and ``unsure`` pass through."""
    if model_verdict == "approve" and DOWNGRADING_FLAGS.intersection(flags):
        return "unsure"
    return model_verdict


SYSTEM_PROMPT = f"""\
You vet YouTube channels for HappyTube, a player of calm, happy videos for one \
vulnerable viewer. A human makes the final decision; your report helps them.

What approval means: an approved channel becomes a source. Its new long-form \
videos are fetched and each one is scored by an agent with the rubric below; \
only videos scored suitable are shown. No human picks videos one by one.

{RUBRIC}

You get one channel: its entry in our registry (what we believe it is), a \
snapshot of the YouTube channel the entry resolved to, and its recent long-form \
uploads (Shorts are already removed).

Do three things:

1. Identity. Does the YouTube channel match the registry entry — the same \
organisation, not a fan page, re-upload channel or look-alike? Compare name, \
kind, languages, title, custom URL, description, country and subscriber count. \
Answer identity_match yes, no or unsure, and explain briefly in identity_note.

2. Videos. Score every long-form video you were given, once each, using its \
exact video_id: calm, happy, flags and a short note (one sentence, English).

3. Channel. Give channel_calm and channel_happy for the channel as a whole, and \
a verdict:
  approve  most recent videos would suit her, and unsuitable ones are rare \
and recognisable from their title and description
  reject   unsuitable content is a staple of the channel, or hard to spot \
from title and description
  unsure   mixed, too little to judge, or the identity is in doubt
Write summary as 1 to 3 plain sentences for the human reviewer, and list \
concrete concerns, citing video titles. Use an empty list when there are none.

Titles and descriptions may be in Czech; read them in Czech. Write your notes, \
summary and concerns in English."""


def _duration(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def build_prompt(channel: Channel, evidence: Evidence) -> Prompt:
    """System and user content for one channel. Deterministic (no clock, stable
    key order) so the system part stays cache-friendly; Shorts are left out."""
    videos = long_form(evidence)
    data = {
        "registry_entry": {
            "name": channel.name,
            "kind": channel.kind,
            "languages": list(channel.languages),
            "handle": channel.handle,
            "url": channel.url,
            "notes": channel.notes,
        },
        "youtube_snapshot": {
            "fetched_at": evidence.model_dump(mode="json")["fetched_at"],
            "title": evidence.title,
            "custom_url": evidence.custom_url,
            "country": evidence.country,
            "subscriber_count": evidence.subscriber_count,
            "video_count": evidence.video_count,
            "description": evidence.description,
        },
        "shorts_left_out": evidence.shorts_count,
        "long_form_videos": [
            {
                "video_id": v.video_id,
                "title": v.title,
                "published": v.model_dump(mode="json")["published_at"][:10],
                "duration": _duration(v.duration_s),
                "language": v.default_language,
                "description": v.description,
            }
            for v in videos
        ],
    }
    user = (
        f"Vet this channel. Score all {len(videos)} long-form videos.\n\n"
        + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    )
    return Prompt(SYSTEM_PROMPT, user)


def check_video_ids(output: VetOutput, evidence: Evidence) -> None:
    """Every long-form video scored exactly once and nothing else; raises
    ``VetOutputError`` naming the ids otherwise."""
    expected = [v.video_id for v in long_form(evidence)]
    got = [v.video_id for v in output.videos]
    problems = []
    if missing := sorted(set(expected) - set(got)):
        problems.append(f"missing {', '.join(missing)}")
    if extra := sorted(set(got) - set(expected)):
        problems.append(f"unexpected {', '.join(extra)}")
    if duplicate := sorted({i for i in got if got.count(i) > 1}):
        problems.append(f"scored twice {', '.join(duplicate)}")
    if problems:
        msg = "model output does not match the videos sent: " + "; ".join(problems)
        raise VetOutputError(msg)


def build_report(  # noqa: PLR0913 - the parts of one report
    evidence: Evidence,
    output: VetOutput,
    flags: list[ChannelFlag],
    *,
    model: str,
    usage: VetUsage,
    vetted_at: datetime | None = None,
) -> VetReport:
    """The report frontmatter: ``flags`` are the deterministic ones, plus
    ``identity_doubt`` when the model was not sure of the identity. Videos follow
    snapshot order."""
    check_video_ids(output, evidence)
    flags = list(flags)
    if output.identity_match != "yes" and "identity_doubt" not in flags:
        flags.append("identity_doubt")
    scores = {s.video_id: s for s in output.videos}
    videos = [
        VetVideo(
            video_id=v.video_id,
            title=v.title,
            calm=scores[v.video_id].calm,
            happy=scores[v.video_id].happy,
            flags=scores[v.video_id].flags,
            suitable=is_suitable(
                scores[v.video_id].calm,
                scores[v.video_id].happy,
                scores[v.video_id].flags,
            ),
            note=scores[v.video_id].note,
        )
        for v in long_form(evidence)
    ]
    fields = {
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "evidence_at": evidence.fetched_at,
        "verdict": apply_verdict_rule(output.verdict, flags),
        "model_verdict": output.verdict,
        "flags": flags,
        "identity_match": output.identity_match,
        "identity_note": output.identity_note,
        "channel_calm": output.channel_calm,
        "channel_happy": output.channel_happy,
        "summary": output.summary,
        "concerns": output.concerns,
        "usage": usage,
        "videos": videos,
        "shorts_skipped": evidence.shorts_count,
    }
    if vetted_at is not None:
        fields["vetted_at"] = vetted_at
    return VetReport.model_validate(fields)


def _cell(text: str) -> str:
    """Text safe inside a markdown table cell."""
    return " ".join(text.split()).replace("|", "\\|")


def render_report(channel: Channel, report: VetReport) -> str:
    """Markdown body of a vet report, for people reading it in git."""
    lines = [
        f"# {channel.name} — vet",
        "",
        f"**Verdict: {report.verdict}** (model: {report.model_verdict}; "
        f"flags: {', '.join(report.flags) or 'none'}) · "
        f"calm {report.channel_calm}/5 · happy {report.channel_happy}/5 · "
        f"{report.suitable_count} of {len(report.videos)} long-form videos "
        f"suitable, {report.shorts_skipped} Shorts skipped",
        "",
        "## Summary",
        "",
        report.summary,
        "",
        f"## Identity: {report.identity_match}",
        "",
        report.identity_note,
        "",
        "## Concerns",
        "",
    ]
    lines += [f"- {c}" for c in report.concerns] or ["None."]
    lines += [
        "",
        "## Videos",
        "",
        "| Title | Calm | Happy | Flags | Suitable | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {_cell(v.title)} | {v.calm} | {v.happy} | {', '.join(v.flags)} | "
        f"{'yes' if v.suitable else 'no'} | {_cell(v.note)} |"
        for v in report.videos
    ]
    return "\n".join(lines) + "\n"


def review_for(report: VetReport, report_name: str) -> Review:
    """The agent review recorded with a vet; it never changes status."""
    flags = ", ".join(report.flags) or "none"
    notes = f"{report.summary} Flags: {flags}."
    if report.verdict != report.model_verdict:
        why = ", ".join(f for f in report.flags if f in DOWNGRADING_FLAGS)
        notes += f" Model said {report.model_verdict}; {report.verdict} because {why}."
    notes += f" Report: vet/{report_name}"
    return Review(
        reviewer=REVIEWER,
        role="agent",
        verdict=report.verdict,
        notes=notes,
        created_at=report.vetted_at,
    )
