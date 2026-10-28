"""The review web app over a temp registry (TestClient, no server, no network)."""

import pytest
import yaml

from happytube.channels.store import ChannelStore
from happytube.review.app import (
    FormError,
    allowed_host_names,
    host_name,
    is_loopback,
    is_wildcard,
    parse_filters,
)
from happytube.review.pages import REVIEWER_COOKIE
from tests.review_helpers import (
    BASE_URL,
    QUEUE,
    chan,
    client,
    detail_url,
    make_vet,
    missing,
    review,
    seed_vetted,
)
from tests.vet_helpers import make_evidence, seed

HTMX = {"HX-Request": "true"}


@pytest.fixture
def store(tmp_path):
    store = ChannelStore(tmp_path / "channels")
    seed_vetted(store, "zoo-praha", "Zoo Praha")
    seed(
        store,
        chan("ct-decko", name="ČT :D / Déčko", channel_id=None, kind="broadcaster"),
    )
    return store


@pytest.fixture
def app(store):
    return client(store)


def _review_files(store, slug):
    return sorted((store.root / slug / "reviews").glob("*.yaml"))


def _post(app, slug="zoo-praha", headers=None, **fields):
    data = {"reviewer": "Matouš", "verdict": "approve", "notes": ""} | fields
    return app.post(
        f"{detail_url(slug)}/reviews",
        data=data,
        headers=headers or {},
        follow_redirects=False,
    )


# --- queue -------------------------------------------------------------------


def test_root_redirects_to_queue(app):
    response = app.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == QUEUE


def test_queue_page_lists_sections_in_order(app, store):
    store.add_review("zoo-praha", review("approve"))

    html = app.get(QUEUE).text

    needs, reviewed = html.split("Needs human review")[1].split("Reviewed")
    assert missing(needs, "ČT :D / Déčko", "unresolved") == []
    # suitable / scored, and the derived status
    assert missing(reviewed, "Zoo Praha", "1/2", 'class="badge status-approved"') == []


def test_queue_filters_plain_get(app):
    html = app.get(QUEUE, params={"kind": "zoo", "language": "", "status": ""}).text
    assert "Zoo Praha" in html
    assert "ČT :D" not in html
    assert '<option value="zoo" selected>' in html


def test_queue_filter_via_htmx_returns_table_partial(app):
    response = app.get(QUEUE, params={"kind": "broadcaster"}, headers=HTMX)
    assert response.status_code == 200
    assert response.text.lstrip().startswith('<div id="queue">')
    assert "<html" not in response.text
    assert "ČT :D" in response.text
    assert "Zoo Praha" not in response.text
    assert response.headers["vary"] == "HX-Request"


def test_queue_htmx_history_restore_gets_full_page(app):
    headers = HTMX | {"HX-History-Restore-Request": "true"}
    assert "<html" in app.get(QUEUE, headers=headers).text


def test_queue_unknown_filter_is_400(app):
    response = app.get(QUEUE, params={"status": "bogus"})
    assert response.status_code == 400
    assert "Unknown status filter" in response.text


def test_parse_filters_blank_means_absent():
    assert parse_filters("", " zoo ", None) == {
        "status": None,
        "kind": "zoo",
        "language": None,
    }


def test_parse_filters_unknown_value_raises_form_error():
    with pytest.raises(FormError, match="Unknown language filter 'xx'"):
        parse_filters(None, None, "xx")


def test_queue_missing_registry_shows_no_channels(tmp_path):
    response = client(ChannelStore(tmp_path / "missing")).get(QUEUE)
    assert response.status_code == 200
    assert "No channels in the registry." in response.text


# --- detail ------------------------------------------------------------------


