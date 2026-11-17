"""E2E: Chapter 1, Program 2, Bairstow quadratic factors, in a real browser."""

import pytest
from playwright.sync_api import Page, expect

from gerald_na.registry import get_registry

from .conftest import LiveServer
from .program_page import ProgramPage, golden, question

pytestmark = pytest.mark.e2e

ENTRY = get_registry().get("ch01_p02")


def test_bairstow_smoke(page: Page, live_server: LiveServer) -> None:
    """Seven fixed coefficients pre-filled, Python run gives 3 factors in 13 corrections."""
    program = ProgramPage(page, ENTRY).open()
    program.expect_book_defaults()
    # a fixed-length list: no add or remove buttons for the seven coefficients
    expect(program.tid("input-a")).to_have_attribute("data-fixed-length", "7")
    expect(program.tid("add-row-a")).to_have_count(0)
    expect(program.tid("remove-row-a-0")).to_have_count(0)
    program.run_book_card("python")
    program.expect_scan(live_server)
    program.expect_sources(
        legacy=["BAIRSTOW METHOD", "Bairstow's method"],
        fortran_module="module bairstow_mod",
        fortran_app="program ch01_p02_bairstow",
        python="def bairstow(",
    )
    program.expect_study()
    program.answer_practice(question(ENTRY, "book-iterations"))


@pytest.mark.fortran
def test_bairstow_fortran_and_compare(page: Page, live_server: LiveServer) -> None:
    """The compiled driver gives the Python result; compare mode reports a bit-for-bit match."""
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
