"""Local web app: the channel review UI (decision 0007), video spot-checks
(decision 0011, routes in ``review.videos``) and the player (decision 0010).

``create_app`` builds a FastAPI app over one ``ChannelStore`` and one
``VideoReviewStore``; they are the only readers and writers, re-read on every
request. Reviews posted here are the same records ``happytube channels review`` /
``happytube videos review`` write, always ``role: human``.

``/player/`` serves the static player page (``happytube/web/static``) and
``/player/videos.json`` the selection read live from ``stages/trusted/``, the
registry and ``video-reviews/`` — the same rule the GitHub Pages export uses.

The app has no auth and writes files, so it only answers requests whose ``Host`` is
loopback (or the ``--host`` it was started with) — against DNS rebinding — and
refuses cross-site ``POST`` by ``Origin`` / ``Sec-Fetch-Site`` — against CSRF.
"""

import ipaddress
import logging
import re
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from happytube.channels.models import KINDS, LANGUAGES, STATUSES, VERDICTS, Review
from happytube.channels.store import (
    ChannelEntry,
    ChannelNotFoundError,
    ChannelStore,
    filter_entries,
)
from happytube.channels.vet import long_form
from happytube.records import StoreError
from happytube.review.estimate import channel_watchable, watchable_estimate
from happytube.review.pages import (
    PACKAGE_DIR,
    FormError,
    Pages,
    blank,
    is_htmx,
    remember_reviewer,
    text_response,
)
from happytube.review.queue import next_entry, queue_sections
from happytube.review.videos import install_video_routes
from happytube.trusted.player import player_videos, videos_json
from happytube.trusted.video_reviews import (
    VIDEO_REVIEWS_DIR,
    VideoNotFoundError,
    VideoReviewsMissingError,
    VideoReviewStore,
)

logger = logging.getLogger(__name__)

PLAYER_DIR = PACKAGE_DIR.parent / "web" / "static"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SAME_SITE_FETCH = frozenset({"same-origin", "none"})
_HOST_RE = re.compile(r"\[(?P<v6>[^\]]+)\](?::\d+)?|(?P<name>[^:\[\]]+)(?::\d+)?")


def is_loopback(host: str) -> bool:
    """``localhost`` or a loopback IP (``127.0.0.0/8``, ``::1``)."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def is_wildcard(host: str) -> bool:
    """An all-interfaces bind address (``0.0.0.0``, ``::``): no client sends it as
    ``Host``, so it cannot be allow-listed."""
    try:
        return ipaddress.ip_address(host.strip("[]")).is_unspecified
    except ValueError:
        return False


def _canonical(name: str) -> str:
    """An IP address in its canonical form (``FE80:0::1`` → ``fe80::1``), else the
    name lowercased."""
    try:
        return str(ipaddress.ip_address(name))
    except ValueError:
        return name.lower()


def host_name(header: str) -> str | None:
    """The host part of a ``Host`` header, without port or brackets, canonical."""
    match = _HOST_RE.fullmatch(header.strip())
    if not match:
        return None
    return _canonical(match["v6"] or match["name"])


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
    """Loopback names, plus ``bind_host`` (a name, or a bare or bracketed IPv4/IPv6
    address) if given."""
    if not bind_host:
        return LOOPBACK_HOSTS
    return LOOPBACK_HOSTS | {_canonical(bind_host.strip().strip("[]"))}


def parse_review(reviewer: str, verdict: str, notes: str) -> Review:
    """A human ``Review`` from form fields; ``FormError`` says what to correct."""
    reviewer = reviewer.strip()
    if not reviewer:
        msg = "Enter your name as reviewer."
        raise FormError(msg)
    if verdict not in VERDICTS:
        msg = "Choose approve, reject or unsure."
        raise FormError(msg)
    try:
        return Review.model_validate(
            {
                "reviewer": reviewer,
                "role": "human",
                "verdict": verdict,
                "notes": blank(notes),
            }
        )
    except ValidationError as e:
        raise FormError("; ".join(err["msg"] for err in e.errors())) from e


def parse_filters(
    status: str | None, kind: str | None, language: str | None
) -> dict[str, str | None]:
    """Queue filters with empty meaning absent; ``FormError`` on an unknown value."""
    filters = {
        "status": blank(status),
        "kind": blank(kind),
        "language": blank(language),
    }
    allowed = {"status": STATUSES, "kind": KINDS, "language": LANGUAGES}
    for key, value in filters.items():
        if value is not None and value not in allowed[key]:
            msg = f"Unknown {key} filter '{value}'"
            raise FormError(msg)
    return filters


def _install_guard(app: FastAPI, allowed_hosts: frozenset[str]) -> None:
    """Refuse a non-allowed ``Host`` (400) and cross-site unsafe requests (403)
    before any route runs, so nothing is written."""

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if host_name(request.headers.get("host", "")) not in allowed_hosts:
            return text_response(HTTPStatus.BAD_REQUEST, "Bad Host header")
        if request.method not in SAFE_METHODS and not _origin_ok(request):
            return text_response(HTTPStatus.FORBIDDEN, "Cross-site request refused")
        return await call_next(request)


class _Pages(Pages):
    """Rendering plus the channel detail page's context."""

    def detail_context(
        self,
        request: Request,
        entry: ChannelEntry,
        form: dict[str, str] | None = None,
        error: str | None = None,
        next_channel: ChannelEntry | None = None,
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
            "watchable": channel_watchable(entry),
            "next_channel": next_channel,
        }


