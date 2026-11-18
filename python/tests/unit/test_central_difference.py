"""Chapter 4, Program 1 (central differences): book data card, every branch, properties.

The analytic derivatives are the references: at X = 0 the book's F(X) = X**2*EXP(X) gives
DX = H*SINH(H) and DDX = 2*COSH(H) exactly, quadratics are differentiated exactly up to
round-off, and for smooth functions the error falls like H**2.
"""

import itertools
import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from gerald_na.algorithms import (
    CentralDifferenceResult,
    CentralDifferenceStep,
    Rounding,
    central_difference,
)
from gerald_na.algorithms.central_difference import BOOK_ROWS, H_FACTOR, HEADING, book_e
from gerald_na.engines import PythonEngine, RunRequest
from gerald_na.engines.adapters import get_adapter
from gerald_na.engines.adapters._common import trace_real
from gerald_na.engines.adapters.central_difference import CentralDifferenceAdapter
from gerald_na.engines.trace import parse_trace
from gerald_na.errors import ExpressionError, FortranRunError, InputError
from gerald_na.expr import compile_expr
from gerald_na.registry import CatalogEntry, get_registry
from gerald_na.tools.book_machine import ChoppedMachine, central_difference_rows

EPS = 2.0**-52


def book_f(x: float) -> float:
    """The statement function F(X) = X**2*EXPF(X) (X**2 is a multiplication, as in Fortran)."""
    return x * x * math.exp(x)


BOOK_TEXT = """\
DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS
AT X =  0.00

   H             DX                 DDX

 1.0E-01      1.0016675E-02      2.0100083E+00
 1.0E-02      1.0000166E-04      2.0001000E+00
 1.0E-03      1.0000001E-06      2.0000010E+00
 1.0E-04      1.0000000E-08      2.0000000E+00
 1.0E-05      1.0000000E-10      2.0000000E+00
 1.0E-06      9.9999999E-13      2.0000000E+00
 1.0E-07      9.9999999E-15      2.0000000E+00
 1.0E-08      9.9999999E-17      2.0000000E+00
 1.0E-09      1.0000000E-18      2.0000000E+00
 1.0E-10      1.0000000E-20      2.0000000E+00
"""
"""The real64 book text of the data card (the scan's layout; DX/DDX digits of real64)."""


@pytest.fixture(scope="module")
def entry() -> CatalogEntry:
    return get_registry().get("ch04_p01")


@pytest.fixture(scope="module")
def book() -> CentralDifferenceResult:
    return central_difference(book_f, 0.0, 0.1)


# ---------------------------------------------------------------- the book data card


def test_book_card_rows_equal_the_catalog_real64_values(
    entry: CatalogEntry, book: CentralDifferenceResult
) -> None:
    expected = next(item for item in entry.expected if item.name == "steps")
    assert isinstance(expected.real64_value, tuple)
    rows = [(step.k, step.h, step.dx, step.ddx) for step in book.steps]
    assert rows == [tuple(row) for row in expected.real64_value]


def test_book_card_result_fields(book: CentralDifferenceResult) -> None:
    assert book.converged
    assert book.iterations == BOOK_ROWS == len(book.steps) == 10
    assert (book.x, book.h, book.fo) == (0.0, 0.1, 0.0)
    assert book.value == book.steps[-1].dx == 1.0000000031710762e-20
    assert book.first_dx == book.steps[0].dx == 0.010016675001984412
    assert book.first_ddx == book.steps[0].ddx == 2.010008336111607
    assert book.last_ddx == book.steps[-1].ddx == 2.0


def test_book_card_matches_the_analytic_differences(book: CentralDifferenceResult) -> None:
    """At X = 0: DX = H*SINH(H) and DDX = 2*COSH(H) for F = X**2*EXP(X)."""
    for step in book.steps:
        assert step.dx == pytest.approx(step.h * math.sinh(step.h), rel=1e-6)
        assert step.ddx == pytest.approx(2.0 * math.cosh(step.h), rel=1e-12)


def test_h_is_accumulated(book: CentralDifferenceResult) -> None:
    """``10 H = 0.1*H``: each H is 0.1 times the previous one, not 0.1**(k-1)*H0."""
    h = 0.1
    for step in book.steps:
        assert step.h == h
        h = H_FACTOR * h
    assert book.steps[-1].h == 1.0000000000000006e-10 != 0.1 * 10.0**-9


