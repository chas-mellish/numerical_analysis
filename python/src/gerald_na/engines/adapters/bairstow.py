"""Engine adapter of ``ch01_p02`` (Bairstow factors, :mod:`gerald_na.algorithms.bairstow`).

Data cards (generic serialization, one line per card): card 1 ``a`` = the seven coefficients of
X**6 ... X**0, card 2 ``R1 S1 TEST LIM N``. Trace (``fortran/app/ch01_p02_bairstow.f90``)::

    STEP,factor=<int>,k=<int>,r=<r>,s=<r>,delr=<r>,dels=<r>
    FACTOR,kind=quadratic,r=<r>,s=<r>          after the last STEP of each factor
    FACTOR,kind=final_quadratic,a2=<r>,a1=<r>,a0=<r>   or   FACTOR,kind=linear,a1=<r>,a0=<r>
    RESULT,value=<number of factors>,converged=T,iterations=<int>,nudges=<int>

The data-card fields of the result are the request's inputs.
"""

import random
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar

from gerald_na.algorithms.bairstow import (
    FACTOR_COEFFICIENT_NAMES,
    BairstowFactor,
    BairstowResult,
    BairstowStep,
    FactorKind,
    bairstow,
)
from gerald_na.engines.adapters._common import int_input, real_input
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Record, Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["FACTOR", "BairstowAdapter", "factor_from_record"]

FACTOR = "FACTOR"
"""Record type of the printed factors."""


def _coefficients(inputs: Mapping[str, InputValue]) -> tuple[float, ...]:
    value = inputs["a"]
    if not isinstance(value, tuple) or not all(isinstance(c, int | float) for c in value):
        raise TypeError(f"input 'a' must be a list of numbers, got {value!r}")
    return tuple(float(c) for c in value)  # type: ignore[arg-type]


def factor_from_record(record: Record) -> BairstowFactor:
    """A :class:`BairstowFactor` from one ``FACTOR`` record (exactly the documented keys)."""
    kind = record.text("kind")
    keys = FACTOR_COEFFICIENT_NAMES.get(kind)  # type: ignore[call-overload]
    if keys is None:
        raise FortranRunError(f"trace line {record.line}: unknown FACTOR kind {kind!r}")
    if set(record.fields) != {"kind", *keys}:
        raise FortranRunError(
            f"trace line {record.line}: FACTOR kind={kind} needs exactly the keys {list(keys)}"
        )
    factor_kind: FactorKind = kind  # type: ignore[assignment]
    return BairstowFactor(factor_kind, tuple(record.real(key) for key in keys))


class BairstowAdapter(ProgramAdapter):
    """``bairstow(coeffs, r1, s1, test, lim, n)`` and its ``STEP``/``FACTOR``/``RESULT`` records."""

    program_id: ClassVar[str] = "ch01_p02"
    result_type: ClassVar[type] = BairstowResult
    step_type: ClassVar[type] = BairstowStep
    parity_outcomes: ClassVar[frozenset[str]] = frozenset({"OK", "NON_CONVERGENT", "DEGREE"})
    parity_cases: ClassVar[Mapping[str, Mapping[str, InputValue]]] = MappingProxyType(
        {"singular": {"a": (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -16.0), "n": 4}}
    )
    """``singular``: x**4 - 16 from R = S = 0, so DENOM is exactly zero (one nudge)."""

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> BairstowResult:
        return bairstow(
            _coefficients(inputs),
            real_input(inputs, "r1"),
            real_input(inputs, "s1"),
            real_input(inputs, "test"),
            int_input(inputs, "lim"),
            int_input(inputs, "n"),
        )

    def random_inputs(self, entry: CatalogEntry, rng: random.Random) -> dict[str, Any] | None:
        """The coefficients above X**N must be zero, so they are drawn with N.

        Mostly valid cards (roots-based or arbitrary coefficients, degree 2..6), plus a few
        DEGREE cases (N out of range, or a nonzero coefficient above X**N) and tight LIMs.
        """
        n = rng.randint(2, 6)
        if rng.random() < 0.5:
            roots = [rng.uniform(-6.0, 6.0) for _ in range(n)]
            poly = [1.0]
            for root in roots:  # multiply by (x - root)
                poly = [a - root * b for a, b in zip([*poly, 0.0], [0.0, *poly], strict=True)]
            lead = rng.choice([1.0, -2.0, 0.5])
            coefficients = [lead * c for c in poly]
        else:
            coefficients = [rng.uniform(-100.0, 100.0) for _ in range(n + 1)]
        a = [0.0] * (6 - n) + coefficients
        roll = rng.random()
        if roll < 0.08:
            n = rng.choice([0, 1, 7, 12])
        elif roll < 0.16 and n < 6:
            a[rng.randint(0, 5 - n)] = rng.uniform(-5.0, 5.0)
        return {
            "a": a,
            "r1": rng.uniform(-3.0, 3.0) if rng.random() < 0.7 else 0.0,
            "s1": rng.uniform(-3.0, 3.0) if rng.random() < 0.7 else 0.0,
            "test": float(10.0 ** rng.uniform(-10.0, -2.0)),
            "lim": rng.choice([rng.randint(1, 8), rng.randint(20, 80)]),
            "n": n,
        }

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> BairstowResult:
        record = trace.result
        if record is None:
            raise FortranRunError("bairstow trace has no RESULT record")
        steps = self.steps_from_trace(entry, trace)
        factors = tuple(factor_from_record(r) for r in trace.of_type(FACTOR))
        value = record.integer("value")
        iterations = record.integer("iterations")
        if iterations != len(steps) or value != len(factors) or not factors:
            raise FortranRunError(
                f"bairstow trace is inconsistent: iterations={iterations} with {len(steps)} STEP "
                f"records, value={value} with {len(factors)} FACTOR records"
            )
        if factors[-1].kind == "quadratic" or any(f.kind != "quadratic" for f in factors[:-1]):
            raise FortranRunError("bairstow trace: only the last FACTOR may be linear/final")
        return BairstowResult(
            value=value,
            converged=record.logical("converged"),
            iterations=iterations,
            steps=tuple(steps),
            factors=factors,
            coeffs=_coefficients(inputs),
            r1=real_input(inputs, "r1"),
            s1=real_input(inputs, "s1"),
            test=real_input(inputs, "test"),
            lim=int_input(inputs, "lim"),
            n=int_input(inputs, "n"),
            nudges=record.integer("nudges"),
        )

    def verbose_text(
        self,
        entry: CatalogEntry,
        inputs: Mapping[str, InputValue],
        result: BairstowResult,
        *,
        preset: int | None = None,
        function: Function | None = None,
    ) -> str:
        """The same extras as the driver's ``--verbose`` (true factors and roots)."""
        return result.verbose_text()
