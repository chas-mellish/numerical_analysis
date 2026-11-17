"""E2E: Chapter 3, Program 1, Simpson's 1/3 rule for Si(B), in a real browser."""

import pytest
from playwright.sync_api import Page

from gerald_na.registry import get_registry

from .conftest import LiveServer
from .program_page import ProgramPage, golden, practice_float, question

pytestmark = pytest.mark.e2e

ENTRY = get_registry().get("ch03_p01")


def test_simpson_smoke(page: Page, live_server: LiveServer) -> None:
    """Card 5.0 100 pre-filled, Python run sums 101 ordinates to Si(5) = 1.5499312."""
    program = ProgramPage(page, ENTRY).open()
    program.expect_book_defaults()
    program.run_book_card("python")
    program.expect_scan(live_server)
    program.expect_sources(
        legacy=["sine integral"],
        fortran_module="module simpson_mod",
        fortran_app="program ch03_p01_simpson",
        python="def simpson(",
    )
    program.expect_study()
    program.answer_practice(question(ENTRY, "book-value-real64"))


@pytest.mark.fortran
def test_simpson_fortran_and_compare(page: Page, live_server: LiveServer) -> None:
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


def test_simpson_custom_function(page: Page) -> None:
    """exp(-x**2) over [0, 2] with 100 panels: Python only, sqrt(pi)/2 erf(2)."""
    program = ProgramPage(page, ENTRY).open()
    program.fill(b="2.0", n="100")
    program.enter_custom_function("exp(-x**2)")
    program.run()
    gauss = question(ENTRY, "gauss-integral")  # the same integrand as preset 2, same card
    program.expect_single_result("python", practice_float(gauss), 1e-12, rows=101)
    assert abs(program.result_value() - 0.8820813907624215) < 1e-8  # sqrt(pi)/2 * erf(2)


def test_simpson_invalid_expression(page: Page) -> None:
    program = ProgramPage(page, ENTRY).open()
    program.enter_custom_function("exp(-x**2")
    program.run()
    program.expect_expression_error("exp(-x**2", 4)
