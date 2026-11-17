"""Lagrangian interpolation (``lagrange_interpolation``): book card, every error path, properties.

There is no scan of this program; the book's only printed digits are ``2.3119`` at X = 5.0 (see
``catalog/lagrange_interpolation.toml``). SciPy and NumPy are used as independent references
only.
"""

import math
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.interpolate import BarycentricInterpolator
from scipy.interpolate import lagrange as scipy_lagrange

from gerald_na.algorithms import LagrangeResult, LagrangeStep, Rounding, lagrange, lagrange_curve
from gerald_na.algorithms.lagrange import (
    BOOK_MAX_POINTS,
    msg_degree,
    msg_duplicate_x,
    msg_not_finite,
)
from gerald_na.engines import FortranRunner, PythonEngine, RunRequest
from gerald_na.engines.adapters import LagrangeAdapter, get_adapter
from gerald_na.engines.trace import parse_trace
from gerald_na.errors import DegreeError, FortranRunError, InputError
from gerald_na.registry import CatalogEntry, Registry
from gerald_na.registry.models import InputValue
from gerald_na.settings import Settings

BOOK_X = (2.3756, 3.2682, 4.4571, 6.0502, 8.1919)
BOOK_Y = (1.6, 1.9, 2.2, 2.5, 2.8)
BOOK_XIN = 5.0
REAL64_VALUE = 2.3119012901784366

# FORMAT 200 of the corrected listing; the carriage-control blank consumed by the printer.
BOOK_TEXT = """\
USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG   5 VALUES,
AT X =      5.000 THE FUNCTION HAS VALUE OF     2.3119
"""

EPS = 2.0**-52


@pytest.fixture(scope="module")
def entry(repo_root: Path) -> CatalogEntry:
    return Registry.load(repo_root).get("lagrange_interpolation")


# ---------------------------------------------------------------- the book's data card


def test_book_card_value() -> None:
    result = lagrange(BOOK_X, BOOK_Y, BOOK_XIN)
    assert isinstance(result, LagrangeResult)
    assert result.value == REAL64_VALUE
    assert abs(result.value - 2.3119) < 1e-4
    assert result.converged is True
    assert result.iterations == 5
    assert result.n == 5
    assert result.xs == BOOK_X
    assert result.ys == BOOK_Y
    assert result.xin == BOOK_XIN


def test_book_card_text() -> None:
    result = lagrange(BOOK_X, BOOK_Y, BOOK_XIN)
    assert result.book_text() == BOOK_TEXT
    assert result.book_text(carriage_control=True) == "".join(
        " " + line + "\n" for line in BOOK_TEXT.splitlines()
    )
    # Rounding to nearest prints the same digits for the book card.
    assert result.book_text(rounding=Rounding.NEAREST) == BOOK_TEXT


def test_book_card_terms() -> None:
    result = lagrange(BOOK_X, BOOK_Y, BOOK_XIN)
    assert [step.i for step in result.steps] == [1, 2, 3, 4, 5]
    assert [(step.x, step.y) for step in result.steps] == list(zip(BOOK_X, BOOK_Y, strict=True))
    expected_terms = [0.1269898, -0.6242720, 2.2763530, 0.5645053, -0.0316748]
    total = 0.0
    for step, want in zip(result.steps, expected_terms, strict=True):
        assert isinstance(step, LagrangeStep)
        assert step.term == pytest.approx(want, abs=1e-7)
        total += step.term
        assert step.partial == total
    assert result.steps[-1].partial == result.value


def test_pairs_are_x_then_y() -> None:
    """The READ list is X(I), Y(I): only that order gives the book's 2.3119."""
    assert abs(lagrange(BOOK_Y, BOOK_X, BOOK_XIN).value - 2.3119) > 1.0
    assert [round(math.sinh(y), 4) for y in BOOK_Y] == list(BOOK_X)
    assert abs(lagrange(BOOK_X, BOOK_Y, BOOK_XIN).value - math.asinh(5.0)) == pytest.approx(
        5.37e-4, abs=1e-5
    )


