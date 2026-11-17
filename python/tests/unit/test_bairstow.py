"""Unit and property tests of :mod:`gerald_na.algorithms.bairstow` (Ch. 1, Program 2).

NumPy is used only as an independent reference (``numpy.polymul``, ``numpy.roots``).
"""

import math
from collections.abc import Sequence
from typing import cast

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from gerald_na.algorithms import Rounding
from gerald_na.algorithms.bairstow import (
    BairstowFactor,
    BairstowResult,
    BairstowStep,
    bairstow,
    factor_roots,
    msg_degree_out_of_range,
    msg_high_coefficient,
    msg_non_convergent,
)
from gerald_na.engines import PythonEngine, RunRequest
from gerald_na.engines.adapters.bairstow import factor_from_record
from gerald_na.engines.trace import parse_trace
from gerald_na.errors import DegreeError, FortranRunError, InputError, NonConvergenceError
from gerald_na.registry import get_registry

BOOK = (0.0, 1.0, -17.8, 99.41, -261.218, 352.611, -134.106)

BOOK_TEXT_REAL64 = """\
 DEMONSTRATION PROGRAM OUTPUT


THE ORIGINAL POLYNOMIAL-

    POWER OF X     COEFFICIENT

          5           1.00000
          4         -17.80000
          3          99.41000
          2        -261.21800
          1         352.61100
          0        -134.10600


THE QUADRATIC FACTORS ARE-

X**2 +    4.19999 X +   -2.09999
X**2 +    3.30000 X +   -6.20000
   1.00000X +  -10.30000
"""


def run_book(**overrides: object) -> BairstowResult:
    args: dict[str, object] = {"r1": 0.0, "s1": 0.0, "test": 1e-5, "lim": 20, "n": 5}
    args.update(overrides)
    coeffs = args.pop("coeffs", BOOK)
    return bairstow(coeffs, **args)  # type: ignore[arg-type]


def card(*coefficients: float) -> tuple[float, ...]:
    """Seven coefficients X**6 ... X**0 from the given highest-first coefficients."""
    return (0.0,) * (7 - len(coefficients)) + tuple(float(c) for c in coefficients)


def product_of_factors(factors: Sequence[BairstowFactor]) -> np.ndarray:
    product = np.array([1.0])
    for factor in factors:
        product = np.polymul(product, np.array(factor.true_coefficients()))
    return np.trim_zeros(product, "f")


# ---------------------------------------------------------------- the book's data cards


def test_book_card_factors() -> None:
    result = run_book()
    assert result.converged
    assert result.value == 3
    assert [f.kind for f in result.factors] == ["quadratic", "quadratic", "linear"]
    exact = ((4.2, -2.1), (3.3, -6.2), (1.0, -10.3))
    for row, want in zip(result.factor_table, exact, strict=True):
        assert row == pytest.approx(want, abs=1e-8)
    assert result.nudges == 0


def test_book_card_iterations() -> None:
    result = run_book()
    assert result.iterations == 13 == len(result.steps)
    assert result.factor_iterations(1) == 8
    assert result.factor_iterations(2) == 5
    assert [step.k for step in result.steps] == [*range(1, 9), *range(1, 6)]


def test_book_text_reproduces_the_scan_layout() -> None:
    result = run_book()
    assert result.book_text() == BOOK_TEXT_REAL64
    with_cc = result.book_text(carriage_control=True)
    assert with_cc.splitlines()[0] == "  DEMONSTRATION PROGRAM OUTPUT"
    assert all(line == "" or line.startswith(" ") for line in with_cc.splitlines())


def test_book_text_differs_from_the_scan_only_in_the_documented_digit() -> None:
    entry = get_registry().get("ch01_p02")
    printed = entry.book_output.strip("\n").splitlines()
    ours = run_book().book_text().splitlines()
    assert ours[0] == " DEMONSTRATION PROGRAM OUTPUT"  # on a new page in the book
    differing = [(a, b) for a, b in zip(ours[3:], printed, strict=True) if a != b]
    assert differing == [("X**2 +    3.30000 X +   -6.20000", "X**2 +    3.29999 X +   -6.20000")]


