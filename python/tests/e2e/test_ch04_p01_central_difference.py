"""E2E: Chapter 4, Program 1, derivatives by central differences, in a real browser."""

import math
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from gerald_na.registry import get_registry

from .conftest import LiveServer
from .program_page import ProgramPage, golden, practice_float, question

pytestmark = pytest.mark.e2e

ENTRY = get_registry().get("ch04_p01")

HEADING = "DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS"
FIRST_ROW = " 1.0E-01      1.0016675E-02      2.0100083E+00"  # also printed by the book
LAST_ROW = " 1.0E-10      1.0000000E-20      2.0000000E+00"  # real64 (the book: 0.0000000E-99)
CHARTS = ("convergence_dx", "convergence_ddx", "convergence_changes")


def _expect_book_card_rows(program: ProgramPage) -> None:
    """Ten rows; the first and last rows and the book text carry the expected digits."""
    rows = program.tid("results-table").get_by_test_id("step-row")
    expect(rows).to_have_count(10)
    first, last = rows.first, rows.last
    expect(first.locator("td[data-key='k']")).to_have_text("1")
    expect(first.locator("td[data-key='h']")).to_have_text("1.0E-01")
    expect(first.locator("td[data-key='dx']")).to_have_text("1.0016675E-02")
    expect(first.locator("td[data-key='ddx']")).to_have_text("2.0100083E+00")
    expect(last.locator("td[data-key='k']")).to_have_text("10")
    expect(last.locator("td[data-key='h']")).to_have_text("1.0E-10")
    expect(last.locator("td[data-key='dx']")).to_have_text("1.0000000E-20")
    expect(last.locator("td[data-key='ddx']")).to_have_text("2.0000000E+00")
    book = program.tid("book-text")
    expect(book).to_contain_text(HEADING)
    expect(book).to_contain_text("AT X =  0.00")
    expect(book).to_contain_text(FIRST_ROW)
    expect(book).to_contain_text(LAST_ROW)


def _expect_charts(program: ProgramPage) -> None:
    """The convergence chart host holds DX, DDX and the row-change figures, drawn by Plotly."""
    expect(program.tid("result-chart")).to_be_visible()
    for figure in CHARTS:
        chart = program.tid(f"chart-{figure}")
        expect(chart).to_be_visible()
        expect(chart.locator("svg.main-svg").first).to_be_visible()


def test_central_difference_smoke(page: Page, live_server: LiveServer) -> None:
    """Card 0.0 0.1 pre-filled; Python run prints 10 rows, DX 1.0016675E-02 .. 1.0E-20."""
    program = ProgramPage(page, ENTRY).open()
    program.expect_book_defaults()
    expect(program.tid("input-x")).to_have_value("0.0")
    expect(program.tid("input-h")).to_have_value("0.1")
    shown = program.run_book_card("python")
    assert float(shown) == golden(ENTRY).value
    _expect_book_card_rows(program)
    _expect_charts(program)
    expect(program.tid("extra-first_dx")).to_contain_text(repr(0.010016675001984412))
    expect(program.tid("extra-first_ddx")).to_contain_text(repr(2.010008336111607))
    program.expect_scan(live_server)
    program.expect_study()
    program.answer_practice(question(ENTRY, "book-first-dx"))
    program.answer_practice(question(ENTRY, "sin-second-derivative"))


