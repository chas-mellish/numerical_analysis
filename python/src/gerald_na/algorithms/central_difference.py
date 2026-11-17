"""Chapter 4, Program 1: first and second derivatives by central-difference formulas.

A line-by-line port of the listing in ``legacy_code/fortran/chapter_4/derivatives.pdf`` (book
p. 90). The original, transcribed from the scan (job-control cards omitted), is::

    C  PROGRAM TO COMPUTE DERIVATIVES BY FINITE DIFFERENCE FORMULAS
    C  DEFINE THE FUNCTION BY AN ARITHMETIC STATEMENT FUNCTION
          F(X) = X**2*EXPF(X)
    C  READ IN X VALUE AND INITIAL VALUE OF DELTA X
          READ 100, X, H
    C  PRINT HEADING
          PRINT 200, X
    C  COMPUTE DERIVATIVES AND PRINT.  DECREASE H AND REPEAT
          FO = F(X)
          DO 10 I = 1,10
          FR = F(X + H)
          FL = F(X - H)
          DX = (FR - FL)/(2.*H)
          DDX = (FR - 2.*FO + FL)/H**2
          PRINT 201, H, DX, DDX
       10 H = 0.1*H
          CALL EXIT
      100 FORMAT (2F10.0)
      200 FORMAT (52H DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS /
         1 8H AT X = , F5.2 // 4X, 1HH, 13X, 2HDX, 17X, 3HDDX /)
      201 FORMAT (1H , E8.1, 5X, E14.7, 5X, E14.7)
          END

The loop below keeps every operation in the listing's order and grouping: ``FO`` once before the
loop, then per row ``FR = F(X + H)``, ``FL = F(X - H)``, ``DX = (FR - FL)/(2*H)``,
``DDX = ((FR - 2*FO) + FL)/(H*H)`` (``H**2`` with an integer exponent is a multiplication, as
in Fortran), and ``H = 0.1*H`` *accumulated* after each row -- so on a binary machine the
printed H values are not exactly 10**-k (H of row 10 is 1.0000000000000006e-10 in real64).
Both engines therefore agree bit for bit.

What :attr:`CentralDifferenceResult.value` means. The program has no stopping test: it prints
ten rows and stops. ``value`` is the DX of the **last** row (the smallest H), the final
estimate the program computes, just as the other ports report their final iterate; it is not a
"best" row, which would need a criterion the book does not have. ``converged`` is always true
(there is nothing to converge). The extras ``first_dx`` / ``first_ddx`` are the estimates with
the data card's H, ``last_ddx`` the second derivative of the last row, and ``fo`` = F(X).

Book output. :meth:`CentralDifferenceResult.book_text` reproduces formats 200 and 201 as the
scan shows them: the book's ``E`` editing printed one digit before the decimal point
(``1.0E-01``, ``1.0016675E-02``: like ``ES``/``1PE`` in modern Fortran), an exact zero as
``0.0000000E-99`` (the exponent field of a floating-point zero on the book's machine) and
``F5.2`` with its leading zero (``0.00``). DX and DDX are chopped (``Rounding.ZERO``) like the
other book printouts. X and H are rounded to nearest: X is the echoed input and H is the card's
H scaled by powers of 0.1, and chopping their binary values would print a decimal input such as
X = 0.29 (0.28999999999999998) as ``0.28`` and H = 1.E-6 (9.9999999999999995e-07) as
``9.9E-07`` (the same reasoning as Bairstow's coefficient echo). For the book card both modes
print the same H digits.

ERRATA (details in ``catalog/ch04_p01_central_difference.toml``): ``EXPF`` is ``EXP``; the
statement function becomes a procedure argument; ``FO`` is the letter O; ``CALL EXIT`` ends the
run; ``READ 100`` with ``FORMAT (2F10.0)`` becomes a list-directed read; a non-finite F, DX or
DDX (no counterpart on the original machine) and a non-positive or non-finite H are
:class:`~gerald_na.errors.InputError` s.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from gerald_na.algorithms._evaluation import evaluate_finite
from gerald_na.algorithms._fortran_format import Rounding, format_es, format_f, render_records
from gerald_na.errors import GeraldNAError, InputError

__all__ = [
    "BOOK_ROWS",
    "BOOK_ZERO_EXPONENT",
    "HEADING",
    "H_FACTOR",
    "CentralDifferenceResult",
    "CentralDifferenceStep",
    "book_e",
    "central_difference",
]

BOOK_ROWS = 10
"""``DO 10 I = 1,10``: the number of rows the book prints."""

H_FACTOR = 0.1
"""``10 H = 0.1*H``: H is divided by ten after every row (accumulated, not recomputed)."""

HEADING = " DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS"
"""The ``52H`` field of format 200, carriage-control blank included."""

COLUMN_HEADINGS = "    H" + " " * 13 + "DX" + " " * 17 + "DDX"
"""``4X, 1HH, 13X, 2HDX, 17X, 3HDDX`` (the first blank of ``4X`` is the carriage control)."""

BOOK_ZERO_EXPONENT = "E-99"
"""How the book prints the exponent of an exact zero (``0.0000000E-99``)."""

_ROUNDING = Rounding.ZERO
"""The book's output conversion truncates (H, DX and DDX)."""

