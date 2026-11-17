"""Page helpers shared by the per-program Playwright tests.

Everything is driven through ``data-testid`` attributes (docs/architecture.md, "Program page
testids") and checked with Playwright's retrying locator assertions: the CSP forbids ``eval``, so
string ``wait_for_function`` calls cannot be used. Expected values come from the catalog
(``[[expected]]`` goldens and practice answers), never from the page under test.
"""

import math
import re
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect

from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import PracticeQuestion
from gerald_na.web.forms import default_form_values

from .conftest import LiveServer


@dataclass(frozen=True)
class Golden:
    """The catalog's book-card result: final value, its real64 tolerance and the table rows."""

    value: float
    tolerance: float
    rows: int


def golden(entry: CatalogEntry) -> Golden:
    """Read the result value and the iteration count of the book data card from the catalog."""
    value: float | None = None
    tolerance = 0.0
    rows: int | None = None
    for expected in entry.expected:
        field = expected.field or expected.name
        if field == "value" and value is None:
            if expected.kind == "int":
                assert isinstance(expected.book_value, int)
                value = float(expected.book_value)
            elif expected.real64_value is not None:
                assert isinstance(expected.real64_value, float)
                value = expected.real64_value
                tolerance = expected.tol_real64_value or 0.0
            else:
                assert isinstance(expected.book_value, float)
                assert isinstance(expected.tol_real64, float)
                value, tolerance = expected.book_value, expected.tol_real64
        elif field == "iterations" and expected.kind == "int":
            assert isinstance(expected.book_value, int)
            rows = expected.book_value
    assert value is not None, f"{entry.id}: no [[expected]] result value"
    assert rows is not None, f"{entry.id}: no [[expected]] iteration count"
    return Golden(value, tolerance, rows)


def question(entry: CatalogEntry, question_id: str) -> PracticeQuestion:
    for item in entry.practice:
        if item.id == question_id:
            return item
    raise AssertionError(f"{entry.id}: no practice question {question_id!r}")


def answer_text(item: PracticeQuestion) -> str:
    """The question's reference answer as a learner would type it."""
    answer = item.answer
    assert answer is not None, item.id
    if isinstance(answer, bool):
        return "yes" if answer else "no"
    return repr(answer)


def practice_float(item: PracticeQuestion) -> float:
    assert isinstance(item.answer, (int, float)), item.id
    return float(item.answer)