def test_book_text_rounding_mode() -> None:
    lines = run_book().book_text(rounding=Rounding.NEAREST).splitlines()
    assert lines[-3] == "X**2 +    4.20000 X +   -2.10000"
    assert run_book().factors[0].book_line() == "X**2 +    4.19999 X +   -2.09999"


def test_step_recurrence_and_warm_start() -> None:
    result = run_book()
    r = s = 0.0
    for step in result.steps:
        assert step.r == step.delr + r
        assert step.s == step.dels + s
        r, s = step.r, step.s
    # the second factor starts from the first factor's R and S (not from R1, S1)
    second = result.steps[8]
    assert second.factor == 2
    assert second.r - second.delr == result.factors[0].coefficients[0]


def test_convergence_test_accepts_equality() -> None:
    """IF (ABSF(DELR) + ABSF(DELS) - TEST) 12, 12, 13: the zero branch converges."""

    def steps_for(test: float) -> tuple[BairstowStep, ...]:
        try:
            return run_book(test=test).steps
        except NonConvergenceError as error:
            return cast("tuple[BairstowStep, ...]", error.steps)

    first = run_book().steps[0]
    test = abs(first.delr) + abs(first.dels)
    equal = steps_for(test)
    below = steps_for(math.nextafter(test, 0.0))
    assert [step.factor for step in equal[:2]] == [1, 2]  # accepted at step 1
    assert [step.factor for step in below[:2]] == [1, 1]  # not accepted


# ---------------------------------------------------------------- singular denominator


def test_singular_denominator_nudges_the_working_r_and_s() -> None:
    coeffs = card(1, 0, 0, 0, -16)
    # at R = S = 0, C(J) = A(J): DENOM = A(7)**2 - A(8)*A(6) = 0 exactly
    assert coeffs[4] * coeffs[4] - coeffs[5] * coeffs[3] == 0.0
    result = bairstow(coeffs, 0.0, 0.0, 1e-5, 20, 4)
    assert result.nudges == 1
    assert result.iterations == 11
    first = result.steps[0]
    assert (first.k, first.r - first.delr, first.s - first.dels) == (1, 1.0, 1.0)
    assert result.factors[0].coefficients == pytest.approx((0.0, 4.0), abs=1e-8)
    assert result.factors[1].kind == "final_quadratic"
    assert result.factors[1].coefficients == pytest.approx((1.0, 0.0, 4.0), abs=1e-8)


def test_singular_cubic_needs_more_than_lim() -> None:
    coeffs = card(1, 0, 0, -8)
    with pytest.raises(NonConvergenceError) as info:
        bairstow(coeffs, 0.0, 0.0, 1e-5, 20, 3)
    assert len(info.value.steps) == 20
    result = bairstow(coeffs, 0.0, 0.0, 1e-5, 50, 3)
    assert (result.nudges, result.iterations) == (1, 26)
    assert result.factors[0].coefficients == pytest.approx((-2.0, -4.0), abs=1e-8)
    assert result.factors[1].coefficients == pytest.approx((1.0, -2.0), abs=1e-6)


def test_nudge_guard_stops_an_all_zero_polynomial() -> None:
    with pytest.raises(NonConvergenceError) as info:
        bairstow((0.0,) * 7, 0.0, 0.0, 1e-5, 20, 4)
    assert info.value.message == msg_non_convergent(20)
    assert info.value.steps == ()


# ---------------------------------------------------------------- non-convergence within LIM


@pytest.mark.parametrize("lim", [3, 7])
def test_non_convergent_within_lim(lim: int) -> None:
    with pytest.raises(NonConvergenceError) as info:
        run_book(lim=lim)
    error = info.value
    assert error.code == "NON_CONVERGENT"
    assert error.message == f"DOES NOT CONVERGE AFTER {lim:4d} ITERATIONS"
    assert len(error.steps) == lim
    assert error.book_output is not None
    lines = error.book_output.splitlines()
    assert lines[-1] == error.message
    assert lines[-2] == ""  # no factor was found before the failure
    assert "THE QUADRATIC FACTORS ARE-" in lines


