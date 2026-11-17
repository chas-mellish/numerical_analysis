"""Every catalogued program through the web layer: page, form, engines, charts and practice.

Parametrized over the repository catalog, so a new program is covered as soon as its catalog file
and adapter land. Per program: the page renders with the book data card prefilled and the right
scan state; a Python run of the prefilled form gives the golden value; the Fortran driver (marked
``fortran``) gives the same value; compare mode matches; the chart JSON holds the figures of the
catalog chart kind; every practice question accepts its reference answer. Program-specific
checks follow for Bairstow (real_list, factor roots), Simpson (F(0) seed in the chart), Romberg
(triangular table, heat-map) and Lagrange (point_list, n consistency, unconfirmed reference).
"""

import json
import math
import re
from collections.abc import Mapping
from typing import Any

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from gerald_na.registry import CatalogEntry, get_registry
from gerald_na.web.charts import polynomial_roots
from gerald_na.web.forms import default_form_values, format_number
from tests.web.conftest import HX

ENTRIES = get_registry().programs
IDS = [entry.id for entry in ENTRIES]

CHART_FIGURES: Mapping[str, set[str]] = {
    "bracket": {"bracket"},
    "abs_residual": {"abs_residual"},
    "romberg_heatmap": {"romberg_heatmap"},
    "integrand_panels": {"integrand_panels"},
    "factors": {"factors_r", "factors_s", "factors_roots"},
    "interpolant": {"interpolant"},
}
"""Figures every chart kind must produce for a successful run."""

PRACTICE = [
    pytest.param(entry, question, id=f"{entry.id}-{question.id}")
    for entry in ENTRIES
    for question in entry.practice
    if question.answer is not None
]


@pytest.fixture(params=ENTRIES, ids=IDS)
def entry(request: pytest.FixtureRequest) -> CatalogEntry:
    value = request.param
    assert isinstance(value, CatalogEntry)
    return value


def has_testid(html: str, name: str) -> bool:
    return f'data-testid="{name}"' in html


def input_value(html: str, testid: str) -> str:
    match = re.search(rf'<input[^>]*data-testid="{re.escape(testid)}"[^>]*>', html, re.S)
    assert match is not None, testid
    value = re.search(r'value="([^"]*)"', match.group(0))
    assert value is not None, testid
    return value.group(1)


def book_form(entry: CatalogEntry, engine: str = "python") -> dict[str, Any]:
    """The run form exactly as the page prefills it (book data card, default preset)."""
    values = default_form_values(entry)
    form: dict[str, Any] = {f"in_{name}": text for name, text in values.scalars.items()}
    for name, items in values.lists.items():
        form[f"in_{name}"] = list(items)
    for name, points in values.points.items():
        form[f"in_{name}.x"] = [x for x, _ in points]
        form[f"in_{name}.y"] = [y for _, y in points]
    form["engine"] = engine
    if values.function:
        form["function"] = values.function
    return form


def run_html(client: TestClient, entry: CatalogEntry, form: Mapping[str, Any]) -> str:
    response = client.post(f"/programs/{entry.id}/run", data=dict(form), headers=HX)
    assert response.status_code == 200, response.text
    return response.text


def result_value(html: str) -> str:
    match = re.search(r'data-testid="result-value">([^<]*)<', html)
    assert match is not None, "no result-value in the fragment"
    return match.group(1)


def figures(html: str) -> list[dict[str, Any]]:
    match = re.search(r'data-testid="result-chart-data">(.*?)</script>', html, re.S)
    assert match is not None, "no chart data in the fragment"
    data = json.loads(match.group(1))
    assert isinstance(data, list)
    return data


def figure(html: str, figure_id: str) -> dict[str, Any]:
    by_id = {item["id"]: item for item in figures(html)}
    assert figure_id in by_id, sorted(by_id)
    return by_id[figure_id]


def golden_value(entry: CatalogEntry) -> tuple[float, float]:
    """The catalog's expected ``value`` for the data card and its real64 tolerance."""
    for expected in entry.expected:
        if (expected.field or expected.name) != "value":
            continue
        if expected.kind == "int":
            assert isinstance(expected.book_value, int)
            return float(expected.book_value), 0.0
        if expected.real64_value is not None:
            assert isinstance(expected.real64_value, float)
            return expected.real64_value, expected.tol_real64_value or 0.0
        assert isinstance(expected.book_value, float)
        assert isinstance(expected.tol_real64, float)
        return expected.book_value, expected.tol_real64
    raise AssertionError(f"{entry.id}: no [[expected]] entry for the result value")


