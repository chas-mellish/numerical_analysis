"""Engine adapter of ``ch04_p01`` (:mod:`gerald_na.algorithms.central_difference`).

Data card ``X H`` (generic serialization). Trace (``fortran/app/ch04_p01_central_difference.f90``)::

    STEP,k=<int>,h=<r>,dx=<r>,ddx=<r>                     one per printed row, k = 1..10
    RESULT,value=<r>,converged=T,iterations=<int>,fo=<r>,first_dx=<r>,first_ddx=<r>,last_ddx=<r>

``value`` is DX of the last row; ``x`` and ``h`` of the result are the request's inputs.
``first_dx``, ``first_ddx`` and ``last_ddx`` repeat the first and last rows, and the adapter
rejects a trace in which they disagree with the ``STEP`` records. ``verbose_text`` reproduces
the driver's ``write_verbose`` (F(X), every row at full precision with the change from the row
before, which estimates the error of the earlier row).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar

from gerald_na.algorithms._fortran_format import render_records
from gerald_na.algorithms.central_difference import (
    BOOK_ROWS,
    CentralDifferenceResult,
    CentralDifferenceStep,
    central_difference,
)
from gerald_na.engines.adapters._common import real_input, trace_real, verbose_header
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["CentralDifferenceAdapter"]


class CentralDifferenceAdapter(ProgramAdapter):
    """``central_difference(f, x, h)`` and its ``STEP``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch04_p01"
    result_type: ClassVar[type] = CentralDifferenceResult
    step_type: ClassVar[type] = CentralDifferenceStep
    parity_outcomes: ClassVar[frozenset[str]] = frozenset({"OK", "INPUT"})
    """The data card itself is an ``INPUT`` error for preset 3 (``1 + LOG10(X)`` at X = 0), and
    random X near 0 leave LOG10's domain; the other presets run everywhere."""
    parity_cases: ClassVar[Mapping[str, Mapping[str, InputValue]]] = MappingProxyType(
        {
            "p91_log_table": {"x": 0.19, "h": 0.02},
            "round_off_zeros": {"x": 100.0, "h": 1.0e-6},
        }
    )
    """``p91_log_table``: the spacing of the book's p. 91 table (problem 2, preset 3).
    ``round_off_zeros``: X + H == X in the last rows, so DX and DDX are exact zeros and the book
    text prints ``0.0000000E-99`` (and ``AT X = *****``, F5.2 overflowing)."""

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> CentralDifferenceResult:
        if function is None:
            raise TypeError("central_difference needs a function")
        return central_difference(
            function, real_input(inputs, "x"), real_input(inputs, "h"), n_steps=BOOK_ROWS
        )

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> CentralDifferenceResult:
        record = trace.result
        if record is None:
            raise FortranRunError("central difference trace has no RESULT record")
        steps: tuple[CentralDifferenceStep, ...] = tuple(self.steps_from_trace(entry, trace))
        iterations = record.integer("iterations")
        if iterations != len(steps) or iterations != BOOK_ROWS:
            raise FortranRunError(
                f"central difference trace is inconsistent: iterations={iterations} with "
                f"{len(steps)} STEP records (the program prints {BOOK_ROWS} rows)"
            )
        if [step.k for step in steps] != list(range(1, BOOK_ROWS + 1)):
            raise FortranRunError("central difference trace: STEP records are not rows 1..10")
        value = record.real("value")
        first_dx = record.real("first_dx")
        first_ddx = record.real("first_ddx")
        last_ddx = record.real("last_ddx")
        if (value, last_ddx) != (steps[-1].dx, steps[-1].ddx) or (first_dx, first_ddx) != (
            steps[0].dx,
            steps[0].ddx,
        ):
            raise FortranRunError(
                "central difference trace: RESULT disagrees with the first or last STEP"
            )
        return CentralDifferenceResult(
            value=value,
            converged=record.logical("converged"),
            iterations=iterations,
            steps=steps,
            x=real_input(inputs, "x"),
            h=real_input(inputs, "h"),
            fo=record.real("fo"),
            first_dx=first_dx,
            first_ddx=first_ddx,
            last_ddx=last_ddx,
        )

    def verbose_text(
        self,
        entry: CatalogEntry,
        inputs: Mapping[str, InputValue],
        result: CentralDifferenceResult,
        *,
        preset: int | None = None,
        function: Function | None = None,
    ) -> str:
        """The driver's ``--verbose`` extras."""
        records = verbose_header(entry, preset, function)
        records.append(f" DATA CARD: X = {trace_real(result.x)}  H = {trace_real(result.h)}")
        records.append(f" FO = F(X) = {trace_real(result.fo)}")
        previous: CentralDifferenceStep | None = None
        for step in result.steps:
            line = (
                f"   ROW {step.k}: H = {trace_real(step.h)}  DX = {trace_real(step.dx)}"
                f"  DDX = {trace_real(step.ddx)}"
            )
            if previous is not None:
                line += (
                    f"  |DX CHANGE| = {trace_real(abs(step.dx - previous.dx))}"
                    f"  |DDX CHANGE| = {trace_real(abs(step.ddx - previous.ddx))}"
                )
            records.append(line)
            previous = step
        records.append(f" VALUE = DX OF THE LAST ROW = {trace_real(result.value)}")
        return render_records(records, carriage_control=False)