class ProgramPage:
    """One program page (``/programs/{id}``) in a Playwright ``Page``."""

    def __init__(self, page: Page, entry: CatalogEntry) -> None:
        self.page = page
        self.entry = entry

    def tid(self, testid: str) -> Locator:
        return self.page.get_by_test_id(testid)

    # ------------------------------------------------------------ loading and the form

    def open(self) -> ProgramPage:
        self.page.goto(f"/programs/{self.entry.id}")
        expect(self.tid("program-title")).to_have_text(self.entry.title)
        expect(self.tid("program-id")).to_have_text(self.entry.id)
        expect(self.tid("results-placeholder")).to_be_visible()
        return self

    def expect_book_defaults(self) -> None:
        """Every input is pre-filled with the book data card; the card text is shown too."""
        values = default_form_values(self.entry)
        for name, text in values.scalars.items():
            expect(self.tid(f"input-{name}")).to_have_value(text)
        for name, items in values.lists.items():
            for i, text in enumerate(items):
                expect(self.tid(f"input-{name}-{i}")).to_have_value(text)
            expect(self.tid(f"input-{name}").locator("input")).to_have_count(len(items))
        for name, points in values.points.items():
            for i, (x, y) in enumerate(points):
                expect(self.tid(f"input-{name}-{i}-x")).to_have_value(x)
                expect(self.tid(f"input-{name}-{i}-y")).to_have_value(y)
            expect(self.tid(f"input-{name}").locator("[data-row]")).to_have_count(len(points))
        self.tid("data-card-toggle").click()
        expect(self.tid("data-card")).to_be_visible()
        for line in self.entry.data_card.text.strip().splitlines():
            expect(self.tid("data-card")).to_contain_text(line.strip())
        if self.entry.function.takes_function:
            expect(self.tid("preset-select")).to_have_value(values.function)
            expect(self.tid("engine-custom-note")).to_be_hidden()
        else:
            expect(self.tid("preset-select")).to_have_count(0)
        expect(self.tid("engine-python")).to_be_checked()

    def fill(self, **inputs: str) -> None:
        for name, text in inputs.items():
            self.tid(f"input-{name}").fill(text)

    def select_engine(self, engine: str) -> None:
        self.tid(f"engine-{engine}").check()

    def run(self) -> None:
        """Submit the run form and wait for the HTMX response (the swap is awaited by callers)."""
        with self.page.expect_response(
            lambda response: response.url.endswith(f"/programs/{self.entry.id}/run")
        ):
            self.tid("run-button").click()

    # ------------------------------------------------------------ results

    def result_value(self) -> float:
        return float(self.tid("result-value").inner_text())

    def expect_single_result(
        self, engine: str, value: float, tolerance: float, rows: int | None
    ) -> str:
        """A converged single-engine result on ``engine``; returns the value as displayed."""
        expect(self.tid("result-engine")).to_contain_text(engine)
        expect(self.tid("result-converged")).to_have_text("yes")
        if rows is not None:
            expect(self.tid("result-iterations")).to_have_text(str(rows))
            table_rows = self.tid("results-table").get_by_test_id("step-row")
            expect(table_rows).to_have_count(rows)
        expect(self.tid("result-chart")).to_be_visible()
        expect(self.tid("book-text")).to_be_visible()
        shown = self.tid("result-value").inner_text()
        assert math.isclose(float(shown), value, rel_tol=0.0, abs_tol=tolerance), (
            f"{self.entry.id} {engine}: {shown} != {value} (tol {tolerance})"
        )
        return shown

    def expect_compare_match(self, rows: int) -> None:
        summary = self.tid("compare-summary")
        expect(summary).to_be_visible()
        expect(summary).to_have_attribute("data-matches", "true")
        expect(self.tid("compare-verdict")).to_have_text("The engines agree bit for bit")
        expect(self.tid("compare-iterations")).to_have_attribute("data-same", "true")
        for side in ("python", "fortran"):
            column = self.tid(f"compare-{side}")
            expect(column).to_be_visible()
            expect(column.get_by_test_id("step-row")).to_have_count(rows)
            expect(self.tid(f"book-text-{side}")).to_be_visible()
        expect(self.tid("diff-cell")).to_have_count(0)
        self.expect_compare_fully_visible()

    def expect_compare_fully_visible(self) -> None:
        """Every compare-mode iteration table and book-text block fits its column (QA finding).

        Each scroll container (``.table-wrap``, the ``<pre>``) must not overflow horizontally and
        each side must stay inside the results panel, so no column or line is cut off.
        """
        panel = self.page.locator(".results-panel")
        panel_box = panel.bounding_box()
        assert panel_box is not None
        right = panel_box["x"] + panel_box["width"]
        for side in ("python", "fortran"):
            column = self.tid(f"compare-{side}")
            box = column.bounding_box()
            assert box is not None
            assert box["x"] + box["width"] <= right + 0.5, f"compare-{side} overflows the panel"
            blocks = [column.locator(".table-wrap").first, self.tid(f"book-text-{side}")]
            for block in blocks:
                expect(block).to_be_visible()
                overflow = block.evaluate("el => el.scrollWidth - el.clientWidth")
                assert overflow <= 0, f"{self.entry.id} compare-{side}: clipped by {overflow}px"
            last_header = column.locator("table.steps thead th").last
            header_box = last_header.bounding_box()
            assert header_box is not None
            assert header_box["x"] + header_box["width"] <= box["x"] + box["width"] + 0.5

    def expect_field_error(self, name: str) -> None:
        """The input ``name`` is marked invalid and described by its ``field-error-<name>``."""
        expect(self.tid(f"field-error-{name}")).to_be_visible()
        expect(self.tid(f"field-error-{name}")).to_have_attribute("id", f"field-error-{name}")
        control = self.tid(f"input-{name}")
        expect(control).to_have_attribute("aria-invalid", "true")
        expect(control).to_have_class(re.compile(r"\binvalid\b"))
        described = re.compile(rf"\bfield-error-{name}\b")
        expect(control).to_have_attribute("aria-describedby", described)

    def expect_no_field_errors(self) -> None:
        """No input of the run form is marked invalid or described by a field error."""
        form = self.tid("run-form")
        expect(form.locator("[aria-invalid]")).to_have_count(0)
        expect(form.locator(".invalid")).to_have_count(0)
        expect(form.locator('[aria-describedby*="field-error-"]')).to_have_count(0)

    def reset(self) -> None:
        """Click "Reset to book data card": the form returns to the card and results clear."""
        with self.page.expect_response(
            lambda response: response.url.endswith(f"/programs/{self.entry.id}/form")
        ):
            self.tid("reset-button").click()
        expect(self.tid("results-placeholder")).to_be_visible()
        expect(self.tid("results-body")).to_have_count(0)

    def run_book_card(self, engine: str) -> str:
        """Run the pre-filled book card on ``engine`` and check the golden value and row count."""
        expected = golden(self.entry)
        self.select_engine(engine)
        self.run()
        return self.expect_single_result(engine, expected.value, expected.tolerance, expected.rows)

    # ------------------------------------------------------------ custom functions

    def enter_custom_function(self, expression: str) -> None:
        """Type a learner function: the select switches to custom, Fortran/compare disable."""
        self.tid("custom-expr").fill(expression)
        expect(self.tid("preset-select")).to_have_value("custom")
        expect(self.tid("preset-expr")).to_be_hidden()
        expect(self.tid("engine-custom-note")).to_be_visible()
        expect(self.tid("engine-fortran")).to_be_disabled()
        expect(self.tid("engine-compare")).to_be_disabled()
        expect(self.tid("engine-python")).to_be_enabled()
        expect(self.tid("engine-python")).to_be_checked()

    def expect_expression_error(self, source: str, column: int) -> None:
        error = self.tid("validation-error")
        expect(error).to_be_visible()
        expect(error).to_have_attribute("data-code", "EXPRESSION")
        expect(self.tid("field-error-expression")).to_contain_text(f"column {column}")
        expect(self.tid("expr-error-column")).to_have_text(str(column))
        caret = " " * (column - 1) + "^"
        expect(self.tid("expr-error-position")).to_have_text(f"{source}\n{caret}")

    # ------------------------------------------------------------ tabs

    def show_tab(self, key: str) -> Locator:
        self.tid(f"tab-{key}").click()
        expect(self.tid(f"tab-{key}")).to_have_attribute("aria-selected", "true")
        panel = self.tid(f"panel-{key}")
        expect(panel).to_be_visible()
        return panel

    def expect_scan(self, server: LiveServer) -> None:
        """The scan tab embeds /files/<id>/scan; headless Chromium shows the download fallback."""
        self.show_tab("scan")
        url = f"/files/{self.entry.id}/scan"
        expect(self.tid("scan-viewer")).to_have_attribute("data", url)
        expect(self.tid("scan-viewer")).to_have_attribute("type", "application/pdf")
        expect(self.tid("scan-download")).to_have_attribute("href", url)
        expect(self.tid("scan-download-fallback")).to_have_attribute("href", url)
        expect(self.tid("scan-missing")).to_have_count(0)
        response = self.page.request.get(f"{server.url}{url}")
        assert response.status == 200, response.status
        assert response.headers["content-type"] == "application/pdf"
        assert response.body().startswith(b"%PDF"), "the scan is not a PDF"

    def expect_no_scan(self) -> None:
        self.show_tab("scan")
        expect(self.tid("scan-missing")).to_be_visible()
        expect(self.tid("scan-missing")).to_contain_text("No scan available for this program")
        expect(self.tid("scan-viewer")).to_have_count(0)

    def expect_sources(
        self, legacy: list[str], fortran_module: str, fortran_app: str, python: str
    ) -> None:
        """Each source tab shows its file, containing a characteristic string."""
        panel = self.show_tab("legacy")
        for i, marker in enumerate(legacy):
            expect(panel.get_by_test_id(f"legacy-source-{i}")).to_be_visible()
            expect(panel.get_by_test_id(f"legacy-source-{i}")).to_contain_text(marker)
        expect(panel.get_by_test_id(f"legacy-source-{len(legacy)}")).to_have_count(0)
        expect(self.tid("panel-scan")).to_be_hidden()

        panel = self.show_tab("fortran")
        expect(panel.get_by_test_id("fortran-module-source")).to_contain_text(fortran_module)
        expect(panel.get_by_test_id("fortran-app-source")).to_contain_text(fortran_app)
        expect(self.tid("panel-legacy")).to_be_hidden()

        panel = self.show_tab("python")
        expect(panel.get_by_test_id("python-source")).to_be_visible()
        expect(panel.get_by_test_id("python-source")).to_contain_text(python)

    def expect_study(self) -> None:
        panel = self.show_tab("study")
        expect(panel.get_by_test_id("study-content")).to_be_visible()
        expect(panel.get_by_test_id("study-content").locator("h1")).to_contain_text(
            self.entry.title
        )
        expect(panel.get_by_test_id("study-missing")).to_have_count(0)
        expect(self.tid("panel-python")).to_be_hidden()

    # ------------------------------------------------------------ practice

    def answer_practice(self, item: PracticeQuestion) -> None:
        """Submit the reference answer of ``item`` and expect the "Correct" verdict."""
        expect(self.tid(f"practice-prompt-{item.id}")).to_have_text(item.prompt.strip())
        self.tid(f"practice-answer-{item.id}").fill(answer_text(item))
        self.tid(f"practice-submit-{item.id}").click()
        feedback = self.tid(f"practice-feedback-{item.id}")
        verdict = feedback.get_by_test_id("practice-verdict")
        expect(verdict).to_have_attribute("data-correct", "true")
        expect(verdict).to_contain_text("Correct")
        expect(feedback.get_by_test_id("practice-computed-python")).to_be_visible()
        expect(feedback.get_by_test_id("practice-explanation")).to_be_visible()