_ECHO_ROUNDING = Rounding.NEAREST
"""X and H are rounded to nearest (see the module docstring)."""


def book_e(value: float, w: int, d: int, *, rounding: Rounding = _ROUNDING) -> str:
    """The book's ``Ew.d`` field: ``ESw.d`` editing, an exact zero with exponent ``E-99``.

    The sign of a negative zero is kept, as gfortran keeps it for ``ES`` editing.
    """
    text = format_es(value, w, d, rounding=rounding)
    if value == 0.0:
        text = text.replace("E+00", BOOK_ZERO_EXPONENT)
    return text


def _fmt_heading(x: float) -> list[str]:
    """Format 200: heading, ``AT X = `` with F5.2, a blank record, the column headings, a blank
    record (``//`` and the closing ``/)`` each end an empty record)."""
    at_x = " AT X = " + format_f(x, 5, 2, rounding=_ECHO_ROUNDING, leading_zero=True)
    return [HEADING, at_x, "", COLUMN_HEADINGS, ""]


def _fmt_row(h: float, dx: float, ddx: float, rounding: Rounding) -> str:
    """``201 FORMAT (1H , E8.1, 5X, E14.7, 5X, E14.7)``; ``rounding`` applies to DX and DDX."""
    return (
        " "
        + book_e(h, 8, 1, rounding=_ECHO_ROUNDING)
        + " " * 5
        + book_e(dx, 14, 7, rounding=rounding)
        + " " * 5
        + book_e(ddx, 14, 7, rounding=rounding)
    )


@dataclass(frozen=True, slots=True)
class CentralDifferenceStep:
    """One printed row (format 201): row number ``k`` (the DO index I), the step ``h`` and the
    estimates ``dx`` of F'(X) and ``ddx`` of F''(X)."""

    k: int
    h: float
    dx: float
    ddx: float


@dataclass(frozen=True, slots=True)
class CentralDifferenceResult:
    """Outcome of :func:`central_difference`.

    ``value`` is DX of the last row (the smallest H); ``converged`` is always true (the program
    has no stopping test); ``iterations`` is the number of rows (10 for the book). ``x`` and
    ``h`` are the inputs (``h`` = H of the first row). ``fo`` is F(X), ``first_dx`` and
    ``first_ddx`` the estimates of the first row, ``last_ddx`` the DDX of the last row.
    """

    value: float
    converged: bool
    iterations: int
    steps: tuple[CentralDifferenceStep, ...]
    x: float
    h: float
    fo: float
    first_dx: float
    first_ddx: float
    last_ddx: float

    def book_text(self, *, carriage_control: bool = False, rounding: Rounding = _ROUNDING) -> str:
        """The program's line-printer output (formats 200 and 201), as laid out in the scan.

        ``carriage_control=True`` keeps the leading blank of every record, as a modern Fortran
        processor writes it to stdout; ``rounding`` selects another output rounding mode for
        DX and DDX (X and H are always rounded to nearest).
        """
        return _book_text(self.x, self.steps, carriage_control, rounding)


