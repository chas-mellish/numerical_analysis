"""Chapter 3, Program 2: Romberg integration of F from 0 to B (the book's Si(B)).

A line-by-line port of the listing in ``docs/chapter_03_program_02_listing.pdf`` (book p. 74).
The original control flow, transcribed from the scan, is::

          H = B/10.
          SUM = 1. + FCN(B)                     1. is FCN(0) = lim SIN(X)/X; here F(0) + F(B)
          X = 0.0
          DO 10 I = 2,10
          X = X + H
       10 SUM = SUM + FCN(X)*2.
          TRAP(1,1) = H/2.*SUM                  trapezoidal rule, 10 subintervals
          DO 20 I = 1,8                         halve H up to 8 times
          H = H/2.
          X = H
          K = 10.*2.**I
          DO 30 J = 2,K,2                       add the new midpoints (odd multiples of H)
          SUM = SUM + FCN(X)*2.
       30 X = X + H + H
          TRAP(1,I+1) = H/2.*SUM
          DO 40 II = 1,I                        Richardson extrapolation of the new column
       40 TRAP(II+1,I+1) = TRAP(II,I+1) + 1./(4.**II - 1.)*(TRAP(II,I+1) - TRAP(II,I))
          IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1))- TOL) 50,50,20
       20 CONTINUE
          PRINT 200, B                          8 halvings without meeting TOL:
          DO 60 K = 1,9                           the 9x9 table and format 201
       60 PRINT 203, (TRAP(J,K), J = 1,K)        -> result with converged = False
          PRINT 201, TRAP(9,9), TOL
          CALL EXIT
       50 PRINT 200, B                          converged after halving I:
          I = I + 1                               I+1 rows and format 202
          DO 70 L = 1,I                          -> result with converged = True
       70 PRINT 203, (TRAP(J,L), J = 1,L)
          PRINT 202, TRAP(I,I), K, TOL
          CALL EXIT

``TRAP(row, col)`` holds the extrapolation order in ``row`` and the halving in ``col``; the book
prints line ``L`` as ``TRAP(1..L, L)``, which is :attr:`RombergResult.table` ``[L-1]``.

ERRATA (scan versus the OCR text in ``legacy_code/fortran/chapter_3/integration.f90``; the full
list is in ``catalog/ch03_p02_romberg.toml`` and in the Fortran driver's header):

* OCR slips corrected from the scan: ``FCNI(B)`` is ``FCN(B)``; ``DO 20 1 =`` is
  ``DO 20 I = 1,8``; the extrapolation (label 40) and the tolerance test read as above; ``F10.7s``
  in format 202 is ``F10.7``; and format 201 has no ``I5`` -- it is
  ``(/ 10H VALUE IS , F10.7, 31H BUT DID NOT MEET TOLERANCE OF E14.7)``, matching its list
  ``TRAP(9,9), TOL``.
* The seed ``SUM = 1. + FCN(B)`` hard-codes FCN(0) = 1, the limit of SIN(X)/X. The port seeds
  with ``f0 + f(b)``, where ``f0`` is the ordinate at X = 0: by default ``f(0)``, and the
  book's :data:`BOOK_SEED` ``1.0`` when the engine adapter recognizes the book's integrand (the
  same convention as :mod:`gerald_na.algorithms.simpson`), so the book run is reproduced
  exactly.
* Not meeting TOL after 8 extrapolations is the book's documented outcome (it prints the table
  and a note), so it is a result with ``converged=False``, not an exception.
* The book's machine printed ``E14.7`` with one digit before the point (``2.0000000E-07``, an
  ``ES14.7`` today) and chopped computed values without a leading zero; :meth:`book_text`
  does the same (``Rounding.ZERO``), while the input echoes B and TOL are rounded to nearest so
  that a card value such as 2.3 does not print as 2.29. The scan shows the table lines one
  column to the left of what ``FORMAT (1H ,8F10.7)`` produces; the port follows the FORMAT.

Every expression keeps the listing's operation order (``(x + h) + h``, ``(h/2)*sum``,
``(1/(4**ii - 1))*(...)``), so the Fortran driver and this port agree bit for bit. In real64 the
book card gives 1.6181944 (the true Si(15)); the book's single-precision decimal machine printed
1.6181936. Both stop after 3 halvings with 80 subintervals.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from gerald_na.algorithms._fortran_format import Rounding, format_es, format_f, format_i
from gerald_na.errors import InputError

__all__ = [
    "BOOK_FIRST_PANELS",
    "BOOK_MAX_HALVINGS",
    "BOOK_SEED",
    "RombergResult",
    "RombergStep",
    "romberg",
    "sinc",
]

BOOK_FIRST_PANELS = 10
"""``PROGRAM BEGINS WITH TRAPEZOIDAL INTEGRATION WITH 10 SUBINTERVALS``."""

BOOK_MAX_HALVINGS = 8
"""``DO 20 I = 1,8``: the book halves the step at most 8 times (2560 subintervals, a 9x9 table)."""

BOOK_SEED = 1.0
"""``SUM = 1. + FCN(B)``: the book's F(0) for SIN(X)/X, the limit of the integrand at X = 0."""

