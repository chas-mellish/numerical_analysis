"""Engine adapter of ``ch03_p02`` (Romberg integration, :mod:`gerald_na.algorithms.romberg`).

Data card ``B TOL`` (generic serialization). Trace (``fortran/app/ch03_p02_romberg.f90``)::

    STEP,k=<int>,panels=<int>,h=<r>,trap=<r>,best=<r>,diff=<r>     one per halving
    TABLE,row=<int>,col=<int>,value=<r>                            TRAP(row,col), every cell
    RESULT,value=<r>,converged=<T|F>,iterations=<int>,subintervals=<int>

``converged=F`` is the book's "did not meet tolerance after 8 extrapolations" outcome, a result
like any other. ``b`` and ``tol`` of the result are the request's inputs.

The seed of the sum: the book writes ``SUM = 1. + FCN(B)`` because its integrand ``SIN(X)/X``
cannot be evaluated at X = 0; the literal is that function's limit at 0. The Fortran preset
(``f_sinc``) returns exactly 1 there, but the catalog expression ``SIN(X)/X`` compiled by
:mod:`gerald_na.expr` divides by zero. So when the function is the book's integrand -- the
default preset, or a learner expression that normalizes to the same text -- this adapter passes
the book's seed :data:`~gerald_na.algorithms.romberg.BOOK_SEED` as ``f0``; every other function
supplies its own ordinate ``f(0)`` (and a learner function undefined at 0 is reported as an
expression error at X = 0). Same convention as the Simpson adapter (``ch03_p01``).
"""

from collections.abc import Mapping
from functools import lru_cache
from typing import ClassVar

from gerald_na.algorithms.romberg import (
    BOOK_FIRST_PANELS,
    BOOK_SEED,
    RombergResult,
    RombergStep,
    romberg,
)
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.expr import CompiledExpr, compile_expr
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["RombergAdapter", "book_seed_for"]

TABLE = "TABLE"
"""Trace record type of the Romberg table cells."""


def _real(inputs: Mapping[str, InputValue], name: str) -> float:
    value = inputs[name]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"input {name!r} must be a number, got {value!r}")
    return float(value)


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


class RombergAdapter(ProgramAdapter):
    """``romberg(f, b, tol)`` and its ``STEP``/``TABLE``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch03_p02"
    result_type: ClassVar[type] = RombergResult
    step_type: ClassVar[type] = RombergStep

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> RombergResult:
        if function is None:
            raise TypeError("romberg needs a function")
        return romberg(
            function,
            _real(inputs, "b"),
            _real(inputs, "tol"),
            f0=book_seed_for(entry, function),
        )

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> RombergResult:
        record = trace.result
        if record is None:
            raise FortranRunError("romberg trace has no RESULT record")
        steps = self.steps_from_trace(entry, trace)
        iterations = record.integer("iterations")
        subintervals = record.integer("subintervals")
        rows = iterations + 1
        if iterations != len(steps) or subintervals != BOOK_FIRST_PANELS * 2**iterations:
            raise FortranRunError(
                f"romberg trace is inconsistent: iterations={iterations}, "
                f"subintervals={subintervals} with {len(steps)} STEP records"
            )
        cells: dict[tuple[int, int], float] = {}
        for cell in trace.of_type(TABLE):
            key = (cell.integer("row"), cell.integer("col"))
            row, col = key
            if key in cells or not 1 <= row <= col <= rows:
                raise FortranRunError(
                    f"trace line {cell.line}: unexpected or repeated TABLE cell {key}"
                )
            cells[key] = cell.real("value")
        if len(cells) != rows * (rows + 1) // 2:
            raise FortranRunError(
                f"romberg trace has {len(cells)} TABLE cells, expected the {rows}-line triangle"
            )
        table = tuple(
            tuple(cells[row, col] for row in range(1, col + 1)) for col in range(1, rows + 1)
        )
        return RombergResult(
            value=record.real("value"),
            converged=record.logical("converged"),
            iterations=iterations,
            steps=tuple(steps),
            table=table,
            subintervals=subintervals,
            b=_real(inputs, "b"),
            tol=_real(inputs, "tol"),
        )
