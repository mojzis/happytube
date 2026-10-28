"""Video spot-check routes of the review app (decision 0011).

``/videos`` is the queue with the agreement summary, ``/videos/{id}`` one video
(the agent's call, both descriptions, an embedded player, its reviews and the
form), ``POST /videos/{id}/reviews`` writes a human review — the same file
``happytube videos review`` writes. Everything is re-read per request through
``load_spot_checks``; a missing video-reviews directory fails the page.
"""

from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from happytube.channels.store import ChannelStore
from happytube.review.pages import (
    FormError,
    Pages,
    blank,
    is_htmx,
    remember_reviewer,
)
from happytube.rubric import FLAGS
from happytube.trusted.spot_checks import (
    SECTION_FILTERS,
    SpotVideo,
    in_section,
    load_spot_checks,
    load_video,
    new_review,
    queue_agreement,
    sections,
)
from happytube.trusted.video_reviews import (
    VIDEO_VERDICTS,
    WATCHED,
    VideoReview,
    VideoReviewStore,
)

SECTION_TITLES = {
    "shown": "Shown in the player, not spot-checked",
    "unreviewed": "Not shown, not spot-checked",
    "reviewed": "Spot-checked",
    "disagree": "Disagreements with the agent",
}


def parse_video_review(  # noqa: PLR0913 - one parameter per form field
    video: SpotVideo,
    reviewer: str,
    verdict: str,
    flags: list[str],
    watched: str,
    notes: str,
) -> VideoReview:
    """A human review of ``video`` from form fields; ``FormError`` says what to
    correct."""
    reviewer = reviewer.strip()
    if not reviewer:
        msg = "Enter your name as reviewer."
        raise FormError(msg)
    if verdict not in VIDEO_VERDICTS:
        msg = "Choose suitable, unsuitable or unsure."
        raise FormError(msg)
    if watched not in WATCHED:
        msg = "Say how much you watched: full, part or title only."
        raise FormError(msg)
    if unknown := sorted(set(flags) - set(FLAGS)):
        msg = f"Unknown flag {', '.join(unknown)}"
        raise FormError(msg)
    try:
        return new_review(
            video,
            reviewer=reviewer,
            role="human",
            verdict=verdict,
            flags=flags,
            watched=watched,
            notes=blank(notes),
        )
    except ValidationError as e:
        raise FormError("; ".join(err["msg"] for err in e.errors())) from e


def parse_section(section: str | None) -> str | None:
    """The queue's section filter, empty meaning all; ``FormError`` if unknown."""
    section = blank(section)
    if section is not None and section not in SECTION_FILTERS:
        msg = f"Unknown section '{section}'"
        raise FormError(msg)
    return section


def queue_view(videos: list[SpotVideo], section: str | None) -> list[dict[str, Any]]:
    """The tables to show: every section, or only the one asked for."""
    if section is not None:
        names = [section]
        rows = {section: in_section(videos, section)}
    else:
        names = ["shown", "unreviewed", "reviewed"]
        rows = sections(videos)
    return [{"name": n, "title": SECTION_TITLES[n], "rows": rows[n]} for n in names]


def install_video_routes(
    app: FastAPI,
    pages: Pages,
    channels: ChannelStore,
    reviews: VideoReviewStore,
    stages_dir: Path,
) -> None:
    def load() -> list[SpotVideo]:
        return load_spot_checks(stages_dir, channels, reviews)

    def get(video_id: str) -> SpotVideo:
        return load_video(stages_dir, channels, reviews, video_id)

    def context(
        request: Request,
        video: SpotVideo,
        form: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        blank_form = {
            "reviewer": pages.reviewer_prefill(request),
            "flags": [],
            "notes": "",
        }
        return {
            "video": video,
            "a": video.assess,
            "reviews": list(reversed(video.state.reviews)),
            "form": form or blank_form,
            "error": error,
            "verdicts": VIDEO_VERDICTS,
            "watched": WATCHED,
            "flags": FLAGS,
        }

    @app.get("/videos", response_model=None)
    def video_queue(request: Request, section: str | None = None) -> Response:
        try:
            chosen = parse_section(section)
        except FormError as e:
            return pages.error(request, HTTPStatus.BAD_REQUEST, str(e))
        videos = load()
        page = {
            "tables": queue_view(videos, chosen),
            "stats": queue_agreement(videos),
            "total": len(videos),
            "section": chosen,
            "filters": SECTION_FILTERS,
            "titles": SECTION_TITLES,
        }
        return pages.render(request, "videos.html", page)

    @app.get("/videos/{video_id}")
    def video_detail(request: Request, video_id: str) -> HTMLResponse:
        return pages.render(request, "video.html", context(request, get(video_id)))

    @app.post("/videos/{video_id}/reviews", response_model=None)
    def post_video_review(  # noqa: PLR0913 - one parameter per form field
        request: Request,
        video_id: str,
        reviewer: Annotated[str, Form()] = "",
        verdict: Annotated[str, Form()] = "",
        watched: Annotated[str, Form()] = "",
        notes: Annotated[str, Form()] = "",
        flags: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        video = get(video_id)  # 404 before anything else
        htmx = is_htmx(request)
        chosen = flags or []
        try:
            review = parse_video_review(
                video, reviewer, verdict, chosen, watched, notes
            )
        except FormError as e:
            form = {
                "reviewer": reviewer.strip(),
                "verdict": verdict,
                "watched": watched,
                "flags": chosen,
                "notes": notes,
            }
            page = context(request, video, form, str(e))
            name = "_video_reviews.html" if htmx else "video.html"
            return pages.render(request, name, page, HTTPStatus.UNPROCESSABLE_ENTITY)
        reviews.add_review(video_id, review)
        if htmx:
            fresh = {"reviewer": review.reviewer, "flags": [], "notes": ""}
            page = context(request, get(video_id), fresh)
            page["oob_shown"] = True
            response: Response = pages.render(request, "_video_reviews.html", page)
        else:
            response = RedirectResponse(
                f"/videos/{video_id}", status_code=HTTPStatus.SEE_OTHER
            )
        remember_reviewer(response, review.reviewer)
        return response