def test_book_text_small_and_negative_values() -> None:
    """Book conventions: chopped digits and no leading zero (``.500``, ``-.2500``)."""
    result = lagrange([0.0, 1.0], [0.0, -0.5], 0.5)
    assert result.book_text().splitlines()[1] == (
        "AT X =       .500 THE FUNCTION HAS VALUE OF     -.2500"
    )
    big = lagrange([0.0, 1.0], [0.0, 1.0e7], 1.0)
    assert big.book_text().splitlines()[1].endswith("**********")


# ---------------------------------------------------------------- edge cases and errors


def test_single_point_is_constant() -> None:
    result = lagrange([3.0], [7.0], 100.0)
    assert result.value == 7.0
    assert result.iterations == 1
    assert result.steps == (LagrangeStep(i=1, x=3.0, y=7.0, term=7.0, partial=7.0),)
    assert "AMONG   1 VALUES," in result.book_text()


def test_ten_points_allowed() -> None:
    xs = [float(i) for i in range(1, BOOK_MAX_POINTS + 1)]
    result = lagrange(xs, [2.0 * x + 1.0 for x in xs], 4.5)
    assert result.iterations == BOOK_MAX_POINTS
    assert result.value == pytest.approx(10.0, abs=1e-11)


@pytest.mark.parametrize("n", [0, BOOK_MAX_POINTS + 1])
def test_point_count_outside_dimension_is_degree_error(n: int) -> None:
    xs = [float(i) for i in range(n)]
    with pytest.raises(DegreeError) as info:
        lagrange(xs, xs, 0.5)
    assert info.value.message == msg_degree(n)
    assert info.value.code == "DEGREE"
    assert "," not in info.value.message  # trace messages carry no commas


def test_mismatched_lengths() -> None:
    with pytest.raises(InputError, match="2 X values but 1 Y values"):
        lagrange([1.0, 2.0], [1.0], 1.5)


@pytest.mark.parametrize(
    ("xs", "pair"),
    [
        ([1.0, 2.0, 3.0, 2.0], (2, 4)),
        ([5.0, 5.0], (1, 2)),
        ([0.0, -0.0], (1, 2)),
    ],
)
def test_duplicate_x_is_input_error(xs: list[float], pair: tuple[int, int]) -> None:
    """The original divides by zero at label 9; the port rejects the data up front."""
    with pytest.raises(InputError) as info:
        lagrange(xs, [1.0] * len(xs), 0.0)
    assert info.value.message == msg_duplicate_x(*pair)
    assert info.value.code == "INPUT"
    assert info.value.steps == ()


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_data_is_input_error(bad: float) -> None:
    with pytest.raises(InputError, match="finite"):
        lagrange([1.0, 2.0], [1.0, bad], 1.5)
    with pytest.raises(InputError, match="finite"):
        lagrange([1.0, 2.0], [1.0, 2.0], bad)


def test_overflow_is_input_error_with_completed_rows() -> None:
    big = 1.7976931348623157e308 / 4
    with pytest.raises(InputError) as info:
        lagrange([1.0, 2.0], [1.0, 4.0 * big], 1.5 * big)
    assert info.value.message == msg_not_finite(2)
    assert len(info.value.steps) == 1
    assert info.value.book_output == ""


def test_curve_passes_through_the_nodes() -> None:
    curve = lagrange_curve(BOOK_X, BOOK_Y, samples=11)
    assert len(curve) == 11
    assert curve[0][0] == BOOK_X[0]
    assert curve[0][1] == pytest.approx(BOOK_Y[0], abs=1e-14)
    assert curve[-1][0] == BOOK_X[-1]
    assert curve[-1][1] == pytest.approx(BOOK_Y[-1], abs=1e-14)
    xs = [x for x, _ in curve]
    assert xs == sorted(xs)
    wide = lagrange_curve(BOOK_X, BOOK_Y, samples=3, lo=0.0, hi=10.0)
    assert [x for x, _ in wide] == [0.0, 5.0, 10.0]
    assert wide[1][1] == REAL64_VALUE
    assert lagrange_curve([2.0], [3.0]) == ((2.0, 3.0),)


