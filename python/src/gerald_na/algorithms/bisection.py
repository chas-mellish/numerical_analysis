"""Chapter 1, Program 1: solution of F(X) = 0 by the interval-halving (bisection) method.

A line-by-line port of the listing in ``docs/chapter_01_program_01_listing.pdf``. The original
control flow, transcribed from the scan, is::

          FX1 = F(X1)
          FX2 = F(X2)
          IF (FX1*FX2) 1, 2, 3
        3 TYPE 200                      no sign change          -> BracketError
          CALL EXIT
        2 IF (FX1) 4, 5, 4              product is exactly zero
        5 PRINT 201, X1                 X1 is a root            -> result, root_at_endpoint
        4 IF (FX2) 6, 7, 6
        7 PRINT 201, X2                 X2 is a root            -> result, root_at_endpoint
          CALL EXIT
        6 PRINT 202                     product underflowed     -> ZeroProductError
          CALL EXIT
        1 DO 30 I = 1, 25
          X = (X1 + X2)/2.
          FX = F(X)
          PRINT 206, X, FX
          IF (ABSF(FX) - TOL) 8, 8, 9   converged when |F(X)| <= TOL
        9 IF (FX*FX1) 10, 11, 12
       10 X2 = X                        root in [X1, X]
          GO TO 30
       12 X1 = X                        root in [X, X2]
          FX1 = FX
       30 CONTINUE
          PRINT 204                     25 halvings used up     -> NonConvergenceError
          CALL EXIT
       11 PRINT 205                     FX*FX1 exactly zero     -> ZeroProductError
          CALL EXIT
        8 PRINT 203, X, I               converged               -> result
          CALL EXIT

ERRATA (scan versus the drifted rewrite in ``legacy_code/fortran/chapter_1/bisection.f90``; the
rewrite is not followed):

* The rewrite drops the ``ERROR.`` branch (label 11) when ``FX*FX1`` is exactly zero; restored.
* The rewrite's messages differ; the scan's ``NON-CONVERGENT IN 25 ITERATIONS.`` and the
  ``F6.3`` edit descriptor of format 201 (the rewrite uses ``F10.7``) are restored.
* Genuine bug in the original (catalog erratum ``label-5-fall-through``): label 5 has no
  ``CALL EXIT``, so when X1 is a root and X2 is not, control falls through to label 4 and then
  to 6, printing the ``ERROR. FX1 AND FX2 NOT ZERO`` message after the root message. The port
  stops after reporting the root(s): the result is a root at X1, and the book text shows format
  201 for X1 (and for X2 as well when both are roots, which the original prints correctly).
* The book's output was printed by a processor that truncates on output (the exact midpoint
  0.443572998046875 appears as ``.4435729``, 0.443359375 as ``.4433593``); :meth:`book_text`
  therefore renders with ``RZ`` rounding and without the optional leading zero.

The book computed in single precision; this port runs in double precision and still needs 15
halvings for the book data card ``0. 1. 1.E-5`` (root ``.4435729``). Only the last printed digit
of a few F(X) values differs from the scan.
"""

from collections.abc import Callable
from dataclasses import dataclass

from gerald_na.algorithms._evaluation import evaluate_finite
from gerald_na.algorithms._fortran_format import Rounding, format_f, format_i, render_records
from gerald_na.errors import BracketError, InputError, NonConvergenceError, ZeroProductError

__all__ = [
    "BOOK_MAX_ITER",
    "MSG_NO_SIGN_CHANGE",
    "MSG_PRODUCT_ZERO",
    "MSG_ZERO_PRODUCT",
    "BisectionResult",
    "BisectionStep",
    "bisection",
    "msg_non_convergent",
]

BOOK_MAX_ITER = 25
"""``DO 30 I = 1, 25``: the book's limit on the number of halvings."""

MSG_NO_SIGN_CHANGE = (
    "FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS."
)
"""Format 200 (``TYPE 200``), printed when F(X1) and F(X2) have the same sign."""

MSG_PRODUCT_ZERO = "ERROR. FX1 AND FX2 NOT ZERO THOUGH PRODUCT TESTS ZERO."
"""Format 202, printed when F(X1)*F(X2) underflows to zero although neither factor is zero."""