def test_detail_shows_channel_evidence_vet_and_reviews(app, store):
    store.add_review("zoo-praha", review("unsure", notes="Podívám se znovu."))

    html = app.get(detail_url("zoo-praha")).text

    assert "https://www.youtube.com/channel/UCzoo-praha" in html
    assert "Resolved to: <strong>Zoologická zahrada hl. m. Prahy</strong>" in html
    assert "39 800" in html  # subscribers
    assert "6 long-form, 2 Shorts" in html
    assert 'class="verdict verdict-approve">approve</span> (model said approve)' in html
    assert "https://i.ytimg.com/vi/v0000000000/mqdefault.jpg" in html
    assert "https://www.youtube.com/watch?v=v0000000000" in html
    assert "predation" in html
    assert "2 Shorts skipped" in html
    assert "one feeding clip" in html
    # newest first; human and agent distinct
    assert html.index("Podívám se znovu.") < html.index("claude-vet")
    assert 'class="review role-human"' in html
    assert 'class="review role-agent"' in html


def test_detail_has_next_channel_button_and_watchable(app):
    html = app.get(detail_url("zoo-praha")).text
    assert (
        '<a class="button" href="/channels/ct-decko">Next: ČT :D / Déčko →</a>' in html
    )
    assert "~392 videos" in html


def test_queue_shows_watchable_estimate_for_approved(app, store):
    assert "No approved channels yet" in app.get(QUEUE).text
    store.add_review("zoo-praha", review("approve"))
    html = app.get(QUEUE).text
    assert "~392 watchable videos</strong> in 1 approved channel" in html


def test_detail_without_evidence_or_vet(app):
    html = app.get(detail_url("ct-decko")).text
    assert "No evidence yet." in html
    assert "Not vetted." in html
    assert "not resolved" in html
    assert "youtube.com/channel/" not in html


def test_detail_evidence_without_vet(app, store):
    seed(store, chan("explore-org", name="explore.org"), make_evidence())
    html = app.get(detail_url("explore-org")).text
    assert "Resolved to:" in html
    assert "Not vetted." in html


@pytest.mark.parametrize("slug", ["nope", "Bad_Slug", "..%2Fetc"])
def test_unknown_or_invalid_slug_is_404(app, slug):
    response = app.get(detail_url(slug))
    assert response.status_code == 404
    assert "Not found" in response.text


@pytest.mark.parametrize("path", [QUEUE, detail_url("zoo-praha")])
def test_broken_channel_yaml_is_500_with_message(app, store, path):
    (store.root / "zoo-praha" / "channel.yaml").write_text("slug: [", encoding="utf-8")

    response = app.get(path)

    assert response.status_code == 500
    assert "channel.yaml: invalid YAML" in response.text
    assert "Traceback" not in response.text


# --- errors on htmx requests (shown by review.js in the role="alert" region) ---


def test_htmx_post_store_error_is_500_plain_message(app, store):
    (store.root / "zoo-praha" / "channel.yaml").write_text("slug: [", encoding="utf-8")

    response = _post(app, headers=HTMX)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    assert "channel.yaml: invalid YAML" in response.text
    assert "<html" not in response.text


def test_htmx_post_unknown_channel_is_404_plain_message(app):
    response = _post(app, slug="nope", headers=HTMX)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/plain")
    assert "nope" in response.text


def test_htmx_unknown_filter_is_400_plain_message(app):
    response = app.get(QUEUE, params={"kind": "bogus"}, headers=HTMX)

    assert response.status_code == 400
    assert response.text == "Unknown kind filter 'bogus'"


