"""Lagrangian polynomial interpolation, program ``lagrange_interpolation`` (book ref unconfirmed).

A line-by-line port of the listing in ``legacy_code/fortran/chapter_2/polynomial.F90``. **No scan
of this program exists**: it was transcribed from the raw OCR text only, so the corrections below
rest on the FORTRAN syntax, the FORMAT Hollerith counts and the book's printed result (2.3119 at
X = 5.0), not on a page image. The corrected program is::

          DIMENSION X(10), Y(10)
          READ 100, N, (X(I), Y(I), I = 1,N)
          READ 101, XIN
          YOUT = 0.0
          DO 20 I = 1,N
          TERM = Y(I)
          DO 10 J = 1,N
          IF (I-J) 9,10,9               skip the factor J = I
        9 TERM = TERM*(XIN - X(J))/(X(I) - X(J))
       10 CONTINUE
       20 YOUT = YOUT + TERM
          PRINT 200, N, XIN, YOUT
      100 FORMAT (I2/(2F10.0))
      101 FORMAT (F10.0)
      200 FORMAT (49H USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG ,I3,
         1   8H VALUES, / 8H AT X = ,F10.3, 27H THE FUNCTION HAS VALUE OF ,
         2   F10.4)
          CALL EXIT

ERRATA (OCR text versus the program that produces the book's 2.3119; see the catalog entry and
the ERRATA header of ``fortran/app/lagrange_interpolation.f90`` for the full list):

* ``IF (I=J) 9,10,9`` is ``IF (I-J) 9,10,9`` (an arithmetic IF needs an expression).
* ``TERM*(XIN - X(J)/X(I) - X(J))`` is ``TERM*(XIN - X(J))/(X(I) - X(J))``: the OCR lost two
  parentheses; only the corrected product gives 2.3119.
* ``FORMAT (12/(2F10.0))`` is ``FORMAT (I2/(2F10.0))``: N is read with ``I2`` (card ``05``).
* The data pairs are X(I), Y(I) in that order, as the READ list says: X = 2.3756 ... 8.1919,
  Y = 1.6 ... 2.8 gives 2.3119013 at X = 5.0 (the swapped order would give 63.35). The X column
  is sinh(Y) to 4 decimals, so the book interpolates the inverse function asinh: asinh(5) =
  2.3124383.

Modernization: ``DIMENSION X(10), Y(10)`` becomes a checked limit of 1 to 10 points
(:class:`DegreeError`), and equal X values -- a division by zero in the original -- are rejected
with an :class:`InputError` before anything is computed. The book printed with a processor that
truncates on output and suppresses leading zeros (the same deck-control cards as the bisection
listing), so :meth:`LagrangeResult.book_text` renders with ``RZ`` rounding and no leading zero.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from gerald_na.algorithms._fortran_format import Rounding, format_f, format_i
from gerald_na.errors import DegreeError, InputError

__all__ = [
    "BOOK_MAX_POINTS",
    "LagrangeResult",
    "LagrangeStep",
    "lagrange",
    "msg_degree",
    "msg_duplicate_x",
    "msg_not_finite",
]

BOOK_MAX_POINTS = 10
"""``DIMENSION X(10), Y(10)``: the most data pairs the book's program can hold."""

_ROUNDING = Rounding.ZERO
"""The book's output conversion truncates (see the module docstring)."""


def msg_degree(n: int) -> str:
    """``DEGREE`` error text: N outside the ``DIMENSION`` (no book message exists)."""
    return (
        f"N = {n} IS NOT BETWEEN 1 AND {BOOK_MAX_POINTS} "
        f"(DIMENSION X({BOOK_MAX_POINTS}) Y({BOOK_MAX_POINTS}))"
    )


def msg_duplicate_x(i: int, j: int) -> str:
    """``INPUT`` error text for X(i) = X(j) (the original divides by zero)."""
    return f"X({i}) AND X({j}) ARE EQUAL: LAGRANGIAN INTERPOLATION NEEDS DISTINCT X VALUES"


def msg_not_finite(i: int) -> str:
    """``INPUT`` error text when term ``i`` or the sum overflows (no book equivalent)."""
    return f"THE INTERPOLATED VALUE IS NOT A FINITE NUMBER AFTER TERM {i}"


# The FORMAT 200 records. Each starts with the carriage-control blank.


def _fmt_header(n: int) -> str:
    """``49H USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG ,I3, 8H VALUES,``."""
    return f" USING LAGRANGIAN POLYNOMIAL INTERPOLATION AMONG {format_i(n, 3)} VALUES,"


