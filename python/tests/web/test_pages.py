"""HTML pages: home, program page, reset form, tabs, scan-missing state, error pages."""

import asyncio
import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape
from starlette.types import Message, Receive, Scope, Send

from gerald_na.registry import get_registry
from gerald_na.web.middleware import BodySizeLimitMiddleware
from tests.web.conftest import BISECTION

PROGRAM_TESTIDS = [
    "nav-home",
    "program-title",
    "book-ref",
    "program-summary",
    "run-form",
    "input-x1",
    "input-x2",
    "input-tol",
    "field-help-tol",
    "field-bounds-tol",
    "data-card",
    "preset-select",
    "preset-expr",
    "custom-expr",
    "engine-selector",
    "engine-python",
    "engine-fortran",
    "engine-compare",
    "engine-custom-note",
    "run-button",
    "reset-button",
    "run-indicator",
    "results",
    "tab-scan",
    "tab-legacy",
    "tab-fortran",
    "tab-python",
    "tab-study",
    "panel-scan",
    "panel-legacy",
    "panel-fortran",
    "panel-python",
    "panel-study",
    "scan-viewer",
    "scan-download",
    "legacy-source-0",
    "fortran-module-source",
    "fortran-app-source",
    "python-source",
    "study-content",
    "practice-section",
]


def has_testid(html: str, name: str) -> bool:
    return f'data-testid="{name}"' in html


def input_tag(html: str, name: str) -> str:
    match = re.search(rf'<input[^>]*data-testid="{re.escape(name)}"[^>]*>', html, re.S)
    assert match is not None, name
    return match.group(0)