# ---------------------------------------------------------------- every program


def test_home_groups_every_program(client: TestClient) -> None:
    html = client.get("/").text
    for entry in ENTRIES:
        assert has_testid(html, f"program-card-{entry.id}")
        if entry.book_ref_confirmed:
            section = f"chapter-{entry.chapter}"
            assert not has_testid(html, f"unconfirmed-badge-{entry.id}")
        else:
            section = "chapter-unconfirmed"
            assert has_testid(html, f"unconfirmed-badge-{entry.id}")
        start = html.index(f'data-testid="{section}"')
        end = html.find("</section>", start)
        assert f'data-testid="program-card-{entry.id}"' in html[start:end], (entry.id, section)
    assert "Book reference unconfirmed" in html
    unconfirmed = html[html.index('data-testid="chapter-unconfirmed"') :]
    assert 'data-testid="program-link-lagrange_interpolation"' in unconfirmed
    assert 'data-testid="scan-status-lagrange_interpolation" data-scan="missing"' in html
    for program_id in ("ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02"):
        assert f'data-testid="scan-status-{program_id}" data-scan="available"' in html


def test_page_renders_with_the_book_card(client: TestClient, entry: CatalogEntry) -> None:
    response = client.get(f"/programs/{entry.id}")
    assert response.status_code == 200
    html = response.text
    assert str(escape(entry.title)) in html
    values = default_form_values(entry)
    for name, text in values.scalars.items():
        assert input_value(html, f"input-{name}") == text
    for name, items in values.lists.items():
        assert has_testid(html, f"input-{name}")
        for i, text in enumerate(items):
            assert input_value(html, f"input-{name}-{i}") == text
        assert not has_testid(html, f"input-{name}-{len(items)}")
    for name, points in values.points.items():
        for i, (x, y) in enumerate(points):
            assert input_value(html, f"input-{name}-{i}-x") == x
            assert input_value(html, f"input-{name}-{i}-y") == y
    assert str(escape(entry.data_card.text.strip())) in html
    assert has_testid(html, "preset-select") == entry.function.takes_function
    if entry.files.scan_pdf is not None:
        assert has_testid(html, "scan-viewer")
        assert not has_testid(html, "scan-missing")
    else:
        assert has_testid(html, "scan-missing")
        assert "No scan available for this program" in html
    if entry.book_ref_confirmed:
        assert not has_testid(html, "book-ref-unconfirmed")
    else:
        assert has_testid(html, "book-ref-unconfirmed")
    for question in entry.practice:
        assert has_testid(html, f"practice-{question.id}")
    for tab in ("scan", "legacy", "fortran", "python", "study"):
        assert has_testid(html, f"tab-{tab}")
    assert has_testid(html, "study-content")


def test_python_run_gives_the_golden_value(client: TestClient, entry: CatalogEntry) -> None:
    html = run_html(client, entry, book_form(entry))
    expected, tolerance = golden_value(entry)
    assert math.isclose(float(result_value(html)), expected, rel_tol=0.0, abs_tol=tolerance)
    assert has_testid(html, "results-table")
    assert has_testid(html, "result-extras")
    assert has_testid(html, "book-text")
    ids = {item["id"] for item in figures(html)}
    assert CHART_FIGURES[entry.chart.kind] <= ids
    for figure_id in ids:
        assert has_testid(html, f"chart-{figure_id}")


@pytest.mark.fortran
def test_fortran_run_gives_the_same_value(client: TestClient, entry: CatalogEntry) -> None:
    python_html = run_html(client, entry, book_form(entry))
    fortran_html = run_html(client, entry, book_form(entry, "fortran"))
    assert "fortran" in re.sub(r"\s+", " ", fortran_html.split('data-testid="result-engine">')[1])
    assert result_value(fortran_html) == result_value(python_html)
    expected, tolerance = golden_value(entry)
    assert math.isclose(float(result_value(fortran_html)), expected, abs_tol=tolerance)
    assert CHART_FIGURES[entry.chart.kind] <= {item["id"] for item in figures(fortran_html)}


@pytest.mark.fortran
def test_compare_matches(client: TestClient, entry: CatalogEntry) -> None:
    html = run_html(client, entry, book_form(entry, "compare"))
    assert 'data-matches="true"' in html
    assert has_testid(html, "compare-python")
    assert has_testid(html, "compare-fortran")
    assert not has_testid(html, "diff-cell")
    assert CHART_FIGURES[entry.chart.kind] <= {item["id"] for item in figures(html)}


