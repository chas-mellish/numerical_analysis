"""E2E: Lagrangian interpolation (book reference unconfirmed, no scan), in a real browser."""

import pytest
from playwright.sync_api import Page, expect

from gerald_na.algorithms.lagrange import lagrange
from gerald_na.registry import get_registry
from gerald_na.web.forms import default_form_values

from .conftest import LiveServer
from .program_page import ProgramPage, golden, question

pytestmark = pytest.mark.e2e

ENTRY = get_registry().get("lagrange_interpolation")

EXTRA_POINT = ("11.0", "3.1")


def test_lagrange_smoke(page: Page) -> None:
    """Five book pairs pre-filled, Python run at XIN = 5.0 gives 2.3119, no scan, unconfirmed."""
    program = ProgramPage(page, ENTRY).open()
    expect(program.tid("book-ref-unconfirmed")).to_have_text("Book reference unconfirmed")
    program.expect_book_defaults()
    expect(program.tid("add-row-points")).to_be_visible()
    expect(program.tid("preset-select")).to_have_count(0)
    program.run_book_card("python")
    expect(program.tid("chart-interpolant")).to_be_visible()
    program.expect_no_scan()
    program.expect_sources(
        legacy=["LAGRANGIAN INTERPOLATION"],
        fortran_module="module lagrange_mod",
        fortran_app="program lagrange_interpolation",
        python="def lagrange(",
    )
    program.expect_study()
    program.answer_practice(question(ENTRY, "book-value"))


@pytest.mark.fortran
def test_lagrange_fortran_and_compare(page: Page, live_server: LiveServer) -> None:
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


def test_lagrange_add_point_keeps_n_in_sync(page: Page) -> None:
    """Adding a sixth pair moves N to 6 and the run uses 6 terms; removing it moves N back to 5.

    app.js keeps the count field (``data-count-of="points"``) equal to the number of rows; the
    server still rejects an N typed by hand that disagrees with the rows.
    """
    program = ProgramPage(page, ENTRY).open()
    book_points = default_form_values(ENTRY).points["points"]
    rows = program.tid("input-points").locator("[data-row]")
    expect(rows).to_have_count(5)
    expect(program.tid("input-n")).to_have_value("5")
    expect(program.tid("field-sync-note-n")).to_be_visible()

    program.tid("add-row-points").click()
    expect(rows).to_have_count(6)
    expect(program.tid("remove-row-points-5")).to_be_visible()
    expect(program.tid("input-n")).to_have_value("6")
    program.tid("input-points-5-x").fill(EXTRA_POINT[0])
    program.tid("input-points-5-y").fill(EXTRA_POINT[1])

    xs = [float(x) for x, _ in book_points] + [float(EXTRA_POINT[0])]
    ys = [float(y) for _, y in book_points] + [float(EXTRA_POINT[1])]
    reference = lagrange(xs, ys, 5.0).value
    program.run()
    program.expect_single_result("python", reference, 1e-12, rows=6)

    program.tid("remove-row-points-5").click()
    expect(rows).to_have_count(5)
    expect(program.tid("input-n")).to_have_value("5")
    expected = golden(ENTRY)
    program.run()
    expect(program.tid("result-iterations")).to_have_text(str(expected.rows))
    assert abs(program.result_value() - expected.value) <= expected.tolerance

    # server validation stays: an N that disagrees with the rows is a field error on n
    program.fill(n="4")
    program.run()
    expect(program.tid("validation-error")).to_be_visible()
    expect(program.tid("field-error-n")).to_contain_text("N must equal the number of (X, Y) pairs")