def test_curve_rejects_bad_arguments() -> None:
    with pytest.raises(InputError):
        lagrange_curve(BOOK_X, BOOK_Y, samples=1)
    with pytest.raises(DegreeError):
        lagrange_curve([], [])


# ---------------------------------------------------------------- properties (Hypothesis)


@st.composite
def well_spaced_nodes(
    draw: st.DrawFn, min_n: int = 1, max_n: int = BOOK_MAX_POINTS, span: float = 4.0
) -> tuple[list[float], list[float]]:
    """Distinct nodes on a jittered grid (spacing >= 0.4 h), in random order, and values."""
    n = draw(st.integers(min_n, max_n))
    lo = draw(st.floats(-50.0, 50.0))
    h = span / max(n - 1, 1)
    jitter = st.floats(-0.3, 0.3)
    xs = [lo + (k + draw(jitter)) * h for k in range(n)]
    xs = draw(st.permutations(xs))
    ys = draw(st.lists(st.floats(-100.0, 100.0), min_size=n, max_size=n))
    return list(xs), ys


@given(well_spaced_nodes())
def test_property_reproduces_every_node(data: tuple[list[float], list[float]]) -> None:
    """P(X(k)) = Y(k): the other terms are exactly zero, L_k(X(k)) = 1 up to rounding."""
    xs, ys = data
    n = len(xs)
    for x, y in zip(xs, ys, strict=True):
        value = lagrange(xs, ys, x).value
        # relative rounding per factor; absolute for subnormal values
        assert abs(value - y) <= 2 * n * (EPS * abs(y) + math.ulp(0.0))


@pytest.mark.filterwarnings("ignore:`lagrange` is deprecated:DeprecationWarning")
@given(well_spaced_nodes(max_n=8), st.floats(0.0, 1.0))
def test_property_matches_scipy(data: tuple[list[float], list[float]], where: float) -> None:
    """Agrees with scipy.interpolate.lagrange (coefficient form) and SciPy's barycentric form."""
    xs, ys = data
    lo, hi = min(xs), max(xs)
    xin = lo + where * (hi - lo)
    # SciPy's monomial coefficients lose digits away from 0: shift the nodes to the origin.
    reference = float(scipy_lagrange(np.array(xs) - lo, np.array(ys))(xin - lo))
    scale = max(1.0, max(abs(y) for y in ys))
    value = lagrange(xs, ys, xin).value
    assert value == pytest.approx(reference, abs=1e-8 * scale)
    if len(xs) > 1:  # SciPy's barycentric form divides by the span of the nodes
        barycentric = float(BarycentricInterpolator(xs, ys)(xin))
        assert value == pytest.approx(barycentric, abs=1e-10 * scale)


@given(
    well_spaced_nodes(min_n=2),
    st.data(),
    st.floats(-0.25, 1.25),
)
def test_property_exact_for_polynomials_of_lower_degree(
    data: tuple[list[float], list[float]], draw: st.DataObject, where: float
) -> None:
    """Through N points of a polynomial of degree < N the interpolant is that polynomial."""
    xs, _ = data
    n = len(xs)
    degree = draw.draw(st.integers(0, n - 1))
    coefficients = draw.draw(
        st.lists(st.floats(-5.0, 5.0), min_size=degree + 1, max_size=degree + 1)
    )
    centre = sum(xs) / n

    def poly(x: float) -> float:
        return float(np.polyval(coefficients, x - centre))

    lo, hi = min(xs), max(xs)
    xin = lo + where * (hi - lo)
    ys = [poly(x) for x in xs]
    scale = max(1.0, *(abs(y) for y in ys), abs(poly(xin)))
    assert lagrange(xs, ys, xin).value == pytest.approx(poly(xin), abs=1e-8 * scale)


