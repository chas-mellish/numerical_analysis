"""Form parsing and result presentation helpers."""

from dataclasses import dataclass

import pytest
from starlette.datastructures import ImmutableMultiDict

from gerald_na.registry import Registry, StepColumn, get_registry
from gerald_na.registry.models import parse_data_card_token
from gerald_na.web.forms import (
    default_form_values,
    format_number,
    parse_number,
    parse_run_form,
)
from gerald_na.web.presenters import _extras, format_cell, format_value
from gerald_na.web.services import MAX_LIST_ITEMS, field_problems
from tests.web.conftest import BISECTION


@pytest.mark.parametrize(
    ("text", "integer", "expected"),
    [
        ("0.", False, 0.0),
        (".5", False, 0.5),
        ("1.E-5", False, 1e-5),
        ("1.D-3", False, 1e-3),
        (" -2.5e2 ", False, -250.0),
        ("20", True, 20),
        ("20.", True, 20),
        ("+7", True, 7),
    ],
)
def test_parse_number(text: str, integer: bool, expected: float) -> None:
    value = parse_number(text, integer=integer)
    assert value == expected
    assert type(value) is type(expected)


@pytest.mark.parametrize(
    ("text", "integer"),
    [
        ("", False),
        ("abc", False),
        ("nan", False),
        ("inf", False),
        ("1e", False),
        ("2.5", True),
        ("0x10", True),
        ("1" * 70, False),
    ],
)
def test_parse_number_rejects(text: str, integer: bool) -> None:
    with pytest.raises(ValueError, match=r"required|not a number|not an integer|too long"):
        parse_number(text, integer=integer)


@pytest.mark.parametrize(
    "text", ["0.", ".5", "1.D-3", "-2.5e2", "+7", "1.", "nan", "inf", "1e", "1.2.3", "0x10", "--1"]
)
def test_parse_number_uses_the_data_card_real_syntax(text: str) -> None:
    """The form accepts exactly the reals the CLI's data-card parser accepts."""
    try:
        expected: float | None = float(parse_data_card_token(text, integer=False))
    except ValueError:
        expected = None
    if expected is None:
        with pytest.raises(ValueError, match="not a number"):
            parse_number(text, integer=False)
    else:
        assert parse_number(text, integer=False) == expected


def test_format_number() -> None:
    assert format_number(0.0) == "0.0"
    assert format_number(1e-5) == "1e-05"
    assert format_number(25) == "25"
    assert format_number(-17.8) == "-17.8"


def test_parse_run_form_bisection() -> None:
    entry = get_registry().get(BISECTION)
    form = ImmutableMultiDict(
        [
            ("in_x1", "0."),
            ("in_x2", "1."),
            ("in_tol", "x"),
            ("engine", "compare"),
            ("function", "2"),
        ]
    )
    parsed = parse_run_form(entry, form)
    assert parsed.inputs == {"x1": 0.0, "x2": 1.0}
    assert set(parsed.errors) == {"tol"}
    assert parsed.engine == "compare"
    assert parsed.preset == 2
    assert parsed.expression is None
    assert parsed.values.scalars["tol"] == "x"


def test_parse_run_form_custom_expression() -> None:
    entry = get_registry().get(BISECTION)
    form = ImmutableMultiDict(
        [
            ("in_x1", "0"),
            ("in_x2", "1"),
            ("in_tol", "1e-5"),
            ("function", "custom"),
            ("expression", "x - 0.5"),
        ]
    )
    parsed = parse_run_form(entry, form)
    assert parsed.expression == "x - 0.5"
    assert parsed.preset is None
    assert parsed.engine == "python"


def test_lists_and_points(synthetic_repo: object) -> None:
    from pathlib import Path

    assert isinstance(synthetic_repo, Path)
    entry = Registry.load(synthetic_repo).get("synthetic_points")
    values = default_form_values(entry)
    assert values.points["points"] == [("1.0", "1.0"), ("2.0", "4.0"), ("4.0", "16.0")]
    assert values.function == ""
    form = ImmutableMultiDict(
        [
            ("in_n", "2"),
            ("in_points.x", "1"),
            ("in_points.y", "2"),
            ("in_points.x", "3"),
            ("in_xin", "2"),
        ]
    )
    parsed = parse_run_form(entry, form)
    assert parsed.errors == {"points": "every point needs both an x and a y value"}
    too_many = ImmutableMultiDict(
        [("in_n", "2"), ("in_xin", "1")]
        + [("in_points.x", "1")] * (MAX_LIST_ITEMS + 1)
        + [("in_points.y", "1")] * (MAX_LIST_ITEMS + 1)
    )
    assert "at most" in parse_run_form(entry, too_many).errors["points"]


def test_field_problems() -> None:
    entry = get_registry().get(BISECTION)
    problems = field_problems(entry, {"x1": True, "x2": float("inf"), "tol": 2.0, "zzz": 1})
    assert set(problems) == {"x1", "x2", "tol", "_unknown"}
    assert field_problems(entry, {"x1": 0.0, "x2": 1.0}) == {"tol": "missing value"}
    assert field_problems(entry, entry.defaults()) == {}


def test_format_cell() -> None:
    assert format_cell(3, "I3") == "3"
    assert (
        format_cell(0.44140625, "F10.7") == "0.4414062"
        or format_cell(0.44140625, "F10.7") == "0.4414063"
    )
    assert format_cell(1234.5, "E15.7") == "1.234500E+03"
    assert format_cell(1234.5, "ES25.17").startswith("1.23450000000000000E+03")
    assert format_cell(0.1, "G0") == "0.1"
    assert format_cell(True, "L1") == "T"
    assert format_cell(None, "F10.7") == ""
    assert format_cell(float("nan"), "F10.7") == "nan"
    assert format_value(complex(1.0, -2.0)) == "1.0 - 2.0i"


@dataclass(frozen=True)
class Row:
    kind: str
    r: float


@dataclass(frozen=True)
class FakeResult:
    value: float
    converged: bool
    iterations: int
    steps: tuple[int, ...]
    table: tuple[tuple[float, ...], ...]
    factors: tuple[Row, ...]
    roots: tuple[complex, ...]
    note: str
    empty: tuple[float, ...]


def test_extras_by_shape() -> None:
    result = FakeResult(
        1.0, True, 2, (), ((1.0,), (2.0, 3.0)), (Row("quadratic", 4.2),), (1j,), "hi", ()
    )
    extras = {extra.name: extra for extra in _extras(result)}
    assert set(extras) == {"table", "factors", "roots", "note", "empty"}
    assert extras["table"].kind == "matrix"
    assert extras["table"].matrix == [["1.0"], ["2.0", "3.0"]]
    assert extras["factors"].kind == "records"
    assert extras["factors"].columns == ["kind", "r"]
    assert extras["roots"].kind == "numbers"
    assert extras["roots"].values == ["0.0 + 1.0i"]
    assert extras["note"].text == "hi"
    assert extras["empty"].text == "(none)"


def test_step_column_model_used_by_tables() -> None:
    column = StepColumn(key="x", label="X", format="F10.7")
    assert format_cell(0.5, column.format) == "0.5000000"
