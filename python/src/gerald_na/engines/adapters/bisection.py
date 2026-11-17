"""Engine adapter of ``ch01_p01`` (interval halving, :mod:`gerald_na.algorithms.bisection`).

Data card ``X1 X2 TOL`` (generic serialization). Trace (``fortran/app/ch01_p01_bisection.f90``)::

    STEP,k=<int>,x1=<r>,x2=<r>,x=<r>,fx=<r>
    RESULT,value=<r>,converged=T,iterations=<int>,root_at_endpoint=<T|F>,fx1=<r>,fx2=<r>

``x1``, ``x2`` and ``tol`` of the result are the request's inputs and ``max_iter`` is the book's
constant 25, which the driver also uses.
"""

from collections.abc import Mapping
from typing import ClassVar

from gerald_na.algorithms.bisection import (
    BOOK_MAX_ITER,
    BisectionResult,
    BisectionStep,
    bisection,
)
from gerald_na.engines.adapters._common import real_input
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["BisectionAdapter"]


class BisectionAdapter(ProgramAdapter):
    """``bisection(f, x1, x2, tol)`` and its ``STEP``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch01_p01"
    result_type: ClassVar[type] = BisectionResult
    step_type: ClassVar[type] = BisectionStep
    parity_outcomes: ClassVar[frozenset[str]] = frozenset({"OK", "BRACKET", "NON_CONVERGENT"})

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> BisectionResult:
        if function is None:
            raise TypeError("bisection needs a function")
        return bisection(
            function,
            real_input(inputs, "x1"),
            real_input(inputs, "x2"),
            real_input(inputs, "tol"),
            max_iter=BOOK_MAX_ITER,
        )

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> BisectionResult:
        record = trace.result
        if record is None:
            raise FortranRunError("bisection trace has no RESULT record")
        steps = self.steps_from_trace(entry, trace)
        iterations = record.integer("iterations")
        root_at_endpoint = record.logical("root_at_endpoint")
        if iterations != len(steps) or (root_at_endpoint and iterations != 0):
            raise FortranRunError(
                f"bisection trace is inconsistent: iterations={iterations} with "
                f"{len(steps)} STEP records (root_at_endpoint={root_at_endpoint})"
            )
        return BisectionResult(
            value=record.real("value"),
            converged=record.logical("converged"),
            iterations=iterations,
            steps=tuple(steps),
            root_at_endpoint=root_at_endpoint,
            x1=real_input(inputs, "x1"),
            x2=real_input(inputs, "x2"),
            tol=real_input(inputs, "tol"),
            max_iter=BOOK_MAX_ITER,
            fx1=record.real("fx1"),
            fx2=record.real("fx2"),
        )