MSG_ZERO_PRODUCT = "ERROR."
"""Format 205 (label 11), printed when F(X)*F(X1) is exactly zero inside the loop."""


def msg_non_convergent(max_iter: int = BOOK_MAX_ITER) -> str:
    """Format 204: ``NON-CONVERGENT IN 25 ITERATIONS.`` (with the actual limit)."""
    return f"NON-CONVERGENT IN {max_iter} ITERATIONS."


_ROUNDING = Rounding.ZERO
"""The book's output conversion truncates (see the module ERRATA)."""

# The FORMAT statements of the listing. Each record starts with the carriage-control blank.


def _fmt_step(x: float, fx: float, rounding: Rounding) -> str:
    """``206 FORMAT (8H AT X = , F10.7, 8H F(X) = ,F10.6)``."""
    return f" AT X = {format_f(x, 10, 7, rounding=rounding)} F(X) = " + format_f(
        fx, 10, 6, rounding=rounding
    )


def _fmt_root(x: float, iterations: int, rounding: Rounding) -> str:
    """``203 FORMAT (16H THE VALUE, X = ,F10.7, 12H IS A ROOT. , I3, 26H ITERATIONS ...)``."""
    return (
        f" THE VALUE, X = {format_f(x, 10, 7, rounding=rounding)} IS A ROOT. "
        f"{format_i(iterations, 3)} ITERATIONS WERE REQUIRED."
    )


def _fmt_input_root(x: float, rounding: Rounding) -> str:
    """``201 FORMAT (22H THE INPUT VALUE, X = ,F6.3, 27H IS A ROOT OF THE EQUATION.)``."""
    return (
        f" THE INPUT VALUE, X = {format_f(x, 6, 3, rounding=rounding)} IS A ROOT OF THE EQUATION."
    )


@dataclass(frozen=True, slots=True)
class BisectionStep:
    """One pass through the ``DO 30`` loop.

    ``x1`` and ``x2`` are the bracket at the start of the pass, ``x`` the midpoint and ``fx``
    the function value printed by format 206.
    """

    k: int
    x1: float
    x2: float
    x: float
    fx: float

    def book_line(self, *, rounding: Rounding = _ROUNDING) -> str:
        """The format-206 line for this step, as printed (no carriage-control column)."""
        return _fmt_step(self.x, self.fx, rounding)[1:]


@dataclass(frozen=True, slots=True)
class BisectionResult:
    """Outcome of :func:`bisection`.

    ``value`` is the root; ``iterations`` the number of halvings (0 when an input value is
    already a root, in which case ``root_at_endpoint`` is true and ``steps`` is empty).
    ``x1``, ``x2``, ``tol`` and ``max_iter`` are the inputs; ``fx1`` and ``fx2`` the function
    values at the input endpoints.
    """

    value: float
    converged: bool
    iterations: int
    steps: tuple[BisectionStep, ...]
    root_at_endpoint: bool
    x1: float
    x2: float
    tol: float
    max_iter: int
    fx1: float
    fx2: float

    def book_text(self, *, carriage_control: bool = False, rounding: Rounding = _ROUNDING) -> str:
        """The program's line-printer output, reproducing the layout of the scan.

        By default each line is shown as printed (the carriage-control blank consumed) with the
        book's truncating output conversion. ``carriage_control=True`` keeps the leading blank of
        every record, as a modern Fortran processor writes it to stdout; ``rounding`` selects
        another output rounding mode (for example ``Rounding.NEAREST``, gfortran's default).
        """
        if self.root_at_endpoint:
            records = [
                _fmt_input_root(x, rounding)
                for x, fx in ((self.x1, self.fx1), (self.x2, self.fx2))
                if fx == 0.0
            ]
        else:
            records = [_fmt_step(step.x, step.fx, rounding) for step in self.steps]
            records.append(_fmt_root(self.value, self.iterations, rounding))
        return render_records(records, carriage_control)


def _steps_text(steps: list[BisectionStep], final: str) -> str:
    records = [_fmt_step(step.x, step.fx, _ROUNDING) for step in steps]
    records.append(" " + final)
    return render_records(records, carriage_control=False)