def test_api_python_run_is_json_safe(client: TestClient, entry: CatalogEntry) -> None:
    response = client.post(f"/api/programs/{entry.id}/run", json={"engine": "python"})
    assert response.status_code == 200
    json.loads(response.text, parse_constant=lambda name: pytest.fail(f"bare {name} in JSON"))
    data = response.json()
    assert data["ok"] is True
    expected, tolerance = golden_value(entry)
    assert math.isclose(float(data["result"]["value"]), expected, abs_tol=tolerance)


@pytest.mark.fortran
@pytest.mark.parametrize("engine", ["fortran", "compare"])
def test_api_fortran_and_compare(client: TestClient, entry: CatalogEntry, engine: str) -> None:
    response = client.post(f"/api/programs/{entry.id}/run", json={"engine": engine})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ok"] is True
    assert data["mode"] == engine
    if engine == "compare":
        assert data["matches"] is True
    else:
        expected, tolerance = golden_value(entry)
        assert math.isclose(float(data["result"]["value"]), expected, abs_tol=tolerance)


@pytest.mark.parametrize(("entry", "question"), PRACTICE)
def test_practice_accepts_the_reference_answer(
    client: TestClient, entry: CatalogEntry, question: Any
) -> None:
    answer = question.answer
    text = ("true" if answer else "false") if isinstance(answer, bool) else repr(answer)
    response = client.post(
        f"/programs/{entry.id}/practice/{question.id}", data={"answer": text}, headers=HX
    )
    assert response.status_code == 200
    assert 'data-correct="true"' in response.text, response.text
    assert has_testid(response.text, "practice-computed-python")


@pytest.mark.fortran
@pytest.mark.parametrize(("entry", "question"), PRACTICE)
def test_practice_runs_fortran_too(client: TestClient, entry: CatalogEntry, question: Any) -> None:
    answer = question.answer
    text = ("true" if answer else "false") if isinstance(answer, bool) else repr(answer)
    response = client.post(
        f"/programs/{entry.id}/practice/{question.id}", data={"answer": text}, headers=HX
    )
    assert 'data-correct="true"' in response.text
    assert has_testid(response.text, "practice-computed-fortran")


# ---------------------------------------------------------------- Bairstow (real_list, factors)

BAIRSTOW = get_registry().get("ch01_p02")


def roots_of(fig: dict[str, Any], trace: int) -> list[complex]:
    data = fig["data"][trace]
    return [complex(x, y) for x, y in zip(data["x"], data["y"], strict=True)]


def test_bairstow_form_has_seven_fixed_coefficients(client: TestClient) -> None:
    html = client.get("/programs/ch01_p02").text
    assert 'data-fixed-length="7"' in html
    assert not has_testid(html, "add-row-a")
    assert not has_testid(html, "remove-row-a-0")
    form = book_form(BAIRSTOW)
    form["in_a"] = form["in_a"][:6]
    response = client.post("/programs/ch01_p02/run", data=form, headers=HX)
    assert response.status_code == 422
    assert has_testid(response.text, "field-error-a")
    assert "expected 7 items, got 6" in response.text


@pytest.mark.parametrize("engine", ["python", pytest.param("fortran", marks=pytest.mark.fortran)])
def test_bairstow_factor_roots_match_the_polynomial(client: TestClient, engine: str) -> None:
    html = run_html(client, BAIRSTOW, book_form(BAIRSTOW, engine))
    assert result_value(html) == "3"
    assert has_testid(html, "extra-table-factors")
    roots_figure = figure(html, "factors_roots")
    from_factors = roots_of(roots_figure, 0)
    reference = polynomial_roots(list(BAIRSTOW.data_card.values["a"]))  # type: ignore[arg-type]
    assert len(from_factors) == 5
    for root in reference:
        assert min(abs(root - other) for other in from_factors) < 1e-6
    # the true factors X**2 - R X - S: the roots sum to 17.8 (X**4 coefficient of the book)
    assert abs(sum(from_factors) - 17.8) < 1e-6
    assert any(abs(root.imag) > 1.0 for root in from_factors)  # 1.65 +- 1.865i
    delta = figure(html, "factors_delta")
    assert delta["layout"]["yaxis"]["type"] == "log"
    polynomial = figure(html, "factors_polynomial")
    assert sorted(polynomial["data"][1]["x"]) == pytest.approx([0.58013, 3.61987, 10.3], abs=1e-4)


