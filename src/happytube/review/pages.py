"""Rendering and request helpers shared by the channel and video review routes."""

from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import jinja2
from fastapi import Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from happytube.review.queue import is_unresolved, needs_attention
from happytube.trusted.stages import is_video_id
from happytube.utils import fmt_utc

PACKAGE_DIR = Path(__file__).parent
REVIEWER_COOKIE = "happytube_reviewer"
COOKIE_MAX_AGE = 365 * 24 * 3600


def _fmt_int(value: int | None) -> str:
    return "—" if value is None else f"{value:,}".replace(",", " ")


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _is_video_id(value: object) -> bool:
    """The one video-id rule (``trusted.stages.is_video_id``); anything else is
    never put in a link."""
    return is_video_id(str(value))


def _templates() -> Jinja2Templates:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(PACKAGE_DIR / "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Typed as Any: ty infers jinja's defaults dicts too narrowly to add to them.
    filters: dict[str, Any] = {
        "dt": fmt_utc,
        "num": _fmt_int,
        "duration": _fmt_duration,
        "pct": _fmt_pct,
    }
    tests: dict[str, Any] = {"video_id": _is_video_id}
    helpers: dict[str, Any] = {
        "needs_attention": needs_attention,
        "is_unresolved": is_unresolved,
    }
    env.filters.update(filters)
    env.tests.update(tests)
    env.globals.update(helpers)
    return Jinja2Templates(env=env)


def blank(value: str | None) -> str | None:
    """Query/form value with empty meaning absent."""
    value = (value or "").strip()
    return value or None


def is_htmx(request: Request) -> bool:
    """An htmx partial request; a history restore wants the full page."""
    return (
        request.headers.get("hx-request") == "true"
        and request.headers.get("hx-history-restore-request") != "true"
    )


class FormError(ValueError):
    """Form or query input the user has to correct; the message is shown to them."""


def text_response(status_code: int, message: str) -> Response:
    return Response(message, status_code, media_type="text/plain")


class Pages:
    """Template rendering, error pages and the reviewer prefill, shared by the
    channel and video routes."""

    def __init__(self, default_reviewer: str | None):
        self.templates = _templates()
        self.default_reviewer = default_reviewer

    def render(
        self,
        request: Request,
        name: str,
        context: dict[str, Any],
        status_code: int = 200,
    ) -> HTMLResponse:
        return self.templates.TemplateResponse(
            request, name, context, status_code=status_code
        )

    def error(self, request: Request, status_code: int, message: str) -> Response:
        """The error page; for an htmx request just the message as plain text,
        which ``review.js`` shows in the ``role="alert"`` region."""
        if is_htmx(request):
            return text_response(status_code, message)
        context = {"status_code": status_code, "message": message}
        return self.render(request, "error.html", context, status_code)

    def reviewer_prefill(self, request: Request) -> str:
        """The server default (``--reviewer``) if set, else the last reviewer name
        used in this browser. The default wins so a name left in the browser by an
        earlier session (e.g. a QA run) can't silently replace the one the server
        was started with."""
        if self.default_reviewer:
            return self.default_reviewer
        cookie = request.cookies.get(REVIEWER_COOKIE)
        return unquote(cookie) if cookie else ""


def remember_reviewer(response: Response, reviewer: str) -> None:
    response.set_cookie(
        REVIEWER_COOKIE,
        quote(reviewer),
        max_age=COOKIE_MAX_AGE,
        path="/",
        httponly=True,
        samesite="strict",
    )