def bisection(
    f: Callable[[float], float],
    x1: float,
    x2: float,
    tol: float,
    max_iter: int = BOOK_MAX_ITER,
) -> BisectionResult:
    """Find a root of ``f`` in ``[x1, x2]`` by interval halving, exactly as the book does.

    The loop stops at the first midpoint where ``|f(x)| <= tol``; there is no test on the
    interval width. ``max_iter`` is the book's constant 25 (``DO 30 I = 1, 25``).

    Raises:
        BracketError: ``f(x1)`` and ``f(x2)`` have the same sign (format 200).
        ZeroProductError: ``f(x1)*f(x2)`` underflows to zero although neither value is zero
            (format 202), or ``f(x)*f(x1)`` is exactly zero inside the loop (format 205). The
            loop case carries the steps computed so far in ``steps``.
        NonConvergenceError: ``max_iter`` halvings did not meet ``tol`` (format 204); carries
            all steps in ``steps``.
        InputError: ``max_iter`` is negative, or ``f`` returned NaN or an infinity (the Fortran
            drivers report the same ``INPUT`` error). Errors raised by ``f`` itself (for example
            :class:`~gerald_na.errors.ExpressionError` from a learner function) propagate with
            their class kept. Inside the loop either carries the rows completed so far in
            ``steps``, and ``book_output`` holds their lines (the book has no message for it).

    Every book error carries the book's output up to the failure in ``book_output``.
    """
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter < 0:
        raise InputError(f"max_iter must be a non-negative integer, got {max_iter!r}")
    x1, x2, tol = float(x1), float(x2), float(tol)
    start_x1, start_x2 = x1, x2

    fx1 = evaluate_finite(f, x1)
    fx2 = evaluate_finite(f, x2)
    start_fx1, start_fx2 = fx1, fx2

    # IF (FX1*FX2) 1, 2, 3
    product = fx1 * fx2
    if product > 0.0:
        raise BracketError(MSG_NO_SIGN_CHANGE, book_output=_steps_text([], MSG_NO_SIGN_CHANGE))
    if product == 0.0:
        if fx1 != 0.0 and fx2 != 0.0:
            raise ZeroProductError(MSG_PRODUCT_ZERO, book_output=_steps_text([], MSG_PRODUCT_ZERO))
        root = x1 if fx1 == 0.0 else x2
        return BisectionResult(
            value=root,
            converged=True,
            iterations=0,
            steps=(),
            root_at_endpoint=True,
            x1=start_x1,
            x2=start_x2,
            tol=tol,
            max_iter=max_iter,
            fx1=start_fx1,
            fx2=start_fx2,
        )

    steps: list[BisectionStep] = []
    for i in range(1, max_iter + 1):
        x = (x1 + x2) / 2.0
        try:
            fx = evaluate_finite(f, x)
        except InputError as exc:
            # Keep the error's class (a learner function raises ExpressionError) and attach the
            # rows completed so far, like the Fortran trace (STEP records before the ERROR).
            exc.steps = tuple(steps)
            exc.book_output = render_records(
                [_fmt_step(step.x, step.fx, _ROUNDING) for step in steps], carriage_control=False
            )
            raise
        steps.append(BisectionStep(k=i, x1=x1, x2=x2, x=x, fx=fx))
        # IF (ABSF(FX) - TOL) 8, 8, 9
        if abs(fx) - tol <= 0.0:
            return BisectionResult(
                value=x,
                converged=True,
                iterations=i,
                steps=tuple(steps),
                root_at_endpoint=False,
                x1=start_x1,
                x2=start_x2,
                tol=tol,
                max_iter=max_iter,
                fx1=start_fx1,
                fx2=start_fx2,
            )
        # IF (FX*FX1) 10, 11, 12
        sign_test = fx * fx1
        if sign_test < 0.0:
            x2 = x
        elif sign_test == 0.0:
            raise ZeroProductError(
                MSG_ZERO_PRODUCT,
                steps=steps,
                book_output=_steps_text(steps, MSG_ZERO_PRODUCT),
            )
        else:
            x1 = x
            fx1 = fx

    message = msg_non_convergent(max_iter)
    raise NonConvergenceError(message, steps=steps, book_output=_steps_text(steps, message))
