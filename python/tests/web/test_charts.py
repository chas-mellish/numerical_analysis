"""Chart builders: every catalog chart kind on synthetic results."""

import json
import math
from dataclasses import dataclass
from typing import Any

import pytest

from gerald_na.registry.models import ChartKind
from gerald_na.web.charts import (
    CHART_BUILDERS,
    ChartInput,
    build_figures,
    factor_roots,
    json_safe,
    polynomial_roots,
)

ALL_KINDS: tuple[str, ...] = ChartKind.__value__.__args__


def traces(figure: dict[str, Any]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = figure["data"]
    return data


def by_name(figure: dict[str, Any], name: str) -> dict[str, Any]:
    return next(trace for trace in traces(figure) if trace.get("name") == name)


def test_every_catalog_kind_has_a_builder() -> None:
    assert set(ALL_KINDS) == set(CHART_BUILDERS)


BISECTION_STEPS = [
    {"k": 1, "x1": 0.0, "x2": 1.0, "x": 0.5, "fx": -0.1},
    {"k": 2, "x1": 0.0, "x2": 0.5, "x": 0.25, "fx": 0.4},
    {"k": 3, "x1": 0.25, "x2": 0.5, "x": 0.375, "fx": 0.0},
]


def test_bracket_with_residual() -> None:
    data = ChartInput(
        kind="bracket",
        options={"lower_key": "x1", "upper_key": "x2", "point_key": "x", "residual_key": "fx"},
        steps=BISECTION_STEPS,
        labels={"x1": "X1", "x2": "X2", "x": "X", "fx": "F(X)"},
    )
    bracket, residual = build_figures(data)
    assert bracket["id"] == "bracket"
    assert residual["id"] == "abs_residual"
    assert by_name(bracket, "X1")["y"] == [0.0, 0.0, 0.25]
    assert by_name(bracket, "X2")["y"] == [1.0, 0.5, 0.5]
    assert by_name(bracket, "midpoint X")["x"] == [1, 2, 3]
    assert residual["layout"]["yaxis"]["type"] == "log"
    assert traces(residual)[0]["y"] == [0.1, 0.4, None]  # |F|, exact zero dropped on log scale


def test_bracket_without_residual_and_without_index() -> None:
    steps = [{"lo": 1.0, "hi": 2.0, "mid": 1.5}, {"lo": 1.0, "hi": 1.5, "mid": 1.25}]
    data = ChartInput(
        kind="bracket",
        options={"lower_key": "lo", "upper_key": "hi", "point_key": "mid"},
        steps=steps,
    )
    (figure,) = build_figures(data)
    assert traces(figure)[0]["x"] == [1.0, 2.0]


def test_abs_residual_linear_scale() -> None:
    data = ChartInput(
        kind="abs_residual",
        options={"residual_key": "fx", "log_residual": False},
        steps=BISECTION_STEPS,
    )
    (figure,) = build_figures(data)
    assert traces(figure)[0]["y"] == [0.1, 0.4, 0.0]
    assert "type" not in figure["layout"]["yaxis"]


BOOK_ROMBERG = [
    [1.6077255],
    [1.6156591, 1.6183036],
    [1.6175654, 1.6182008, 1.6181940],
    [1.6180369, 1.6181940, 1.6181936, 1.6181936],
]


def test_romberg_heatmap_error_colouring() -> None:
    data = ChartInput(
        kind="romberg_heatmap",
        result={"value": 1.6181936, "table": BOOK_ROMBERG},
    )
    (figure,) = build_figures(data)
    heat = traces(figure)[0]
    assert heat["type"] == "heatmap"
    assert len(heat["z"]) == 4
    assert all(len(row) == 4 for row in heat["z"])
    assert heat["z"][0][1] is None  # outside the triangle
    assert heat["z"][3][3] == pytest.approx(-17.0)  # equals the result
    assert heat["z"][0][0] == pytest.approx(math.log10(abs(1.6077255 - 1.6181936)))
    assert heat["text"][1][1] == "1.6183036"
    assert figure["layout"]["yaxis"]["autorange"] == "reversed"


def test_romberg_heatmap_value_colouring_and_missing_table() -> None:
    data = ChartInput(
        kind="romberg_heatmap", options={"color": "value"}, result={"table": BOOK_ROMBERG}
    )
    (figure,) = build_figures(data)
    assert traces(figure)[0]["z"][0][0] == pytest.approx(1.6077255)
    (empty,) = build_figures(ChartInput(kind="romberg_heatmap", result=None))
    assert traces(empty)[0]["z"] == []


def test_integrand_panels_samples_the_function() -> None:
    steps = [
        {"k": k, "x": 0.5 * k, "fx": math.sin(0.5 * k) / (0.5 * k) if k else 1.0, "weight": w}
        for k, w in enumerate([1, 4, 2, 4, 1])
    ]

    def si(x: float) -> float:
        return math.sin(x) / x  # raises at 0: drawn as a gap

    data = ChartInput(kind="integrand_panels", steps=steps, inputs={"b": 2.0, "n": 4}, function=si)
    (figure,) = build_figures(data)
    curve = by_name(figure, "F(x)")
    assert len(curve["x"]) == 400
    assert curve["x"][0] == 0.0
    assert curve["x"][-1] == 2.0
    assert curve["y"][0] is None
    assert curve["y"][-1] == pytest.approx(math.sin(2.0) / 2.0)
    ordinates = by_name(figure, "ordinates fx")
    assert ordinates["x"] == [0.0, 0.5, 1.0, 1.5, 2.0]
    assert ordinates["customdata"] == [1, 4, 2, 4, 1]
    stems = by_name(figure, "panel ordinates")
    assert stems["x"][:3] == [0.0, 0.0, None]


def test_integrand_panels_without_function() -> None:
    data = ChartInput(
        kind="integrand_panels",
        options={"a": -1.0, "upper_input": "upper"},
        steps=[{"x": -1.0, "fx": 1.0}, {"x": 1.0, "fx": 1.0}],
        inputs={"upper": 1.0},
    )
    (figure,) = build_figures(data)
    assert [t["name"] for t in traces(figure)] == ["panel ordinates", "ordinates fx"]
    assert by_name(figure, "ordinates fx")["customdata"] is None


@dataclass(frozen=True)
class Factor:
    kind: str
    r: float | None = None
    s: float | None = None
    a2: float | None = None
    a1: float | None = None
    a0: float | None = None


BAIRSTOW_STEPS = [
    {"factor": 1, "k": 1, "r": 0.0, "s": 0.0, "delr": 1.0, "dels": 1.0},
    {"factor": 1, "k": 2, "r": 4.0, "s": -2.0, "delr": 0.2, "dels": 0.1},
    {"factor": 2, "k": 1, "r": 0.0, "s": 0.0, "delr": 3.3, "dels": -6.2},
]
BAIRSTOW_COEFFS = [0.0, 1.0, -17.8, 99.41, -261.218, 352.611, -134.106]


def test_factors_from_factor_records() -> None:
    factors = [
        Factor("quadratic", r=4.2, s=-2.1),
        {"kind": "quadratic", "r": 3.3, "s": -6.2},
        {"kind": "linear", "a1": 1.0, "a0": -10.3},
    ]
    data = ChartInput(
        kind="factors",
        options={"poly_input": "a"},
        steps=BAIRSTOW_STEPS,
        result={"value": 3, "factors": factors},
        inputs={"a": BAIRSTOW_COEFFS},
        labels={"r": "R", "s": "S"},
    )
    r_fig, s_fig, roots_fig = build_figures(data)
    assert [t["name"] for t in traces(r_fig)] == ["factor 1", "factor 2"]
    assert by_name(r_fig, "factor 1")["y"] == [0.0, 4.0]
    assert by_name(s_fig, "factor 1")["y"] == [0.0, -2.0]
    found = by_name(roots_fig, "roots from the factors")
    reference = by_name(roots_fig, "polynomial roots (reference)")
    assert len(found["x"]) == 5
    assert len(reference["x"]) == 5
    assert sorted(found["x"]) == pytest.approx(sorted(reference["x"]), abs=1e-9)
    assert sum(found["x"]) == pytest.approx(17.8)  # x^2 - r x - s convention
    json.dumps(roots_fig)  # complex parts became plain floats


def test_factors_alternative_shapes() -> None:
    plus = factor_roots([{"r": 2.0, "s": 1.0}], "x^2 + r x + s")
    assert plus == [complex(-1.0, 0.0), complex(-1.0, 0.0)]
    final = factor_roots([{"kind": "final_quadratic", "a2": 1.0, "a1": 0.0, "a0": 1.0}], "")
    assert sorted(z.imag for z in final) == [-1.0, 1.0]
    data = ChartInput(
        kind="factors",
        steps=[],
        result={"roots": [complex(1, 2), [3.0, 0.0], {"re": -1.0, "im": 0.5}, "bad"]},
    )
    roots = build_figures(data)[2]
    assert by_name(roots, "roots from the factors")["y"] == [2.0, 0.0, 0.5]


def test_polynomial_roots() -> None:
    roots = polynomial_roots([1.0, -6.0, 11.0, -6.0])
    assert sorted(z.real for z in roots) == pytest.approx([1.0, 2.0, 3.0])
    assert polynomial_roots([0.0, 5.0]) == []


def test_interpolant() -> None:
    data = ChartInput(
        kind="interpolant",
        steps=[],
        result={"value": 9.0},
        inputs={"n": 3, "points": [[1.0, 1.0], [2.0, 4.0], [4.0, 16.0], [9.0, 0.0]], "xin": 3.0},
    )
    (figure,) = build_figures(data)
    nodes = by_name(figure, "data nodes")
    assert nodes["x"] == [1.0, 2.0, 4.0]  # only the first n points
    curve = by_name(figure, "Lagrange polynomial")
    for x, y in zip(curve["x"], curve["y"], strict=True):
        assert y == pytest.approx(x * x)
    point = by_name(figure, "interpolated value")
    assert point["x"] == [3.0]
    assert point["y"] == [9.0]


def test_interpolant_after_error_has_no_point() -> None:
    data = ChartInput(kind="interpolant", inputs={"points": [[1.0, 2.0], [1.0, 3.0]], "xin": 1.0})
    (figure,) = build_figures(data)
    assert [t["name"] for t in traces(figure)] == ["data nodes"]


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_kind_survives_empty_input_and_is_json(kind: str) -> None:
    figures = build_figures(ChartInput(kind=kind))
    assert figures
    for figure in figures:
        assert set(figure) == {"id", "title", "data", "layout"}
        json.dumps(figure, allow_nan=False)


def test_unknown_kind_and_json_safe() -> None:
    assert build_figures(ChartInput(kind="pie")) == []
    assert json_safe({"a": (math.nan, math.inf, 1.5, 2j, {3})}) == {
        "a": [None, None, 1.5, {"re": 0.0, "im": 2.0}, [3]]
    }