@settings(max_examples=50)
@given(well_spaced_nodes(min_n=2), st.floats(0.0, 1.0))
def test_property_order_of_nodes_does_not_matter(
    data: tuple[list[float], list[float]], where: float
) -> None:
    xs, ys = data
    xin = min(xs) + where * (max(xs) - min(xs))
    pairs = sorted(zip(xs, ys, strict=True))
    value = lagrange(xs, ys, xin).value
    sorted_value = lagrange([x for x, _ in pairs], [y for _, y in pairs], xin).value
    scale = max(1.0, max(abs(y) for y in ys))
    assert value == pytest.approx(sorted_value, abs=1e-9 * scale)


# ---------------------------------------------------------------- catalog and engines


def test_catalog_entry_matches_the_book(entry: CatalogEntry) -> None:
    assert entry.book_ref_confirmed is False
    assert entry.book_ref is None
    assert entry.files.scan_pdf is None
    assert entry.function.takes_function is False
    assert entry.data_card.tokens() == [
        "05",
        *[token for x, y in zip(BOOK_X, BOOK_Y, strict=True) for token in (str(x), str(y))],
        "5.0",
    ]
    assert entry.defaults() == {
        "n": 5,
        "points": tuple(zip(BOOK_X, BOOK_Y, strict=True)),
        "xin": 5.0,
    }
    assert entry.input("n").min == 1
    assert entry.input("n").max == BOOK_MAX_POINTS
    expected = {item.name: item for item in entry.expected}
    assert expected["value"].book_value == pytest.approx(2.3119)
    assert expected["value"].real64_value == REAL64_VALUE
    assert expected["n"].book_value == 5
    assert [column.key for column in entry.trace.step_columns] == [
        "i",
        "x",
        "y",
        "term",
        "partial",
    ]
    assert entry.chart.kind == "interpolant"
    assert entry.book_output.strip().splitlines()[-1].endswith("2.3119")


def test_practice_answers_match_the_python_engine(entry: CatalogEntry) -> None:
    for question in entry.practice:
        outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, question.inputs))
        assert outcome.ok, (question.id, outcome.error)
        got = getattr(outcome.result, question.answer_field)
        assert question.answer is not None
        assert abs(got - question.answer) <= question.tolerance, question.id


def test_adapter_card_layout(entry: CatalogEntry) -> None:
    adapter = get_adapter(entry.id)
    assert isinstance(adapter, LagrangeAdapter)
    card = adapter.data_card(entry, entry.defaults())
    assert card == ("05\n2.3756 1.6\n3.2682 1.9\n4.4571 2.2\n6.0502 2.5\n8.1919 2.8\n5.0\n")
    one = adapter.data_card(entry, {"n": 1, "points": ((0.1, -2.0),), "xin": 3})
    assert one == "01\n0.1 -2.0\n3.0\n"


def test_mismatched_n_is_rejected_before_running(entry: CatalogEntry) -> None:
    request = RunRequest.for_entry(entry, {"n": 4})
    with pytest.raises(InputError, match="'n' is 4 but 'points' has 5 pairs"):
        PythonEngine().run(entry, request)
    with pytest.raises(InputError, match="'n' is 4"):
        FortranRunner(Settings()).run(entry, request)


def test_function_and_type_guards(entry: CatalogEntry) -> None:
    adapter = get_adapter(entry.id)
    with pytest.raises(TypeError):
        adapter.run_python(entry, entry.defaults(), math.sin)
    with pytest.raises(TypeError):
        adapter.check_inputs(entry, {**entry.defaults(), "n": 5.0})
    with pytest.raises(TypeError):
        adapter.check_inputs(entry, {**entry.defaults(), "points": (1.0, 2.0)})
    with pytest.raises(TypeError):
        adapter.data_card(entry, {**entry.defaults(), "xin": (1.0,)})
    with pytest.raises(InputError, match="takes data"):
        PythonEngine().run(entry, RunRequest(inputs=entry.defaults(), preset=1))


def test_engine_reports_duplicate_x(entry: CatalogEntry) -> None:
    points = [[1.0, 1.0], [2.0, 2.0], [1.0, 3.0]]
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {"n": 3, "points": points}))
    assert outcome.status == "INPUT"
    assert outcome.error is not None
    assert outcome.error.message == msg_duplicate_x(1, 3)
    assert outcome.book_text == ""