def _cell(html: str, testid: str) -> str:
    match = re.search(
        rf'data-testid="{re.escape(testid)}"><th scope="row">[^<]*</th><td>([^<]*)<', html
    )
    assert match is not None, testid
    return match.group(1)


@pytest.mark.parametrize("engine", ["python", pytest.param("fortran", marks=pytest.mark.fortran)])
def test_bairstow_result_details_name_each_factor_coefficient(
    client: TestClient, engine: str
) -> None:
    html = run_html(client, BAIRSTOW, book_form(BAIRSTOW, engine))
    table = html.split('data-testid="extra-table-factors"')[1].split("</table>")[0]
    assert re.findall(r'data-testid="extra-factors-(\d)" data-kind="([a-z_]+)"', table) == [
        ("0", "quadratic"),
        ("1", "quadratic"),
        ("2", "linear"),
    ]
    assert "1. quadratic <code>X**2 + R X + S</code>" in table
    assert "3. linear <code>A1 X + A0</code>" in table
    expected = {
        "extra-factors-0-r": 4.2,
        "extra-factors-0-s": -2.1,
        "extra-factors-1-r": 3.3,
        "extra-factors-1-s": -6.2,
        "extra-factors-2-a1": 1.0,
        "extra-factors-2-a0": -10.3,
    }
    for testid, value in expected.items():
        assert float(_cell(table, testid)) == pytest.approx(value, abs=1e-6), testid
    assert "coefficients" not in table  # no raw tuple column
    assert not has_testid(table, "extra-factors-2-r")


def test_bairstow_result_details_final_quadratic_names_a2_a1_a0(client: TestClient) -> None:
    form = book_form(BAIRSTOW)
    # (x**2 - 4.2x + 2.1)(x**2 - 3.3x + 6.2): degree 4 ends with a final quadratic
    form["in_a"] = ["0", "0", "1", "-7.5", "22.16", "-32.97", "13.02"]
    form["in_n"] = "4"
    html = run_html(client, BAIRSTOW, form)
    table = html.split('data-testid="extra-table-factors"')[1].split("</table>")[0]
    assert 'data-testid="extra-factors-1" data-kind="final_quadratic"' in table
    assert "2. final quadratic <code>A2 X**2 + A1 X + A0</code>" in table
    assert float(_cell(table, "extra-factors-1-a2")) == pytest.approx(1.0)
    assert float(_cell(table, "extra-factors-1-a1")) == pytest.approx(-3.3, abs=1e-6)
    assert float(_cell(table, "extra-factors-1-a0")) == pytest.approx(6.2, abs=1e-6)


def test_bairstow_api_serializes_factors(client: TestClient) -> None:
    data = client.post("/api/programs/ch01_p02/run", json={"engine": "python"}).json()
    factors = data["result"]["factors"]
    assert [factor["kind"] for factor in factors] == ["quadratic", "quadratic", "linear"]
    assert factors[0]["coefficients"] == pytest.approx([4.2, -2.1])
    assert factors[2]["coefficients"] == pytest.approx([1.0, -10.3])
    assert data["result"]["nudges"] == 0


# ---------------------------------------------------------------- Simpson (F(0) seed)

SIMPSON = get_registry().get("ch03_p01")


@pytest.mark.parametrize(
    ("function", "expression"), [("1", ""), ("custom", "SINF(X)/X"), ("custom", "sin(x)/x")]
)
def test_simpson_chart_uses_the_book_seed_at_zero(
    client: TestClient, function: str, expression: str
) -> None:
    form = {**book_form(SIMPSON), "function": function, "expression": expression}
    html = run_html(client, SIMPSON, form)
    curve = figure(html, "integrand_panels")["data"][0]
    assert curve["x"][0] == 0.0
    assert curve["y"][0] == 1.0
    assert None not in curve["y"]
    assert float(result_value(html)) == pytest.approx(1.5499312397703537, abs=1e-12)


def test_simpson_other_functions_evaluate_f0(client: TestClient) -> None:
    html = run_html(client, SIMPSON, {**book_form(SIMPSON), "function": "2"})
    curve = figure(html, "integrand_panels")["data"][0]
    assert curve["y"][0] == 1.0  # exp(-0**2), evaluated
    html = run_html(
        client, SIMPSON, {**book_form(SIMPSON), "function": "custom", "expression": "1/x"}
    )
    assert has_testid(html, "result-error")  # undefined at 0: an expression error, no crash


def test_simpson_odd_panels_is_a_book_error(client: TestClient) -> None:
    html = run_html(client, SIMPSON, {**book_form(SIMPSON), "in_n": "7"})
    assert 'data-code="ODD_PANELS"' in html


