"""Chapter 3, Program 1 (Simpson's 1/3 rule): book data card, every original branch, properties.

SciPy is used only as an independent reference (``scipy.special.sici`` for Si(B)).
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.special import sici

from gerald_na.algorithms import Rounding, SimpsonResult, SimpsonStep, simpson
from gerald_na.algorithms.simpson import (
    BOOK_SEED,
    MAX_PANELS,
    MSG_ODD_PANELS,
    TRACE_MSG_ODD_PANELS,
)
from gerald_na.engines import PythonEngine, RunRequest
from gerald_na.engines.adapters import get_adapter
from gerald_na.engines.adapters._common import book_seed_for
from gerald_na.engines.adapters.simpson import SimpsonAdapter
from gerald_na.engines.trace import parse_trace
from gerald_na.errors import ExpressionError, FortranRunError, InputError, OddPanelsError
from gerald_na.expr import compile_expr
from gerald_na.registry import CatalogEntry, get_registry

BOOK_CARD = (5.0, 100)  # "5.0           100"
SCAN_OUTPUT = "VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499307 WITH 100 PANELS\n"
REAL64_VALUE = 1.5499312397703537
SI_5 = 1.5499312449446741


def sinc(x: float) -> float:
    """The book's integrand with its limit at 0 (the Fortran preset ``f_sinc``)."""
    return math.sin(x) / x if x != 0.0 else 1.0


def book_sinc(x: float) -> float:
    """The statement function F(X) = SINF(X)/X: undefined at 0, like the catalog expression."""
    return math.sin(x) / x


@pytest.fixture(scope="module")
def entry() -> CatalogEntry:
    return get_registry().get("ch03_p01")


# ---------------------------------------------------------------- the book data card


def test_book_card_value() -> None:
    result = simpson(sinc, *BOOK_CARD)
    assert isinstance(result, SimpsonResult)
    assert result.value == REAL64_VALUE
    assert abs(result.value - 1.5499307) < 1e-6  # the book's single-precision digits
    assert abs(result.value - SI_5) < 1e-8
    assert result.converged
    assert result.iterations == 101
    assert result.b == 5.0
    assert result.n == 100
    assert result.delx == 0.05
    assert result.value == result.delx / 3.0 * result.sum


def test_book_seed_is_f_of_zero() -> None:
    """``SUM = 1.0 + ...``: the literal seed gives the same bits as evaluating F(0)."""
    seeded = simpson(book_sinc, *BOOK_CARD, f0=BOOK_SEED)
    evaluated = simpson(sinc, *BOOK_CARD)
    assert seeded == evaluated
    assert seeded.steps[0] == SimpsonStep(k=0, x=0.0, fx=1.0, weight=1.0)


def test_seed_generalizes_to_any_f0() -> None:
    """Without ``f0`` the ordinate F(0) is evaluated; cos integrates to sin(B)."""
    result = simpson(math.cos, 1.0, 10)
    assert result.steps[0].fx == 1.0
    assert result.value == pytest.approx(math.sin(1.0), abs=1e-6)
    wrong_seed = simpson(math.cos, 1.0, 10, f0=0.0)
    assert wrong_seed.value == pytest.approx(result.value - 0.1 / 3.0, abs=1e-15)


def test_book_text_reproduces_the_layout_of_the_scan() -> None:
    result = simpson(sinc, *BOOK_CARD)
    # The book's digit 7 is its machine's arithmetic; real64 gives ...312 (see precision notes).
    assert result.book_text() == SCAN_OUTPUT.replace("1.5499307", "1.5499312")
    assert result.book_text(carriage_control=True) == " " + result.book_text()
    below_one = simpson(sinc, 1.0, 100)
    assert below_one.book_text() == (
        "VALUE OF SINE INTEGRAL FROM X = 0 TO X =  1.00 IS  .9460830 WITH 100 PANELS\n"
    )
    assert "0.9460831" in below_one.book_text(rounding=Rounding.NEAREST).replace(" .", " 0.")


def test_ordinates_follow_the_weight_pattern() -> None:
    result = simpson(sinc, *BOOK_CARD)
    assert [step.k for step in result.steps] == list(range(101))
    weights = [step.weight for step in result.steps]
    assert weights[0] == weights[-1] == 1.0
    assert weights[1:-1] == [4.0, 2.0] * 49 + [4.0]
    assert sum(weights) == 300.0
    assert result.steps[-1].x == 5.0
    for step in result.steps[1:]:
        assert step.x == pytest.approx(step.k * 0.05, abs=1e-13)
        assert step.fx == math.sin(step.x) / step.x


