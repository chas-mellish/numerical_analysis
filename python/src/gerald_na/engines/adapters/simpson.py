"""Engine adapter of ``ch03_p01`` (Simpson's 1/3 rule, :mod:`gerald_na.algorithms.simpson`).

Data card ``B N`` (generic serialization). Trace (``fortran/app/ch03_p01_simpson.f90``)::

    STEP,k=<int>,x=<r>,fx=<r>,weight=<r>          one per ordinate, k = 0..N
    RESULT,value=<r>,converged=T,iterations=<int>,delx=<r>,sum=<r>

``b`` and ``n`` of the result are the request's inputs.

The seed of the sum: the book writes ``SUM = 1.0 + ...`` because its integrand ``SIN(X)/X``
cannot be evaluated at X = 0. The shared base class
:class:`~gerald_na.engines.adapters._common.BookSeededIntegrandAdapter` passes the book's seed
:data:`~gerald_na.algorithms.simpson.BOOK_SEED` as ``f0`` when the function is the book's
integrand (:func:`~gerald_na.engines.adapters._common.book_seed_for`, also used by the
Romberg adapter); every other function supplies its own ordinate ``f(0)``.
"""

from collections.abc import Mapping
from typing import ClassVar

from gerald_na.algorithms.simpson import BOOK_SEED, SimpsonResult, SimpsonStep, simpson
from gerald_na.engines.adapters._common import BookSeededIntegrandAdapter, int_input, real_input
from gerald_na.engines.programs import Function
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["SimpsonAdapter"]


class SimpsonAdapter(BookSeededIntegrandAdapter):
    """``simpson(f, b, n)`` and its ``STEP``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch03_p01"
    result_type: ClassVar[type] = SimpsonResult
    step_type: ClassVar[type] = SimpsonStep
    book_seed: ClassVar[float] = BOOK_SEED
    parity_outcomes: ClassVar[frozenset[str]] = frozenset({"OK", "ODD_PANELS"})

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> SimpsonResult:
        if function is None:
            raise TypeError("simpson needs a function")
        return simpson(
            self.integrand(entry, function),
            real_input(inputs, "b"),
            int_input(inputs, "n"),
            f0=self.seed(entry, function),
        )

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> SimpsonResult:
        record = trace.result
        if record is None:
            raise FortranRunError("simpson trace has no RESULT record")
        steps = self.steps_from_trace(entry, trace)
        iterations = record.integer("iterations")
        n = int_input(inputs, "n")
        if iterations != len(steps) or iterations != n + 1:
            raise FortranRunError(
                f"simpson trace is inconsistent: iterations={iterations} with "
                f"{len(steps)} STEP records for N = {n}"
            )
        if [step.k for step in steps] != list(range(n + 1)):
            raise FortranRunError("simpson trace: STEP records are not the ordinates k = 0..N")
        return SimpsonResult(
            value=record.real("value"),
            converged=record.logical("converged"),
            iterations=iterations,
            steps=tuple(steps),
            b=real_input(inputs, "b"),
            n=n,
            delx=record.real("delx"),
            sum=record.real("sum"),
        )
