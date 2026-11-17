"""Engine interface: run requests, outcomes and catalog-driven input validation.

An :class:`Engine` runs one catalog program for a :class:`RunRequest` and returns a
:class:`RunOutcome`. Both engines return the *same* result dataclass for a program (for example
:class:`~gerald_na.algorithms.bisection.BisectionResult`), so the UI, the golden tests and compare
mode never need to know which engine produced it.

Error contract of :meth:`Engine.run`:

* Problems with the request itself are raised before anything runs: :class:`InputError`
  (unknown/missing input, wrong type, NaN or infinity, outside the catalog ``min``/``max``,
  wrong list length, bad preset; :class:`~gerald_na.errors.ExpressionError` for a bad custom
  function) and :class:`EngineUnavailableError` (engine disabled, executable missing, or a custom
  function requested on the Fortran engine).
* Everything that happens while the program runs is returned in :attr:`RunOutcome.error`: the
  typed algorithm errors (``BracketError``, ``NonConvergenceError``, ...) with the partial
  ``steps`` computed before the failure, and :class:`FortranRunError` (timeout, crash, protocol
  violation).
"""

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, ClassVar, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gerald_na.errors import GeraldNAError, InputError
from gerald_na.registry import CatalogEntry, CatalogInput
from gerald_na.registry.models import InputValue

__all__ = [
    "FORTRAN_INT_MAX",
    "Engine",
    "ProgramResult",
    "RunOutcome",
    "RunRequest",
    "consume_carriage_control",
    "resolve_preset",
    "result_to_dict",
    "step_to_dict",
    "validate_inputs",
    "validate_request",
]

FORTRAN_INT_MAX = 2**31 - 1
"""Largest default-kind Fortran integer; integer inputs without catalog bounds are limited to it."""


@runtime_checkable
class ProgramResult(Protocol):
    """What every algorithm result dataclass provides (``gerald_na.algorithms``)."""

    @property
    def value(self) -> Any: ...
    @property
    def converged(self) -> bool: ...
    @property
    def iterations(self) -> int: ...
    @property
    def steps(self) -> Sequence[Any]: ...
    def book_text(self, *, carriage_control: bool = False) -> str: ...


