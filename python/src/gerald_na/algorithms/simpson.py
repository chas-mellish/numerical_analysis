"""Chapter 3, Program 1: the sine integral Si(B) by Simpson's 1/3 rule.

A line-by-line port of the listing in ``docs/chapter_03_program_01_listing.pdf`` (book p. 73).
The original, transcribed from the scan, is::

          F(X) = SINF(X)/X
          READ 100, B, N
          NHALF = N/2
          IF (N - 2*NHALF) 99,1,99
       99 PRINT 200                              N odd               -> OddPanelsError
          CALL EXIT
        1 XN = N
          DELX = B/XN
          SUM = 1.0 + 4.*F(DELX) + F(B)          first, second and last ordinates
          X = 2.*DELX
          DO 10 I = 2,NHALF
          SUM = SUM + 2.*F(X) + 4.*F(X+DELX)     the rest, in (2, 4) pairs
       10 X = X + 2.*DELX
          SININT = DELX/3.*SUM
          PRINT 201, B, SININT, N
          CALL EXIT
      100 FORMAT (F10.0, I10)
      200 FORMAT (60H WITH ODD NUMBER OF PANELS, SIMPSONS 1/3 RULE DOES NOT
         1APPLY )
      201 FORMAT (41H VALUE OF SINE INTEGRAL FROM X = 0 TO X = , F6.2,
         1 3H IS , F10.7, 5H WITH , I4, 7H PANELS )

The loop below keeps that order and grouping exactly (``(SUM + 2*F(X)) + 4*F(X+DELX)``, an
accumulated ``X``, ``(DELX/3)*SUM``), so the Python engine agrees with the Fortran driver bit for
bit; in single precision the order also decides the last printed digit.

The seed of the sum. ``SUM = 1.0 + ...`` is the book's value of F(0): ``SINF(X)/X`` cannot be
evaluated at X = 0, so the listing writes its limit, 1, as a literal. In general the first term
of Simpson's sum is the ordinate F(0) with weight 1, so :func:`simpson` evaluates ``f(0.0)``
unless the caller passes ``f0`` -- the engine adapter passes the book's ``1.0`` when the function
is the book's ``SIN(X)/X`` (whose expression has no value at 0), and any other function supplies
its own F(0).

ERRATA (details in ``catalog/ch03_p01_simpson.toml`` and ``fortran/app/ch03_p01_simpson.f90``):

* Text-transcription slips noted by the earlier rewrite (``IF (N = 2*NHALF)``, ``2.NHALF``,
  ``5UM``, ``Fl0.7``) do not occur in the scan, which reads as above.
* The earlier rewrite printed a prompt and blank lines; the book prints only format 201 (or 200).
* N = 2 is accepted: the modern loop is zero-trip. A FORTRAN II/IV DO loop runs at least once,
  so the original added two ordinates beyond B for N = 2 -- the reason for its comment
  "N GREATER THAN 2". N = 0 (``DELX = B/0``) and negative even N raise :class:`InputError`.
* :meth:`SimpsonResult.book_text` renders with the book's truncating output conversion and no
  leading zero, like the other ports.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from gerald_na.algorithms._fortran_format import Rounding, format_f, format_i, render_records
from gerald_na.errors import GeraldNAError, InputError, OddPanelsError

__all__ = [
    "BOOK_SEED",
    "MAX_PANELS",
    "MSG_ODD_PANELS",
    "TRACE_MSG_ODD_PANELS",
    "SimpsonResult",
    "SimpsonStep",
    "simpson",
]

BOOK_SEED = 1.0
"""``SUM = 1.0 + ...``: the book's F(0) for SIN(X)/X, the limit of the integrand at X = 0."""

MAX_PANELS = 1_000_000
"""Largest accepted N (the Fortran module's ``max_panels``); one step is kept per ordinate."""

MSG_ODD_PANELS = "WITH ODD NUMBER OF PANELS, SIMPSONS 1/3 RULE DOES NOT APPLY"
"""Format 200 (``60H``), printed when N is odd."""

TRACE_MSG_ODD_PANELS = MSG_ODD_PANELS.replace(",", ";")
"""Message of :class:`OddPanelsError`: format 200 as the ``--trace`` ``ERROR`` record carries
it (trace messages contain no commas, DD2). The book text keeps the comma."""

_ROUNDING = Rounding.ZERO
"""The book's output conversion truncates (see the module ERRATA)."""


def _fmt_value(b: float, value: float, n: int, rounding: Rounding) -> str:
    """``201 FORMAT (41H VALUE OF ... X = , F6.2, 3H IS , F10.7, 5H WITH , I4, 7H PANELS )``."""
    return (
        f" VALUE OF SINE INTEGRAL FROM X = 0 TO X ={format_f(b, 6, 2, rounding=rounding)}"
        f" IS{format_f(value, 10, 7, rounding=rounding)} WITH{format_i(n, 4)} PANELS"
    )