def test_central_difference_sources(page: Page, live_server: LiveServer) -> None:
    """The legacy tab links both scanned pages as PDFs (no OCR text); modern sources as text."""
    program = ProgramPage(page, ENTRY).open()
    panel = program.show_tab("legacy")
    urls = [f"/files/{ENTRY.id}/legacy", f"/files/{ENTRY.id}/legacy?index=1"]
    assert len(ENTRY.files.legacy) == len(urls)
    for i, url in enumerate(urls):
        block = panel.get_by_test_id(f"legacy-source-{i}-pdf")
        expect(block).to_be_visible()
        expect(block).to_contain_text("no OCR text")
        expect(block.get_by_role("link", name="Open the PDF")).to_have_attribute("href", url)
        expect(panel.get_by_test_id(f"download-legacy-source-{i}")).to_have_attribute("href", url)
        expect(panel.get_by_test_id(f"legacy-source-{i}")).to_have_count(0)
        expect(panel.get_by_test_id(f"legacy-source-{i}-missing")).to_have_count(0)
        response = page.request.get(f"{live_server.url}{url}")
        assert response.status == 200, (url, response.status)
        assert response.headers["content-type"] == "application/pdf"
        assert response.body().startswith(b"%PDF"), f"{url} is not a PDF"
    expect(panel.get_by_test_id(f"legacy-source-{len(urls)}-pdf")).to_have_count(0)
    expect(panel).to_contain_text(ENTRY.files.legacy[0])

    panel = program.show_tab("fortran")
    expect(panel.get_by_test_id("fortran-module-source")).to_contain_text("module derivative_mod")
    expect(panel.get_by_test_id("fortran-app-source")).to_contain_text(
        "program ch04_p01_central_difference"
    )
    expect(program.tid("panel-legacy")).to_be_hidden()

    panel = program.show_tab("python")
    expect(panel.get_by_test_id("python-source")).to_be_visible()
    expect(panel.get_by_test_id("python-source")).to_contain_text("def central_difference(")


@pytest.mark.fortran
def test_central_difference_fortran_and_compare(page: Page, live_server: LiveServer) -> None:
    """The compiled driver gives the Python rows bit for bit; compare mode reports a match."""
    for engine in ("fortran", "compare"):
        reason = live_server.engine_reason(ENTRY.id, engine)
        if reason is not None:
            pytest.skip(reason)
    program = ProgramPage(page, ENTRY).open()
    python_value = program.run_book_card("python")
    assert program.run_book_card("fortran") == python_value
    _expect_book_card_rows(program)
    _expect_charts(program)
    program.select_engine("compare")
    program.run()
    program.expect_compare_match(golden(ENTRY).rows)
    for side in ("python", "fortran"):
        expect(program.tid(f"book-text-{side}")).to_contain_text(FIRST_ROW)
        expect(program.tid(f"book-text-{side}")).to_contain_text(LAST_ROW)


@pytest.mark.fortran
def test_central_difference_compare_fits_at_1280(
    page: Page, live_server: LiveServer, output_path: str
) -> None:
    """QA: at 1280px the compare tables and the book text are not cut off on the right."""
    reason = live_server.engine_reason(ENTRY.id, "compare")
    if reason is not None:
        pytest.skip(reason)
    page.set_viewport_size({"width": 1280, "height": 900})
    program = ProgramPage(page, ENTRY).open()
    program.select_engine("compare")
    program.run()
    program.expect_compare_match(golden(ENTRY).rows)
    page.screenshot(path=Path(output_path) / "central-difference-compare-1280.png", full_page=True)


def test_central_difference_custom_function(page: Page) -> None:
    """SIN(X) at X = 1: Python only; DX tends to cos(1), first DDX matches the preset-2 question."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(x="1.0", h="0.1")
    program.enter_custom_function("SIN(X)")
    program.run()
    # the last row (H = 1E-10) keeps about 6 digits of cos(1): round-off ~ eps/H
    program.expect_single_result("python", math.cos(1.0), 1e-5, rows=10)
    sine = question(ENTRY, "sin-second-derivative")  # preset 2 on the same card
    expect(program.tid("extra-first_ddx")).to_contain_text(repr(practice_float(sine)))
    first = program.tid("results-table").get_by_test_id("step-row").first
    expect(first.locator("td[data-key='dx']")).to_have_text("5.3940225E-01")  # sin(.1)/.1 cos 1
    expect(program.tid("book-text")).to_contain_text("AT X =  1.00")
    _expect_charts(program)


def test_central_difference_out_of_range_then_reset(page: Page) -> None:
    """H = 0 is below its minimum: #in-h is marked invalid; reset restores the card."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(h="0")
    program.run()
    expect(program.tid("validation-error")).to_have_attribute("data-code", "INPUT")
    program.expect_field_error("h")
    program.reset()
    program.expect_no_field_errors()
    expect(program.tid("input-h")).to_have_value("0.1")


def test_central_difference_invalid_expression(page: Page) -> None:
    program = ProgramPage(page, ENTRY).open()
    program.enter_custom_function("SIN(X")
    program.run()
    program.expect_expression_error("SIN(X", 4)
