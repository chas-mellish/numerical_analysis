"""Typed errors shared by the Python engine, the Fortran runner and the web layer.

Every error path that ended in ``CALL EXIT`` in the original listings raises one of these.
Each class carries a stable :attr:`GeraldNAError.code`. The codes of the algorithm errors are
exactly the ``code=`` values of the ``ERROR`` records that the Fortran drivers print in
``--trace`` mode, so both engines report failures identically (see ``docs/architecture.md``).
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import ClassVar

__all__ = [
    "TRACE_ERROR_CODES",
    "BracketError",
    "DegreeError",
    "EngineError",
    "EngineUnavailableError",
    "ExpressionError",
    "FortranRunError",
    "GeraldNAError",
    "InputError",
    "NonConvergenceError",
    "OddPanelsError",
    "ZeroProductError",
]


class GeraldNAError(Exception):
    """Base class of every error raised by :mod:`gerald_na`.

    Algorithm errors raised part-way through an iteration may carry context for the UI:
    ``steps`` holds the iteration rows computed before the failure (the step dataclasses of the
    algorithm that raised, for example ``BisectionStep``), and ``book_output`` holds the book's
    line-printer text up to and including the error message.
    """

    code: ClassVar[str] = "ERROR"

    def __init__(
        self,
        message: str,
        *,
        steps: Iterable[object] = (),
        book_output: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.steps: tuple[object, ...] = tuple(steps)
        self.book_output = book_output


class InputError(GeraldNAError, ValueError):
    """Invalid input data (data card values out of range, malformed values, bad options)."""

    code: ClassVar[str] = "INPUT"


class ExpressionError(InputError):
    """A learner-supplied function expression is invalid, unsafe, or cannot be evaluated.

    ``position`` is the 1-based column in :attr:`source` where a parse or validation problem
    was found (``None`` for evaluation errors and whole-input problems), so the form can point
    at it.
    """

    code: ClassVar[str] = "EXPRESSION"

    def __init__(self, message: str, *, source: str = "", position: int | None = None) -> None:
        super().__init__(message)
        self.source = source
        self.position = position


class BracketError(GeraldNAError, ValueError):
    """The starting interval does not bracket a root (no sign change)."""

    code: ClassVar[str] = "BRACKET"


class ZeroProductError(BracketError):
    """Bisection ``ERROR.`` branch: the product ``F(X)*F(X1)`` is exactly zero mid-iteration."""

    code: ClassVar[str] = "ZERO_PRODUCT"


class OddPanelsError(GeraldNAError, ValueError):
    """Simpson's 1/3 rule needs an even number of panels."""

    code: ClassVar[str] = "ODD_PANELS"


class NonConvergenceError(GeraldNAError, ArithmeticError):
    """The iteration did not meet its tolerance within the allowed number of steps."""

    code: ClassVar[str] = "NON_CONVERGENT"


class DegreeError(GeraldNAError, ValueError):
    """The polynomial degree (or number of interpolation points) is outside the supported range."""

    code: ClassVar[str] = "DEGREE"


class EngineError(GeraldNAError):
    """An engine could not produce a result for reasons other than the algorithm itself."""

    code: ClassVar[str] = "ENGINE"


class EngineUnavailableError(EngineError):
    """The requested engine is disabled or its executable is missing."""

    code: ClassVar[str] = "ENGINE_UNAVAILABLE"


class FortranRunError(EngineError):
    """A Fortran driver timed out, crashed, or produced output that violates the trace protocol."""

    code: ClassVar[str] = "FORTRAN_RUN"


TRACE_ERROR_CODES: Mapping[str, type[GeraldNAError]] = MappingProxyType(
    {
        cls.code: cls
        for cls in (
            InputError,
            BracketError,
            ZeroProductError,
            OddPanelsError,
            NonConvergenceError,
            DegreeError,
        )
    }
)
"""Map from the ``code=`` field of a trace ``ERROR`` record to the matching error class."""
