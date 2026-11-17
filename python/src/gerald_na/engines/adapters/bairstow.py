"""Engine adapter of ``ch01_p02`` (Bairstow factors, :mod:`gerald_na.algorithms.bairstow`).

Data cards (generic serialization, one line per card): card 1 ``a`` = the seven coefficients of
X**6 ... X**0, card 2 ``R1 S1 TEST LIM N``. Trace (``fortran/app/ch01_p02_bairstow.f90``)::

    STEP,factor=<int>,k=<int>,r=<r>,s=<r>,delr=<r>,dels=<r>
    FACTOR,kind=quadratic,r=<r>,s=<r>          after the last STEP of each factor
    FACTOR,kind=final_quadratic,a2=<r>,a1=<r>,a0=<r>   or   FACTOR,kind=linear,a1=<r>,a0=<r>
    RESULT,value=<number of factors>,converged=T,iterations=<int>,nudges=<int>

The data-card fields of the result are the request's inputs.
"""

from collections.abc import Mapping
from typing import ClassVar

from gerald_na.algorithms.bairstow import (
    BairstowFactor,
    BairstowResult,
    BairstowStep,
    FactorKind,
    bairstow,
)
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Record, Trace
from gerald_na.errors import FortranRunError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = ["FACTOR", "BairstowAdapter", "factor_from_record"]

FACTOR = "FACTOR"
"""Record type of the printed factors."""

_FACTOR_KEYS: dict[str, tuple[str, ...]] = {
    "quadratic": ("r", "s"),
    "final_quadratic": ("a2", "a1", "a0"),
    "linear": ("a1", "a0"),
}


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


def _coefficients(inputs: Mapping[str, InputValue]) -> tuple[float, ...]:
    value = inputs["a"]
    if not isinstance(value, tuple) or not all(isinstance(c, int | float) for c in value):
        raise TypeError(f"input 'a' must be a list of numbers, got {value!r}")
    return tuple(float(c) for c in value)  # type: ignore[arg-type]


def factor_from_record(record: Record) -> BairstowFactor:
    """A :class:`BairstowFactor` from one ``FACTOR`` record (exactly the documented keys)."""
    kind = record.text("kind")
    keys = _FACTOR_KEYS.get(kind)
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

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> BairstowResult:
        return bairstow(
            _coefficients(inputs),
            _real(inputs, "r1"),
            _real(inputs, "s1"),
            _real(inputs, "test"),
            _int(inputs, "lim"),
            _int(inputs, "n"),
        )

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
            r1=_real(inputs, "r1"),
            s1=_real(inputs, "s1"),
            test=_real(inputs, "test"),
            lim=_int(inputs, "lim"),
            n=_int(inputs, "n"),
            nudges=record.integer("nudges"),
        )

    def verbose_text(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], result: BairstowResult
    ) -> str:
        """The same extras as the driver's ``--verbose`` (true factors and roots)."""
        return result.verbose_text()
