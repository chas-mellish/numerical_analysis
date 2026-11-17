"""Engine adapter of ``lagrange_interpolation`` (:mod:`gerald_na.algorithms.lagrange`).

Inputs ``n`` (int), ``points`` (``n`` pairs X, Y) and ``xin`` are coupled: ``n`` must equal the
number of points, which :meth:`LagrangeAdapter.input_problems` reports (keyed by ``n``, so the
web form marks that field) and ``check_inputs`` enforces on both engines before anything runs
(the catalog bounds alone cannot express it).

Data card (book layout, ``READ 100, N, (X(I), Y(I), I = 1,N)`` with ``100 FORMAT (I2/(2F10.0))``
and ``READ 101, XIN``): N on the first card written like the book's ``05``, one ``X Y`` pair per
card, XIN on the last card; reals with ``repr`` precision. Trace
(``fortran/app/lagrange_interpolation.f90``)::

    STEP,i=<int>,x=<r>,y=<r>,term=<r>,partial=<r>
    RESULT,value=<r>,converged=T,iterations=<n>

``n``, ``xs``, ``ys`` and ``xin`` of the result are the request's inputs. ``verbose_text``
reproduces the driver's ``write_verbose`` (every term and running sum at full precision).
"""

import random
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar

from gerald_na.algorithms._fortran_format import format_i, render_records
from gerald_na.algorithms.lagrange import LagrangeResult, LagrangeStep, lagrange
from gerald_na.engines.adapters._common import int_input, real_input, trace_real, verbose_header
from gerald_na.engines.programs import Function, ProgramAdapter, card_number
from gerald_na.engines.trace import Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["LagrangeAdapter"]


def _points(inputs: Mapping[str, InputValue]) -> tuple[tuple[float, float], ...]:
    value = inputs["points"]
    if not isinstance(value, tuple) or not all(
        isinstance(point, tuple) and len(point) == 2 for point in value
    ):
        raise TypeError(f"input 'points' must be a list of (x, y) pairs, got {value!r}")
    return tuple((float(point[0]), float(point[1])) for point in value)  # type: ignore[index]


class LagrangeAdapter(ProgramAdapter):
    """``lagrange(xs, ys, xin)`` and its ``STEP``/``RESULT`` records."""

    program_id: ClassVar[str] = "lagrange_interpolation"
    result_type: ClassVar[type] = LagrangeResult
    step_type: ClassVar[type] = LagrangeStep
    count_inputs: ClassVar[Mapping[str, str]] = MappingProxyType({"n": "points"})
    parity_outcomes: ClassVar[frozenset[str]] = frozenset({"OK", "INPUT"})

    def input_problems(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue]
    ) -> dict[str, str]:
        n, points = int_input(inputs, "n"), _points(inputs)
        if n != len(points):
            return {
                "n": f"input 'n' is {n} but 'points' has {len(points)} pairs: "
                "N must equal the number of (X, Y) pairs on the data card"
            }
        return {}

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> LagrangeResult:
        if function is not None:
            raise TypeError("lagrange takes data, not a function")
        points = _points(inputs)
        return lagrange([x for x, _ in points], [y for _, y in points], real_input(inputs, "xin"))

    def random_inputs(self, entry: CatalogEntry, rng: random.Random) -> dict[str, Any] | None:
        """``n`` in 1..10 and exactly ``n`` well-spaced pairs.

        Half the sets lie around the book's data (X in [2, 9], Y = ASINH-like values), half
        anywhere in the catalog range at scales from 1e-2 to 1e5. Nodes are a jittered grid
        (distinct and well spaced) in random order; XIN ranges a quarter span beyond the nodes
        (extrapolation). About one set in ten repeats an X value, exercising the INPUT error on
        both engines.
        """
        item = entry.input("points")
        spread = 10.0  # the catalog bounds, or +-10 around 0 where one is missing
        low = item.min if item.min is not None else -spread
        high = item.max if item.max is not None else spread
        n = rng.randint(1, 10)
        if rng.random() < 0.5:
            lo, hi = 2.0, 9.0
        else:
            span = 10.0 ** rng.uniform(-2.0, 5.0)
            lo = rng.uniform(low / 2.0, high / 2.0)
            hi = lo + span
        h = (hi - lo) / max(n - 1, 1)
        xs = [lo + (k + rng.uniform(-0.3, 0.3)) * h for k in range(n)]
        rng.shuffle(xs)
        scale = 10.0 ** rng.uniform(-1.0, 3.0)
        ys = [rng.uniform(-scale, scale) for _ in range(n)]
        if n >= 2 and rng.random() < 0.1:
            i, j = rng.sample(range(n), 2)
            xs[j] = xs[i]
        width = max(hi - lo, 1.0)
        xin = rng.uniform(lo - width / 4.0, hi + width / 4.0)

        def clamp(value: float) -> float:
            return float(min(max(value, low), high))

        return {
            "n": n,
            "points": [[clamp(x), clamp(y)] for x, y in zip(xs, ys, strict=True)],
            "xin": clamp(xin),
        }

    def data_card(self, entry: CatalogEntry, inputs: Mapping[str, InputValue]) -> str:
        n = int_input(inputs, "n")
        lines = [f"{n:02d}" if 0 <= n <= 99 else str(n)]  # I2, as on the book's card "05"
        lines.extend(f"{card_number(x)} {card_number(y)}" for x, y in _points(inputs))
        lines.append(card_number(real_input(inputs, "xin")))
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
            n=int_input(inputs, "n"),
            xs=tuple(x for x, _ in points),
            ys=tuple(y for _, y in points),
            xin=real_input(inputs, "xin"),
        )

    def verbose_text(
        self,
        entry: CatalogEntry,
        inputs: Mapping[str, InputValue],
        result: LagrangeResult,
        *,
        preset: int | None = None,
        function: Function | None = None,
    ) -> str:
        """The driver's ``--verbose`` extras (data only: no function line)."""
        records = verbose_header(entry, None, None)
        records.append(f" DATA CARD: N = {result.n}  XIN = {trace_real(result.xin)}")
        records.append(
            " TERM(I) = Y(I) * PRODUCT OVER J /= I OF (XIN - X(J))/(X(I) - X(J));"
            "  YOUT = RUNNING SUM"
        )
        records.extend(
            f" I = {format_i(step.i, 2)}  X = {trace_real(step.x)}  Y = {trace_real(step.y)}"
            f"  TERM = {trace_real(step.term)}  YOUT = {trace_real(step.partial)}"
            for step in result.steps
        )
        records.append(f" VALUE = {trace_real(result.value)}  ({result.iterations} TERMS)")
        return render_records(records, carriage_control=False)