# ---------------------------------------------------------------- Romberg (table, heat-map)

ROMBERG = get_registry().get("ch03_p02")


def test_romberg_triangular_table_and_heatmap(client: TestClient) -> None:
    html = run_html(client, ROMBERG, book_form(ROMBERG))
    match = re.search(r'data-testid="extra-table-table">(.*?)</table>', html, re.S)
    assert match is not None
    rows = re.findall(r"<tr>(.*?)</tr>", match.group(1), re.S)
    assert [row.count("<td>") for row in rows] == [1, 2, 3, 4]
    heatmap = figure(html, "romberg_heatmap")
    z = heatmap["data"][0]["z"]
    assert [sum(cell is not None for cell in row) for row in z] == [1, 2, 3, 4]
    assert heatmap["layout"]["xaxis"]["title"]["text"] == "Extrapolation order"
    assert heatmap["layout"]["yaxis"]["autorange"] == "reversed"
    assert 'data-testid="extra-subintervals"' in html


def test_romberg_not_converged_is_a_result(client: TestClient) -> None:
    form = {**book_form(ROMBERG), "in_b": "100.", "in_tol": "1.E-13", "function": "3"}
    html = run_html(client, ROMBERG, form)
    assert has_testid(html, "result-converged")
    assert ">no<" in html.split('data-testid="result-converged"')[1][:10]
    assert len(figure(html, "romberg_heatmap")["data"][0]["z"]) == 9


# ---------------------------------------------------------------- Lagrange (point_list, n)

LAGRANGE = get_registry().get("lagrange_interpolation")


def test_lagrange_n_must_match_the_points(client: TestClient) -> None:
    form = book_form(LAGRANGE)
    form["in_n"] = "4"
    response = client.post("/programs/lagrange_interpolation/run", data=form, headers=HX)
    assert response.status_code == 422
    assert has_testid(response.text, "field-error-n")
    assert "N must equal the number of (X, Y) pairs" in response.text
    api = client.post(
        "/api/programs/lagrange_interpolation/run", json={"engine": "python", "inputs": {"n": 4}}
    )
    assert api.status_code == 422
    assert set(api.json()["error"]["fields"]) == {"n"}


@pytest.mark.parametrize("engine", ["python", pytest.param("fortran", marks=pytest.mark.fortran)])
def test_lagrange_added_point_with_matching_n(client: TestClient, engine: str) -> None:
    form = book_form(LAGRANGE, engine)
    form["in_points.x"] = [*form["in_points.x"], "10.0179"]
    form["in_points.y"] = [*form["in_points.y"], "3.0"]
    form["in_n"] = "6"
    html = run_html(client, LAGRANGE, form)
    assert result_value(html)
    assert len(re.findall(r'data-testid="step-row"', html)) == 6
    interpolant = figure(html, "interpolant")
    nodes = next(t for t in interpolant["data"] if t["name"] == "data nodes")
    assert len(nodes["x"]) == 6
    point = next(t for t in interpolant["data"] if t["name"] == "interpolated value")
    assert point["x"] == [5.0]
    assert point["y"] == [float(result_value(html))]
    assert interpolant["layout"]["xaxis"]["title"]["text"] == "X"


def test_lagrange_n_is_marked_as_the_count_of_points(client: TestClient) -> None:
    html = client.get("/programs/lagrange_interpolation").text
    match = re.search(r'<input[^>]*data-testid="input-n"[^>]*>', html, re.S)
    assert match is not None
    assert 'data-count-of="points"' in match.group(0)
    assert has_testid(html, "field-sync-note-n")
    reset = client.get("/programs/lagrange_interpolation/form").text  # the HTMX reset fragment
    assert 'data-count-of="points"' in reset
    for other in ("ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02"):
        assert "data-count-of" not in client.get(f"/programs/{other}").text, other


def test_app_js_keeps_count_fields_in_sync(client: TestClient) -> None:
    script = client.get("/static/app.js").text
    assert "function syncCounts(fieldset)" in script
    assert "[data-count-of]" in script
    assert script.count("syncCounts(fieldset);") == 2  # after adding and after removing a row


def test_lagrange_page_states(client: TestClient) -> None:
    html = client.get("/programs/lagrange_interpolation").text
    assert has_testid(html, "scan-missing")
    assert has_testid(html, "book-ref-unconfirmed")
    assert has_testid(html, "add-row-points")
    assert input_value(html, "input-n") == format_number(5)
    assert not has_testid(html, "preset-select")