@dataclass(frozen=True, slots=True)
class SimpsonStep:
    """One ordinate of Simpson's sum: index ``k`` (0..N), abscissa ``x``, ``fx`` = F(X) and its
    ``weight`` (1 at both ends, 4 at odd k, 2 at interior even k)."""

    k: int
    x: float
    fx: float
    weight: float


@dataclass(frozen=True, slots=True)
class SimpsonResult:
    """Outcome of :func:`simpson`.

    ``value`` is SININT = DELX/3*SUM; ``iterations`` the number of ordinates evaluated (N + 1);
    ``steps`` the ordinates sorted by ``k``. ``b`` and ``n`` are the inputs, ``delx`` = B/N and
    ``sum`` the weighted sum of the ordinates before the DELX/3 factor.
    """

    value: float
    converged: bool
    iterations: int
    steps: tuple[SimpsonStep, ...]
    b: float
    n: int
    delx: float
    sum: float

    def book_text(self, *, carriage_control: bool = False, rounding: Rounding = _ROUNDING) -> str:
        """The program's line-printer output (format 201), reproducing the layout of the scan.

        ``carriage_control=True`` keeps the leading blank of the record, as a modern Fortran
        processor writes it to stdout; ``rounding`` selects another output rounding mode.
        """
        return render_records([_fmt_value(self.b, self.value, self.n, rounding)], carriage_control)


def _sorted_steps(rows: dict[int, SimpsonStep]) -> tuple[SimpsonStep, ...]:
    return tuple(rows[k] for k in sorted(rows))


def simpson(
    f: Callable[[float], float],
    b: float,
    n: int,
    *,
    f0: float | None = None,
) -> SimpsonResult:
    """Integrate ``f`` from 0 to ``b`` with Simpson's 1/3 rule on ``n`` panels, as the book does.

    ``f0`` is the ordinate at X = 0, the seed of the sum (the book writes ``1.0``, the limit of
    SIN(X)/X); when omitted, ``f(0.0)`` is evaluated.

    Raises:
        OddPanelsError: ``n`` is odd (format 200); checked first, as in the scan.
        InputError: ``n`` is not an integer, ``n < 2`` (N = 0 divides by zero in the book) or
            ``n > MAX_PANELS``; ``b`` or ``f0`` is not finite; or ``f`` returned NaN or an
            infinity (the Fortran driver reports the same ``INPUT`` error). Errors raised by
            ``f`` itself (for example :class:`~gerald_na.errors.ExpressionError` from a learner
            function, such as a division by zero at X = 0) propagate with their class kept.
            Both carry the ordinates evaluated before the failure in ``steps``.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise InputError(f"the number of panels N must be an integer, got {n!r}")
    b = float(b)
    if not math.isfinite(b):
        raise InputError(f"the upper limit B must be a finite number, got {b!r}")

    # NHALF = N/2 (truncating, as Fortran integer division);  IF (N - 2*NHALF) 99,1,99
    nhalf = abs(n) // 2 if n >= 0 else -(abs(n) // 2)
    if n - 2 * nhalf != 0:
        raise OddPanelsError(TRACE_MSG_ODD_PANELS, book_output=MSG_ODD_PANELS + "\n")
    if n < 2 or n > MAX_PANELS:
        raise InputError(
            f"the number of panels N must be an even number from 2 to {MAX_PANELS} (got {n})"
        )

    rows: dict[int, SimpsonStep] = {}

    def ordinate(k: int, x: float, weight: float, value: float | None = None) -> float:
        try:
            fx = float(f(x)) if value is None else float(value)
        except GeraldNAError as exc:
            exc.steps = _sorted_steps(rows)
            exc.book_output = ""
            raise
        if not math.isfinite(fx):
            raise InputError(
                f"F(X) is not a finite number at X = {x!r}",
                steps=_sorted_steps(rows),
                book_output="",
            )
        rows[k] = SimpsonStep(k=k, x=x, fx=fx, weight=weight)
        return fx

    # 1 XN = N;  DELX = B/XN
    xn = float(n)
    delx = b / xn

    # SUM = 1.0 + 4.*F(DELX) + F(B)
    y0 = ordinate(0, 0.0, 1.0, f0)
    y1 = ordinate(1, delx, 4.0)
    yb = ordinate(n, b, 1.0)
    total = y0 + 4.0 * y1 + yb

    # X = 2.*DELX;  DO 10 I = 2,NHALF
    x = 2.0 * delx
    for i in range(2, nhalf + 1):
        # SUM = SUM + 2.*F(X) + 4.*F(X+DELX)
        ya = ordinate(2 * i - 2, x, 2.0)
        yc = ordinate(2 * i - 1, x + delx, 4.0)
        total = total + 2.0 * ya + 4.0 * yc
        # 10 X = X + 2.*DELX
        x = x + 2.0 * delx

    # SININT = DELX/3.*SUM
    value = delx / 3.0 * total
    steps = _sorted_steps(rows)
    return SimpsonResult(
        value=value,
        converged=True,
        iterations=len(steps),
        steps=steps,
        b=b,
        n=n,
        delx=delx,
        sum=total,
    )