def test_lim_bounds_each_factor() -> None:
    assert run_book(lim=8).iterations == 13
    assert run_book(r1=4.2, s1=-2.1, lim=5).iterations == 6
    with pytest.raises(NonConvergenceError) as info:
        run_book(r1=4.2, s1=-2.1, lim=4)
    assert len(info.value.steps) == 5
    assert info.value.book_output is not None
    assert info.value.book_output.splitlines()[-2].startswith("X**2 +    4.")


def test_lim_zero_allows_one_correction() -> None:
    with pytest.raises(NonConvergenceError) as info:
        run_book(lim=0)
    assert len(info.value.steps) == 1
    assert info.value.message == "DOES NOT CONVERGE AFTER    0 ITERATIONS"


def test_overflow_to_nan_is_non_convergence() -> None:
    with pytest.raises(NonConvergenceError):
        bairstow(card(1e300, 1e300, 1e300), 1e200, 1e200, 1e-5, 5, 2)


# ---------------------------------------------------------------- degree branches


def test_degree_2_prints_the_constant_quotient() -> None:
    result = bairstow(card(2, -6, 4), 0.0, 0.0, 1e-5, 20, 2)
    assert [f.kind for f in result.factors] == ["quadratic", "linear"]
    assert result.factors[0].coefficients == pytest.approx((3.0, -2.0))
    assert result.factors[1].coefficients == (0.0, 2.0)
    assert result.book_text().splitlines()[-1] == "    .00000X +    2.00000"
    assert factor_roots(result.factors[1]) == ()


def test_degree_3_ends_with_a_linear_factor() -> None:
    result = bairstow(card(1, -6, 11, -6), 0.0, 0.0, 1e-5, 20, 3)
    assert (result.value, result.iterations) == (2, 8)
    assert result.factors[1].kind == "linear"
    assert result.factors[1].coefficients == pytest.approx((1.0, -3.0), abs=1e-6)


def test_degree_4_ends_with_a_final_quadratic() -> None:
    result = bairstow(card(1, -10, 35, -50, 24), 0.0, 0.0, 1e-5, 20, 4)
    assert (result.value, result.iterations) == (2, 11)
    assert result.factors[1].kind == "final_quadratic"
    assert result.factors[1].coefficients == pytest.approx((1.0, -5.0, 6.0), abs=1e-6)
    assert result.book_text().splitlines()[-1].endswith("X + ") is False
    assert "X**2 + " in result.book_text().splitlines()[-1]


def test_degree_6_three_factors() -> None:
    coeffs = tuple(float(c) for c in np.poly([1, 2, 3, 4, 5, 6]))
    result = bairstow(coeffs, 0.0, 0.0, 1e-5, 50, 6)
    assert [f.kind for f in result.factors] == ["quadratic", "quadratic", "final_quadratic"]
    roots = sorted(root.real for f in result.factors for root in factor_roots(f))
    assert roots == pytest.approx([1, 2, 3, 4, 5, 6], abs=1e-5)


def test_book_card_with_n_6_has_a_zero_leading_final_quadratic() -> None:
    result = run_book(n=6)
    assert result.factors[-1].kind == "final_quadratic"
    assert result.factors[-1].coefficients == pytest.approx((0.0, 1.0, -10.3))
    assert factor_roots(result.factors[-1]) == pytest.approx((10.3 + 0j,))


@pytest.mark.parametrize("n", [-1, 0, 1, 7, 99])
def test_degree_out_of_range(n: int) -> None:
    with pytest.raises(DegreeError) as info:
        run_book(n=n)
    assert info.value.code == "DEGREE"
    assert info.value.message == msg_degree_out_of_range(n)
    assert info.value.book_output == (
        f" DEMONSTRATION PROGRAM OUTPUT\nDEGREE N = {n} IS OUTSIDE 2 TO 6.\n"
    )


def test_nonzero_coefficient_above_n() -> None:
    with pytest.raises(DegreeError) as info:
        run_book(n=4)
    assert info.value.message == msg_high_coefficient(5, 4)
    assert info.value.message == "COEFFICIENT OF X**5 IS NOT ZERO BUT N = 4."


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"coeffs": BOOK[:6]}, "seven|7 coefficients"),
        ({"coeffs": "0 1 2 3 4 5 6"}, "7 coefficients"),
        ({"coeffs": (*BOOK[:6], math.nan)}, "finite"),
        ({"r1": math.inf}, "finite"),
        ({"test": "1e-5"}, "real number"),
        ({"lim": 20.0}, "integer"),
        ({"n": True}, "integer"),
    ],
)
def test_input_errors(overrides: dict[str, object], match: str) -> None:
    with pytest.raises(InputError, match=match):
        run_book(**overrides)


