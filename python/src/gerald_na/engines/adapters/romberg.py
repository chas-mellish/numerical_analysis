"""Engine adapter of ``ch03_p02`` (Romberg integration, :mod:`gerald_na.algorithms.romberg`).

Data card ``B TOL`` (generic serialization). Trace (``fortran/app/ch03_p02_romberg.f90``)::

    STEP,k=<int>,panels=<int>,h=<r>,trap=<r>,best=<r>,diff=<r>     one per halving
    TABLE,row=<int>,col=<int>,value=<r>                            TRAP(row,col), every cell
    RESULT,value=<r>,converged=<T|F>,iterations=<int>,subintervals=<int>

``converged=F`` is the book's "did not meet tolerance after 8 extrapolations" outcome, a result
like any other. ``b`` and ``tol`` of the result are the request's inputs. ``verbose_text``
reproduces the driver's ``write_verbose`` (the seed F(0) + F(B), the whole table, the last test).

The seed of the sum: the book writes ``SUM = 1. + FCN(B)`` because its integrand ``SIN(X)/X``
cannot be evaluated at X = 0. The shared base class
:class:`~gerald_na.engines.adapters._common.BookSeededIntegrandAdapter` passes the book's seed
:data:`~gerald_na.algorithms.romberg.BOOK_SEED` as ``f0`` when the function is the book's
integrand (:func:`~gerald_na.engines.adapters._common.book_seed_for`, also used by the
Simpson adapter); every other function supplies its own ordinate ``f(0)``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar

from gerald_na.algorithms._fortran_format import render_records
from gerald_na.algorithms.romberg import (
    BOOK_FIRST_PANELS,
    BOOK_MAX_HALVINGS,
    BOOK_SEED,
    RombergResult,
    RombergStep,
    romberg,
)
from gerald_na.engines.adapters._common import (
    BookSeededIntegrandAdapter,
    real_input,
    trace_logical,
    trace_real,
    verbose_header,
)
from gerald_na.engines.programs import Function
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["RombergAdapter"]

TABLE = "TABLE"
"""Trace record type of the Romberg table cells."""


class RombergAdapter(BookSeededIntegrandAdapter):
    """``romberg(f, b, tol)`` and its ``STEP``/``TABLE``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch03_p02"
    result_type: ClassVar[type] = RombergResult
    step_type: ClassVar[type] = RombergStep
    book_seed: ClassVar[float] = BOOK_SEED
    parity_cases: ClassVar[Mapping[str, Mapping[str, InputValue]]] = MappingProxyType(
        {"table_full": {"b": 100.0, "tol": 1.0e-14}}
    )
    """``table_full``: a TOL no row meets for presets 2 and 3, so the table fills (9x9) and the
    result has ``converged=F``."""

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> RombergResult:
        if function is None:
            raise TypeError("romberg needs a function")
        return romberg(
            self.integrand(entry, function),
            real_input(inputs, "b"),
            real_input(inputs, "tol"),
            f0=self.seed(entry, function),
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
            b=real_input(inputs, "b"),
            tol=real_input(inputs, "tol"),
        )

    def verbose_text(
        self,
        entry: CatalogEntry,
        inputs: Mapping[str, InputValue],
        result: RombergResult,
        *,
        preset: int | None = None,
        function: Function | None = None,
    ) -> str:
        """The driver's ``--verbose`` extras; the seed line evaluates the integrand at 0 and B.

        The book's integrand gives its literal seed at X = 0 (:meth:`integrand`), as the
        driver's preset ``f_sinc`` does.
        """
        if function is None:
            raise TypeError("romberg needs a function")
        f = self.integrand(entry, function)
        records = verbose_header(entry, preset, function, suffix=" ON [0, B]")
        records.append(f" DATA CARD: B = {trace_real(result.b)}  TOL = {trace_real(result.tol)}")
        records.append(
            f" SEED F(0) + F(B) = {trace_real(f(0.0))} + {trace_real(f(result.b))}"
            "  (THE BOOK USES 1. + FCN(B))"
        )
        records.append(
            " TABLE TRAP(ROW, COL), ROW = EXTRAPOLATION ORDER, COL = 10*2**(COL-1) SUBINTERVALS:"
        )
        for col, column in enumerate(result.table, start=1):
            records.extend(
                f"   TRAP({row},{col}) = {trace_real(value)}"
                for row, value in enumerate(column, start=1)
            )
        if result.steps:
            last = result.steps[-1]
            records.append(
                f" LAST TEST |TRAP(I+1,I+1) - TRAP(I,I+1)| = {trace_real(last.diff)}"
                f"  WITH I = {last.k}"
            )
        records.append(
            f" VALUE = {trace_real(result.value)}  CONVERGED = {trace_logical(result.converged)}"
        )
        records.append(
            f" HALVINGS = {result.iterations} OF {BOOK_MAX_HALVINGS}"
            f"  SUBINTERVALS = {result.subintervals}"
            f"  FUNCTION EVALUATIONS = {result.subintervals + 1}"
        )
        if not result.converged:
            size = BOOK_MAX_HALVINGS + 1
            records.append(
                f" THE TABLE IS FULL ({size}x{size}): TOL WAS NOT MET AFTER 8 EXTRAPOLATIONS"
            )
        return render_records(records, carriage_control=False)
