"""Chapter 1, Program 1 (interval halving): book data card, every original branch, properties."""

import itertools
import math
from collections.abc import Callable

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from gerald_na.algorithms import BisectionResult, BisectionStep, Rounding, bisection
from gerald_na.algorithms.bisection import (
    BOOK_MAX_ITER,
    MSG_NO_SIGN_CHANGE,
    MSG_PRODUCT_ZERO,
    MSG_ZERO_PRODUCT,
    msg_non_convergent,
)
from gerald_na.errors import (
    BracketError,
    InputError,
    NonConvergenceError,
    ZeroProductError,
)
from gerald_na.expr import compile_expr

BOOK_EXPR = "EXPF(-X) - SINF(3.1415926*X/2.)"
BOOK_CARD = (0.0, 1.0, 1.0e-5)  # "0.  1.  1.E-5"

# The printed output of the scan (docs/chapter_01_program_01_listing.pdf), transcribed line by
# line with the carriage-control column consumed by the line printer.
SCAN_OUTPUT = """\
AT X =   .5000000 F(X) =   -.100576
AT X =   .2500000 F(X) =    .396117
AT X =   .3750000 F(X) =    .131719
AT X =   .4375000 F(X) =    .011255
AT X =   .4687500 F(X) =   -.045774
AT X =   .4531250 F(X) =   -.017534
AT X =   .4453125 F(X) =   -.003207
AT X =   .4414062 F(X) =    .004006
AT X =   .4433593 F(X) =    .000395
AT X =   .4443359 F(X) =   -.001407
AT X =   .4438476 F(X) =   -.000506
AT X =   .4436035 F(X) =   -.000055
AT X =   .4434814 F(X) =    .000170
AT X =   .4435424 F(X) =    .000057
AT X =   .4435729 F(X) =    .000001
THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED.
"""

SCAN_TABLE = [
    (0.5000000, -0.100576),
    (0.2500000, 0.396117),
    (0.3750000, 0.131719),
    (0.4375000, 0.011255),
    (0.4687500, -0.045774),
    (0.4531250, -0.017534),
    (0.4453125, -0.003207),
    (0.4414062, 0.004006),
    (0.4433593, 0.000395),
    (0.4443359, -0.001407),
    (0.4438476, -0.000506),
    (0.4436035, -0.000055),
    (0.4434814, 0.000170),
    (0.4435424, 0.000057),
    (0.4435729, 0.000001),
]


def book_f(x: float) -> float:
    return math.exp(-x) - math.sin(3.1415926 * x / 2.0)


@pytest.fixture(scope="module")
def book_result() -> BisectionResult:
    return bisection(compile_expr(BOOK_EXPR), *BOOK_CARD)


def test_book_data_card(book_result: BisectionResult) -> None:
    assert book_result.converged
    assert book_result.iterations == 15
    assert len(book_result.steps) == 15
    assert not book_result.root_at_endpoint
    assert book_result.value == pytest.approx(0.4435729, abs=1e-7)
    assert book_result.value == 14535 / 32768  # exact dyadic midpoint, printed .4435729
    assert (book_result.x1, book_result.x2, book_result.tol) == BOOK_CARD
    assert book_result.max_iter == BOOK_MAX_ITER
    assert book_result.fx1 == pytest.approx(1.0)
    assert book_result.fx2 == pytest.approx(math.exp(-1.0) - 1.0, abs=1e-6)


def test_book_table_matches_scan(book_result: BisectionResult) -> None:
    for k, (step, (x, fx)) in enumerate(zip(book_result.steps, SCAN_TABLE, strict=True), 1):
        assert step.k == k
        assert step.x == pytest.approx(x, abs=1.0e-7)  # the book truncates to 7 places
        assert step.fx == pytest.approx(fx, abs=2.0e-6)  # single precision in the book
        assert step.x == (step.x1 + step.x2) / 2.0


