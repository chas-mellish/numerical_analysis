"""E2E: Chapter 3, Program 2, Romberg integration for Si(B), in a real browser."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from gerald_na.registry import get_registry

from .conftest import LiveServer
from .program_page import ProgramPage, golden, practice_float, question

pytestmark = pytest.mark.e2e

ENTRY = get_registry().get("ch03_p02")


def test_romberg_smoke(page: Page, live_server: LiveServer) -> None:
    """Card 15.0 2.E-7 pre-filled, Python run gives Si(15) = 1.6181944 after 3 halvings."""
    program = ProgramPage(page, ENTRY).open()
    program.expect_book_defaults()
    program.run_book_card("python")
    expect(program.tid("chart-romberg_heatmap")).to_be_visible()
    program.expect_scan(live_server)
    program.expect_sources(
        legacy=["ROMBERG INTEGRATION"],
        fortran_module="module romberg_mod",
        fortran_app="program ch03_p02_romberg",
        python="def romberg(",
    )
    program.expect_study()
    program.answer_practice(question(ENTRY, "book-subintervals"))


@pytest.mark.fortran
def test_romberg_fortran_and_compare(page: Page, live_server: LiveServer) -> None:
    """The compiled driver gives the Python value; compare mode reports a bit-for-bit match."""
    for engine in ("fortran", "compare"):
        reason = live_server.engine_reason(ENTRY.id, engine)
        if reason is not None:
            pytest.skip(reason)
    program = ProgramPage(page, ENTRY).open()
    python_value = program.run_book_card("python")
    assert program.run_book_card("fortran") == python_value
    program.select_engine("compare")
    program.run()
    program.expect_compare_match(golden(ENTRY).rows)


@pytest.mark.fortran
def test_romberg_compare_fits_at_1280(
    page: Page, live_server: LiveServer, output_path: str
) -> None:
    """QA: at 1280px the compare tables and book text are not cut off on the right."""
    reason = live_server.engine_reason(ENTRY.id, "compare")
    if reason is not None:
        pytest.skip(reason)
    page.set_viewport_size({"width": 1280, "height": 900})
    program = ProgramPage(page, ENTRY).open()
    program.select_engine("compare")
    program.run()
    program.expect_compare_match(golden(ENTRY).rows)
    program.expect_compare_fully_visible()
    page.screenshot(path=Path(output_path) / "romberg-compare-1280.png", full_page=True)


def test_romberg_out_of_range_then_reset(page: Page) -> None:
    """A TOL above its maximum marks #in-tol invalid; reset restores the card and clears results."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(tol="5")
    program.run()
    program.expect_field_error("tol")
    program.reset()
    program.expect_no_field_errors()
    expect(program.tid("validation-error")).to_have_count(0)


def test_romberg_custom_function(page: Page) -> None:
    """exp(-x**2) over [0, 3] with TOL = 1.E-8: Python only, close to sqrt(pi)/2 erf(3)."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(b="3", tol="1.E-8")
    program.enter_custom_function("exp(-x**2)")
    program.run()
    gauss = question(ENTRY, "gauss-value")  # the same integrand as preset 2, same card
    program.expect_single_result("python", practice_float(gauss), 1e-12, rows=None)
    assert abs(program.result_value() - 0.886207348259521) < 1e-8  # sqrt(pi)/2 * erf(3)


def test_romberg_invalid_expression(page: Page) -> None:
    program = ProgramPage(page, ENTRY).open()
    program.enter_custom_function("sin(x)/x + __import__")
    program.run()
    program.expect_expression_error("sin(x)/x + __import__", 12)