_ROUNDING = Rounding.ZERO
"""The book's output conversion chops computed values (see the module ERRATA)."""

_VALUES_PER_LINE = 8
"""``203 FORMAT (1H ,8F10.7)``: 8 values per record; format reversion starts a new record."""


def sinc(x: float) -> float:
    """The book's integrand ``SIN(X)/X`` with its limit 1 at ``x = 0`` (preset 1).

    The listing never evaluates FCN(0): it writes the limit as the literal ``1.`` in
    ``SUM = 1. + FCN(B)`` (:data:`BOOK_SEED`). The Fortran preset (``functions_mod: f_sinc``)
    and this function return that limit at 0, so seeding with ``f(0) + f(b)`` reproduces the
    book; a convenience for calling :func:`romberg` directly with the book's integrand.
    """
    return math.sin(x) / x if x != 0.0 else 1.0


# The FORMAT statements of the listing. Each record starts with the carriage-control blank;
# the empty records come from the slashes of formats 200, 201 and 202.


def _fmt_heading(b: float) -> list[str]:
    """``200 FORMAT (// 38H VALUE OF SINE INTEGRAL BETWEEN 0 AND , F6.2, 24H BY ... / )``."""
    title = (
        " VALUE OF SINE INTEGRAL BETWEEN 0 AND "
        f"{format_f(b, 6, 2, rounding=Rounding.NEAREST)} BY ROMBERG INTEGRATION "
    )
    return ["", "", title, ""]


def _fmt_row(values: tuple[float, ...], rounding: Rounding) -> list[str]:
    """``203 FORMAT (1H ,8F10.7)`` for one printed line of the table (9 values need 2 records)."""
    return [
        " "
        + "".join(format_f(v, 10, 7, rounding=rounding) for v in values[i : i + _VALUES_PER_LINE])
        for i in range(0, len(values), _VALUES_PER_LINE)
    ]


def _fmt_converged(value: float, subintervals: int, tol: float, rounding: Rounding) -> list[str]:
    """``202 FORMAT (/ 10H VALUE IS , F10.7, 2H, / I5, 49H SUBINTERVALS ... OF , E14.7)``."""
    return [
        "",
        f" VALUE IS {format_f(value, 10, 7, rounding=rounding)}, ",
        f"{format_i(subintervals, 5)} SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF "
        + format_es(tol, 14, 7, rounding=Rounding.NEAREST),
    ]


def _fmt_not_converged(value: float, tol: float, rounding: Rounding) -> list[str]:
    """``201 FORMAT (/ 10H VALUE IS , F10.7, 31H BUT DID NOT MEET TOLERANCE OF E14.7)``."""
    return [
        "",
        f" VALUE IS {format_f(value, 10, 7, rounding=rounding)} BUT DID NOT MEET TOLERANCE OF "
        + format_es(tol, 14, 7, rounding=Rounding.NEAREST),
    ]