def test_steps_record_the_bracket_at_the_start_of_each_pass(book_result: BisectionResult) -> None:
    steps = book_result.steps
    assert (steps[0].x1, steps[0].x2) == (0.0, 1.0)
    for previous, step in itertools.pairwise(steps):
        if previous.fx * book_f(previous.x1) < 0:
            assert (step.x1, step.x2) == (previous.x1, previous.x)  # label 10: X2 = X
        else:
            assert (step.x1, step.x2) == (previous.x, previous.x2)  # label 12: X1 = X
        assert step.x2 - step.x1 == pytest.approx((previous.x2 - previous.x1) / 2)


def test_book_text_reproduces_scan(book_result: BisectionResult) -> None:
    text = book_result.book_text()
    produced = text.splitlines()
    expected = SCAN_OUTPUT.splitlines()
    assert len(produced) == len(expected) == 16
    differing = [i for i, (a, b) in enumerate(zip(produced, expected, strict=True)) if a != b]
    # The only difference is the last digit of F(X) in row 15: real64 gives 9.989E-07, which
    # truncates to .000000, where the book's single-precision value printed as .000001.
    assert differing == [14]
    assert produced[14] == "AT X =   .4435729 F(X) =    .000000"
    assert text.endswith("\n")


def test_book_text_with_book_function_values_matches_scan_exactly(
    book_result: BisectionResult,
) -> None:
    # Feed the book's own printed F(X) values back in (the midpoints are exact dyadic numbers,
    # identical in single and double precision): the output must then match the scan character
    # for character, which pins down every FORMAT (texts, widths, truncation, no leading zero).
    printed = {step.x: fx for step, (_, fx) in zip(book_result.steps, SCAN_TABLE, strict=True)}

    def replay(x: float) -> float:
        if x in printed:
            fx = printed[x]
            return fx + math.copysign(1e-9, fx)  # keep the 6th decimal under truncation
        return book_f(x)

    assert bisection(replay, *BOOK_CARD).book_text() == SCAN_OUTPUT


def test_book_text_carriage_control_and_rounding(book_result: BisectionResult) -> None:
    with_cc = book_result.book_text(carriage_control=True).splitlines()
    assert with_cc[0] == " AT X =   .5000000 F(X) =   -.100576"
    assert with_cc[-1] == " THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED."
    nearest = book_result.book_text(rounding=Rounding.NEAREST).splitlines()
    assert nearest[-1] == "THE VALUE, X =   .4435730 IS A ROOT.  15 ITERATIONS WERE REQUIRED."


def test_step_book_line(book_result: BisectionResult) -> None:
    assert book_result.steps[0].book_line() == "AT X =   .5000000 F(X) =   -.100576"


def test_python_callable_and_expression_agree(book_result: BisectionResult) -> None:
    assert bisection(book_f, *BOOK_CARD) == book_result


def test_no_sign_change_raises_bracket_error() -> None:
    with pytest.raises(BracketError) as info:
        bisection(book_f, 0.0, 0.2, 1e-5)
    error = info.value
    assert type(error) is BracketError
    assert error.code == "BRACKET"
    assert error.message == MSG_NO_SIGN_CHANGE
    assert error.message == (
        "FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS."
    )
    assert error.steps == ()
    assert error.book_output == MSG_NO_SIGN_CHANGE + "\n"


def test_root_at_x1() -> None:
    result = bisection(compile_expr("x*(x-3)"), 0.0, 1.0, 1e-5)
    assert result.root_at_endpoint
    assert result.converged
    assert result.value == 0.0
    assert result.iterations == 0
    assert result.steps == ()
    # Format 201 uses F6.3; the original's fall-through to the 202 ERROR message is not
    # reproduced (see the module ERRATA).
    assert result.book_text() == "THE INPUT VALUE, X =   .000 IS A ROOT OF THE EQUATION.\n"