def test_book_text(book: CentralDifferenceResult) -> None:
    assert book.book_text() == BOOK_TEXT
    raw = book.book_text(carriage_control=True)
    lines = raw.splitlines()
    assert lines[0] == HEADING
    assert lines[2] == lines[4] == ""  # the // and the closing /) end empty records
    assert lines[3] == "    H             DX                 DDX"
    assert lines[5] == "  1.0E-01      1.0016675E-02      2.0100083E+00"
    assert [line[1:] for line in lines] == BOOK_TEXT.splitlines()
    assert len(lines) == 5 + BOOK_ROWS


def test_book_text_layout_matches_the_scan(
    entry: CatalogEntry, book: CentralDifferenceResult
) -> None:
    """Same lines and columns as the scan; only the round-off digits of DX and DDX differ."""
    printed = entry.book_output.strip("\n").splitlines()
    ours = book.book_text().splitlines()
    assert len(printed) == len(ours)
    assert ours[:6] == printed[:6]  # heading, X, column headings and the first row
    for got, want in zip(ours, printed, strict=True):
        assert len(got) == len(want)
        assert got[:8] == want[:8]  # the H column
    assert "0.0000000E-99" in entry.book_output


def test_book_text_with_another_rounding(book: CentralDifferenceResult) -> None:
    nearest = book.book_text(rounding=Rounding.NEAREST).splitlines()
    assert nearest[6] == " 1.0E-02      1.0000167E-04      2.0001000E+00"
    assert nearest[10] == " 1.0E-06      1.0000000E-12      2.0000000E+00"


def test_book_e_field() -> None:
    assert book_e(0.0, 14, 7) == " 0.0000000E-99"
    assert book_e(-0.0, 14, 7) == "-0.0000000E-99"
    assert book_e(0.0, 8, 1) == " 0.0E-99"
    assert book_e(-0.010016675001984412, 14, 7) == "-1.0016675E-02"
    assert book_e(-1.0016675e-2, 14, 7) == "-1.0016674E-02"  # the binary value is just below
    assert book_e(2.0, 14, 7) == " 2.0000000E+00"
    assert book_e(1.99999999999, 14, 7) == " 1.9999999E+00"  # chopped
    assert book_e(1.99999999999, 14, 7, rounding=Rounding.NEAREST) == " 2.0000000E+00"
    assert book_e(1.5e-120, 14, 7) == " 1.5000000-120"
    assert book_e(math.inf, 14, 7) == "      Infinity"


@pytest.mark.parametrize(
    ("x", "h", "at_x", "h_column"),
    [
        (0.29, 0.1, " AT X =  0.29", " 1.0E-01"),  # 0.28999999999999998 chopped would be 0.28
        (-0.5, 1.0e-6, " AT X = -0.50", " 1.0E-06"),  # 9.9999999999999995e-07 chopped: 9.9E-07
        (10.5, 10.0, " AT X = 10.50", " 1.0E+01"),
        (100.0, 0.1, " AT X = *****", " 1.0E-01"),  # F5.2 overflows, as on any processor
    ],
)
def test_x_and_h_are_echoed_rounded_to_nearest(
    x: float, h: float, at_x: str, h_column: str
) -> None:
    lines = central_difference(math.sin, x, h).book_text(carriage_control=True).splitlines()
    assert lines[1] == at_x
    assert lines[5][:9] == " " + h_column


def test_exact_zero_rows_print_the_book_exponent() -> None:
    """X + H == X for tiny H: FR = FL = FO, so DX = DDX = 0 prints as 0.0000000E-99."""
    result = central_difference(book_f, 100.0, 1.0e-6)
    last = result.steps[-1]
    assert (last.dx, last.ddx) == (0.0, 0.0)
    assert result.book_text().splitlines()[-1] == " 1.0E-15      0.0000000E-99      0.0000000E-99"


# ---------------------------------------------------------------- error paths


@pytest.mark.parametrize(
    ("x", "h", "n_steps"),
    [
        (0.0, 0.0, 10),
        (0.0, -0.1, 10),
        (0.0, math.nan, 10),
        (0.0, math.inf, 10),
        (math.inf, 0.1, 10),
        (math.nan, 0.1, 10),
        (0.0, 0.1, 0),
        (0.0, 0.1, True),
        (0.0, 0.1, 2.0),
    ],
)
def test_bad_inputs_are_input_errors(x: float, h: float, n_steps: int) -> None:
    with pytest.raises(InputError) as info:
        central_difference(book_f, x, h, n_steps)
    assert info.value.steps == ()
    assert info.value.book_output is None  # rejected before the heading is printed