def test_x_is_accumulated_like_the_book() -> None:
    """``10 X = X + 2.*DELX``: X is advanced, not recomputed as K*DELX (bit-level check)."""
    result = simpson(sinc, 1.0, 20)
    delx = 1.0 / 20.0
    x = 2.0 * delx
    for i in range(2, 11):
        assert result.steps[2 * i - 2].x == x
        assert result.steps[2 * i - 1].x == x + delx
        x = x + 2.0 * delx


# ---------------------------------------------------------------- error paths


@pytest.mark.parametrize("n", [1, 3, 7, 99, 101, -1, -3])
def test_odd_panels(n: int) -> None:
    calls: list[float] = []

    def f(x: float) -> float:
        calls.append(x)
        return 1.0

    with pytest.raises(OddPanelsError) as info:
        simpson(f, 5.0, n)
    assert info.value.code == "ODD_PANELS"
    assert info.value.message == TRACE_MSG_ODD_PANELS
    assert "," not in info.value.message
    assert info.value.book_output == MSG_ODD_PANELS + "\n"
    assert info.value.steps == ()
    assert calls == []  # the parity test comes first, as in the scan


def test_odd_panels_message_is_the_scan_hollerith() -> None:
    # 60H: 54 characters on the first card, one blank in column 72, "APPLY" on the continuation.
    assert len(" " + MSG_ODD_PANELS) == 60
    assert MSG_ODD_PANELS.replace(",", ";") == TRACE_MSG_ODD_PANELS


@pytest.mark.parametrize("n", [0, -2, -100, MAX_PANELS + 2])
def test_n_out_of_range_is_an_input_error(n: int) -> None:
    with pytest.raises(InputError, match="even number from 2"):
        simpson(sinc, 5.0, n)


@pytest.mark.parametrize("n", [True, 4.0, "4"])
def test_n_must_be_an_integer(n: object) -> None:
    with pytest.raises(InputError, match="integer"):
        simpson(sinc, 5.0, n)  # type: ignore[arg-type]


@pytest.mark.parametrize("b", [math.nan, math.inf, -math.inf])
def test_b_must_be_finite(b: float) -> None:
    with pytest.raises(InputError, match="finite"):
        simpson(sinc, b, 4)


def test_two_panels_skip_the_loop() -> None:
    """N = 2: ``DO 10 I = 2,1`` is zero-trip, the three-ordinate rule results."""
    result = simpson(sinc, 5.0, 2)
    assert [step.k for step in result.steps] == [0, 1, 2]
    assert result.value == 2.5 / 3.0 * (1.0 + 4.0 * sinc(2.5) + sinc(5.0))


def test_zero_upper_limit() -> None:
    result = simpson(sinc, 0.0, 4)
    assert result.value == 0.0
    assert result.iterations == 5


def test_negative_upper_limit_is_odd_symmetric() -> None:
    assert simpson(sinc, -5.0, 100).value == -simpson(sinc, 5.0, 100).value


def test_non_finite_ordinate_keeps_the_rows_before_it() -> None:
    def f(x: float) -> float:
        return math.nan if 2.0 < x < 3.0 else 1.0

    # Evaluation order k = 0, 1, 8, 2, 3, 4, 5: X = 2.5 (k = 5) is NaN.
    with pytest.raises(InputError, match=r"not a finite number at X = 2\.5") as info:
        simpson(f, 4.0, 8)
    assert [step.k for step in info.value.steps if isinstance(step, SimpsonStep)] == [
        0,
        1,
        2,
        3,
        4,
        8,
    ]
    assert info.value.book_output == ""


def test_non_finite_seed() -> None:
    with pytest.raises(InputError) as info:
        simpson(sinc, 1.0, 4, f0=math.inf)
    assert info.value.steps == ()


def test_expression_errors_keep_their_class_and_rows() -> None:
    f = compile_expr("SIN(X)/X")
    with pytest.raises(ExpressionError, match="division by zero") as info:
        simpson(f, 5.0, 100)
    assert info.value.steps == ()
    g = compile_expr("1/(X - 1)")
    with pytest.raises(ExpressionError) as info2:
        simpson(g, 2.0, 4)  # X = 1 is ordinate k = 2, after k = 0, 1 and 4
    assert [step.k for step in info2.value.steps if isinstance(step, SimpsonStep)] == [0, 1, 4]


# ---------------------------------------------------------------- property tests

coefficient = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False)
upper = st.floats(min_value=-5.0, max_value=5.0, allow_nan=False)
even_panels = st.integers(min_value=1, max_value=50).map(lambda half: 2 * half)


def _cubic_integral(c: tuple[float, float, float, float], b: float) -> float:
    c3, c2, c1, c0 = c
    return c3 * b**4 / 4.0 + c2 * b**3 / 3.0 + c1 * b**2 / 2.0 + c0 * b


