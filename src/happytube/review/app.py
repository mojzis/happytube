"""Local web review UI for the channel registry (decision 0007).

``create_app`` builds a FastAPI app over one ``ChannelStore``; the store is the only
reader and writer, re-read on every request. Reviews posted here are the same
records ``happytube channels review`` writes, always ``role: human``.

The app has no auth and writes files, so it only answers requests whose ``Host`` is
loopback (or the ``--host`` it was started with) — against DNS rebinding — and
refuses cross-site ``POST`` by ``Origin`` / ``Sec-Fetch-Site`` — against CSRF.
"""

import ipaddress
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote, unquote

import jinja2
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from happytube.channels.models import KINDS, LANGUAGES, STATUSES, VERDICTS, Review
from happytube.channels.store import (
    ChannelEntry,
    ChannelNotFoundError,
    ChannelStore,
    ChannelStoreError,
    filter_entries,
)
from happytube.channels.vet import long_form
from happytube.review.queue import is_unresolved, needs_attention, queue_sections

PACKAGE_DIR = Path(__file__).parent
REVIEWER_COOKIE = "happytube_reviewer"
COOKIE_MAX_AGE = 365 * 24 * 3600
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SAME_SITE_FETCH = frozenset({"same-origin", "none"})
# YouTube video ids are URL-safe base64; anything else is never put in a link.
VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
_HOST_RE = re.compile(r"\[(?P<v6>[^\]]+)\](?::\d+)?|(?P<name>[^:\[\]]+)(?::\d+)?")

HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE = 422
HTTP_SERVER_ERROR = 500