def test_htmx_cross_site_post_is_403_plain_message(app, store):
    response = _post(app, headers=HTMX | {"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.text == "Cross-site request refused"
    assert len(_review_files(store, "zoo-praha")) == 1


@pytest.mark.parametrize("path", [QUEUE, detail_url("zoo-praha")])
def test_pages_have_an_alert_region_for_htmx_errors(app, path):
    html = app.get(path).text
    alert = 'class="error-message htmx-error" role="alert" hidden'
    assert missing(html, alert, 'src="/static/review.js"') == []


def test_review_js_shows_error_as_text(app):
    js = app.get("/static/review.js").text
    assert missing(js, "htmx:responseError", "textContent") == []
    assert "innerHTML" not in js


@pytest.fixture
def evil(store):
    """A channel whose notes and a YouTube video title carry markup."""
    seed(
        store,
        chan("evil", name="<b>Evil</b>", notes="<script>alert(1)</script>"),
        make_evidence(),
    )
    store.add_vet(
        "evil", make_vet(make_evidence(), title="<script>alert(2)</script>"), "body"
    )
    return "evil"


def test_untrusted_text_is_escaped_on_detail(app, evil):
    html = app.get(detail_url(evil)).text

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html  # notes
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in html  # video title


def test_untrusted_text_is_escaped_in_queue(app, evil):
    html = app.get(QUEUE).text

    assert "<b>Evil</b>" not in html
    assert "&lt;b&gt;Evil&lt;/b&gt;" in html


def test_invalid_video_id_gets_no_link(app, store):
    evidence = make_evidence()
    report = make_vet(evidence)
    report.videos[0].video_id = 'x"><img src=y'
    seed(store, chan("odd"), evidence)
    store.add_vet("odd", report, "body")

    html = app.get(detail_url("odd")).text

    assert "watch?v=x" not in html
    assert "vi/x" not in html


# --- posting reviews ---------------------------------------------------------


def test_plain_post_writes_human_review_and_changes_status(app, store):
    _post(app, notes="Hezké.")

    [path] = [p for p in _review_files(store, "zoo-praha") if "matous" in p.name]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data | {"created_at": None} == {
        "reviewer": "Matouš",
        "role": "human",
        "verdict": "approve",
        "notes": "Hezké.",
        "created_at": None,
    }
    assert store.get("zoo-praha").status == "approved"


def test_plain_post_redirects_to_detail(app):
    response = _post(app)

    assert response.status_code == 303
    assert response.headers["location"] == detail_url("zoo-praha")


def test_post_sets_reviewer_cookie(app):
    cookie = _post(app).headers["set-cookie"]

    assert (
        missing(
            cookie,
            f"{REVIEWER_COOKIE}=Matou%C5%A1",
            "HttpOnly",
            "SameSite=strict",
            "Path=/",
            "Max-Age=31536000",
        )
        == []
    )


def test_htmx_post_returns_reviews_partial_with_oob_status(app):
    response = _post(app, headers=HTMX, notes="Hezké.")

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<section class="card" id="reviews">')
    assert (
        missing(
            response.text,
            "Hezké.",
            'id="status-badge" class="badge status-approved" hx-swap-oob="true"',
            # form cleared except the reviewer
            'name="reviewer" value="Matouš"',
            '<textarea name="notes" rows="3"></textarea>',
        )
        == []
    )
    assert " checked" not in response.text


def test_htmx_post_writes_review(app, store):
    _post(app, headers=HTMX)

    assert len(_review_files(store, "zoo-praha")) == 2
    assert store.get("zoo-praha").status == "approved"


def test_unsure_and_agent_reviews_do_not_change_status(app, store):
    _post(app, verdict="unsure")
    store.add_review("zoo-praha", review("approve", role="agent", hours=5))

    assert len(_review_files(store, "zoo-praha")) == 3
    assert store.get("zoo-praha").status == "candidate"


def test_reject_post_makes_status_rejected(app, store):
    _post(app, verdict="reject")
    assert store.get("zoo-praha").status == "rejected"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"reviewer": "   "}, "Enter your name as reviewer."),
        ({"verdict": "maybe"}, "Choose approve, reject or unsure."),
        ({"verdict": ""}, "Choose approve, reject or unsure."),
    ],
)
@pytest.mark.parametrize("headers", [None, HTMX])
def test_invalid_post_is_422_and_writes_nothing(app, store, fields, message, headers):
    response = _post(app, headers=headers, notes="moje poznámka", **fields)

    assert response.status_code == 422
    assert missing(response.text, message, "moje poznámka") == []  # values kept
    assert len(_review_files(store, "zoo-praha")) == 1
    assert "set-cookie" not in response.headers


def test_post_to_unknown_channel_is_404(app, store):
    assert _post(app, slug="nope").status_code == 404
    assert not (store.root / "nope").exists()


def test_reviewer_empty_without_cookie_or_default(store):
    html = client(store).get(detail_url("zoo-praha")).text
    assert 'name="reviewer" value=""' in html


