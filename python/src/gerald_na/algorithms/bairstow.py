"""Chapter 1, Program 2: quadratic factors of polynomials to sixth degree, Bairstow method.

A line-by-line port of the listing in ``docs/chapter_01_program_02_listing.pdf`` (book p. 25,
output p. 26). The original control flow, transcribed from the scan, is::

          READ 1, (A(I), I = 3,9)            card 1: coefficients of X**6 ... X**0
          READ 2, R1, S1, TEST, LIM, N       card 2
          B(1) = 0., B(2) = 0., C(1) = 0., C(2) = 0.
          R = R1
          S = S1
       11 KOUNT = 1
       16 DO 8 J = 3,9
          B(J) = A(J) + R*B(J - 1) + S*B(J - 2)
        8 C(J) = B(J) + R*C(J - 1) + S*C(J - 2)
          DENOM = C(7)*C(7) - C(8)*C(6)
          IF ( DENOM) 9, 10, 9
       10 R1 = R1 + 1.                       original bug: R, S never reloaded (see ERRATA)
          S1 = S1 + 1.
          GO TO 11
        9 DELR = (-B(8)*C(7) + C(6)*B(9))/DENOM
          DELS = (-C(7)*B(9) + B(8)*C(8))/DENOM
          R = DELR + R
          S = DELS + S
          IF ( ABSF(DELR) + ABSF(DELS) - TEST) 12, 12, 13
       13 IF (KOUNT - LIM) 14, 15, 15
       15 PRINT 24, LIM                      -> NonConvergenceError
       14 KOUNT = KOUNT + 1
          GO TO 16
       12 PRINT 17, R, S                     quadratic factor (printed X**2 + R X + S)
          N = N - 2
          IF (N - 2) 18, 19, 20
       20 DO 21 K = 3,9
       21 A(K) = B(K - 2)                    reduced polynomial, R and S carried over
          GO TO 11
       19 PRINT 22, B(5), B(6), B(7)         final quadratic factor
       18 PRINT 23, B(6), B(7)               final linear factor

ERRATA (details in ``catalog/ch01_p02_bairstow.toml`` and the Fortran driver's header):

* Genuine bug in the original: label 10 bumps ``R1``/``S1`` and jumps to label 11, which never
  reloads ``R`` and ``S``, so an exactly zero ``DENOM`` looped forever. The port bumps the
  working ``R`` and ``S`` (the book's text: "the r and s values are arbitrarily incremented by
  one") and restarts ``KOUNT`` at 1 as ``GO TO 11`` does. ``DENOM`` is tested for an exact zero,
  like the arithmetic IF (the earlier rewrite used an epsilon).
* Modernization guard: more than ``max(LIM, 0)`` nudges during one factor (``DENOM`` staying
  zero, e.g. an all-zero polynomial) raise :class:`NonConvergenceError` with message 24.
* Modernization: ``N`` outside 2..6, or a nonzero coefficient of a power above ``N``, raise
  :class:`DegreeError` (the book has no check).
* Original quirk, kept: FORMAT 17 prints ``X**2 + R X + S`` but the recurrence divides by
  ``X**2 - R X - S``; the book's exact factors are x**2 - 4.2x + 2.1, x**2 - 3.3x + 6.2 and
  x - 10.3 for the printed 4.19999/-2.09999, 3.29999/-6.20000 and 1.00000X + -10.30000.
  :func:`factor_roots` and :meth:`BairstowResult.verbose_text` use the true factor.
* The book's machine chopped printed digits: the factor lines use ``Rounding.ZERO`` and no
  leading zero. The echoed data-card coefficients (exact decimals on the book's machine) are
  rounded to nearest, so 99.41 (99.40999... in binary) prints as 99.41000 like the book.
* The page eject of FORMAT 1000 (``1H1``) is written as a blank carriage-control column.

The book data card needs 8 + 5 = 13 corrections in real64 (and in real32).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from gerald_na.algorithms._fortran_format import Rounding, format_f, format_i
from gerald_na.errors import DegreeError, InputError, NonConvergenceError

__all__ = [
    "MAX_DEGREE",
    "MIN_DEGREE",
    "N_COEFFS",
    "BairstowFactor",
    "BairstowResult",
    "BairstowStep",
    "FactorKind",
    "bairstow",
    "factor_roots",
    "msg_degree_out_of_range",
    "msg_high_coefficient",
    "msg_non_convergent",
]

N_COEFFS = 7
"""``READ 1, (A(I), I = 3,9)``: the first card holds the coefficients of X**6 ... X**0."""
MIN_DEGREE = 2
MAX_DEGREE = 6

type FactorKind = Literal["quadratic", "final_quadratic", "linear"]

_FACTOR_ROUNDING = Rounding.ZERO
"""The book's line printer chopped the factor digits (4.19999, -2.09999)."""
_ECHO_ROUNDING = Rounding.NEAREST
"""The echoed card values were exact decimals on the book's machine; see the module ERRATA."""