def test_non_finite_f_of_x_keeps_the_heading() -> None:
    with pytest.raises(InputError, match=r"F\(X\) is not a finite number") as info:
        central_difference(lambda t: math.nan if t == 0.5 else t, 0.5, 0.1)
    assert info.value.steps == ()
    assert info.value.book_output == (
        "DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS\nAT X =  0.50\n\n"
        "   H             DX                 DDX\n\n"
    )


def test_non_finite_f_mid_run_keeps_the_rows() -> None:
    """F(X+H) overflows on row 3: rows 1 and 2 are kept, in the result and in the book text."""

    def f(t: float) -> float:
        return math.inf if t > 0.0 and t < 0.002 else t * t

    with pytest.raises(InputError, match=r"F\(X\+H\)") as info:
        central_difference(f, 0.0, 0.1)
    steps = info.value.steps
    assert [s.k for s in steps if isinstance(s, CentralDifferenceStep)] == [1, 2]
    assert info.value.book_output is not None
    assert info.value.book_output.splitlines()[-1].startswith(" 1.0E-02")


def test_non_finite_f_left_point() -> None:
    with pytest.raises(InputError, match=r"F\(X-H\)") as info:
        central_difference(lambda t: math.nan if t < 0.0 else t, 0.0, 0.1)
    assert info.value.steps == ()


def test_overflowing_differences_are_input_errors() -> None:
    """Finite F values whose difference overflows (DX), and an H*H that underflows (DDX)."""
    with pytest.raises(InputError, match="DX or DDX"):
        central_difference(lambda t: 1.0e308 if t > 0 else -1.0e308, 0.0, 1.0)
    with pytest.raises(InputError, match="DX or DDX") as info:
        central_difference(math.sin, 1.0, 1.0e-170)
    assert info.value.steps == ()


def test_expression_errors_keep_their_class() -> None:
    """A learner function outside its domain (LOG10 of X - H <= 0) is an ExpressionError."""
    with pytest.raises(ExpressionError) as info:
        central_difference(compile_expr("1 + LOG10(X)"), 0.05, 0.1)
    assert info.value.steps == ()
    assert info.value.book_output is not None
    assert info.value.book_output.startswith("DERIVATIVES COMPUTED")


# ---------------------------------------------------------------- properties


finite = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
steps_h = st.floats(min_value=1.0e-2, max_value=5.0, allow_nan=False, allow_infinity=False)


@settings(max_examples=200, deadline=None)
@given(a=finite, b=finite, c=finite, x=finite, h=steps_h)
def test_quadratics_are_differentiated_exactly(
    a: float, b: float, c: float, x: float, h: float
) -> None:
    """Both formulas are exact for quadratics; only round-off of the F values remains."""
    result = central_difference(lambda t: (a * t + b) * t + c, x, h, n_steps=2)
    for step in result.steps:
        size = (abs(a) * (abs(x) + step.h) + abs(b)) * (abs(x) + step.h) + abs(c) + 1.0
        assert abs(step.dx - (2.0 * a * x + b)) <= 16.0 * EPS * size / step.h
        assert abs(step.ddx - 2.0 * a) <= 32.0 * EPS * size / step.h**2


@settings(max_examples=200, deadline=None)
@given(a=st.floats(min_value=0.1, max_value=5.0), x=finite, h=steps_h)
def test_cubic_error_is_h_squared(a: float, x: float, h: float) -> None:
    """For a*X**3 the error of DX is exactly a*H**2 (the H**2/6 * F''' term)."""
    result = central_difference(lambda t: a * t * t * t, x, h, n_steps=1)
    (step,) = result.steps
    size = a * (abs(x) + h) ** 3 + 1.0
    assert step.dx - 3.0 * a * x * x == pytest.approx(a * h * h, abs=16.0 * EPS * size / h)
    assert step.ddx == pytest.approx(6.0 * a * x, abs=32.0 * EPS * size / h**2 + 1e-12)


@settings(max_examples=100, deadline=None)
@given(x=st.floats(min_value=-3.0, max_value=3.0))
def test_smooth_functions_converge_like_h_squared(x: float) -> None:
    """For EXP the errors of DX and DDX fall by about 100 per row while truncation dominates,
    and DDX tends to F''(X)."""
    exact = math.exp(x)
    result = central_difference(math.exp, x, 0.1, n_steps=3)
    dx_err = [abs(step.dx - exact) for step in result.steps]
    ddx_err = [abs(step.ddx - exact) for step in result.steps]
    for errors in (dx_err[:3], ddx_err[:2]):
        for big, small in itertools.pairwise(errors):
            assert 90.0 < big / small < 110.0
    assert dx_err[0] == pytest.approx(exact * 0.01 / 6.0, rel=0.01)
    assert ddx_err[0] == pytest.approx(exact * 0.01 / 12.0, rel=0.01)
    assert ddx_err[2] < 1e-5 * exact