def _book_text(
    x: float,
    steps: tuple[CentralDifferenceStep, ...],
    carriage_control: bool,
    rounding: Rounding = _ROUNDING,
) -> str:
    records = _fmt_heading(x)
    records.extend(_fmt_row(step.h, step.dx, step.ddx, rounding) for step in steps)
    return render_records(records, carriage_control)


def central_difference(
    f: Callable[[float], float],
    x: float,
    h: float,
    n_steps: int = BOOK_ROWS,
) -> CentralDifferenceResult:
    """Estimate F'(X) and F''(X) by central differences for ``n_steps`` decreasing H, as the
    book does.

    Row k uses ``H = h * 0.1**(k-1)``, accumulated by ``H = 0.1*H``::

        DX  = (F(X+H) - F(X-H)) / (2H)            error  H**2/6  * F'''(X)  + O(H**4)
        DDX = (F(X+H) - 2F(X) + F(X-H)) / H**2    error  H**2/12 * F''''(X) + O(H**4)

    Raises:
        InputError: ``x`` or ``h`` is not finite, ``h <= 0`` or ``n_steps < 1``; or F(X),
            F(X+H) or F(X-H) is NaN or infinite, or DX or DDX overflows (the Fortran driver
            reports the same ``INPUT`` error). Errors raised by ``f`` itself (for example
            :class:`~gerald_na.errors.ExpressionError` from a learner function outside its
            domain) propagate with their class kept. Both carry the rows computed before the
            failure in ``steps`` and the book text printed so far (the heading is printed
            before F(X) is evaluated) in ``book_output``.
    """
    if isinstance(n_steps, bool) or not isinstance(n_steps, int) or n_steps < 1:
        raise InputError(f"the number of rows must be a positive integer, got {n_steps!r}")
    x = float(x)
    h = float(h)
    if not math.isfinite(x):
        raise InputError(f"X must be a finite number, got {x!r}")
    if not math.isfinite(h) or h <= 0.0:
        raise InputError(f"the initial step H must be a positive finite number, got {h!r}")

    rows: list[CentralDifferenceStep] = []

    def failed(exc: GeraldNAError) -> GeraldNAError:
        exc.steps = tuple(rows)
        exc.book_output = _book_text(x, tuple(rows), carriage_control=False)
        return exc

    def evaluate(at: float, name: str) -> float:
        try:
            return evaluate_finite(f, at, name)
        except GeraldNAError as exc:
            raise failed(exc) from None

    # FO = F(X)
    fo = evaluate(x, "F(X)")
    step = h
    for k in range(1, n_steps + 1):
        # FR = F(X + H);  FL = F(X - H)
        fr = evaluate(x + step, "F(X+H)")
        fl = evaluate(x - step, "F(X-H)")
        # DX = (FR - FL)/(2.*H);  DDX = (FR - 2.*FO + FL)/H**2
        dx = (fr - fl) / (2.0 * step)
        denominator = step * step
        ddx = (fr - 2.0 * fo + fl) / denominator if denominator != 0.0 else math.inf
        if not (math.isfinite(dx) and math.isfinite(ddx)):
            raise failed(InputError(f"DX or DDX is not a finite number at H = {step!r} (row {k})"))
        rows.append(CentralDifferenceStep(k=k, h=step, dx=dx, ddx=ddx))
        # 10 H = 0.1*H
        step = H_FACTOR * step

    steps = tuple(rows)
    return CentralDifferenceResult(
        value=steps[-1].dx,
        converged=True,
        iterations=len(steps),
        steps=steps,
        x=x,
        h=h,
        fo=fo,
        first_dx=steps[0].dx,
        first_ddx=steps[0].ddx,
        last_ddx=steps[-1].ddx,
    )