# Book records (leading blank = carriage control). FORMAT 1000's page eject 1H1 is a blank.
_MSG_1000 = "  DEMONSTRATION PROGRAM OUTPUT"
_MSG_3 = " THE ORIGINAL POLYNOMIAL-"
_MSG_4 = "     POWER OF X     COEFFICIENT"
_MSG_7 = " THE QUADRATIC FACTORS ARE-"


def msg_non_convergent(lim: int) -> str:
    """``24 FORMAT (25H DOES NOT CONVERGE AFTER , I4, 11H ITERATIONS )`` (no leading blank)."""
    return f"DOES NOT CONVERGE AFTER {format_i(lim, 4)} ITERATIONS"


def msg_degree_out_of_range(n: int) -> str:
    """DEGREE error for ``N`` outside 2..6 (no book equivalent)."""
    return f"DEGREE N = {n} IS OUTSIDE {MIN_DEGREE} TO {MAX_DEGREE}."


def msg_high_coefficient(power: int, n: int) -> str:
    """DEGREE error for a nonzero coefficient of a power above ``N`` (no book equivalent)."""
    return f"COEFFICIENT OF X**{power} IS NOT ZERO BUT N = {n}."


@dataclass(frozen=True, slots=True)
class BairstowStep:
    """One Bairstow correction (one pass from label 16 to the TEST).

    ``factor`` is the 1-based index of the factor being searched, ``k`` the book's ``KOUNT``
    within it, ``r`` and ``s`` the values after the correction (``R = DELR + R``), ``delr`` and
    ``dels`` the corrections.
    """

    factor: int
    k: int
    r: float
    s: float
    delr: float
    dels: float


@dataclass(frozen=True, slots=True)
class BairstowFactor:
    """One printed factor.

    ``kind == "quadratic"``: ``coefficients = (r, s)`` as printed by FORMAT 17
    (``X**2 + r X + s``); the factor divided out is ``X**2 - r X - s``.
    ``kind == "final_quadratic"``: ``(a2, a1, a0)`` = B(5), B(6), B(7) (FORMAT 22).
    ``kind == "linear"``: ``(a1, a0)`` = B(6), B(7) (FORMAT 23).
    """

    kind: FactorKind
    coefficients: tuple[float, ...]

    def true_coefficients(self) -> tuple[float, ...]:
        """The factor's coefficients, highest power first (``(1, -r, -s)`` for a quadratic)."""
        if self.kind == "quadratic":
            r, s = self.coefficients
            return (1.0, -r, -s)
        return self.coefficients

    def book_line(self, *, rounding: Rounding = _FACTOR_ROUNDING) -> str:
        """The factor's line as printed (no carriage-control column)."""
        return _fmt_factor(self, rounding)[1:]


