"""Engine adapter of ``lagrange_interpolation`` (:mod:`gerald_na.algorithms.lagrange`).

Inputs ``n`` (int), ``points`` (``n`` pairs X, Y) and ``xin`` are coupled: ``n`` must equal the
number of points, which :meth:`LagrangeAdapter.check_inputs` enforces on both engines before
anything runs (the catalog bounds alone cannot express it).

Data card (book layout, ``READ 100, N, (X(I), Y(I), I = 1,N)`` with ``100 FORMAT (I2/(2F10.0))``
and ``READ 101, XIN``): N on the first card written like the book's ``05``, one ``X Y`` pair per
card, XIN on the last card; reals with ``repr`` precision. Trace
(``fortran/app/lagrange_interpolation.f90``)::

    STEP,i=<int>,x=<r>,y=<r>,term=<r>,partial=<r>
    RESULT,value=<r>,converged=T,iterations=<n>

``n``, ``xs``, ``ys`` and ``xin`` of the result are the request's inputs.
"""

from collections.abc import Mapping
from typing import ClassVar

from gerald_na.algorithms.lagrange import LagrangeResult, LagrangeStep, lagrange
from gerald_na.engines.programs import Function, ProgramAdapter, card_number
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError, InputError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["LagrangeAdapter"]


def _count(inputs: Mapping[str, InputValue]) -> int:
    value = inputs["n"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"input 'n' must be an integer, got {value!r}")
    return value


def _points(inputs: Mapping[str, InputValue]) -> tuple[tuple[float, float], ...]:
    value = inputs["points"]
    if not isinstance(value, tuple) or not all(
        isinstance(point, tuple) and len(point) == 2 for point in value
    ):
        raise TypeError(f"input 'points' must be a list of (x, y) pairs, got {value!r}")
    return tuple((float(point[0]), float(point[1])) for point in value)  # type: ignore[index]


def _real(inputs: Mapping[str, InputValue], name: str) -> float:
    value = inputs[name]
    if not isinstance(value, int | float):
        raise TypeError(f"input {name!r} must be a number, got {value!r}")
    return float(value)


class LagrangeAdapter(ProgramAdapter):
    """``lagrange(xs, ys, xin)`` and its ``STEP``/``RESULT`` records."""

    program_id: ClassVar[str] = "lagrange_interpolation"
    result_type: ClassVar[type] = LagrangeResult
    step_type: ClassVar[type] = LagrangeStep

    def check_inputs(self, entry: CatalogEntry, inputs: Mapping[str, InputValue]) -> None:
        n, points = _count(inputs), _points(inputs)
        if n != len(points):
            raise InputError(
                f"input 'n' is {n} but 'points' has {len(points)} pairs: "
                "N must equal the number of (X, Y) pairs on the data card"
            )

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> LagrangeResult:
        if function is not None:
            raise TypeError("lagrange takes data, not a function")
        points = _points(inputs)
        return lagrange([x for x, _ in points], [y for _, y in points], _real(inputs, "xin"))

    def data_card(self, entry: CatalogEntry, inputs: Mapping[str, InputValue]) -> str:
        n = _count(inputs)
        lines = [f"{n:02d}" if 0 <= n <= 99 else str(n)]  # I2, as on the book's card "05"
        lines.extend(f"{card_number(x)} {card_number(y)}" for x, y in _points(inputs))
        lines.append(card_number(_real(inputs, "xin")))
        return "".join(line + "\n" for line in lines)

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> LagrangeResult:
        record = trace.result
        if record is None:
            raise FortranRunError("lagrange trace has no RESULT record")
        steps = self.steps_from_trace(entry, trace)
        points = _points(inputs)
        iterations = record.integer("iterations")
        if iterations != len(steps) or iterations != len(points):
            raise FortranRunError(
                f"lagrange trace is inconsistent: iterations={iterations} with "
                f"{len(steps)} STEP records for {len(points)} points"
            )
        if [step.i for step in steps] != list(range(1, len(points) + 1)):
            raise FortranRunError("lagrange trace STEP records are not numbered 1..n")
        return LagrangeResult(
            value=record.real("value"),
            converged=record.logical("converged"),
            iterations=iterations,
            steps=tuple(steps),
            n=_count(inputs),
            xs=tuple(x for x, _ in points),
            ys=tuple(y for _, y in points),
            xin=_real(inputs, "xin"),
        )