@settings(max_examples=100, deadline=None)
@given(x=finite, h=st.floats(min_value=1.0e-6, max_value=10.0))
def test_rows_mirror_the_listing(x: float, h: float) -> None:
    """Every row is (FR - FL)/(2H) and (FR - 2FO + FL)/(H*H) with accumulated H, bit for bit."""
    result = central_difference(math.sin, x, h)
    fo = math.sin(x)
    step_h = h
    for step in result.steps:
        fr, fl = math.sin(x + step_h), math.sin(x - step_h)
        assert step.h == step_h
        assert step.dx == (fr - fl) / (2.0 * step_h)
        assert step.ddx == (fr - 2.0 * fo + fl) / (step_h * step_h)
        step_h = 0.1 * step_h
    assert result.fo == fo
    assert result.value == result.steps[-1].dx


@settings(max_examples=100, deadline=None)
@given(x=finite, h=steps_h)
def test_odd_and_even_functions(x: float, h: float) -> None:
    """DX of an even function is odd in X and DDX even, so at X = 0 DX vanishes exactly."""
    assume(abs(x) > 1e-3)
    plus = central_difference(math.cos, x, h, n_steps=1).steps[0]
    minus = central_difference(math.cos, -x, h, n_steps=1).steps[0]
    assert plus.dx == pytest.approx(-minus.dx, abs=1e-12)
    assert plus.ddx == pytest.approx(minus.ddx, abs=1e-9)
    assert central_difference(math.cos, 0.0, h, n_steps=1).steps[0].dx == 0.0


# ---------------------------------------------------------------- book machine


def test_chopped_models_do_not_reproduce_the_small_h_digits() -> None:
    """The precision notes' claim: the book's 1.0000150E-04 depends on the machine's EXPF."""
    rows = central_difference_rows(ChoppedMachine(10, 8))
    assert f"{float(rows[1][0]):.7E}" == "1.0000135E-04"
    for model in (ChoppedMachine(2, 27), ChoppedMachine(10, 8), ChoppedMachine(10, 9)):
        dx2 = f"{float(central_difference_rows(model)[1][0]):.7E}"
        assert dx2 != "1.0000150E-04"
    assert all(f"{float(ddx):.7f}" == "2.0100083" for _, ddx in rows[:1])


# ---------------------------------------------------------------- adapter and engine


def _trace_text(result: CentralDifferenceResult, **override: float) -> str:
    lines = [
        f"STEP,k={s.k},h={trace_real(s.h)},dx={trace_real(s.dx)},ddx={trace_real(s.ddx)}"
        for s in result.steps
    ]
    values = {
        "value": result.value,
        "fo": result.fo,
        "first_dx": result.first_dx,
        "first_ddx": result.first_ddx,
        "last_ddx": result.last_ddx,
        **override,
    }
    lines.append(
        f"RESULT,value={trace_real(values['value'])},converged=T,iterations={len(result.steps)},"
        f"fo={trace_real(values['fo'])},first_dx={trace_real(values['first_dx'])},"
        f"first_ddx={trace_real(values['first_ddx'])},last_ddx={trace_real(values['last_ddx'])}"
    )
    return "\n".join(lines) + "\n"


def test_adapter_is_registered() -> None:
    assert isinstance(get_adapter("ch04_p01"), CentralDifferenceAdapter)
    assert CentralDifferenceAdapter.result_fields() == (
        "value",
        "converged",
        "iterations",
        "steps",
        "x",
        "h",
        "fo",
        "first_dx",
        "first_ddx",
        "last_ddx",
    )


def test_adapter_rebuilds_the_result_from_a_trace(
    entry: CatalogEntry, book: CentralDifferenceResult
) -> None:
    rebuilt = CentralDifferenceAdapter().result_from_trace(
        entry, {"x": 0.0, "h": 0.1}, parse_trace(_trace_text(book))
    )
    assert rebuilt == book
    assert rebuilt.book_text(carriage_control=True) == book.book_text(carriage_control=True)