def _install_error_handlers(app: FastAPI, pages: _Pages) -> None:
    """Store errors and HTTP errors as HTML pages; never a traceback."""

    @app.exception_handler(ChannelNotFoundError)
    async def not_found(request: Request, exc: ChannelNotFoundError) -> Response:
        return pages.error(request, HTTPStatus.NOT_FOUND, str(exc))

    @app.exception_handler(VideoNotFoundError)
    async def no_video(request: Request, exc: VideoNotFoundError) -> Response:
        return pages.error(request, HTTPStatus.NOT_FOUND, str(exc))

    @app.exception_handler(StoreError)
    async def store_error(request: Request, exc: StoreError) -> Response:
        return pages.error(request, HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        return pages.error(request, exc.status_code, str(exc.detail))


def _install_player(
    app: FastAPI, store: ChannelStore, stages_dir: Path, reviews: VideoReviewStore
) -> None:
    """``/player/videos.json`` (the live selection) and the static player page."""
    trusted_dir = stages_dir / "trusted"
    warned_missing = False

    # Before the /player mount, so a videos.json left in the static dir by an
    # export never shadows the live selection (HEAD included).
    @app.api_route("/player/videos.json", methods=["GET", "HEAD"])
    def player_json() -> JSONResponse:
        nonlocal warned_missing
        if not trusted_dir.is_dir() and not warned_missing:
            # A wrong --stages-dir would otherwise look like "no videos yet".
            logger.warning("Player: %s does not exist; showing no videos", trusted_dir)
            warned_missing = True
        try:
            videos = videos_json(player_videos(stages_dir, store, reviews))
        except VideoReviewsMissingError as e:
            # Never "no reviews": that could show videos a human hid.
            logger.error("Player: %s", e)  # noqa: TRY400 — message, no traceback
            return JSONResponse({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        return JSONResponse(videos, headers={"Cache-Control": "no-store"})

    app.mount("/player", StaticFiles(directory=PLAYER_DIR, html=True), name="player")


def create_app(
    store: ChannelStore,
    *,
    default_reviewer: str | None,
    bind_host: str | None = None,
    stages_dir: Path = Path("stages"),
    video_reviews: VideoReviewStore | None = None,
) -> FastAPI:
    """The review app over ``store``. ``default_reviewer`` prefills the form; without
    it, the browser's reviewer cookie does. ``bind_host`` is the ``--host`` served on;
    a non-loopback one is also accepted in the ``Host`` header. The player reads
    ``<stages_dir>/trusted/`` and ``video_reviews`` (default: ``video-reviews/`` at
    the repo root)."""
    reviews = video_reviews or VideoReviewStore(VIDEO_REVIEWS_DIR)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    pages = _Pages(default_reviewer)
    _install_guard(app, allowed_host_names(bind_host))
    _install_error_handlers(app, pages)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")

    _install_player(app, store, stages_dir, reviews)
    install_video_routes(app, pages, store, reviews, stages_dir)

    @app.get("/")
    async def index() -> RedirectResponse:
        return RedirectResponse("/channels", status_code=HTTPStatus.SEE_OTHER)

    # Routes reading or writing the registry are plain ``def``: FastAPI runs them in
    # a thread pool, so file I/O does not block the event loop.
    @app.get("/channels", response_model=None)
    def queue(
        request: Request,
        status: str | None = None,
        kind: str | None = None,
        language: str | None = None,
    ) -> Response:
        try:
            filters = parse_filters(status, kind, language)
        except FormError as e:
            return pages.error(request, HTTPStatus.BAD_REQUEST, str(e))
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
            "estimate": watchable_estimate(entries),
            "filters": filters,
            "statuses": STATUSES,
            "kinds": KINDS,
            "languages": LANGUAGES,
        }
        name = "_queue_table.html" if is_htmx(request) else "queue.html"
        response = pages.render(request, name, context)
        response.headers["Vary"] = "HX-Request"
        return response

    @app.get("/channels/{slug}")
    def detail(request: Request, slug: str) -> HTMLResponse:
        entry = store.get(slug)
        upcoming = next_entry(store.entries(), slug)
        context = pages.detail_context(request, entry, next_channel=upcoming)
        return pages.render(request, "channel.html", context)

    @app.post("/channels/{slug}/reviews", response_model=None)
    def post_review(
        request: Request,
        slug: str,
        reviewer: Annotated[str, Form()] = "",
        verdict: Annotated[str, Form()] = "",
        notes: Annotated[str, Form()] = "",
    ) -> Response:
        entry = store.get(slug)  # 404 before anything else
        htmx = is_htmx(request)
        try:
            review = parse_review(reviewer, verdict, notes)
        except FormError as e:
            form = {"reviewer": reviewer.strip(), "verdict": verdict, "notes": notes}
            context = pages.detail_context(request, entry, form, str(e))
            name = "_reviews.html" if htmx else "channel.html"
            return pages.render(request, name, context, HTTPStatus.UNPROCESSABLE_ENTITY)
        store.add_review(slug, review)
        if htmx:
            fresh = {"reviewer": review.reviewer, "notes": ""}
            context = pages.detail_context(request, store.get(slug), fresh)
            context["oob_status"] = True
            response: Response = pages.render(request, "_reviews.html", context)
        else:
            response = RedirectResponse(
                f"/channels/{slug}", status_code=HTTPStatus.SEE_OTHER
            )
        remember_reviewer(response, review.reviewer)
        return response

    return app
