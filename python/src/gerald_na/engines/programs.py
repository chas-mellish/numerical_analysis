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

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import fields, is_dataclass
from typing import Any, ClassVar

from gerald_na.engines.trace import STEP, Record, Trace
from gerald_na.errors import FortranRunError
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

    @abstractmethod
    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> Any:
        """Call the Python algorithm. ``function`` is ``None`` for data-only programs."""

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