def test_adapter_rejects_inconsistent_traces(
    entry: CatalogEntry, book: CentralDifferenceResult
) -> None:
    adapter = CentralDifferenceAdapter()
    inputs = {"x": 0.0, "h": 0.1}
    good = _trace_text(book)
    lines = good.splitlines()
    bad_traces = [
        "\n".join(lines[:3] + lines[-1:]).replace("iterations=10", "iterations=3") + "\n",
        "\n".join(lines[1:]) + "\n",  # 9 rows
        good.replace("STEP,k=1,", "STEP,k=11,", 1),
        _trace_text(book, value=1.0),
        _trace_text(book, first_ddx=1.0),
        _trace_text(book, last_ddx=1.0),
        _trace_text(book, first_dx=1.0),
    ]
    for text in bad_traces:
        with pytest.raises(FortranRunError):
            adapter.result_from_trace(entry, inputs, parse_trace(text))
    with pytest.raises(FortranRunError):
        adapter.result_from_trace(entry, inputs, parse_trace("ERROR,code=INPUT,message=boom\n"))


def test_adapter_needs_a_function(entry: CatalogEntry) -> None:
    with pytest.raises(TypeError):
        CentralDifferenceAdapter().run_python(entry, {"x": 0.0, "h": 0.1}, None)


def test_python_engine_runs_the_book_card(entry: CatalogEntry) -> None:
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry))
    assert outcome.ok, outcome.error
    assert outcome.book_text == BOOK_TEXT
    assert outcome.result is not None
    assert outcome.result.book_text(carriage_control=True).startswith(HEADING + "\n")


@pytest.mark.parametrize(
    ("preset", "x", "dx", "ddx"),
    [
        (2, 1.0, math.cos(1.0), -math.sin(1.0)),
        (3, 0.19, 1.0 / (0.19 * math.log(10.0)), -1.0 / (0.19**2 * math.log(10.0))),
    ],
)
def test_presets_approach_the_analytic_derivatives(
    entry: CatalogEntry, preset: int, x: float, dx: float, ddx: float
) -> None:
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {"x": x}, preset=preset))
    assert outcome.ok, outcome.error
    result = outcome.result
    assert isinstance(result, CentralDifferenceResult)
    best_dx = min(abs(step.dx - dx) for step in result.steps)
    best_ddx = min(abs(step.ddx - ddx) for step in result.steps)
    assert best_dx < 1e-9 * max(1.0, abs(dx))
    assert best_ddx < 1e-5 * max(1.0, abs(ddx))


def test_log_preset_outside_its_domain_is_an_input_error(entry: CatalogEntry) -> None:
    """Preset 3 at the book card (X = 0): an INPUT error, with the heading as book text."""
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, preset=3))
    assert outcome.status == "INPUT"
    assert outcome.error is not None
    assert outcome.book_text.startswith("DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS\n")
    custom = PythonEngine().run(entry, RunRequest.for_entry(entry, expression="ALOG10(X)"))
    assert custom.status == "EXPRESSION"


def test_python_engine_verbose_text_on_the_book_card(entry: CatalogEntry) -> None:
    """The driver's ``--verbose`` extras (compared with the driver in ``tests/parity``)."""
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, verbose=True))
    lines = outcome.verbose_text.splitlines()
    assert lines[:5] == [
        "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)",
        "PRESET 1: F(X) = X**2*EXP(X)",
        "WORKING PRECISION: REAL64",
        "DATA CARD: X = 0.00000000000000000E+000  H = 1.00000000000000006E-001",
        "FO = F(X) = 0.00000000000000000E+000",
    ]
    assert lines[5] == (
        "  ROW 1: H = 1.00000000000000006E-001  DX = 1.00166750019844118E-002"
        "  DDX = 2.01000833611160701E+000"
    )
    assert lines[6] == (
        "  ROW 2: H = 1.00000000000000019E-002  DX = 1.00001666674998809E-004"
        "  DDX = 2.00010000083333628E+000  |DX CHANGE| = 9.91667333530941303E-003"
        "  |DDX CHANGE| = 9.90833527827073013E-003"
    )
    assert lines[-1] == "VALUE = DX OF THE LAST ROW = 1.00000000317107625E-020"
    assert len(lines) == 5 + BOOK_ROWS + 1


def test_practice_answers_are_the_engine_values(entry: CatalogEntry) -> None:
    for question in entry.practice:
        request = RunRequest.for_entry(
            entry, entry.practice_inputs(question), preset=question.preset
        )
        outcome = PythonEngine().run(entry, request)
        assert outcome.ok, (question.id, outcome.error)
        assert getattr(outcome.result, question.answer_field) == question.answer, question.id