def _cubic_scale(c: tuple[float, float, float, float], b: float) -> float:
    """Magnitude of the terms, for a rounding-error tolerance."""
    return sum(abs(ci) * max(abs(b), 1.0) ** (4 - i) for i, ci in enumerate(c))


@settings(max_examples=200, deadline=None)
@given(st.tuples(coefficient, coefficient, coefficient, coefficient), upper, even_panels)
def test_exact_for_cubics_with_a_callable(
    c: tuple[float, float, float, float], b: float, n: int
) -> None:
    c3, c2, c1, c0 = c

    def cubic(x: float) -> float:
        return ((c3 * x + c2) * x + c1) * x + c0

    result = simpson(cubic, b, n)
    assert result.value == pytest.approx(_cubic_integral(c, b), abs=1e-12 * _cubic_scale(c, b))


@settings(max_examples=100, deadline=None)
@given(st.tuples(coefficient, coefficient, coefficient, coefficient), upper, even_panels)
def test_exact_for_cubics_with_a_custom_expression(
    c: tuple[float, float, float, float], b: float, n: int
) -> None:
    c3, c2, c1, c0 = c
    f = compile_expr(f"({c3!r})*X**3 + ({c2!r})*X**2 + ({c1!r})*X + ({c0!r})")
    result = simpson(f, b, n)
    assert result.value == pytest.approx(_cubic_integral(c, b), abs=1e-12 * _cubic_scale(c, b))


@settings(max_examples=100, deadline=None)
@given(st.floats(min_value=0.1, max_value=30.0, allow_nan=False))
def test_converges_to_the_sine_integral(b: float) -> None:
    """|error| <= B*DELX**4*max|F''''|/180 with max|F''''| <= 1/5 for sin(x)/x, and it shrinks."""
    reference = float(sici(b)[0])
    errors = []
    for n in (10, 20, 40, 80, 160, 320):
        delx = b / n
        error = abs(simpson(sinc, b, n).value - reference)
        assert error <= b * delx**4 / 900.0 + 1e-13
        errors.append(error)
    assert errors[-1] <= errors[0]
    assert errors[-1] < 3e-6  # the bound at N = 320 for B <= 30


def test_fourth_order_convergence() -> None:
    reference = float(sici(5.0)[0])
    coarse = abs(simpson(sinc, 5.0, 10).value - reference)
    fine = abs(simpson(sinc, 5.0, 20).value - reference)
    assert 12.0 < coarse / fine < 20.0


@given(st.integers(min_value=-1001, max_value=1001).filter(lambda n: n % 2 != 0), upper)
def test_odd_n_always_raises(n: int, b: float) -> None:
    with pytest.raises(OddPanelsError):
        simpson(sinc, b, n)


# ---------------------------------------------------------------- engine adapter


def test_adapter_is_registered(entry: CatalogEntry) -> None:
    assert isinstance(get_adapter("ch03_p01"), SimpsonAdapter)
    assert SimpsonAdapter.result_fields() == (
        "value",
        "converged",
        "iterations",
        "steps",
        "b",
        "n",
        "delx",
        "sum",
    )


def test_book_seed_only_for_the_book_integrand(entry: CatalogEntry) -> None:
    assert book_seed_for(entry, compile_expr("SIN(X)/X"), BOOK_SEED) == BOOK_SEED
    assert book_seed_for(entry, compile_expr("SINF(X) / X"), BOOK_SEED) == BOOK_SEED
    assert book_seed_for(entry, compile_expr("EXP(-X**2)"), BOOK_SEED) is None
    assert book_seed_for(entry, sinc, BOOK_SEED) is None


def test_adapter_substitutes_the_seed_for_the_chart(entry: CatalogEntry) -> None:
    adapter = get_adapter("ch03_p01")
    assert adapter.substituted_ordinates(entry, compile_expr("SIN(X)/X")) == {0.0: BOOK_SEED}
    assert adapter.substituted_ordinates(entry, compile_expr("EXP(-X**2)")) == {}


def test_book_integrand_at_zero_upper_limit(entry: CatalogEntry) -> None:
    """B = 0 puts every ordinate at X = 0: the book's integrand is 1 there, as in f_sinc."""
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {"b": 0.0, "n": 100}))
    assert outcome.ok, outcome.error
    assert isinstance(outcome.result, SimpsonResult)
    assert outcome.result.value == 0.0
    assert all(step.fx == BOOK_SEED for step in outcome.result.steps)
    custom = RunRequest.for_entry(entry, {"b": 0.0, "n": 100}, expression="EXP(-X)/X")
    assert not PythonEngine().run(entry, custom).ok


