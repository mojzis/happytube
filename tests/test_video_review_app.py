"""The video spot-check routes (TestClient, no server, no network)."""

import pytest
import yaml
from fastapi.testclient import TestClient

from happytube.channels.store import ChannelStore
from happytube.review.app import create_app
from happytube.trusted.video_reviews import VideoReviewStore
from tests.player_helpers import (
    PLAYER_JSON,
    UNREADABLE,
    assess_fm,
    make_unreadable,
    review_store,
    vid,
    vreview,
    write,
    write_shown,
)
from tests.review_helpers import BASE_URL, QUEUE, missing
from tests.trusted_helpers import add_channel

HTMX = {"HX-Request": "true"}
VIDEOS = "/videos"


def video_url(n: int) -> str:
    return f"{VIDEOS}/{vid(n)}"


def post_url(n: int) -> str:
    return f"{video_url(n)}/reviews"


def form(**over) -> dict:
    return {"reviewer": "mojzis", "verdict": "unsuitable", "watched": "full"} | over


@pytest.fixture
def setup(tmp_path):
    """Video 1 shown, 2 scored unsuitable (enhanced anyway), 3 shown."""
    store = ChannelStore(tmp_path / "channels")
    add_channel(store, "zoo", "UCzoo")
    stages = tmp_path / "stages"
    write_shown(stages, "zoo", 1)
    write(stages, "assess", 2, assess_fm(2, suitable=False, flags=["scary"]))
    write_shown(stages, "zoo", 3)
    reviews = review_store(tmp_path)
    app = create_app(
        store, default_reviewer=None, stages_dir=stages, video_reviews=reviews
    )
    return TestClient(app, base_url=BASE_URL), reviews


def shown(client) -> list[str]:
    return [v["video_id"] for v in client.get(PLAYER_JSON).json()]


def test_queue_sections_and_empty_agreement(setup):
    client, _ = setup
    html = client.get(VIDEOS).text
    assert (
        missing(
            html,
            'Shown in the player, not spot-checked <span class="count">(2)</span>',
            "No human spot-checks yet",
        )
        == []
    )
    assert html.index(vid(3)) < html.index(vid(1)) < html.index(vid(2))


def test_queue_agreement_summary_and_disagree_filter(setup):
    client, reviews = setup
    reviews.add_review(vid(1), vreview("unsuitable", agent=True))
    reviews.add_review(vid(3), vreview("suitable", agent=True))
    html = client.get(VIDEOS).text
    assert "<strong>50%</strong>" in html
    filtered = client.get(VIDEOS, params={"section": "disagree"}).text
    assert (vid(1) in filtered, vid(3) in filtered) == (True, False)


def test_queue_unknown_section_is_400(setup):
    client, _ = setup
    assert client.get(VIDEOS, params={"section": "nope"}).status_code == 400


def test_queue_marks_an_unreadable_review(setup):
    client, reviews = setup
    bad = reviews.root / vid(1) / "20261028T120000Z-x.yaml"
    bad.parent.mkdir()
    bad.write_text("verdict: [", encoding="utf-8")
    response = client.get(VIDEOS)
    assert response.status_code == 200
    assert "unreadable review" in response.text
    assert shown(client) == [vid(3)]


@pytest.mark.parametrize("kind", UNREADABLE)
def test_undecodable_review_hides_and_queue_renders(setup, kind):
    client, reviews = setup
    bad = reviews.root / vid(1) / "20261028T120000Z-x.yaml"
    make_unreadable(bad, kind)
    response = client.get(VIDEOS)
    assert (response.status_code, "unreadable review" in response.text) == (200, True)
    assert client.get(PLAYER_JSON).status_code == 200
    assert shown(client) == [vid(3)]


def test_detail_shows_call_descriptions_embed_and_form(setup):
    client, _ = setup
    html = client.get(video_url(2)).text
    assert (
        missing(
            html,
            "Title 2",
            "not in the player",
            '<span class="flag">scary</span>',
            "Original text 2.",
            "No enhanced description.",
            f"https://www.youtube.com/embed/{vid(2)}",
            f"https://www.youtube.com/watch?v={vid(2)}",
            f'action="/videos/{vid(2)}/reviews"',
            "also hides this video",
            "public",
        )
        == []
    )


@pytest.mark.parametrize("bad", ["..%2Fx", "short", "a" * 12])
def test_invalid_id_is_404(setup, bad):
    client, reviews = setup
    assert client.get(f"{VIDEOS}/{bad}").status_code == 404
    assert client.post(f"{VIDEOS}/{bad}/reviews", data=form()).status_code == 404
    assert list(reviews.root.iterdir()) == []