def factor_roots(factor: BairstowFactor) -> tuple[complex, ...]:
    """Roots of the true factor (0, 1 or 2 values), with the Fortran driver's arithmetic.

    A quadratic ``A2 X**2 + A1 X + A0`` (``1, -r, -s`` for a ``quadratic`` factor; a
    ``final_quadratic`` with ``A2 = 0`` is linear) has ``D = A1*A1 - 4*A2*A0`` and the roots
    ``(-A1 +- sqrt(D))/(2*A2)`` for ``D >= 0``, else ``-A1/(2*A2) +- i sqrt(-D)/(2*A2)``. A linear
    factor ``A1 X + A0`` has the root ``-A0/A1``, none when ``A1 = 0`` (a constant factor).
    """
    if factor.kind == "quadratic":
        a2, a1, a0 = 1.0, -factor.coefficients[0], -factor.coefficients[1]
        is_linear = False
    elif factor.kind == "final_quadratic":
        a2, a1, a0 = factor.coefficients
        is_linear = a2 == 0.0
    else:
        a2 = 0.0
        a1, a0 = factor.coefficients
        is_linear = True
    if is_linear:
        if a1 == 0.0:
            return ()
        return (complex(-a0 / a1, 0.0),)
    d = a1 * a1 - 4.0 * a2 * a0
    if d >= 0.0:
        return (
            complex((-a1 + math.sqrt(d)) / (2.0 * a2), 0.0),
            complex((-a1 - math.sqrt(d)) / (2.0 * a2), 0.0),
        )
    # D < 0, or NaN (math.sqrt(nan) is nan, as in Fortran).
    im = math.sqrt(-d) / (2.0 * a2)
    re = -a1 / (2.0 * a2)
    return (complex(re, im), complex(re, -im))


# The FORMAT statements of the listing. Each record starts with the carriage-control column.


def _fmt_coefficient(power: int, value: float) -> str:
    """``6 FORMAT (10X, I2, 8X, F10.5)``."""
    fixed = format_f(value, 10, 5, rounding=_ECHO_ROUNDING)
    return " " * 10 + format_i(power, 2) + " " * 8 + fixed


def _fmt_factor(factor: BairstowFactor, rounding: Rounding) -> str:
    """FORMAT 17, 22 or 23."""
    fixed = [format_f(c, 10, 5, rounding=rounding) for c in factor.coefficients]
    if factor.kind == "quadratic":
        return f" X**2 + {fixed[0]} X + {fixed[1]}"
    if factor.kind == "final_quadratic":
        return f" {fixed[0]}X**2 + {fixed[1]}X + {fixed[2]}"
    return f" {fixed[0]}X + {fixed[1]}"


def _render(records: list[str], carriage_control: bool) -> str:
    """Join records as printed: the line printer consumes the carriage-control column."""
    lines = records if carriage_control else [record[1:] for record in records]
    return "".join(line + "\n" for line in lines)


def _book_records(
    coeffs: Sequence[float], n: int, factors: Sequence[BairstowFactor], rounding: Rounding
) -> list[str]:
    """Records of PRINT 1000, 3, 4, the DO 5 loop, PRINT 7 and the factor lines."""
    records = [_MSG_1000, "", "", _MSG_3, "", _MSG_4, ""]
    # J = 9 - N; DO 5 I = J,9: A(I) is coeffs[I - 3], printed with M = 9 - I.
    records += [_fmt_coefficient(9 - i, coeffs[i - 3]) for i in range(9 - n, 10)]
    records += ["", "", _MSG_7, ""]
    records += [_fmt_factor(factor, rounding) for factor in factors]
    return records


def _f14(value: float) -> str:
    """``(RN,F14.6)`` as gfortran writes it (leading zero kept)."""
    return format_f(value, 14, 6, rounding=Rounding.NEAREST, leading_zero=True)


def _root_text(root: complex) -> str:
    if root.imag == 0.0:
        return _f14(root.real)
    imag = format_f(root.imag, 14, 6, rounding=Rounding.NEAREST, leading_zero=True, sign_plus=True)
    return _f14(root.real) + imag + "i"


