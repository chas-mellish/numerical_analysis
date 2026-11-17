"""Engine adapter of ``ch03_p01`` (Simpson's 1/3 rule, :mod:`gerald_na.algorithms.simpson`).

Data card ``B N`` (generic serialization). Trace (``fortran/app/ch03_p01_simpson.f90``)::

    STEP,k=<int>,x=<r>,fx=<r>,weight=<r>          one per ordinate, k = 0..N
    RESULT,value=<r>,converged=T,iterations=<int>,delx=<r>,sum=<r>

``b`` and ``n`` of the result are the request's inputs.

The seed of the sum: the book writes ``SUM = 1.0 + ...`` because its integrand ``SIN(X)/X``
cannot be evaluated at X = 0; the literal is that function's limit at 0. The Fortran preset
(``f_sinc``) returns exactly 1 there, but the catalog expression ``SIN(X)/X`` compiled by
:mod:`gerald_na.expr` divides by zero. So when the function is the book's integrand -- the
default preset, or a learner expression that normalizes to the same text -- this adapter passes
the book's seed :data:`~gerald_na.algorithms.simpson.BOOK_SEED` as ``f0``; every other function
supplies its own ordinate ``f(0)`` (and a learner function undefined at 0 is reported as an
expression error at X = 0).
"""

from collections.abc import Mapping
from functools import lru_cache
from typing import ClassVar

from gerald_na.algorithms.simpson import BOOK_SEED, SimpsonResult, SimpsonStep, simpson
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.expr import CompiledExpr, compile_expr
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["SimpsonAdapter", "book_seed_for"]


def _real(inputs: Mapping[str, InputValue], name: str) -> float:
    value = inputs[name]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"input {name!r} must be a number, got {value!r}")
    return float(value)


def _int(inputs: Mapping[str, InputValue], name: str) -> int:
    value = inputs[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"input {name!r} must be an integer, got {value!r}")
    return value


@lru_cache(maxsize=16)
def _normalized(source: str) -> str:
    return compile_expr(source).normalized


def book_seed_for(entry: CatalogEntry, function: Function) -> float | None:
    """``BOOK_SEED`` when ``function`` is the book's integrand (the default preset), else ``None``.

    The comparison uses the normalized expression text, so ``SINF(X)/X`` typed by a learner is
    recognized as the book's function as well.
    """
    if not isinstance(function, CompiledExpr) or entry.function.default_preset is None:
        return None
    book = entry.function.preset(entry.function.default_preset).expr
    return BOOK_SEED if function.normalized == _normalized(book) else None


class SimpsonAdapter(ProgramAdapter):
    """``simpson(f, b, n)`` and its ``STEP``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch03_p01"
    result_type: ClassVar[type] = SimpsonResult
    step_type: ClassVar[type] = SimpsonStep

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> SimpsonResult:
        if function is None:
            raise TypeError("simpson needs a function")
        return simpson(
            function,
            _real(inputs, "b"),
            _int(inputs, "n"),
            f0=book_seed_for(entry, function),
        )

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> SimpsonResult:
        record = trace.result
        if record is None:
            raise FortranRunError("simpson trace has no RESULT record")
        steps = self.steps_from_trace(entry, trace)
        iterations = record.integer("iterations")
        n = _int(inputs, "n")
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
            b=_real(inputs, "b"),
            n=n,
            delx=record.real("delx"),
            sum=record.real("sum"),
        )