# ---------------------------------------------------------------- roots, verbose text, adapter


def test_factor_roots_and_true_coefficients() -> None:
    real = BairstowFactor("quadratic", (4.2, -2.1))
    assert real.true_coefficients() == (1.0, -4.2, 2.1)
    assert sorted(z.real for z in factor_roots(real)) == pytest.approx(
        sorted(np.roots([1.0, -4.2, 2.1]).real)
    )
    pair = factor_roots(BairstowFactor("quadratic", (3.3, -6.2)))
    assert pair[0] == pytest.approx(complex(1.65, math.sqrt(3.4775)))
    assert pair[1] == pair[0].conjugate()
    assert factor_roots(BairstowFactor("final_quadratic", (2.0, -10.0, 12.0))) == (3 + 0j, 2 + 0j)
    assert factor_roots(BairstowFactor("linear", (1.0, -10.3))) == (10.3 + 0j,)
    assert factor_roots(BairstowFactor("linear", (0.0, 1.0))) == ()


def test_verbose_text() -> None:
    text = run_book().verbose_text()
    lines = text.splitlines()
    assert lines[0] == "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"
    assert "  TRUE FACTOR X**2 - R X - S = X**2 +     -4.200000 X +      2.100000" in lines
    assert "  ROOT       1.650000     +1.864806i" in lines
    assert "  ROOT      10.300000" in lines
    assert lines[-1] == "TOTAL ITERATIONS = 13"
    constant = bairstow(card(1, -3, 2), 0.0, 0.0, 1e-5, 20, 2).verbose_text()
    assert "  NO ROOT (CONSTANT FACTOR)" in constant.splitlines()
    final = bairstow(card(1, -10, 35, -50, 24), 0.0, 0.0, 1e-5, 20, 4).verbose_text()
    assert "FINAL QUADRATIC" in final


def test_python_engine_runs_the_catalog_entry_with_verbose() -> None:
    entry = get_registry().get("ch01_p02")
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, verbose=True))
    assert outcome.ok
    assert outcome.verbose_text.startswith("VERBOSE OUTPUT")
    assert outcome.result.book_text() == outcome.book_text


def test_catalog_entry_matches_the_book() -> None:
    entry = get_registry().get("ch01_p02")
    assert entry.data_card.tokens() == [
        "0.", "1.", "-17.8", "99.41", "-261.218", "352.611", "-134.106",
        "0.", "0.", "1.E-5", "20", "5",
    ]  # fmt: skip
    assert entry.defaults()["a"] == BOOK
    assert entry.book_output.splitlines()[-1] == "   1.00000X +  -10.30000"
    assert [c.key for c in entry.trace.step_columns] == ["factor", "k", "r", "s", "delr", "dels"]
    assert not entry.function.takes_function


def test_factor_records() -> None:
    trace = parse_trace(
        "FACTOR,kind=quadratic,r=1.0E+000,s=2.0E+000\n"
        "FACTOR,kind=linear,a1=1.0E+000,a0=-3.0E+000\n"
        "RESULT,value=2,converged=T,iterations=0,nudges=0\n"
    )
    factors = [factor_from_record(r) for r in trace.of_type("FACTOR")]
    assert factors == [
        BairstowFactor("quadratic", (1.0, 2.0)),
        BairstowFactor("linear", (1.0, -3.0)),
    ]
    for bad in ("FACTOR,kind=cubic,r=1.0", "FACTOR,kind=linear,a1=1.0", "FACTOR,kind=linear"):
        record = parse_trace(bad + "\nRESULT,value=1,converged=T,iterations=0\n").records[0]
        with pytest.raises(FortranRunError):
            factor_from_record(record)


# ---------------------------------------------------------------- property tests (NumPy reference)