def _fmt_value(xin: float, yout: float, rounding: Rounding) -> str:
    """``/ 8H AT X = ,F10.3, 27H THE FUNCTION HAS VALUE OF ,F10.4``."""
    return (
        f" AT X = {format_f(xin, 10, 3, rounding=rounding)} THE FUNCTION HAS VALUE OF "
        + format_f(yout, 10, 4, rounding=rounding)
    )


def _render(records: list[str], carriage_control: bool) -> str:
    """Join records as printed: the line printer consumes the carriage-control column."""
    lines = records if carriage_control else [record[1:] for record in records]
    return "".join(line + "\n" for line in lines)


@dataclass(frozen=True, slots=True)
class LagrangeStep:
    """One pass through the ``DO 20`` loop.

    ``x`` and ``y`` are the data pair X(I), Y(I); ``term`` is Y(I) times the Lagrange basis
    polynomial L_I(XIN) (TERM at label 20) and ``partial`` the running sum YOUT after adding it.
    """

    i: int
    x: float
    y: float
    term: float
    partial: float


@dataclass(frozen=True, slots=True)
class LagrangeResult:
    """Outcome of :func:`lagrange`.

    ``value`` is YOUT, the interpolating polynomial through the ``n`` points evaluated at
    ``xin``; ``iterations`` is the number of terms summed (``n``); ``converged`` is always true
    (the method is direct). ``xs``, ``ys`` and ``xin`` are the inputs.
    """

    value: float
    converged: bool
    iterations: int
    steps: tuple[LagrangeStep, ...]
    n: int
    xs: tuple[float, ...]
    ys: tuple[float, ...]
    xin: float

    def book_text(self, *, carriage_control: bool = False, rounding: Rounding = _ROUNDING) -> str:
        """The program's line-printer output (FORMAT 200: two records).

        By default each line is shown as printed (the carriage-control blank consumed) with the
        book's truncating output conversion; ``carriage_control=True`` keeps the leading blank of
        every record, as the Fortran driver writes it to stdout.
        """
        records = [_fmt_header(self.n), _fmt_value(self.xin, self.value, rounding)]
        return _render(records, carriage_control)


def _check_points(xs: tuple[float, ...], ys: tuple[float, ...], xin: float) -> None:
    if len(xs) != len(ys):
        raise InputError(f"{len(xs)} X values but {len(ys)} Y values: give N (X, Y) pairs")
    n = len(xs)
    if not 1 <= n <= BOOK_MAX_POINTS:
        raise DegreeError(msg_degree(n))
    if not all(math.isfinite(v) for v in (*xs, *ys, xin)):
        raise InputError("data card values must be finite numbers")
    for i in range(n):
        for j in range(i + 1, n):
            if xs[i] == xs[j]:
                raise InputError(msg_duplicate_x(i + 1, j + 1))


def lagrange(xs: Sequence[float], ys: Sequence[float], xin: float) -> LagrangeResult:
    """Evaluate the Lagrangian interpolating polynomial through ``(xs[i], ys[i])`` at ``xin``.

    The sum and the products are formed exactly as in the listing: for each I, TERM = Y(I) is
    multiplied by ``(XIN - X(J))/(X(I) - X(J))`` for J = 1..N, J /= I, in that order and
    left to right, then added to YOUT. The Fortran driver evaluates the same expression, so both
    engines agree bit for bit.

    Raises:
        DegreeError: fewer than 1 or more than :data:`BOOK_MAX_POINTS` points (the book's
            ``DIMENSION X(10), Y(10)``).
        InputError: ``xs`` and ``ys`` differ in length; a value is not finite; two X values are
            equal (the original divides by zero); or a term or the sum overflows (carries the
            rows completed before it in ``steps``).
    """
    x = tuple(float(v) for v in xs)
    y = tuple(float(v) for v in ys)
    xin = float(xin)
    _check_points(x, y, xin)
    n = len(x)

    yout = 0.0
    steps: list[LagrangeStep] = []
    for i in range(n):  # DO 20 I = 1,N
        term = y[i]
        for j in range(n):  # DO 10 J = 1,N
            if i - j != 0:  # IF (I-J) 9,10,9
                term = term * (xin - x[j]) / (x[i] - x[j])
        yout = yout + term  # 20 YOUT = YOUT + TERM
        if not (math.isfinite(term) and math.isfinite(yout)):
            raise InputError(msg_not_finite(i + 1), steps=steps, book_output="")
        steps.append(LagrangeStep(i=i + 1, x=x[i], y=y[i], term=term, partial=yout))

    return LagrangeResult(
        value=yout,
        converged=True,
        iterations=n,
        steps=tuple(steps),
        n=n,
        xs=x,
        ys=y,
        xin=xin,
    )
