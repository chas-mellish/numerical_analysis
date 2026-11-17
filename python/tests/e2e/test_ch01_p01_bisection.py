"""E2E: Chapter 1, Program 1, interval halving (bisection), in a real browser."""

import pytest
from playwright.sync_api import Page

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