@st.composite
def separated_real_roots(draw: st.DrawFn) -> tuple[int, float, list[float]]:
    """Degree 2..6, a leading coefficient and distinct roots at least 0.5 apart in [-5, 5]."""
    degree = draw(st.integers(min_value=2, max_value=6))
    grid = [x / 2 for x in range(-10, 11)]
    roots = draw(st.lists(st.sampled_from(grid), min_size=degree, max_size=degree, unique=True))
    lead = draw(st.sampled_from([1.0, -1.0, 0.5, 2.0, 3.0]))
    return degree, lead, roots


@settings(max_examples=200, deadline=None)
@given(separated_real_roots())
def test_factors_reconstruct_the_polynomial(case: tuple[int, float, list[float]]) -> None:
    degree, lead, roots = case
    reference = lead * np.poly(roots)
    coeffs = card(*(float(c) for c in reference))
    try:
        result = bairstow(coeffs, 0.0, 0.0, 1e-10, 100, degree)
    except NonConvergenceError:
        assume(False)  # rare from R = S = 0 (about 1 in 3000 such polynomials)
        raise
    assert result.value == degree // 2 + (1 if degree % 2 or degree == 2 else 0)
    product = product_of_factors(result.factors)
    scale = float(np.max(np.abs(reference)))
    assert product == pytest.approx(reference, abs=1e-7 * scale)
    found = sorted(z.real for f in result.factors for z in factor_roots(f))
    assert all(abs(z.imag) == 0.0 for f in result.factors for z in factor_roots(f))
    assert found == pytest.approx(sorted(np.roots(reference).real), abs=1e-6)


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False),
        min_size=7,
        max_size=7,
    ),
    st.integers(min_value=2, max_value=6),
)
def test_random_cards_either_factor_or_fail_cleanly(coeffs: list[float], n: int) -> None:
    """Arbitrary cards end in a result or a typed error, never a hang or a crash."""
    coeffs[: 6 - n] = [0.0] * (6 - n)
    failure: NonConvergenceError | None = None
    try:
        result = bairstow(coeffs, 0.0, 0.0, 1e-5, 30, n)
    except NonConvergenceError as error:
        failure = error
    if failure is not None:
        assert failure.book_output is not None
        assert failure.book_output.splitlines()[-1] == msg_non_convergent(30)
        return
    assert result.iterations == len(result.steps)
    assert result.factors[-1].kind in ("linear", "final_quadratic")


def test_factor_named_coefficients_follow_the_listing_names() -> None:
    from gerald_na.algorithms.bairstow import (
        FACTOR_COEFFICIENT_NAMES,
        FACTOR_FORMS,
        BairstowFactor,
    )

    quadratic = BairstowFactor("quadratic", (4.2, -2.1))
    assert quadratic.named_coefficients() == {"r": 4.2, "s": -2.1}
    assert quadratic.form == "X**2 + R X + S"
    final = BairstowFactor("final_quadratic", (1.0, -3.3, 6.2))
    assert final.named_coefficients() == {"a2": 1.0, "a1": -3.3, "a0": 6.2}
    assert final.form == "A2 X**2 + A1 X + A0"
    linear = BairstowFactor("linear", (1.0, -10.3))
    assert linear.named_coefficients() == {"a1": 1.0, "a0": -10.3}
    assert linear.form == "A1 X + A0"
    assert (
        set(FACTOR_COEFFICIENT_NAMES)
        == set(FACTOR_FORMS)
        == {
            "quadratic",
            "final_quadratic",
            "linear",
        }
    )
    with pytest.raises(ValueError, match="zip"):
        BairstowFactor("linear", (1.0, 2.0, 3.0)).named_coefficients()


def test_factor_names_match_the_catalog_factor_record() -> None:
    from gerald_na.algorithms.bairstow import FACTOR_COEFFICIENT_NAMES
    from gerald_na.registry import get_registry

    record = next(r for r in get_registry().get("ch01_p02").trace.records if r.type == "FACTOR")
    names = {name for names in FACTOR_COEFFICIENT_NAMES.values() for name in names}
    assert names == set(record.fields) - {"kind"}


def test_only_lagrange_declares_a_count_input() -> None:
    from gerald_na.engines.adapters import adapters

    declared = {pid: dict(a.count_inputs) for pid, a in adapters().items() if a.count_inputs}
    assert declared == {"lagrange_interpolation": {"n": "points"}}
