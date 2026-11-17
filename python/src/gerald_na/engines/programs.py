"""Per-program adapters: the only program-specific code of the engines.

The engines themselves are generic. For each catalog program an adapter (a subclass of
:class:`ProgramAdapter`, registered in :mod:`gerald_na.engines.adapters`) knows how to

(a) call the Python algorithm with the validated inputs and the compiled function
    (:meth:`ProgramAdapter.run_python`),
(b) write the book data card that the Fortran driver reads from stdin
    (:meth:`ProgramAdapter.data_card`, generic by default: :func:`serialize_card`), and
(c) build the program's result dataclass from the parsed ``--trace`` records
    (:meth:`ProgramAdapter.result_from_trace`; partial rows for errors come from
    :meth:`ProgramAdapter.steps_from_trace`, generic by default: :func:`steps_from_records`).

Both engines therefore return the same result type. See ``docs/architecture.md`` ("Engines")
for the step-by-step recipe of adding a program.
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import fields, is_dataclass
from types import MappingProxyType
from typing import Any, ClassVar

from gerald_na.engines.trace import STEP, Record, Trace
from gerald_na.errors import FortranRunError, InputError
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = [
    "Function",
    "ProgramAdapter",
    "card_number",
    "serialize_card",
    "steps_from_records",
]

type Function = Callable[[float], float]


def card_number(value: float) -> str:
    """One list-directed data-card field: integers as written, reals with ``repr`` precision.

    ``repr`` is the shortest text that reads back as the same float64, so the Fortran driver
    (real64) receives exactly the value the Python engine uses. Booleans are rejected; the
    callers validate that values are finite before any card is written.
    """
    if isinstance(value, bool):
        raise TypeError("booleans are not data-card numbers")
    if isinstance(value, int):
        return str(value)
    return repr(float(value))


def serialize_card(entry: CatalogEntry, inputs: Mapping[str, InputValue]) -> str:
    """The data card(s) for ``inputs`` in the book's reading order (generic, list-directed).

    Inputs are grouped by their catalog ``card`` number; each card is one line with its numbers
    separated by blanks (lists are flattened). Every pair of a ``point_list`` input goes on a
    line of its own, after the card's other fields, which suits both a single list-directed
    ``READ`` (it continues across lines) and a ``READ`` per point.
    """
    cards: dict[int, list[list[str]]] = {}
    for item in entry.ordered_inputs():
        lines = cards.setdefault(item.card, [[]])
        value = inputs[item.name]
        if item.type == "point_list" and isinstance(value, tuple):
            for point in value:
                coordinates = point if isinstance(point, tuple) else (point,)
                lines.append([card_number(coordinate) for coordinate in coordinates])
            lines.append([])
        else:
            lines[-1].extend(card_number(number) for number in item.numbers(value))
    text: list[str] = []
    for card in sorted(cards):
        text.extend(" ".join(tokens) for tokens in cards[card] if tokens)
    return "".join(line + "\n" for line in text)


def steps_from_records(
    entry: CatalogEntry, records: Iterable[Record], step_type: Callable[..., Any]
) -> tuple[Any, ...]:
    """Build step dataclasses from ``STEP`` records using the catalog's ``step_columns``.

    Each record must carry exactly the catalog keys; ``I`` columns are read as integers, the
    others as reals. ``step_type`` is called with the keys as keyword arguments (the step
    dataclass attribute names equal the trace keys, per the per-program contract).
    """
    columns = entry.trace.step_columns
    expected = {column.key for column in columns}
    steps: list[Any] = []
    for record in records:
        if set(record.fields) != expected:
            missing = sorted(expected - set(record.fields))
            extra = sorted(set(record.fields) - expected)
            raise FortranRunError(
                f"trace line {record.line}: STEP keys do not match the catalog "
                f"(missing {missing}, unexpected {extra})"
            )
        values = {
            column.key: record.integer(column.key) if column.is_integer else record.real(column.key)
            for column in columns
        }
        steps.append(step_type(**values))
    return tuple(steps)


class ProgramAdapter(ABC):
    """Glue between one catalog program and the engines.

    Subclasses set :attr:`program_id`, :attr:`result_type` and :attr:`step_type` and implement
    :meth:`run_python` and :meth:`result_from_trace`; the defaults of the other methods cover
    programs whose data card and ``STEP`` records follow the catalog directly.
    """

    program_id: ClassVar[str]
    """The catalog id this adapter serves."""
    result_type: ClassVar[type]
    """The result dataclass returned by both engines."""
    step_type: ClassVar[type]
    """The step dataclass built from ``STEP`` records (fields == catalog step keys)."""
    count_inputs: ClassVar[Mapping[str, str]] = MappingProxyType({})
    """Integer inputs that count the rows of a list input, ``{count input: list input}``
    (Lagrange: ``{"n": "points"}``). The web form keeps such a field equal to the number of rows
    while the learner adds or removes rows; :meth:`input_problems` still enforces the rule on
    every request."""
    parity_outcomes: ClassVar[frozenset[str]] = frozenset({"OK"})
    """Statuses the generated parity input sets must reach on the Python engine (default: only
    ``OK``); for example Bairstow's ``{"OK", "NON_CONVERGENT", "DEGREE"}``."""
    parity_cases: ClassVar[Mapping[str, Mapping[str, InputValue]]] = MappingProxyType({})
    """Extra labelled input sets for the parity tests, ``{label: inputs}`` (default: none), such
    as a hand-built edge case; inputs not given take their data-card value."""

    @abstractmethod
    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> Any:
        """Call the Python algorithm. ``function`` is ``None`` for data-only programs."""

    def input_problems(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue]
    ) -> dict[str, str]:
        """Cross-input problems the per-input catalog bounds cannot express (default: none).

        Returns a message per input name (for example Lagrange's ``n`` not matching its number
        of points), so the web form can point at the field. ``inputs`` are already validated
        one by one (:func:`~gerald_na.engines.base.validate_request`).
        """
        return {}

    def check_inputs(self, entry: CatalogEntry, inputs: Mapping[str, InputValue]) -> None:
        """Raise :class:`InputError` when :meth:`input_problems` reports anything.

        Both engines call this after :func:`~gerald_na.engines.base.validate_request` and before
        anything runs, so a violation is a request problem (``INPUT``) on either engine.
        """
        problems = self.input_problems(entry, inputs)
        if problems:
            raise InputError("; ".join(problems.values()))

    def random_inputs(self, entry: CatalogEntry, rng: random.Random) -> dict[str, Any] | None:
        """One random input set for the parity tests, drawn from ``rng`` (default: ``None``).

        ``None`` means the tests' generic per-input generator (independent values within the
        catalog ``min``/``max``) suits the program. Programs whose inputs constrain each other
        (Lagrange's ``n`` and its points, Bairstow's coefficients above X**N) override this.
        """
        return None

    def substituted_ordinates(self, entry: CatalogEntry, function: Function) -> dict[float, float]:
        """Points where the program uses a fixed value instead of evaluating ``function``.

        Default: none. Simpson and Romberg seed their sums with the book's literal ``1.0`` at
        X = 0 for SIN(X)/X; the web charts use this to draw F the way the program evaluates it.
        """
        return {}

    def data_card(self, entry: CatalogEntry, inputs: Mapping[str, InputValue]) -> str:
        """The stdin text for the Fortran driver (default: :func:`serialize_card`)."""
        return serialize_card(entry, inputs)

    def steps_from_trace(self, entry: CatalogEntry, trace: Trace) -> tuple[Any, ...]:
        """The step dataclasses of ``trace`` (also used for the partial rows of an error)."""
        return steps_from_records(entry, trace.of_type(STEP), self.step_type)

    @abstractmethod
    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> Any:
        """Build :attr:`result_type` from a successful trace (one that ends with ``RESULT``).

        Implementations raise :class:`FortranRunError` when the records are inconsistent.
        """

    def verbose_text(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], result: Any
    ) -> str:
        """Python-engine extras for ``verbose`` requests (default: none).

        The Fortran engine returns its driver's ``--verbose`` extras instead.
        """
        return ""

    def check_result_type(self, result: object) -> None:
        """Assert that ``result`` is this program's result dataclass (both engines)."""
        if not isinstance(result, self.result_type) or not is_dataclass(result):
            raise TypeError(
                f"{self.program_id}: expected {self.result_type.__name__}, got "
                f"{type(result).__name__}"
            )

    @classmethod
    def result_fields(cls) -> tuple[str, ...]:
        """Field names of :attr:`result_type` (used by compare mode and the parity tests)."""
        return tuple(f.name for f in fields(cls.result_type))