def test_root_at_x2() -> None:
    result = bisection(lambda x: x - 2.5, 0.0, 2.5, 1e-5)
    assert result.root_at_endpoint
    assert result.value == 2.5
    assert result.iterations == 0
    assert result.book_text() == "THE INPUT VALUE, X =  2.500 IS A ROOT OF THE EQUATION.\n"
    assert result.book_text(carriage_control=True).startswith(" THE INPUT VALUE, X =  2.500")


def test_roots_at_both_endpoints_print_both() -> None:
    result = bisection(lambda x: (x + 1.25) * (x - 1.0), -1.25, 1.0, 1e-5)
    assert result.value == -1.25
    assert result.book_text() == (
        "THE INPUT VALUE, X = -1.250 IS A ROOT OF THE EQUATION.\n"
        "THE INPUT VALUE, X =  1.000 IS A ROOT OF THE EQUATION.\n"
    )


def test_input_root_f63_overflow_prints_asterisks() -> None:
    result = bisection(lambda x: x - 1000.0, 1000.0, 2000.0, 1e-5)
    assert result.book_text() == "THE INPUT VALUE, X = ****** IS A ROOT OF THE EQUATION.\n"


def test_product_underflow_raises_zero_product_error() -> None:
    def f(x: float) -> float:
        return 1e-200 if x < 0.5 else -1e-200

    assert f(0.0) * f(1.0) == 0.0  # the product underflows although neither value is zero
    with pytest.raises(ZeroProductError) as info:
        bisection(f, 0.0, 1.0, 1e-300)
    error = info.value
    assert error.code == "ZERO_PRODUCT"
    assert isinstance(error, BracketError)
    assert error.message == MSG_PRODUCT_ZERO
    assert error.message == "ERROR. FX1 AND FX2 NOT ZERO THOUGH PRODUCT TESTS ZERO."
    assert error.steps == ()
    assert error.book_output == MSG_PRODUCT_ZERO + "\n"


def test_zero_product_inside_loop_raises_error_branch() -> None:
    # The first midpoint moves X1 (FX1 = 1E-100); at the second one FX*FX1 = -1E-330 underflows
    # to zero although |FX| > TOL: IF (FX*FX1) 10, 11, 12 takes label 11.
    values = {0.0: 1e-160, 1.0: -1.0, 0.5: 1e-100, 0.75: -1e-230}

    def f(x: float) -> float:
        return values[x]

    with pytest.raises(ZeroProductError) as info:
        bisection(f, 0.0, 1.0, 1e-300)
    error = info.value
    assert error.message == MSG_ZERO_PRODUCT == "ERROR."
    assert error.steps == (
        BisectionStep(k=1, x1=0.0, x2=1.0, x=0.5, fx=1e-100),
        BisectionStep(k=2, x1=0.5, x2=1.0, x=0.75, fx=-1e-230),
    )
    assert error.book_output == (
        "AT X =   .5000000 F(X) =    .000000\nAT X =   .7500000 F(X) =   -.000000\nERROR.\n"
    )


def test_zero_product_with_negative_tolerance_and_exact_zero() -> None:
    # A negative TOL defeats the convergence test, so an exact zero reaches label 11.
    with pytest.raises(ZeroProductError):
        bisection(lambda x: x - 0.5, 0.0, 1.0, -1.0)


def test_exact_zero_midpoint_converges() -> None:
    result = bisection(lambda x: x - 0.25, 0.0, 1.0, 0.0)
    assert result.converged
    assert result.iterations == 2
    assert result.value == 0.25
    assert result.steps[-1].fx == 0.0
    assert result.book_text().splitlines()[-1] == (
        "THE VALUE, X =   .2500000 IS A ROOT.   2 ITERATIONS WERE REQUIRED."
    )