def is_loopback(host: str) -> bool:
    """``localhost`` or a loopback IP (``127.0.0.0/8``, ``::1``)."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def host_name(header: str) -> str | None:
    """The host part of a ``Host`` header, lowercased, without port or brackets."""
    match = _HOST_RE.fullmatch(header.strip())
    if not match:
        return None
    return (match["v6"] or match["name"]).lower()


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_int(value: int | None) -> str:
    return "—" if value is None else f"{value:,}".replace(",", " ")


def _is_video_id(value: object) -> bool:
    return bool(VIDEO_ID_RE.fullmatch(str(value)))


def _templates() -> Jinja2Templates:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(PACKAGE_DIR / "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Typed as Any: ty infers jinja's defaults dicts too narrowly to add to them.
    filters: dict[str, Any] = {"dt": _fmt_dt, "num": _fmt_int}
    tests: dict[str, Any] = {"video_id": _is_video_id}
    helpers: dict[str, Any] = {
        "needs_attention": needs_attention,
        "is_unresolved": is_unresolved,
    }
    env.filters.update(filters)
    env.tests.update(tests)
    env.globals.update(helpers)
    return Jinja2Templates(env=env)


def evidence_view(entry: ChannelEntry) -> dict[str, Any] | None:
    """Counts and the newest upload of the latest snapshot, for the detail page."""
    evidence = entry.latest_evidence
    if evidence is None:
        return None
    return {
        "evidence": evidence,
        "long_form_count": len(long_form(evidence)),
        "shorts_count": evidence.shorts_count,
        "newest_upload": max((v.published_at for v in evidence.videos), default=None),
    }


def _blank(value: str | None) -> str | None:
    """Query/form value with empty meaning absent."""
    value = (value or "").strip()
    return value or None


def _is_htmx(request: Request) -> bool:
    """An htmx partial request; a history restore wants the full page."""
    return (
        request.headers.get("hx-request") == "true"
        and request.headers.get("hx-history-restore-request") != "true"
    )


def _origin_ok(request: Request) -> bool:
    """Same-origin by ``Origin``, else by ``Sec-Fetch-Site``; neither → allowed
    (non-browser clients such as ``curl`` send neither)."""
    origin = request.headers.get("origin")
    if origin is not None:
        own = f"{request.url.scheme}://{request.headers.get('host', '')}"
        return origin.lower() == own.lower()
    site = request.headers.get("sec-fetch-site")
    return site is None or site in SAME_SITE_FETCH


def allowed_host_names(bind_host: str | None) -> frozenset[str]:
    """Loopback names, plus the host part of ``bind_host`` if given."""
    name = host_name(bind_host) if bind_host else None
    return LOOPBACK_HOSTS | {name} if name else LOOPBACK_HOSTS


def parse_review(reviewer: str, verdict: str, notes: str) -> Review | str:
    """A human ``Review`` from form fields, or the error message to show."""
    reviewer = reviewer.strip()
    if not reviewer:
        return "Enter your name as reviewer."
    if verdict not in VERDICTS:
        return "Choose approve, reject or unsure."
    try:
        return Review.model_validate(
            {
                "reviewer": reviewer,
                "role": "human",
                "verdict": verdict,
                "notes": _blank(notes),
            }
        )
    except ValidationError as e:
        return "; ".join(err["msg"] for err in e.errors())


def parse_filters(**values: str | None) -> dict[str, str | None] | str:
    """Queue filters with empty meaning absent, or the error for an unknown value."""
    allowed = {"status": STATUSES, "kind": KINDS, "language": LANGUAGES}
    filters = {key: _blank(value) for key, value in values.items()}
    for key, value in filters.items():
        if value is not None and value not in allowed[key]:
            return f"Unknown {key} filter '{value}'"
    return filters


def _text(status_code: int, message: str) -> Response:
    return Response(message, status_code, media_type="text/plain")


def _install_guard(app: FastAPI, allowed_hosts: frozenset[str]) -> None:
    """Refuse a non-allowed ``Host`` (400) and cross-site unsafe requests (403)
    before any route runs, so nothing is written."""

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if host_name(request.headers.get("host", "")) not in allowed_hosts:
            return _text(HTTP_BAD_REQUEST, "Bad Host header")
        if request.method not in SAFE_METHODS and not _origin_ok(request):
            return _text(HTTP_FORBIDDEN, "Cross-site request refused")
        return await call_next(request)


class _Pages:
    """Template rendering shared by the routes."""

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

    def error(self, request: Request, status_code: int, message: str) -> HTMLResponse:
        context = {"status_code": status_code, "message": message}
        return self.render(request, "error.html", context, status_code)

    def reviewer_prefill(self, request: Request) -> str:
        """Last reviewer name used in this browser, else the server default."""
        cookie = request.cookies.get(REVIEWER_COOKIE)
        return unquote(cookie) if cookie else (self.default_reviewer or "")

    def detail_context(
        self,
        request: Request,
        entry: ChannelEntry,
        form: dict[str, str] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        blank_form = {"reviewer": self.reviewer_prefill(request), "notes": ""}
        return {
            "entry": entry,
            "channel": entry.channel,
            "ev": evidence_view(entry),
            "vet": entry.latest_vet,
            "reviews": list(reversed(entry.reviews)),
            "form": form or blank_form,
            "error": error,
            "verdicts": VERDICTS,
        }


def _install_error_handlers(app: FastAPI, pages: _Pages) -> None:
    """Store errors and HTTP errors as HTML pages; never a traceback."""

    @app.exception_handler(ChannelNotFoundError)
    async def not_found(request: Request, exc: ChannelNotFoundError) -> HTMLResponse:
        return pages.error(request, HTTP_NOT_FOUND, str(exc))

    @app.exception_handler(ChannelStoreError)
    async def store_error(request: Request, exc: ChannelStoreError) -> HTMLResponse:
        return pages.error(request, HTTP_SERVER_ERROR, str(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
        return pages.error(request, exc.status_code, str(exc.detail))


def _remember_reviewer(response: Response, reviewer: str) -> None:
    response.set_cookie(
        REVIEWER_COOKIE,
        quote(reviewer),
        max_age=COOKIE_MAX_AGE,
        path="/",
        httponly=True,
        samesite="strict",
    )


def create_app(
    store: ChannelStore,
    *,
    default_reviewer: str | None,
    bind_host: str | None = None,
) -> FastAPI:
    """The review app over ``store``. ``default_reviewer`` prefills the form when
    the browser has no reviewer cookie. ``bind_host`` is the ``--host`` served on;
    a non-loopback one is also accepted in the ``Host`` header."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    pages = _Pages(default_reviewer)
    _install_guard(app, allowed_host_names(bind_host))
    _install_error_handlers(app, pages)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")

    @app.get("/")
    async def index() -> RedirectResponse:
        return RedirectResponse("/channels", status_code=303)

    @app.get("/channels")
    async def queue(
        request: Request,
        status: str | None = None,
        kind: str | None = None,
        language: str | None = None,
    ) -> HTMLResponse:
        filters = parse_filters(status=status, kind=kind, language=language)
        if isinstance(filters, str):
            return pages.error(request, HTTP_BAD_REQUEST, filters)
        entries = store.entries()
        context = {
            "sections": queue_sections(
                filter_entries(
                    entries,
                    status=filters["status"],
                    kind=filters["kind"],
                    language=filters["language"],
                )
            ),
            "total": len(entries),
            "filters": filters,
            "statuses": STATUSES,
            "kinds": KINDS,
            "languages": LANGUAGES,
        }
        name = "_queue_table.html" if _is_htmx(request) else "queue.html"
        response = pages.render(request, name, context)
        response.headers["Vary"] = "HX-Request"
        return response

    @app.get("/channels/{slug}")
    async def detail(request: Request, slug: str) -> HTMLResponse:
        context = pages.detail_context(request, store.get(slug))
        return pages.render(request, "channel.html", context)

    @app.post("/channels/{slug}/reviews", response_model=None)
    async def post_review(
        request: Request,
        slug: str,
        reviewer: Annotated[str, Form()] = "",
        verdict: Annotated[str, Form()] = "",
        notes: Annotated[str, Form()] = "",
    ) -> Response:
        entry = store.get(slug)  # 404 before anything else
        review = parse_review(reviewer, verdict, notes)
        htmx = _is_htmx(request)
        if isinstance(review, str):
            form = {"reviewer": reviewer.strip(), "verdict": verdict, "notes": notes}
            context = pages.detail_context(request, entry, form, review)
            name = "_reviews.html" if htmx else "channel.html"
            return pages.render(request, name, context, HTTP_UNPROCESSABLE)
        store.add_review(slug, review)
        if htmx:
            fresh = {"reviewer": review.reviewer, "notes": ""}
            context = pages.detail_context(request, store.get(slug), fresh)
            context["oob_status"] = True
            response: Response = pages.render(request, "_reviews.html", context)
        else:
            response = RedirectResponse(f"/channels/{slug}", status_code=303)
        _remember_reviewer(response, review.reviewer)
        return response

    return app
