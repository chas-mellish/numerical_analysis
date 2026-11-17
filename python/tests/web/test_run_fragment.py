"""``POST /programs/{id}/run``: results fragment on every engine, errors and validation."""

import dataclasses
import json
import re

import pytest
from fastapi.testclient import TestClient

from gerald_na.engines import PythonEngine, RunRequest, diff_outcomes
from gerald_na.registry import get_registry
from gerald_na.web.presenters import compare_view
from gerald_na.web.templating import templates
from tests.web.conftest import BISECTION, HX, book_form


def run(client: TestClient, form: dict[str, str]) -> tuple[int, str]:
    response = client.post(f"/programs/{BISECTION}/run", data=form, headers=HX)
    return response.status_code, response.text


def chart_specs(html: str) -> list[dict[str, object]]:
    match = re.search(r'data-testid="result-chart-data">(.*?)</script>', html, re.S)
    assert match is not None
    figures: list[dict[str, object]] = json.loads(match.group(1))
    return figures


def test_python_engine_book_card(client: TestClient) -> None:
    status, html = run(client, book_form("python"))
    assert status == 200
    assert html.count('data-testid="step-row"') == 15
    assert 'data-testid="results-table"' in html
    value = re.search(r'data-testid="result-value">([^<]+)<', html)
    assert value is not None
    assert value.group(1).startswith("0.4435729")
    assert re.search(r'data-testid="result-iterations">15<', html)
    assert re.search(r'data-testid="result-converged">yes<', html)
    assert 'data-testid="book-text"' in html
    assert "THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED." in html
    # catalog column labels and formats
    assert '<th scope="col" data-key="fx">F(X)</th>' in html
    assert ">0.5000000<" in html
    assert ">-0.100576<" in html
    # extras from the result dataclass
    assert 'data-testid="extra-root_at_endpoint"' in html
    # bisection shows the bracket and |f(x)| charts
    assert 'data-testid="result-chart"' in html
    assert [figure["id"] for figure in chart_specs(html)] == ["bracket", "abs_residual"]
    assert not html.lstrip().startswith("<!doctype")


def test_without_htmx_returns_full_page(client: TestClient) -> None:
    response = client.post(f"/programs/{BISECTION}/run", data=book_form("python"))
    assert response.status_code == 200
    assert response.text.lstrip().lower().startswith("<!doctype html>")
    assert response.text.count('data-testid="step-row"') == 15
    assert 'data-testid="run-form"' in response.text


@pytest.mark.fortran
def test_fortran_engine_book_card(client: TestClient) -> None:
    status, html = run(client, book_form("fortran"))
    assert status == 200
    assert html.count('data-testid="step-row"') == 15
    assert re.search(r'data-testid="result-value">0\.4435729', html)
    assert re.search(r'data-testid="result-engine">fortran', html)
    assert "15 ITERATIONS WERE REQUIRED." in html


@pytest.mark.fortran
def test_compare_mode_book_card(client: TestClient) -> None:
    status, html = run(client, book_form("compare"))
    assert status == 200
    for name in ("compare-view", "compare-summary", "compare-python", "compare-fortran"):
        assert f'data-testid="{name}"' in html
    assert html.count('data-testid="step-row"') == 30
    assert 'data-matches="true"' in html
    assert "diff-cell" not in html
    assert 'data-testid="book-text-python"' in html
    assert 'data-testid="book-text-fortran"' in html
    assert "python 15, fortran 15" in html


def test_compare_highlights_differing_cells() -> None:
    entry = get_registry().get(BISECTION)
    request = RunRequest.for_entry(entry)
    left = PythonEngine().run(entry, request)
    steps = list(left.result.steps)
    steps[3] = dataclasses.replace(steps[3], fx=steps[3].fx * (1 + 1e-6))
    right_result = dataclasses.replace(left.result, steps=tuple(steps[:-1]), iterations=14)
    right = dataclasses.replace(left, engine="fortran", result=right_result)
    report = diff_outcomes(entry, left, right)
    html = templates.get_template("partials/results.html").render(
        entry=entry,
        results={"kind": "compare", "mode": "compare", "view": compare_view(entry, report)},
    )
    assert html.count('data-testid="diff-cell"') == 2  # the cell on both sides
    assert 'class="diff-cell"' in html
    assert "abs diff" in html
    assert "rel diff 1.000e-06" in html
    assert 'data-matches="false"' in html
    assert "iteration counts differ" in html
    assert "python has 15 rows, fortran has 14" in html