def test_home_lists_programs_by_chapter(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert has_testid(html, "program-list")
    assert has_testid(html, "chapter-1")
    assert "Chapter 1: Solution of Nonlinear Equations" in html
    for entry in get_registry().programs:
        assert has_testid(html, f"program-link-{entry.id}")
        assert f'href="/programs/{entry.id}"' in html
        assert str(escape(entry.title)) in html
    assert "Chapter 1, Program 1, page 24" in html
    assert 'data-testid="scan-status-ch01_p01" data-scan="available"' in html


def test_home_groups_unconfirmed_references(synthetic_client: TestClient) -> None:
    html = synthetic_client.get("/").text
    assert has_testid(html, "chapter-unconfirmed")
    assert "Book reference unconfirmed" in html
    assert has_testid(html, "program-link-synthetic_points")
    assert has_testid(html, "unconfirmed-badge-synthetic_points")
    assert 'data-testid="scan-status-synthetic_points" data-scan="missing"' in html


def test_program_page_has_every_testid(client: TestClient) -> None:
    response = client.get(f"/programs/{BISECTION}")
    assert response.status_code == 200
    html = response.text
    missing = [name for name in PROGRAM_TESTIDS if not has_testid(html, name)]
    assert missing == []
    entry = get_registry().get(BISECTION)
    for question in entry.practice:
        for prefix in ("practice", "practice-answer", "practice-submit", "practice-feedback"):
            assert has_testid(html, f"{prefix}-{question.id}")


def test_program_page_prefills_book_card(client: TestClient) -> None:
    html = client.get(f"/programs/{BISECTION}").text
    assert 'value="0.0"' in input_tag(html, "input-x1")
    assert 'value="1.0"' in input_tag(html, "input-x2")
    assert 'value="1e-05"' in input_tag(html, "input-tol")
    assert "0.        1.        1.E-5" in html  # the data card as printed
    assert "min 1e-12" in html
    assert "max 1.0" in html
    assert re.search(r'<option value="1"[^>]*selected', html)
    assert "EXP(-X) - SIN(3.1415926*X/2.)" in html
    assert "checked" in input_tag(html, "engine-python")
    assert "Interval halving (bisection)" in html
    assert "Chapter 1, Program 1, page 24" in html
    assert not has_testid(html, "book-ref-unconfirmed")


def test_program_page_book_text_and_sources_are_escaped(client: TestClient) -> None:
    html = client.get(f"/programs/{BISECTION}").text
    # Fortran sources contain comparison operators; they must arrive escaped.
    fortran = html.split('data-testid="fortran-module-source"')[1].split("</pre>")[0]
    assert "module bisection_mod" in fortran.lower()
    assert "<=" not in fortran.replace("&lt;=", "")
    assert "def bisection(" in html


def test_fortran_engine_disabled_when_driver_missing(no_binaries_client: TestClient) -> None:
    html = no_binaries_client.get(f"/programs/{BISECTION}").text
    assert "disabled" in input_tag(html, "engine-fortran")
    assert "disabled" in input_tag(html, "engine-compare")
    assert "disabled" not in input_tag(html, "engine-python")
    assert has_testid(html, "engine-note-fortran")
    assert "make build-fortran" in html


def test_fortran_engine_disabled_in_settings(python_only_client: TestClient) -> None:
    html = python_only_client.get(f"/programs/{BISECTION}").text
    assert "disabled" in input_tag(html, "engine-fortran")
    assert "disabled in the settings" in html


def test_reset_form_fragment(client: TestClient) -> None:
    response = client.get(f"/programs/{BISECTION}/form")
    assert response.status_code == 200
    assert response.text.lstrip().startswith("<form")
    assert 'value="1e-05"' in input_tag(response.text, "input-tol")


def test_reset_form_clears_results_out_of_band(client: TestClient) -> None:
    """The reset response also swaps the placeholder into #results (QA: stale results stayed)."""
    html = client.get(f"/programs/{BISECTION}/form").text
    form_end = html.index("</form>")
    oob = re.search(r'<div id="results" hx-swap-oob="innerHTML">(.*?)</div>', html, re.S)
    assert oob is not None
    assert oob.start() > form_end
    assert 'data-testid="results-placeholder"' in oob.group(1)
    assert "aria-invalid" not in html
    assert 'class="invalid"' not in html
    page = client.get(f"/programs/{BISECTION}").text
    assert page.count('data-testid="results-placeholder"') == 1


def test_unknown_program_page_is_404(client: TestClient) -> None:
    response = client.get("/programs/ch99_p99", headers={"accept": "text/html"})
    assert response.status_code == 404
    assert has_testid(response.text, "error-page")
    assert client.get("/programs/ch99_p99/form").status_code == 404
    assert client.post("/programs/ch99_p99/run", data={}).status_code == 404


def test_synthetic_page_shows_scan_missing(synthetic_client: TestClient) -> None:
    response = synthetic_client.get("/programs/synthetic_points")
    assert response.status_code == 200
    html = response.text
    assert has_testid(html, "scan-missing")
    assert "No scan available for this program" in html
    assert not has_testid(html, "scan-viewer")
    assert has_testid(html, "book-ref-unconfirmed")
    # point_list rendered as editable rows prefilled with the data card
    assert has_testid(html, "input-points")
    assert 'value="16.0"' in input_tag(html, "input-points-2-y")
    assert has_testid(html, "add-row-points")
    assert has_testid(html, "remove-row-points-0")
    # no function selector for a data-only program
    assert not has_testid(html, "preset-select")
    # no engine adapter: every engine is explained as unavailable
    assert "no engine adapter yet" in html
    # files that do not exist are reported, not crashing the page
    assert has_testid(html, "fortran-module-source-missing")
    assert has_testid(html, "legacy-source-0")
    assert "&lt;b&gt;raw&lt;/b&gt;" in html


def test_study_page_markdown_is_safe(synthetic_client: TestClient) -> None:
    html = synthetic_client.get("/programs/synthetic_points").text
    study = html.split('data-testid="study-content"')[1].split("</article>")[0]
    assert "<h1>Lagrange</h1>" in study
    assert "<script>" not in study
    assert "&lt;script&gt;" in study
    assert "javascript:" not in study.replace("[x](javascript:alert(1))", "")


def test_study_page_renders_tables(client: TestClient) -> None:
    html = client.get(f"/programs/{BISECTION}").text
    study = html.split('data-testid="study-content"')[1].split("</article>")[0]
    assert "<table>" in study
    assert "<h2>" in study


def test_study_page_drops_generated_block_markers(client: TestClient) -> None:
    html = client.get(f"/programs/{BISECTION}").text
    study = html.split('data-testid="study-content"')[1].split("</article>")[0]
    assert "ERRATA_TABLE" not in study
    assert "<code>zero-product-branch</code>" in study  # generated errata table rendered


def test_render_markdown_keeps_other_comments_escaped() -> None:
    from gerald_na.web.markdown import render_markdown

    html = str(render_markdown("<!-- PROGRAM_INDEX_START -->\ntext <!-- inline -->\n"))
    assert "PROGRAM_INDEX_START" not in html
    assert "&lt;!-- inline --&gt;" in html


def test_security_headers(client: TestClient) -> None:
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in response.headers["content-security-policy"]


def test_static_assets_are_vendored(client: TestClient) -> None:
    html = client.get(f"/programs/{BISECTION}").text
    assert "cdn." not in html
    assert "https://" not in html.split("<body")[0]
    for path in (
        "/static/vendor/htmx.min.js",
        "/static/vendor/plotly-cartesian.min.js",
        "/static/app.js",
        "/static/app.css",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
    assert "htmx" in client.get("/static/vendor/htmx.min.js").text[:200]
    assert "plotly.js" in client.get("/static/vendor/plotly-cartesian.min.js").text[:200]


@pytest.mark.parametrize("size", [70 * 1024])
def test_request_body_limit(client: TestClient, size: int) -> None:
    response = client.post(
        f"/programs/{BISECTION}/run", content=b"a" * size, headers={"content-type": "text/plain"}
    )
    assert response.status_code == 413


def _chunks(total: int, size: int = 8 * 1024) -> Iterator[bytes]:
    sent = 0
    while sent < total:
        yield b"a" * size
        sent += size


def test_request_body_limit_streamed_html(client: TestClient) -> None:
    response = client.post(
        f"/programs/{BISECTION}/run",
        content=_chunks(70 * 1024),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 413


def test_api_request_body_limit_declared(client: TestClient) -> None:
    response = client.post(
        f"/api/programs/{BISECTION}/run",
        content=b"a" * (70 * 1024),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "TOO_LARGE"


def test_api_request_body_limit_streamed(client: TestClient) -> None:
    response = client.post(
        f"/api/programs/{BISECTION}/run",
        content=_chunks(70 * 1024),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "TOO_LARGE"


def test_malformed_content_length_is_rejected() -> None:
    sent: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        raise AssertionError("the app must not run")

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = BodySizeLimitMiddleware(app, max_bytes=10)
    scope: Scope = {"type": "http", "path": "/", "headers": [(b"content-length", b"abc")]}
    asyncio.run(middleware(scope, receive, send))
    assert sent[0]["status"] == 413