@dataclass(frozen=True, slots=True)
class BairstowResult:
    """Outcome of :func:`bairstow`.

    ``value`` is the number of printed factors (quadratic factors plus the final linear or
    quadratic one); ``iterations`` the total number of corrections, ``steps`` all corrections in
    order and ``factors`` the printed factors. ``coeffs``, ``r1``, ``s1``, ``test``, ``lim`` and
    ``n`` are the data cards; ``nudges`` counts the zero-denominator nudges (R, S + 1).
    """

    value: int
    converged: bool
    iterations: int
    steps: tuple[BairstowStep, ...]
    factors: tuple[BairstowFactor, ...]
    coeffs: tuple[float, ...]
    r1: float
    s1: float
    test: float
    lim: int
    n: int
    nudges: int

    @property
    def factor_table(self) -> tuple[tuple[float, ...], ...]:
        """The printed factor coefficients, one row per factor (the golden ``factors`` table)."""
        return tuple(factor.coefficients for factor in self.factors)

    def factor_iterations(self, index: int) -> int:
        """Corrections used for factor ``index`` (1-based)."""
        return sum(1 for step in self.steps if step.factor == index)

    def book_text(
        self, *, carriage_control: bool = False, rounding: Rounding = _FACTOR_ROUNDING
    ) -> str:
        """The program's line-printer output, reproducing the layout of the scan.

        ``carriage_control=True`` keeps the leading blank of every record, as the Fortran driver
        writes it to stdout; ``rounding`` selects the rounding of the factor lines (default: the
        book's chopping, ``Rounding.ZERO``).
        """
        return _render(_book_records(self.coeffs, self.n, self.factors, rounding), carriage_control)

    def verbose_text(self, *, carriage_control: bool = False) -> str:
        """The driver's ``--verbose`` extras (real64 build): true factors and their roots."""
        records = [
            " VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)",
            " WORKING PRECISION: REAL64",
            " FORMAT 17 PRINTS X**2 + R X + S; THE FACTOR DIVIDED OUT IS X**2 - R X - S.",
        ]
        for index, factor in enumerate(self.factors, start=1):
            c = factor.coefficients
            if factor.kind == "quadratic":
                records.append(
                    f" FACTOR {index}: R ={_f14(c[0])}  S ={_f14(c[1])}  ITERATIONS = "
                    f"{self.factor_iterations(index)}"
                )
                records.append(
                    f"   TRUE FACTOR X**2 - R X - S = X**2 +{_f14(-c[0])} X +{_f14(-c[1])}"
                )
            elif factor.kind == "final_quadratic":
                records.append(
                    f" FACTOR {index}: FINAL QUADRATIC A2 X**2 + A1 X + A0  A2 ={_f14(c[0])}"
                    f"  A1 ={_f14(c[1])}  A0 ={_f14(c[2])}"
                )
            else:
                records.append(
                    f" FACTOR {index}: FINAL LINEAR A1 X + A0  A1 ={_f14(c[0])}  A0 ={_f14(c[1])}"
                )
            roots = factor_roots(factor)
            if not roots:
                records.append("   NO ROOT (CONSTANT FACTOR)")
            records += [f"   ROOT {_root_text(root)}" for root in roots]
        records.append(f" ZERO-DENOMINATOR NUDGES = {self.nudges}")
        records.append(f" TOTAL ITERATIONS = {self.iterations}")
        return _render(records, carriage_control)


def _check_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(f"{name} must be an integer, got {value!r}")
    return value