def test_custom_expression_on_python(client: TestClient) -> None:
    status, html = run(client, book_form("python", function="custom", expression="x**2 - 0.25"))
    assert status == 200
    value = re.search(r'data-testid="result-value">([^<]+)<', html)
    assert value is not None
    assert abs(float(value.group(1)) - 0.5) < 1e-5
    # the chart was drawn with the learner's function
    assert [figure["id"] for figure in chart_specs(html)] == ["bracket", "abs_residual"]


@pytest.mark.parametrize("engine", ["fortran", "compare"])
def test_custom_expression_rejected_on_fortran(client: TestClient, engine: str) -> None:
    status, html = run(client, book_form(engine, function="custom", expression="x - 0.5"))
    assert status == 422
    assert 'data-testid="validation-error"' in html
    assert "CUSTOM_FUNCTION_ENGINE" in html
    assert "Python engine only" in html


def test_custom_expression_selected_but_empty(client: TestClient) -> None:
    status, html = run(client, book_form("python", function="custom", expression="  "))
    assert status == 422
    assert 'data-testid="field-error-expression"' in html


def test_bad_expression_reports_position(client: TestClient) -> None:
    status, html = run(client, book_form("python", function="custom", expression="x + * 2"))
    assert status == 422
    assert "EXPRESSION" in html
    column = re.search(r'data-testid="expr-error-column">(\d+)<', html)
    assert column is not None
    assert int(column.group(1)) >= 1
    assert 'data-testid="expr-error-position"' in html


def test_unsafe_expression_rejected(client: TestClient) -> None:
    status, html = run(
        client, book_form("python", function="custom", expression="__import__('os')")
    )
    assert status == 422
    assert "EXPRESSION" in html
    assert "__import__(&#39;os&#39;)" in html or "__import__(&#x27;os&#x27;)" in html


def test_out_of_range_value(client: TestClient) -> None:
    status, html = run(client, book_form("python", in_tol="5"))
    assert status == 422
    assert 'data-testid="field-error-tol"' in html
    assert "above the maximum" in html


def test_non_numeric_values(client: TestClient) -> None:
    status, html = run(client, book_form("python", in_x1="abc", in_x2="nan"))
    assert status == 422
    assert 'data-testid="field-error-x1"' in html
    assert 'data-testid="field-error-x2"' in html
    assert "is not a number" in html


def test_unknown_engine_and_preset(client: TestClient) -> None:
    status, html = run(client, book_form("bogus"))
    assert status == 422
    assert "unknown engine" in html
    status, html = run(client, book_form("python", function="9"))
    assert status == 422
    assert "unknown preset 9" in html
    status, html = run(client, book_form("python", function="one"))
    assert status == 422
    assert 'data-testid="field-error-function"' in html


def test_book_error_path_is_a_completed_run(client: TestClient) -> None:
    status, html = run(client, book_form("python", in_x1="2.", in_x2="3."))
    assert status == 200
    assert 'data-testid="result-error"' in html
    assert 'data-code="BRACKET"' in html
    assert "NOT OF OPPOSITE SIGNS" in html


def test_non_convergence_shows_partial_steps(client: TestClient) -> None:
    status, html = run(client, book_form("python", in_tol="1e-12"))
    assert status == 200
    assert 'data-code="NON_CONVERGENT"' in html
    assert html.count('data-testid="step-row"') == 25
    assert "NON-CONVERGENT IN 25 ITERATIONS." in html


def test_engine_unavailable_is_503(no_binaries_client: TestClient) -> None:
    for engine in ("fortran", "compare"):
        response = no_binaries_client.post(
            f"/programs/{BISECTION}/run", data=book_form(engine), headers=HX
        )
        assert response.status_code == 503
        assert 'data-testid="engine-unavailable"' in response.text
        assert "ENGINE_UNAVAILABLE" in response.text


def test_point_list_program_runs(synthetic_client: TestClient, synthetic_adapter: object) -> None:
    form = {
        "in_n": "4",
        "in_points.x": ["1", "2", "4", "5"],
        "in_points.y": ["1", "4", "16", "25"],
        "in_xin": "3.",
        "engine": "python",
    }
    response = synthetic_client.post("/programs/synthetic_points/run", data=form, headers=HX)
    assert response.status_code == 200, response.text
    html = response.text
    assert html.count('data-testid="step-row"') == 4
    assert re.search(r'data-testid="result-value">9\.0', html)
    assert 'data-testid="extra-terms"' in html
    figures = chart_specs(html)
    assert [figure["id"] for figure in figures] == ["interpolant"]