class RunRequest(BaseModel):
    """What to run: data-card values, the function and options.

    ``inputs`` maps catalog input names to values; inputs left out take the book data card's
    value when the request is built with :meth:`for_entry`. ``preset`` selects a catalog function
    preset (default: the program's ``default_preset``); ``expression`` is a learner function
    (Python engine only, DD3) and excludes ``preset``. ``verbose`` asks for the driver's extras
    after the book text.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)
    preset: int | None = Field(default=None, ge=1)
    expression: str | None = Field(default=None, min_length=1)
    verbose: bool = False

    @model_validator(mode="after")
    def _one_function(self) -> Self:
        if self.preset is not None and self.expression is not None:
            raise ValueError("give either a preset or a custom expression, not both")
        return self

    @classmethod
    def for_entry(
        cls,
        entry: CatalogEntry,
        inputs: Mapping[str, object] | None = None,
        *,
        preset: int | None = None,
        expression: str | None = None,
        verbose: bool = False,
    ) -> Self:
        """The book data card with ``inputs`` overriding individual values."""
        merged: dict[str, object] = dict(entry.defaults())
        merged.update(inputs or {})
        return cls(inputs=merged, preset=preset, expression=expression, verbose=verbose)

    @property
    def custom_function(self) -> bool:
        """True when the request carries a learner expression instead of a preset."""
        return self.expression is not None


def _check_finite(item: CatalogInput, value: InputValue) -> None:
    for number in item.numbers(value):
        if not math.isfinite(number):
            raise InputError(f"input {item.name!r}: {number!r} is not a finite number")


def validate_inputs(entry: CatalogEntry, raw: Mapping[str, object]) -> dict[str, InputValue]:
    """Validate ``raw`` against the catalog inputs and return the typed values in card order.

    Every catalog input must be present and no others. Each value must have the input's type
    (numbers only: strings and booleans are rejected), be finite, respect ``min``/``max`` (every
    element of a list) and, for lists, the fixed ``length``. Integer inputs without bounds must
    fit a default Fortran integer. Raises :class:`InputError` naming the input.
    """
    unknown = sorted(set(raw) - set(entry.input_names))
    if unknown:
        raise InputError(
            f"unknown input(s) {', '.join(unknown)} for {entry.id} "
            f"(expected {', '.join(entry.input_names)})"
        )
    validated: dict[str, InputValue] = {}
    for item in entry.ordered_inputs():
        if item.name not in raw:
            raise InputError(f"missing input {item.name!r} for {entry.id}")
        value = raw[item.name]
        try:
            coerced = item.coerce(value)
        except ValueError as exc:
            raise InputError(f"input {item.name!r}: {exc}") from None
        _check_finite(item, coerced)
        problem = item.check_value(coerced)
        if problem is not None:
            raise InputError(f"input {item.name!r}: {problem}")
        if item.type == "int" and isinstance(coerced, int) and abs(coerced) > FORTRAN_INT_MAX:
            raise InputError(f"input {item.name!r}: {coerced} does not fit a Fortran integer")
        validated[item.name] = coerced
    return validated


def resolve_preset(entry: CatalogEntry, request: RunRequest) -> int | None:
    """The catalog preset id to run (``None`` for a custom expression or a data-only program).

    Raises :class:`InputError` for an unknown preset, or for a function given to a program that
    takes data instead of a function.
    """
    spec = entry.function
    if not spec.takes_function:
        if request.preset is not None or request.expression is not None:
            raise InputError(f"{entry.id} takes data, not a function: no preset or expression")
        return None
    if request.expression is not None:
        return None
    preset_id = request.preset if request.preset is not None else spec.default_preset
    if preset_id is None:  # pragma: no cover - the catalog requires a default preset
        raise InputError(f"{entry.id} has no default preset")
    known = [preset.id for preset in spec.presets]
    if preset_id not in known:
        raise InputError(
            f"unknown preset {preset_id} for {entry.id} (valid: {', '.join(map(str, known))})"
        )
    return preset_id


def validate_request(
    entry: CatalogEntry, request: RunRequest
) -> tuple[dict[str, InputValue], int | None]:
    """Validate a request: the typed inputs and the preset id (see :func:`validate_inputs`)."""
    return validate_inputs(entry, request.inputs), resolve_preset(entry, request)


def consume_carriage_control(text: str) -> str:
    """Drop the carriage-control column of every record, as the line printer did.

    Fortran list output starts each record with a blank that the printer consumed; the book
    text shown in the UI (and the default ``book_text()``) has it removed.
    """
    lines = text.splitlines()
    return "".join((line[1:] if line.startswith(" ") else line) + "\n" for line in lines)


def step_to_dict(step: object) -> dict[str, Any]:
    """A step dataclass (or mapping) as a plain dict of its fields."""
    if is_dataclass(step) and not isinstance(step, type):
        return {f.name: getattr(step, f.name) for f in fields(step)}
    if isinstance(step, Mapping):
        return dict(step)
    raise TypeError(f"cannot convert step {step!r} to a dict")


def _plain(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def result_to_dict(result: object) -> dict[str, Any]:
    """A result dataclass as JSON-ready nested dicts and lists."""
    plain = _plain(result)
    if not isinstance(plain, dict):
        raise TypeError(f"cannot convert result {result!r} to a dict")
    return plain


@dataclass(frozen=True)
class RunOutcome:
    """What one engine run produced.

    Exactly one of ``result`` and ``error`` is set. ``book_text`` is the line-printer text with
    the carriage-control column consumed (as in the scan); on an error it is the book's output up
    to the error message. ``raw_stdout`` is the Fortran driver's book-mode stdout exactly as
    written (carriage-control blanks kept), ``trace_text`` its ``--trace`` output; both are
    ``None`` on the Python engine. ``elapsed_ms`` is the wall-clock time of the whole run.
    """

    engine: str
    program_id: str
    inputs: Mapping[str, InputValue]
    preset: int | None
    expression: str | None
    result: Any = None
    error: GeraldNAError | None = None
    book_text: str = ""
    elapsed_ms: float = 0.0
    raw_stdout: str | None = None
    trace_text: str | None = None
    verbose_text: str = ""

    def __post_init__(self) -> None:
        if (self.result is None) == (self.error is None):
            raise ValueError("a RunOutcome has exactly one of result and error")

    @property
    def ok(self) -> bool:
        """True when the run produced a result."""
        return self.error is None

    @property
    def steps(self) -> tuple[Any, ...]:
        """The iteration rows: the result's steps, or the partial steps carried by the error."""
        if self.result is not None:
            return tuple(self.result.steps)
        return self.error.steps if self.error is not None else ()

    @property
    def status(self) -> str:
        """``OK`` or the error's code (``BRACKET``, ``NON_CONVERGENT``, ``FORTRAN_RUN``, ...)."""
        return "OK" if self.error is None else self.error.code

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready view (used by ``gerald-na run --trace-json`` and the web API)."""
        data: dict[str, Any] = {
            "engine": self.engine,
            "program_id": self.program_id,
            "inputs": _plain(dict(self.inputs)),
            "preset": self.preset,
            "expression": self.expression,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "steps": [step_to_dict(step) for step in self.steps],
            "book_text": self.book_text,
        }
        if self.result is not None:
            result = result_to_dict(self.result)
            result.pop("steps", None)
            data["result"] = result
        if self.error is not None:
            data["error"] = {"code": self.error.code, "message": self.error.message}
        if self.verbose_text:
            data["verbose_text"] = self.verbose_text
        if self.raw_stdout is not None:
            data["raw_stdout"] = self.raw_stdout
        return data


class Engine(ABC):
    """A way of running catalog programs (``python`` or ``fortran``)."""

    name: ClassVar[str]

    @property
    def label(self) -> str:
        """Display name of this engine instance (for example ``fortran (single)``)."""
        return self.name

    def is_available(self, entry: CatalogEntry) -> bool:
        """Whether this engine can run ``entry`` at all (for example, its binary exists)."""
        return True

    @abstractmethod
    def run(self, entry: CatalogEntry, request: RunRequest) -> RunOutcome:
        """Run ``entry`` for ``request`` (see the module docstring for the error contract)."""