_GOOD_TRACE = (
    "STEP,i=1,x=1.0,y=2.0,term=2.0,partial=2.0\nRESULT,value=2.0,converged=T,iterations=1\n"
)


def test_result_from_trace(entry: CatalogEntry) -> None:
    adapter = get_adapter(entry.id)
    inputs: dict[str, InputValue] = {"n": 1, "points": ((1.0, 2.0),), "xin": 0.0}
    result = adapter.result_from_trace(entry, inputs, parse_trace(_GOOD_TRACE))
    assert result == lagrange([1.0], [2.0], 0.0)


@pytest.mark.parametrize(
    "text",
    [
        "RESULT,value=2.0,converged=T,iterations=1\n",
        "STEP,i=2,x=1.0,y=2.0,term=2.0,partial=2.0\nRESULT,value=2.0,converged=T,iterations=1\n",
        "ERROR,code=INPUT,message=x\n",
    ],
)
def test_inconsistent_trace_is_rejected(entry: CatalogEntry, text: str) -> None:
    adapter = get_adapter(entry.id)
    inputs: dict[str, InputValue] = {"n": 1, "points": ((1.0, 2.0),), "xin": 0.0}
    with pytest.raises(FortranRunError):
        adapter.result_from_trace(entry, inputs, parse_trace(text))


# ---------------------------------------------------------------- the Fortran driver itself


def _drive(path: Path, card: str, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executable from the build directory
        [str(path), *flags], input=card, capture_output=True, text=True, timeout=10, check=False
    )


@pytest.mark.fortran
def test_driver_prints_the_book_text(fortran_executable: Callable[[str], Path]) -> None:
    driver = fortran_executable("lagrange_interpolation")
    card = "05\n2.3756  1.6\n3.2682  1.9\n4.4571  2.2\n6.0502  2.5\n8.1919  2.8\n5.0\n05\n"
    run = _drive(driver, card)
    assert run.returncode == 0, run.stderr
    assert run.stdout == lagrange(BOOK_X, BOOK_Y, BOOK_XIN).book_text(carriage_control=True)
    # any layout: everything on one line, N without the leading zero
    assert _drive(driver, "5 " + " ".join(card.split()[1:-1])).stdout == run.stdout


@pytest.mark.fortran
@pytest.mark.parametrize(
    ("card", "code", "message"),
    [
        ("11\n", "DEGREE", msg_degree(11)),
        ("0\n", "DEGREE", msg_degree(0)),
        ("3\n1 1\n2 2\n1 3\n1.5\n", "INPUT", msg_duplicate_x(1, 3)),
        ("2\n1 1\n2\n", "INPUT", "could not read the data card"),
        ("five\n", "INPUT", "could not read N"),
    ],
)
def test_driver_error_paths(
    fortran_executable: Callable[[str], Path], card: str, code: str, message: str
) -> None:
    driver = fortran_executable("lagrange_interpolation")
    traced = _drive(driver, card, "--trace")
    assert traced.returncode == 2
    assert traced.stdout.startswith(f"ERROR,code={code},message={message}")
    book = _drive(driver, card)
    assert book.returncode == 1
    assert book.stdout == ""
    assert message in book.stderr


@pytest.mark.fortran
def test_driver_flags(fortran_executable: Callable[[str], Path]) -> None:
    driver = fortran_executable("lagrange_interpolation")
    card = "2\n1 1\n3 5\n2\n"
    help_run = _drive(driver, "", "--help")
    assert help_run.returncode == 0
    assert "usage: lagrange_interpolation" in help_run.stdout
    preset = _drive(driver, card, "--preset", "1")
    assert preset.returncode == 1
    assert "no presets" in preset.stderr
    unknown = _drive(driver, card, "--bogus")
    assert unknown.returncode == 1
    verbose = _drive(driver, card, "--verbose")
    assert verbose.returncode == 0
    assert "VERBOSE OUTPUT" in verbose.stdout
    assert "VALUE = 3.00000000000000000E+000" in verbose.stdout