def test_python_engine_runs_the_book_card(entry: CatalogEntry) -> None:
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {}))
    assert outcome.ok, outcome.error
    assert isinstance(outcome.result, SimpsonResult)
    assert outcome.result.value == REAL64_VALUE
    assert outcome.book_text == SCAN_OUTPUT.replace("1.5499307", "1.5499312")


@pytest.mark.parametrize(
    ("preset", "b", "expected"),
    [
        (2, 2.0, math.sqrt(math.pi) / 2.0 * math.erf(2.0)),
        (3, 1.0, math.pi / 4.0),
        (3, 5.0, math.atan(5.0)),
    ],
)
def test_presets_2_and_3(entry: CatalogEntry, preset: int, b: float, expected: float) -> None:
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {"b": b}, preset=preset))
    assert outcome.result is not None
    assert outcome.result.value == pytest.approx(expected, abs=1e-8)


def test_custom_expressions(entry: CatalogEntry) -> None:
    engine = PythonEngine()
    same = engine.run(entry, RunRequest(inputs={"b": 5.0, "n": 100}, expression="sinf(x)/x"))
    assert same.result is not None
    assert same.result.value == REAL64_VALUE
    scaled = engine.run(entry, RunRequest(inputs={"b": 5.0, "n": 100}, expression="2*sin(x)/x"))
    assert scaled.status == "EXPRESSION"
    assert scaled.error is not None
    assert "x = 0.0" in scaled.error.message
    cosine = engine.run(entry, RunRequest(inputs={"b": 1.0, "n": 10}, expression="cos(x)"))
    assert cosine.result is not None
    assert cosine.result.value == pytest.approx(math.sin(1.0), abs=1e-6)


def test_odd_panels_through_the_engine(entry: CatalogEntry) -> None:
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {"n": 7}))
    assert outcome.status == "ODD_PANELS"
    assert outcome.book_text == MSG_ODD_PANELS + "\n"


def _trace(*lines: str) -> str:
    return "".join(line + "\n" for line in lines)


STEP0 = "STEP,k=0,x=0.0,fx=1.0,weight=1.0"
STEP1 = "STEP,k=1,x=2.5,fx=0.2,weight=4.0"
STEP2 = "STEP,k=2,x=5.0,fx=-0.1,weight=1.0"


def test_result_from_trace(entry: CatalogEntry) -> None:
    adapter = SimpsonAdapter()
    inputs = {"b": 5.0, "n": 2}
    trace = parse_trace(
        _trace(STEP0, STEP1, STEP2, "RESULT,value=1.0,converged=T,iterations=3,delx=2.5,sum=1.2")
    )
    result = adapter.result_from_trace(entry, inputs, trace)
    assert result.n == 2
    assert result.delx == 2.5
    assert result.sum == 1.2
    assert [step.k for step in result.steps] == [0, 1, 2]


@pytest.mark.parametrize(
    "text",
    [
        _trace(STEP0, STEP1, "RESULT,value=1.0,converged=T,iterations=3,delx=2.5,sum=1.2"),
        _trace(STEP0, STEP1, STEP2, "RESULT,value=1.0,converged=T,iterations=2,delx=2.5,sum=1.2"),
        _trace(STEP0, STEP2, STEP1, "RESULT,value=1.0,converged=T,iterations=3,delx=2.5,sum=1.2"),
        _trace("ERROR,code=ODD_PANELS,message=x"),
    ],
)
def test_result_from_trace_checks_consistency(entry: CatalogEntry, text: str) -> None:
    with pytest.raises(FortranRunError):
        SimpsonAdapter().result_from_trace(entry, {"b": 5.0, "n": 2}, parse_trace(text))


def test_adapter_needs_a_function(entry: CatalogEntry) -> None:
    with pytest.raises(TypeError):
        SimpsonAdapter().run_python(entry, {"b": 5.0, "n": 2}, None)
    with pytest.raises(TypeError):
        SimpsonAdapter().run_python(entry, {"b": True, "n": 2}, sinc)
    with pytest.raises(TypeError):
        SimpsonAdapter().run_python(entry, {"b": 5.0, "n": 2.0}, sinc)


def test_python_engine_verbose_text_on_the_book_card(entry: CatalogEntry) -> None:
    """The driver's ``--verbose`` extras (compared with the driver in ``tests/parity``)."""
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, verbose=True))
    assert outcome.verbose_text.splitlines() == [
        "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)",
        "PRESET 1: F(X) = SIN(X)/X",
        "WORKING PRECISION: REAL64",
        "DATA CARD: B = 5.00000000000000000E+000  N = 100",
        "DELX = B/N = 5.00000000000000028E-002",
        "SUM OF WEIGHTED ORDINATES = 9.29958743862212316E+001",
        "INTEGRAL = DELX/3*SUM = 1.54993123977035374E+000",
        "ORDINATES EVALUATED = 101",
    ]
