"""Typed errors shared by the Python engine, the Fortran runner and the web layer.

Every error path that ended in ``CALL EXIT`` in the original listings raises one of these.
Each class carries a stable :attr:`GeraldNAError.code`. The codes of the algorithm errors are
exactly the ``code=`` values of the ``ERROR`` records that the Fortran drivers print in
``--trace`` mode, so both engines report failures identically (see ``docs/architecture.md``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar

__all__ = [
    "TRACE_ERROR_CODES",
    "BracketError",
    "DegreeError",
    "EngineError",
    "EngineUnavailableError",
    "FortranRunError",
    "GeraldNAError",
    "InputError",
    "NonConvergenceError",
    "OddPanelsError",
    "ZeroProductError",
    "error_from_trace",
]


class GeraldNAError(Exception):
    """Base class of every error raised by :mod:`gerald_na`."""

    code: ClassVar[str] = "ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InputError(GeraldNAError, ValueError):
    """Invalid input data (data card values out of range, malformed values, bad options)."""

    code: ClassVar[str] = "INPUT"


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


def error_from_trace(code: str, message: str) -> GeraldNAError:
    """Build the typed error for an ``ERROR,code=<code>,message=<message>`` trace record.

    Unknown codes are a protocol violation and yield a :class:`FortranRunError`.
    """
    cls = TRACE_ERROR_CODES.get(code)
    if cls is None:
        return FortranRunError(f"unknown trace error code {code!r}: {message}")
    return cls(message)
