"""E2E: Chapter 1, Program 1, interval halving (bisection), in a real browser."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from gerald_na.registry import get_registry

from .conftest import LiveServer
from .program_page import ProgramPage, golden, practice_float, question

pytestmark = pytest.mark.e2e

ENTRY = get_registry().get("ch01_p01")


def test_bisection_smoke(page: Page, live_server: LiveServer) -> None:
    """Book card pre-filled, Python run gives 15 rows and X = 0.4435730, tabs, study, practice."""
    program = ProgramPage(page, ENTRY).open()
    program.expect_book_defaults()
    program.run_book_card("python")
    program.expect_scan(live_server)
    program.expect_sources(
        legacy=["interval-halving"],
        fortran_module="module bisection_mod",
        fortran_app="program ch01_p01_bisection",
        python="def bisection(",
    )
    program.expect_study()
    program.answer_practice(question(ENTRY, "book-iterations"))


@pytest.mark.fortran
def test_bisection_fortran_and_compare(page: Page, live_server: LiveServer) -> None:
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
def test_bisection_compare_fits_at_1280(
    page: Page, live_server: LiveServer, output_path: str
) -> None:
    """QA: at 1280px the compare tables and book text (F(X), "15 ITERATIONS ...") are not cut."""
    reason = live_server.engine_reason(ENTRY.id, "compare")
    if reason is not None:
        pytest.skip(reason)
    page.set_viewport_size({"width": 1280, "height": 900})
    program = ProgramPage(page, ENTRY).open()
    program.select_engine("compare")
    program.run()
    program.expect_compare_match(golden(ENTRY).rows)
    program.expect_compare_fully_visible()
    expect(program.tid("book-text-fortran")).to_contain_text("15 ITERATIONS WERE REQUIRED.")
    page.screenshot(path=Path(output_path) / "bisection-compare-1280.png", full_page=True)


def test_bisection_out_of_range_marks_input(page: Page) -> None:
    """QA: X2 = 5000 marks #in-x2 invalid (aria-invalid, style, aria-describedby).

    A following successful run clears the marks."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(x2="5000")
    program.run()
    expect(program.tid("validation-error")).to_have_attribute("data-code", "INPUT")
    expect(program.tid("field-error-x2")).to_contain_text("above the maximum")
    program.expect_field_error("x2")
    expect(program.tid("input-x1")).not_to_have_attribute("aria-invalid", "true")
    program.fill(x2="1")
    program.run()
    expect(program.tid("result-value")).to_be_visible()
    program.expect_no_field_errors()
    expect(program.tid("input-x2")).to_have_attribute("aria-describedby", "help-x2")


def test_bisection_expression_error_marks_input(page: Page) -> None:
    program = ProgramPage(page, ENTRY).open()
    program.enter_custom_function("x**3 - 2*y")
    program.run()
    custom = program.tid("custom-expr")
    expect(custom).to_have_attribute("aria-invalid", "true")
    expect(custom).to_have_attribute("aria-describedby", "custom-expr-help field-error-expression")


def test_bisection_reset_clears_results(page: Page) -> None:
    """QA: "Reset to book data card" clears stale errors and results, and the invalid marks."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(x2="5000")
    program.select_engine("python")
    program.run()
    program.expect_field_error("x2")
    program.reset()
    expect(program.tid("validation-error")).to_have_count(0)
    expect(program.tid("input-x2")).to_have_value("1.0")
    program.expect_no_field_errors()
    program.run_book_card("python")
    program.reset()
    expect(program.tid("result-value")).to_have_count(0)
    expect(program.tid("results-table")).to_have_count(0)


def test_bisection_custom_function(page: Page) -> None:
    """x**3 - x - 1 on [1, 2]: Python only, converges to the plastic number."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(x1="1", x2="2")
    program.enter_custom_function("x**3 - x - 1")
    program.run()
    cubic = question(ENTRY, "cubic-root")  # the same function as preset 2, same card
    program.expect_single_result("python", practice_float(cubic), 1e-12, rows=None)
    assert abs(program.result_value() - 1.324717957244746) < 1e-5  # the plastic number


def test_bisection_invalid_expression(page: Page) -> None:
    program = ProgramPage(page, ENTRY).open()
    program.enter_custom_function("x**3 - * x")
    program.run()
    program.expect_expression_error("x**3 - * x", 8)