def test_point_list_validation(synthetic_client: TestClient, synthetic_adapter: object) -> None:
    form = {
        "in_n": "3",
        "in_points.x": ["1", "2", "x"],
        "in_points.y": ["1", "4", "9"],
        "in_xin": "500",
        "engine": "python",
    }
    response = synthetic_client.post("/programs/synthetic_points/run", data=form, headers=HX)
    assert response.status_code == 422
    assert 'data-testid="field-error-points"' in response.text
    assert "entry 3" in response.text
    assert 'data-testid="field-error-xin"' in response.text


def form_control(html: str, testid: str) -> str:
    pattern = rf'<(?:input|select|fieldset)[^>]*data-testid="{re.escape(testid)}"[^>]*>'
    match = re.search(pattern, html, re.S)
    assert match is not None, testid
    return match.group(0)


def test_field_errors_carry_ids_for_aria_describedby(client: TestClient) -> None:
    """Each field-error message has the id the input's aria-describedby points at (QA finding)."""
    status, html = run(client, book_form("python", in_x2="5000"))
    assert status == 422
    assert '<li id="field-error-x2" data-field-error="x2" data-testid="field-error-x2">' in html


def test_full_page_marks_invalid_inputs(client: TestClient) -> None:
    """Without HTMX the re-rendered form marks the offending input; the others stay clean."""
    response = client.post(f"/programs/{BISECTION}/run", data=book_form("python", in_x2="5000"))
    assert response.status_code == 422
    x2 = form_control(response.text, "input-x2")
    assert 'aria-invalid="true"' in x2
    assert 'class="invalid"' in x2
    assert 'aria-describedby="help-x2 field-error-x2"' in x2
    assert 'id="field-error-x2"' in response.text
    x1 = form_control(response.text, "input-x1")
    assert "aria-invalid" not in x1
    assert 'aria-describedby="help-x1"' in x1


def test_full_page_marks_invalid_expression(client: TestClient) -> None:
    form = book_form("python", function="custom", expression="x**3 - 2*y")
    response = client.post(f"/programs/{BISECTION}/run", data=form)
    assert response.status_code == 422
    custom = form_control(response.text, "custom-expr")
    assert 'aria-invalid="true"' in custom
    assert 'aria-describedby="custom-expr-help field-error-expression"' in custom
    assert 'id="field-error-expression"' in response.text


def test_successful_full_page_run_has_no_invalid_marks(client: TestClient) -> None:
    response = client.post(f"/programs/{BISECTION}/run", data=book_form("python"))
    assert response.status_code == 200
    assert "aria-invalid" not in response.text
    assert 'class="invalid"' not in response.text
    assert 'aria-describedby="help-x2"' in form_control(response.text, "input-x2")


def test_point_list_errors_mark_the_rows(
    synthetic_client: TestClient, synthetic_adapter: object
) -> None:
    """A list input with a field error marks its fieldset and every element input."""
    form = {
        "in_n": "3",
        "in_points.x": ["1", "2", "x"],
        "in_points.y": ["1", "4", "9"],
        "in_xin": "1.5",
        "engine": "python",
    }
    response = synthetic_client.post("/programs/synthetic_points/run", data=form)
    assert response.status_code == 422
    fieldset = form_control(response.text, "input-points")
    assert 'class="list-input invalid"' in fieldset
    assert 'aria-describedby="help-points field-error-points"' in fieldset
    for testid in ("input-points-0-x", "input-points-2-y"):
        row = form_control(response.text, testid)
        assert 'aria-invalid="true"' in row
        assert 'aria-describedby="field-error-points"' in row
    assert "aria-invalid" not in form_control(response.text, "input-xin")


def test_compare_traces_stack_when_narrow(client: TestClient) -> None:
    """The compare columns get a 36rem minimum (stacked at 1280px) and scroll containers."""
    css = client.get("/static/app.css").text
    rule = re.search(r"\.compare-grid \{[^}]*\}", css)
    assert rule is not None
    assert "minmax(min(100%, 36rem), 1fr)" in rule.group(0)
    status, html = run(client, book_form("compare"))
    assert status == 200
    for side in ("python", "fortran"):
        column = html.split(f'data-testid="compare-{side}"', 1)[1]
        assert column.index('class="table-wrap"') < column.index('data-testid="results-table"')
