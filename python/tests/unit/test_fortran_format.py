"""Fortran edit-descriptor rendering, checked against gfortran 16 output and the book scans."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gerald_na.algorithms._fortran_format import (
    Rounding,
    format_e,
    format_es,
    format_f,
    format_i,
)

INF = math.inf
NAN = math.nan

# Expected strings below were produced by gfortran 16 (``print '(<descriptor>)', value``), which
# prints the optional leading zero whenever it fits: hence ``leading_zero=True`` in those cases.


@pytest.mark.parametrize(
    ("value", "w", "d", "rounding", "expected"),
    [
        (0.125, 5, 2, Rounding.NEAREST, " 0.12"),  # ties to even on the exact binary value
        (0.375, 5, 2, Rounding.NEAREST, " 0.38"),
        (0.125, 5, 2, Rounding.COMPATIBLE, " 0.13"),  # ties away from zero
        (0.5, 10, 0, Rounding.NEAREST, "        0."),
        (1.5, 10, 0, Rounding.NEAREST, "        2."),
        (2.5, 10, 0, Rounding.NEAREST, "        2."),
        (0.4, 5, 0, Rounding.NEAREST, "   0."),  # d = 0: the zero is mandatory
        (3.0, 5, 0, Rounding.NEAREST, "   3."),
        (-0.0, 6, 3, Rounding.NEAREST, "-0.000"),  # negative zero keeps its sign
        (-0.0001, 6, 3, Rounding.NEAREST, "-0.000"),  # so does a negative value rounding to 0
        (0.5, 4, 3, Rounding.NEAREST, ".500"),  # no room for the optional zero
        (-0.5, 4, 3, Rounding.NEAREST, "****"),  # "-.500" does not fit
        (-12.5, 0, 3, Rounding.NEAREST, "-12.500"),  # F0.d: minimal width
        (0.5, 0, 3, Rounding.NEAREST, ".500"),  # F0.d never prints the optional zero
        (0.0, 0, 0, Rounding.NEAREST, "0."),
        (123.456, 6, 2, Rounding.NEAREST, "123.46"),
        (123.456, 5, 2, Rounding.NEAREST, "*****"),
        (0.29, 5, 1, Rounding.ZERO, "  0.2"),
        (-0.29, 5, 1, Rounding.ZERO, " -0.2"),
        (0.21, 5, 1, Rounding.UP, "  0.3"),
        (-0.29, 5, 1, Rounding.UP, " -0.2"),
        (0.29, 5, 1, Rounding.DOWN, "  0.2"),
        (-0.21, 5, 1, Rounding.DOWN, " -0.3"),
        (-0.25, 5, 1, Rounding.COMPATIBLE, " -0.3"),
        (-0.25, 5, 1, Rounding.NEAREST, " -0.2"),
    ],
)
def test_format_f_matches_gfortran(
    value: float, w: int, d: int, rounding: Rounding, expected: str
) -> None:
    assert format_f(value, w, d, rounding=rounding, leading_zero=True) == expected


@pytest.mark.parametrize(
    ("value", "w", "d", "expected"),
    [
        # Book style (scan of Chapter 1, Program 1): no optional zero, truncation.
        (0.5, 10, 7, "  .5000000"),
        (0.443572998046875, 10, 7, "  .4435729"),
        (0.443359375, 10, 7, "  .4433593"),
        (-0.10057611200048755, 10, 6, "  -.100576"),
        (0.3961173568951292, 10, 6, "   .396117"),
        (0.0, 6, 3, "  .000"),
        (1.0, 6, 3, " 1.000"),
        (-1.0e-9, 10, 6, "  -.000000"),  # gfortran RZ: " -0.000000"
    ],
)
def test_format_f_book_style(value: float, w: int, d: int, expected: str) -> None:
    assert format_f(value, w, d, rounding=Rounding.ZERO) == expected


def test_format_f_sign_plus() -> None:
    assert format_f(1.5, 6, 2, sign_plus=True, leading_zero=True) == " +1.50"
    assert format_f(0.5, 6, 2, sign_plus=True, leading_zero=True) == " +0.50"
    assert format_f(0.5, 6, 2, sign_plus=True) == "  +.50"


@pytest.mark.parametrize(
    ("value", "w", "expected"),
    [
        (INF, 10, "  Infinity"),
        (INF, 8, "Infinity"),
        (-INF, 9, "-Infinity"),
        (-INF, 8, "    -Inf"),
        (-INF, 4, "-Inf"),
        (-INF, 3, "***"),
        (INF, 3, "Inf"),
        (INF, 2, "**"),
        (NAN, 5, "  NaN"),
        (NAN, 2, "**"),
        (INF, 0, "Infinity"),
        (NAN, 0, "NaN"),
    ],
)
def test_non_finite_values(value: float, w: int, expected: str) -> None:
    assert format_f(value, w, 3) == expected
    if w:
        assert format_e(value, w, 3) == expected
        assert format_es(value, w, 3) == expected


def test_non_finite_sign_plus() -> None:
    assert format_f(INF, 9, 1, sign_plus=True) == "+Infinity"


@pytest.mark.parametrize(
    ("value", "w", "d", "e", "expected"),
    [
        (0.99999, 12, 4, None, "  0.1000E+01"),  # rounding carries into the exponent
        (1234.5, 9, 4, None, ".1234E+04"),  # ties to even; no room for the zero
        (1.0e-150, 12, 4, None, "  0.1000-149"),  # three-digit exponent drops the letter
        (1.0e100, 12, 4, None, "  0.1000+101"),
        (0.0, 12, 4, None, "  0.0000E+00"),
        (-0.0, 10, 3, None, "-0.000E+00"),
        (0.5, 8, 3, None, ".500E+00"),
        (12.0, 12, 4, 3, " 0.1200E+002"),
        (1.0e-150, 12, 4, 2, "************"),  # exponent -149 does not fit E2
        (1.0e15, 10, 2, 1, "**********"),
        (123.0, 5, 2, None, "*****"),
    ],
)
def test_format_e_matches_gfortran(
    value: float, w: int, d: int, e: int | None, expected: str
) -> None:
    assert format_e(value, w, d, e, leading_zero=True) == expected


def test_format_e_rounding_modes_match_gfortran() -> None:
    assert format_e(0.15, 10, 3, leading_zero=True) == " 0.150E+00"
    assert format_e(0.12349, 10, 3, rounding=Rounding.ZERO, leading_zero=True) == " 0.123E+00"
    assert format_e(-0.12341, 11, 3, rounding=Rounding.DOWN, leading_zero=True) == " -0.124E+00"
    assert format_e(-0.12349, 11, 3, rounding=Rounding.UP, leading_zero=True) == " -0.123E+00"
    assert format_e(9.5, 10, 1, sign_plus=True, leading_zero=True) == "  +0.1E+02"


def test_format_e_book_style_omits_leading_zero() -> None:
    assert format_e(0.15, 10, 3) == "  .150E+00"
    assert format_e(-0.15, 9, 3) == "-.150E+00"


@pytest.mark.parametrize(
    ("value", "w", "d", "e", "expected"),
    [
        (0.0, 12, 4, None, "  0.0000E+00"),
        (0.1, 25, 17, 3, " 1.00000000000000006E-001"),  # the trace protocol's format
        (9.99996, 12, 4, None, "  1.0000E+01"),
        (1.0e-300, 12, 4, None, "  1.0000-300"),
        (1.0e15, 12, 4, 1, "************"),
        (-2.5, 10, 0, None, "   -2.E+00"),
        (-1.0e-5, 25, 17, 3, "-1.00000000000000008E-005"),
    ],
)
def test_format_es_matches_gfortran(
    value: float, w: int, d: int, e: int | None, expected: str
) -> None:
    assert format_es(value, w, d, e) == expected


def test_format_es_rounding_and_sign() -> None:
    assert format_es(1.99, 10, 1, rounding=Rounding.ZERO) == "   1.9E+00"
    assert format_es(1.5, 10, 2, sign_plus=True) == " +1.50E+00"


@pytest.mark.parametrize(
    ("value", "w", "m", "expected"),
    [
        (-42, 5, None, "  -42"),
        (7, 5, 3, "  007"),
        (0, 3, 0, "   "),  # Iw.0 prints zero as blanks
        (123, 2, None, "**"),
        (-123, 0, None, "-123"),  # I0: minimal width
        (15, 3, None, " 15"),
        (5, 0, 3, "005"),
    ],
)
def test_format_i_matches_gfortran(value: int, w: int, m: int | None, expected: str) -> None:
    assert format_i(value, w, m) == expected


def test_format_i_sign_plus() -> None:
    assert format_i(5, 4, sign_plus=True) == "  +5"


@pytest.mark.parametrize(
    "call",
    [
        lambda: format_f(1.0, -1, 2),
        lambda: format_f(1.0, 5, -1),
        lambda: format_e(1.0, 0, 2),
        lambda: format_e(1.0, 10, 0),
        lambda: format_e(1.0, 10, 2, 0),
        lambda: format_es(1.0, 10, 2, 0),
        lambda: format_i(1, -1),
        lambda: format_i(1, 3, 4),
        lambda: format_i(1, 3, -1),
    ],
)
def test_invalid_descriptors_are_rejected(call: object) -> None:
    assert callable(call)
    with pytest.raises(ValueError, match=r"invalid|needs"):
        call()


finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e15, max_value=1e15)


@given(value=finite, d=st.integers(min_value=0, max_value=12))
def test_format_f_nearest_agrees_with_python(value: float, d: int) -> None:
    # Python's fixed-point formatting also rounds the exact binary value half-to-even.
    python = f"{abs(value):.{d}f}"
    if d == 0:
        python += "."
    sign = "-" if math.copysign(1.0, value) < 0 else ""
    assert format_f(value, 0, d, leading_zero=True).lstrip() in {
        sign + python,
        sign + python.removeprefix("0"),
    }


@given(value=st.floats(allow_nan=False, allow_infinity=False), d=st.integers(1, 17))
def test_format_es_nearest_agrees_with_python(value: float, d: int) -> None:
    mantissa, exponent = f"{value:.{d}e}".split("e")
    expected = f"{mantissa}E{int(exponent):+04d}"
    assert format_es(value, 40, d, 3) == expected.rjust(40)


@given(value=finite, w=st.integers(1, 30), d=st.integers(0, 10))
def test_format_f_has_width_w(value: float, w: int, d: int) -> None:
    for rounding in Rounding:
        assert len(format_f(value, w, d, rounding=rounding)) == w


@given(value=finite, d=st.integers(1, 10))
def test_truncation_never_exceeds_magnitude(value: float, d: int) -> None:
    text = format_f(value, 0, d, rounding=Rounding.ZERO)
    assert abs(float(text)) <= abs(value)