def test_reviewer_prefilled_from_default(store):
    html = client(store, default_reviewer="babička-helper").get(detail_url("ct-decko"))
    assert 'name="reviewer" value="babička-helper"' in html.text


def test_reviewer_default_beats_cookie(store):
    app = client(store, default_reviewer="babička-helper")
    _post(app, reviewer="QA Tester")  # TestClient keeps the cookie
    html = app.get(detail_url("ct-decko")).text
    assert 'name="reviewer" value="babička-helper"' in html


def test_reviewer_cookie_used_without_default(store):
    app = client(store)
    _post(app, reviewer="Matouš")  # TestClient keeps the cookie
    assert 'name="reviewer" value="Matouš"' in app.get(detail_url("ct-decko")).text


# --- safety --------------------------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost", "[::1]:8765"])
def test_loopback_hosts_allowed(app, host):
    assert app.get(QUEUE, headers={"Host": host}).status_code == 200


@pytest.mark.parametrize(
    "host", ["evil.example", "evil.example:8000", "", "127.0.0.1.evil.example"]
)
def test_other_host_is_400(app, store, host):
    assert app.get(QUEUE, headers={"Host": host}).status_code == 400
    response = _post(app, headers={"Host": host})
    assert response.status_code == 400
    assert len(_review_files(store, "zoo-praha")) == 1


@pytest.mark.parametrize(
    ("bind_host", "header"),
    [
        ("192.168.1.5", "192.168.1.5:8000"),
        ("fe80::1", "[fe80::1]:8000"),
        ("[FE80:0::1]", "[fe80::1]"),
        ("Pi.local", "pi.local:8000"),
    ],
)
def test_non_loopback_bind_host_is_also_allowed(store, bind_host, header):
    app = client(store, bind_host=bind_host)
    assert app.get(QUEUE, headers={"Host": header}).status_code == 200
    assert app.get(QUEUE, headers={"Host": "evil.example"}).status_code == 400


def test_allowed_host_names_without_bind_host_is_loopback_only():
    assert allowed_host_names(None) == {"127.0.0.1", "localhost", "::1"}


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Origin": "http://127.0.0.1:9999"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_cross_site_post_is_403_and_writes_nothing(app, store, headers):
    response = _post(app, headers=headers)
    assert response.status_code == 403
    assert len(_review_files(store, "zoo-praha")) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": BASE_URL},
        {"Sec-Fetch-Site": "same-origin"},
        {"Sec-Fetch-Site": "none"},
        {},
    ],
)
def test_same_origin_post_allowed(app, store, headers):
    assert _post(app, headers=headers).status_code == 303
    assert len(_review_files(store, "zoo-praha")) == 2


def test_static_assets_served(app):
    js = app.get("/static/htmx.min.js")
    assert js.status_code == 200
    assert js.text.startswith("/* htmx 2.")
    assert app.get("/static/review.css").status_code == 200


def test_pages_load_no_external_scripts_or_styles(app):
    html = app.get(detail_url("zoo-praha")).text
    assert 'src="/static/htmx.min.js"' in html
    assert '<script src="http' not in html
    assert '<link rel="stylesheet" href="http' not in html


@pytest.mark.parametrize(
    ("header", "name"),
    [
        ("127.0.0.1:8000", "127.0.0.1"),
        ("[::1]:80", "::1"),
        ("LocalHost", "localhost"),
        ("[FE80:0:0::1]:8000", "fe80::1"),
        ("a:b:c", None),
    ],
)
def test_host_name(header, name):
    assert host_name(header) == name


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("::1", True),
        ("localhost", True),
        ("0.0.0.0", False),  # noqa: S104
        ("example.com", False),
    ],
)
def test_is_loopback(host, loopback):
    assert is_loopback(host) is loopback


@pytest.mark.parametrize(
    ("host", "wildcard"),
    [
        ("0.0.0.0", True),  # noqa: S104
        ("::", True),
        ("[::]", True),
        ("192.168.1.5", False),
        ("localhost", False),
    ],
)
def test_is_wildcard(host, wildcard):
    assert is_wildcard(host) is wildcard