def _render(records: list[str], carriage_control: bool) -> str:
    """Join records as printed: the line printer consumes the carriage-control column."""
    lines = records if carriage_control else [record[1:] for record in records]
    return "".join(line + "\n" for line in lines)


@dataclass(frozen=True, slots=True)
class RombergStep:
    """One halving (one pass through ``DO 20``) and its tolerance test.

    ``k`` is the halving index I (1..8), ``panels`` the subintervals of the new trapezoidal sum
    (the book's ``K = 10*2**I``), ``h`` the step after halving, ``trap`` the trapezoidal value
    ``TRAP(1,I+1)``, ``best`` the new diagonal value ``TRAP(I+1,I+1)`` and ``diff`` the tested
    quantity ``|TRAP(I+1,I+1) - TRAP(I,I+1)|``.
    """

    k: int
    panels: int
    h: float
    trap: float
    best: float
    diff: float


@dataclass(frozen=True, slots=True)
class RombergResult:
    """Outcome of :func:`romberg`.

    ``table`` is the triangular table as the book prints it: ``table[L-1]`` is line ``L``,
    ``(TRAP(1,L), ..., TRAP(L,L))``, so the first column holds the trapezoidal sums and the last
    entry of each line the best estimate so far. ``value`` is ``table[-1][-1]``; ``converged``
    says whether TOL was met (otherwise all 9 lines were computed, format 201); ``iterations``
    is the number of halvings, ``len(table) - 1``; ``subintervals`` the subintervals of the last
    trapezoidal sum (the book's ``K``: 80 for the data card, 2560 at most). ``b`` and ``tol``
    are the inputs.
    """

    value: float
    converged: bool
    iterations: int
    steps: tuple[RombergStep, ...]
    table: tuple[tuple[float, ...], ...]
    subintervals: int
    b: float
    tol: float

    def trap(self, row: int, col: int) -> float:
        """The book's ``TRAP(row, col)`` (1-based; ``row <= col <= len(table)``)."""
        if not 1 <= row <= col <= len(self.table):
            raise IndexError(f"TRAP({row},{col}) is not in the computed table")
        return self.table[col - 1][row - 1]

    def book_text(self, *, carriage_control: bool = False, rounding: Rounding = _ROUNDING) -> str:
        """The program's line-printer output, reproducing the layout of formats 200-203.

        By default each line is shown as printed (the carriage-control blank consumed) with the
        book's chopping output conversion for computed values. ``carriage_control=True`` keeps
        the leading blank of every record, as the Fortran driver writes it to stdout;
        ``rounding`` selects another rounding mode for the computed values (for example
        ``Rounding.NEAREST``, gfortran's default). Trailing blanks of the Hollerith fields
        (``24H ... INTEGRATION ``, ``2H, ``) are kept.
        """
        records = _fmt_heading(self.b)
        for line in self.table:
            records.extend(_fmt_row(line, rounding))
        if self.converged:
            records.extend(_fmt_converged(self.value, self.subintervals, self.tol, rounding))
        else:
            records.extend(_fmt_not_converged(self.value, self.tol, rounding))
        return _render(records, carriage_control)


def _evaluate(f: Callable[[float], float], x: float) -> float:
    value = float(f(x))
    if not math.isfinite(value):
        raise InputError(f"F(X) is not a finite number at X = {x!r}")
    return value