def test_non_convergence_keeps_partial_steps() -> None:
    with pytest.raises(NonConvergenceError) as info:
        bisection(book_f, *BOOK_CARD[:2], 1e-12)
    error = info.value
    assert error.code == "NON_CONVERGENT"
    assert error.message == "NON-CONVERGENT IN 25 ITERATIONS."
    assert error.message == msg_non_convergent()
    assert len(error.steps) == 25
    assert all(isinstance(step, BisectionStep) for step in error.steps)
    assert error.book_output is not None
    lines = error.book_output.splitlines()
    assert len(lines) == 26
    assert lines[0] == "AT X =   .5000000 F(X) =   -.100576"
    assert lines[-1] == "NON-CONVERGENT IN 25 ITERATIONS."


def test_non_convergence_with_other_limit() -> None:
    with pytest.raises(NonConvergenceError, match=r"^NON-CONVERGENT IN 3 ITERATIONS\.$") as info:
        bisection(book_f, 0.0, 1.0, 1e-5, max_iter=3)
    assert len(info.value.steps) == 3
    with pytest.raises(NonConvergenceError, match="IN 0 ITERATIONS"):
        bisection(book_f, 0.0, 1.0, 1e-5, max_iter=0)


@pytest.mark.parametrize("max_iter", [-1, 2.5, True])
def test_invalid_max_iter(max_iter: object) -> None:
    with pytest.raises(InputError, match="max_iter"):
        bisection(book_f, 0.0, 1.0, 1e-5, max_iter=max_iter)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_x", [0.0, 0.5])
def test_nan_function_values_are_rejected(bad_x: float) -> None:
    def f(x: float) -> float:
        return math.nan if x == bad_x else x - 0.3

    with pytest.raises(InputError, match="not a number"):
        bisection(f, 0.0, 1.0, 1e-9)


def test_reversed_bracket_and_integer_inputs() -> None:
    result = bisection(book_f, 1, 0, 1e-5)
    assert result.iterations == 15
    assert result.value == pytest.approx(0.4435729, abs=1e-7)
    assert isinstance(result.x1, float)


def test_expression_errors_propagate() -> None:
    from gerald_na.errors import ExpressionError

    with pytest.raises(ExpressionError, match="domain"):
        bisection(compile_expr("sqrt(x) - 0.5"), -1.0, 1.0, 1e-5)


def test_result_is_frozen(book_result: BisectionResult) -> None:
    with pytest.raises(AttributeError):
        book_result.value = 1.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        book_result.steps[0].x = 1.0  # type: ignore[misc]


bracket_offsets = st.floats(min_value=1e-3, max_value=50.0, allow_nan=False)


@given(
    r=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False),
    left=bracket_offsets,
    right=bracket_offsets,
    tol=st.sampled_from([1e-2, 1e-5, 1e-8, 1e-12]),
)
def test_property_bracketed_polynomial(r: float, left: float, right: float, tol: float) -> None:
    a, b = r - left, r + right
    assume(a < r < b)

    def f(x: float) -> float:
        return (x - r) * (x * x + 1.0)

    try:
        result = bisection(f, a, b, tol)
    except NonConvergenceError as error:
        steps = error.steps
        assert len(steps) == BOOK_MAX_ITER
        last = steps[-1]
        assert isinstance(last, BisectionStep)
        # 25 halvings shrink the bracket by 2**24 at the start of the last pass.
        assert last.x2 - last.x1 == pytest.approx((b - a) / 2**24, rel=1e-6)
        assert last.x1 <= r <= last.x2
        assert abs(f(last.x)) > tol
        return
    assert result.converged
    assert abs(f(result.value)) <= tol
    assert a <= result.value <= b
    check_bracket_invariant(result.steps, r, f)


def check_bracket_invariant(
    steps: tuple[BisectionStep, ...], r: float, f: Callable[[float], float]
) -> None:
    width = None
    for step in steps:
        assert step.x1 <= r <= step.x2
        assert step.x == (step.x1 + step.x2) / 2.0
        assert step.fx == f(step.x)
        if width is not None:
            assert step.x2 - step.x1 == pytest.approx(width / 2, rel=1e-9)
        width = step.x2 - step.x1