def test_unknown_or_orphan_id_is_404(setup):
    client, reviews = setup
    reviews.add_review(vid(9), vreview())
    assert client.get(video_url(9)).status_code == 404
    assert client.get(video_url(8)).status_code == 404


def test_post_writes_human_review_with_snapshot_and_hides(setup):
    client, reviews = setup
    data = form(flags=["loud_fast", "promo"], notes="Shouting at 2:10.")
    response = client.post(post_url(1), data=data, follow_redirects=False)
    assert response.status_code == 303
    [path] = (reviews.root / vid(1)).iterdir()
    stored = yaml.safe_load(path.read_text(encoding="utf-8"))
    picked = {k: stored[k] for k in ("role", "verdict", "flags", "agent_suitable")}
    assert picked == {
        "role": "human",
        "verdict": "unsuitable",
        "flags": ["loud_fast", "promo"],
        "agent_suitable": True,
    }
    assert (stored["rubric_version"], stored["assessed_at"]) == (
        1,
        "2026-10-27T12:00:00Z",
    )
    assert shown(client) == [vid(3)]


@pytest.fixture
def incomplete(setup):
    """Video 4 shown, its assess file lacking ``rubric_version``."""
    client, reviews = setup
    fm = assess_fm(4)
    del fm["rubric_version"]
    stages = reviews.root.parent / "stages"
    write(stages, "assess", 4, fm)
    write(stages, "enhance", 4, fm | {"enhanced_description": "Calm."})
    return client, reviews


def test_incomplete_assess_is_marked_in_queue_and_detail(incomplete):
    client, _ = incomplete
    assert vid(4) in shown(client)
    assert "incomplete assess" in client.get(VIDEOS).text
    assert "Incomplete assess" in client.get(video_url(4)).text


def test_shown_video_with_incomplete_assess_can_be_hidden(incomplete):
    client, reviews = incomplete
    response = client.post(post_url(4), data=form(), follow_redirects=False)
    assert response.status_code == 303
    [path] = (reviews.root / vid(4)).iterdir()
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["rubric_version"] is None
    assert vid(4) not in shown(client)


def test_later_human_suitable_shows_it_again(setup):
    client, _ = setup
    client.post(post_url(1), data=form())
    client.post(post_url(1), data=form(verdict="suitable"))
    assert shown(client) == [vid(3), vid(1)]


def test_role_field_cannot_be_forged(setup):
    client, reviews = setup
    client.post(post_url(1), data=form(role="agent"))
    [path] = (reviews.root / vid(1)).iterdir()
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["role"] == "human"


def test_htmx_post_swaps_reviews_and_shown_badge(setup):
    client, _ = setup
    response = client.post(post_url(1), data=form(), headers=HTMX)
    html = response.text
    assert html.lstrip().startswith('<section class="card" id="reviews">')
    snippets = ['id="shown-badge"', 'hx-swap-oob="true"', "not in the player"]
    assert missing(html, *snippets) == []


def test_post_remembers_the_reviewer(setup):
    client, _ = setup
    response = client.post(post_url(1), data=form(), headers=HTMX)
    assert "happytube_reviewer=mojzis" in response.headers["set-cookie"]


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"reviewer": " "}, "Enter your name"),
        ({"verdict": "approve"}, "Choose suitable"),
        ({"watched": "half"}, "how much you watched"),
        ({"flags": ["kittens"]}, "Unknown flag kittens"),
    ],
)
def test_bad_form_is_422_and_writes_nothing(setup, over, message):
    client, reviews = setup
    response = client.post(post_url(1), data=form(**over), headers=HTMX)
    assert response.status_code == 422
    assert message in response.text
    assert not (reviews.root / vid(1)).exists()


def test_cross_site_post_refused(setup):
    client, reviews = setup
    response = client.post(
        post_url(1),
        data=form(),
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403
    assert not (reviews.root / vid(1)).exists()


def test_bad_host_refused(tmp_path):
    app = create_app(
        ChannelStore(tmp_path),
        default_reviewer=None,
        video_reviews=review_store(tmp_path),
    )
    client = TestClient(app, base_url="http://evil.example")
    assert client.get(VIDEOS).status_code == 400


def test_missing_reviews_dir_fails_loudly(tmp_path):
    reviews = VideoReviewStore(tmp_path / "nope")
    app = create_app(
        ChannelStore(tmp_path / "channels"),
        default_reviewer=None,
        video_reviews=reviews,
    )
    response = TestClient(app, base_url=BASE_URL).get(VIDEOS)
    assert response.status_code == 500
    assert "nope" in response.text


def test_nav_links_everywhere(setup):
    client, _ = setup
    for url in (VIDEOS, video_url(1), QUEUE):
        html = client.get(url).text
        assert (
            missing(html, 'href="/channels"', 'href="/videos"', 'href="/player/"') == []
        )