def romberg(
    f: Callable[[float], float],
    b: float,
    tol: float,
    *,
    f0: float | None = None,
) -> RombergResult:
    """Integrate ``f`` from 0 to ``b`` by Romberg's method, exactly as the book does.

    The trapezoidal sum starts with 10 subintervals and the step is halved up to 8 times; after
    halving I the new column is extrapolated and the run stops when
    ``|TRAP(I+1,I+1) - TRAP(I,I+1)| <= tol``. A negative ``tol`` can never be met.

    ``f0`` is the ordinate at X = 0, which seeds the sum ``f0 + f(b)`` (the book writes
    ``1. + FCN(B)``: :data:`BOOK_SEED`, the limit of SIN(X)/X); when omitted, ``f(0.0)`` is
    evaluated. ``f`` itself is never called at 0 when ``f0`` is given.

    Not meeting ``tol`` after 8 halvings is not an error: the result has ``converged=False``,
    the full 9-line table, ``value = TRAP(9,9)`` and 2560 subintervals, as the book prints them.

    Raises:
        InputError: ``b``, ``tol`` or ``f0`` is not finite, or ``f`` returned NaN or an infinity
            (the Fortran driver reports the same ``INPUT`` error). The error carries the
            halvings completed so far in ``steps``.
            Errors raised by ``f`` itself (for example
            :class:`~gerald_na.errors.ExpressionError` from a learner function) propagate with
            their class kept and the same ``steps``.
    """
    b, tol = float(b), float(tol)
    if not (math.isfinite(b) and math.isfinite(tol)):
        raise InputError(f"B and TOL must be finite numbers, got B = {b!r}, TOL = {tol!r}")
    if f0 is not None and not math.isfinite(float(f0)):
        raise InputError(f"F(X) is not a finite number at X = 0.0 (f0 = {f0!r})")
    steps: list[RombergStep] = []
    try:
        # H = B/10. / SUM = 1. + FCN(B)  (generalized: F0 + F(B), F0 = F(0) by default)
        h = b / float(BOOK_FIRST_PANELS)
        total = float(f0) if f0 is not None else _evaluate(f, 0.0)
        total = total + _evaluate(f, b)
        # DO 10 I = 2,10: the 9 interior ordinates, X advancing by H
        x = 0.0
        for _ in range(2, BOOK_FIRST_PANELS + 1):
            x = x + h
            total = total + _evaluate(f, x) * 2.0
        # columns[c] is TRAP(1..c+1, c+1), i.e. printed line c+1
        columns: list[list[float]] = [[(h / 2.0) * total]]

        for i in range(1, BOOK_MAX_HALVINGS + 1):
            h = h / 2.0
            x = h
            k = BOOK_FIRST_PANELS * 2**i
            # DO 30 J = 2,K,2: SUM = SUM + FCN(X)*2. / X = X + H + H
            for _ in range(2, k + 1, 2):
                total = total + _evaluate(f, x) * 2.0
                x = (x + h) + h
            previous = columns[i - 1]
            column = [(h / 2.0) * total]
            # DO 40 II = 1,I
            for ii in range(1, i + 1):
                column.append(
                    column[ii - 1] + (1.0 / (4.0**ii - 1.0)) * (column[ii - 1] - previous[ii - 1])
                )
            columns.append(column)
            diff = abs(column[i] - column[i - 1])
            steps.append(RombergStep(k=i, panels=k, h=h, trap=column[0], best=column[i], diff=diff))
            # IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1)) - TOL) 50,50,20  (NaN -> 20)
            if diff - tol <= 0.0:
                return _result(columns, steps, converged=True, b=b, tol=tol)
    except InputError as exc:
        # Keep the error's class (a learner function raises ExpressionError) and attach the
        # halvings completed so far, like the Fortran trace (STEP records before the ERROR).
        exc.steps = tuple(steps)
        raise
    # 20 CONTINUE exhausted: PRINT 201, TRAP(9,9), TOL
    return _result(columns, steps, converged=False, b=b, tol=tol)


def _result(
    columns: list[list[float]], steps: list[RombergStep], *, converged: bool, b: float, tol: float
) -> RombergResult:
    iterations = len(columns) - 1
    return RombergResult(
        value=columns[-1][-1],
        converged=converged,
        iterations=iterations,
        steps=tuple(steps),
        table=tuple(tuple(column) for column in columns),
        subintervals=BOOK_FIRST_PANELS * 2**iterations,
        b=b,
        tol=tol,
    )