def _check_real(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InputError(f"{name} must be a real number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise InputError(f"{name} must be a finite number, got {value!r}")
    return number


def bairstow(
    coeffs: Sequence[float],
    r1: float,
    s1: float,
    test: float,
    lim: int,
    n: int,
) -> BairstowResult:
    """Factor the polynomial of the book's data cards exactly as the book program does.

    ``coeffs`` are the seven coefficients of X**6 ... X**0 (card 1); ``r1``, ``s1`` the starting
    R and S, ``test`` the bound on ``|DELR| + |DELS|``, ``lim`` the iteration limit per factor
    and ``n`` the degree (card 2). Each factor's search stops at the first correction with
    ``|DELR| + |DELS| <= TEST``; the next factor starts from the previous factor's R and S.

    Raises:
        NonConvergenceError: a factor needed more than ``lim`` corrections, or ``DENOM`` stayed
            exactly zero through more than ``lim`` nudges (message 24). Carries the corrections
            made in ``steps`` and the book text so far (with the factors found) in
            ``book_output``.
        DegreeError: ``n`` outside 2..6, or a nonzero coefficient of a power above ``n``.
        InputError: not seven coefficients, a non-finite real, or a non-integer ``lim``/``n``.
    """
    raw: object = coeffs  # callers outside the type checker may pass anything
    if isinstance(raw, str) or not isinstance(raw, Sequence) or len(raw) != N_COEFFS:
        raise InputError(f"card 1 needs {N_COEFFS} coefficients (X**6 ... X**0)")
    card = tuple(_check_real(f"coefficient of X**{6 - i}", c) for i, c in enumerate(coeffs))
    r1, s1, test = _check_real("R1", r1), _check_real("S1", s1), _check_real("TEST", test)
    lim, n = _check_int("LIM", lim), _check_int("N", n)

    if not MIN_DEGREE <= n <= MAX_DEGREE:
        message = msg_degree_out_of_range(n)
        raise DegreeError(message, book_output=_render([_MSG_1000, " " + message], False))
    for power in range(MAX_DEGREE, n, -1):
        if card[N_COEFFS - 1 - power] != 0.0:
            message = msg_high_coefficient(power, n)
            raise DegreeError(message, book_output=_render([_MSG_1000, " " + message], False))

    # 1-based arrays as in the listing: a[3..9] = A(3..9); index 0 unused.
    a = [0.0, 0.0, 0.0, *card]
    b = [0.0] * 10
    c = [0.0] * 10
    r, s = r1, s1
    degree = n
    factor_index = 1
    nudges = 0
    steps: list[BairstowStep] = []
    factors: list[BairstowFactor] = []

    def fail() -> NonConvergenceError:
        message = msg_non_convergent(lim)
        records = [*_book_records(card, n, factors, _FACTOR_ROUNDING), " " + message]
        return NonConvergenceError(message, steps=steps, book_output=_render(records, False))

    while True:
        kount = 1  # 11 KOUNT = 1
        nudges_here = 0
        while True:
            # 16 DO 8 J = 3,9
            for j in range(3, 10):
                b[j] = a[j] + r * b[j - 1] + s * b[j - 2]
                c[j] = b[j] + r * c[j - 1] + s * c[j - 2]
            denom = c[7] * c[7] - c[8] * c[6]
            # IF ( DENOM) 9, 10, 9 -- exact zero; NaN is nonzero
            if denom == 0.0:
                nudges += 1
                nudges_here += 1
                if nudges_here > max(lim, 0):
                    raise fail()
                r = r + 1.0
                s = s + 1.0
                kount = 1
                continue
            delr = (-b[8] * c[7] + c[6] * b[9]) / denom
            dels = (-c[7] * b[9] + b[8] * c[8]) / denom
            r = delr + r
            s = dels + s
            steps.append(BairstowStep(factor=factor_index, k=kount, r=r, s=s, delr=delr, dels=dels))
            # IF ( ABSF(DELR) + ABSF(DELS) - TEST) 12, 12, 13
            if abs(delr) + abs(dels) - test <= 0.0:
                break
            # 13 IF (KOUNT - LIM) 14, 15, 15
            if kount - lim >= 0:
                raise fail()
            kount += 1

        # 12 PRINT 17, R, S
        factors.append(BairstowFactor("quadratic", (r, s)))
        degree -= 2
        if degree - 2 > 0:
            # 20 DO 21 K = 3,9 / 21 A(K) = B(K - 2); GO TO 11 with R and S kept
            a[3:10] = b[1:8]
            factor_index += 1
            continue
        if degree - 2 == 0:
            factors.append(BairstowFactor("final_quadratic", (b[5], b[6], b[7])))
        else:
            factors.append(BairstowFactor("linear", (b[6], b[7])))
        break

    return BairstowResult(
        value=len(factors),
        converged=True,
        iterations=len(steps),
        steps=tuple(steps),
        factors=tuple(factors),
        coeffs=card,
        r1=r1,
        s1=s1,
        test=test,
        lim=lim,
        n=n,
        nudges=nudges,
    )
