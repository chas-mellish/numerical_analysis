"""Generic parser of the ``--trace`` protocol (DD2, ``docs/architecture.md``).

Every line of a driver's ``--trace`` output is one record::

    STEP,k=1,x1=0.00000000000000000E+000,x2=1.00000000000000000E+000,x=...,fx=...
    TABLE,row=1,col=2,value=1.60772551000000000E+000
    FACTOR,kind=quadratic,r=...,s=...
    RESULT,value=...,converged=T,iterations=15,root_at_endpoint=F
    ERROR,code=BRACKET,message=FUNCTION VALUES WITH INITIAL X VALUES ...

The first field is the record type (upper case), the others are ``key=value`` pairs. Values are
typed without any program knowledge: ``T``/``F`` become :class:`bool`, integer literals
:class:`int`, anything :func:`float` accepts (``ES25.17E3`` reals, ``NaN``, ``Infinity``)
:class:`float`, and everything else stays :class:`str`. The ``message`` of an ``ERROR`` record is
taken verbatim up to the end of the line. Any violation of the protocol raises
:class:`~gerald_na.errors.FortranRunError`, so a crashing or misbehaving driver can never be
mistaken for a result.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from gerald_na.errors import FortranRunError

__all__ = [
    "ERROR",
    "MAX_LINE_LENGTH",
    "RESULT",
    "STEP",
    "TABLE",
    "Record",
    "Trace",
    "TraceValue",
    "parse_trace",
    "parse_value",
]

type TraceValue = bool | int | float | str

STEP = "STEP"
TABLE = "TABLE"
RESULT = "RESULT"
ERROR = "ERROR"

MAX_LINE_LENGTH = 4096
"""Longest accepted trace line; longer lines are a protocol violation."""

_RECORD_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_INT = re.compile(r"^[+-]?\d+$")
_SNIPPET = 80


def parse_value(text: str) -> TraceValue:
    """Type one field value: ``T``/``F`` -> bool, integer -> int, real -> float, else str."""
    if text == "T":
        return True
    if text == "F":
        return False
    if _INT.match(text):
        return int(text)
    try:
        return float(text)
    except ValueError:
        return text


@dataclass(frozen=True, slots=True)
class Record:
    """One parsed trace line: its ``type``, typed ``fields`` and 1-based ``line`` number."""

    type: str
    fields: Mapping[str, TraceValue]
    line: int = 0

    def __getitem__(self, key: str) -> TraceValue:
        return self.fields[key]

    def __contains__(self, key: object) -> bool:
        return key in self.fields

    def _require(self, key: str) -> TraceValue:
        try:
            return self.fields[key]
        except KeyError:
            raise FortranRunError(
                f"trace line {self.line}: {self.type} record has no '{key}' field"
            ) from None

    def real(self, key: str) -> float:
        """Field ``key`` as a float (integers are widened); raises on other types."""
        value = self._require(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise FortranRunError(
                f"trace line {self.line}: {self.type} field '{key}' is not a real ({value!r})"
            )
        return float(value)

    def integer(self, key: str) -> int:
        """Field ``key`` as an int; raises unless it was written as an integer."""
        value = self._require(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise FortranRunError(
                f"trace line {self.line}: {self.type} field '{key}' is not an integer ({value!r})"
            )
        return value

    def logical(self, key: str) -> bool:
        """Field ``key`` as a bool (``T``/``F``); raises on other values."""
        value = self._require(key)
        if not isinstance(value, bool):
            raise FortranRunError(
                f"trace line {self.line}: {self.type} field '{key}' is not T or F ({value!r})"
            )
        return value

    def text(self, key: str) -> str:
        """Field ``key`` as text (numbers and logicals are returned in their trace spelling)."""
        value = self._require(key)
        if isinstance(value, bool):
            return "T" if value else "F"
        return str(value)


@dataclass(frozen=True, slots=True)
class Trace:
    """A complete, validated trace: records in output order with exactly one terminal record.

    The terminal record is the last one and is either ``RESULT`` (success) or ``ERROR``.
    """

    records: tuple[Record, ...]
    _by_type: Mapping[str, tuple[Record, ...]] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        grouped: dict[str, list[Record]] = {}
        for record in self.records:
            grouped.setdefault(record.type, []).append(record)
        object.__setattr__(
            self, "_by_type", MappingProxyType({k: tuple(v) for k, v in grouped.items()})
        )

    def __iter__(self) -> Iterator[Record]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    def of_type(self, record_type: str) -> tuple[Record, ...]:
        """All records of ``record_type``, in output order."""
        return self._by_type.get(record_type, ())

    @property
    def steps(self) -> tuple[Record, ...]:
        """The ``STEP`` records."""
        return self.of_type(STEP)

    @property
    def terminal(self) -> Record:
        """The final ``RESULT`` or ``ERROR`` record."""
        return self.records[-1]

    @property
    def result(self) -> Record | None:
        """The ``RESULT`` record, or ``None`` when the run ended with ``ERROR``."""
        return self.terminal if self.terminal.type == RESULT else None

    @property
    def error(self) -> Record | None:
        """The ``ERROR`` record, or ``None`` on success."""
        return self.terminal if self.terminal.type == ERROR else None


def _snippet(line: str) -> str:
    return line if len(line) <= _SNIPPET else line[: _SNIPPET - 3] + "..."


def _parse_line(line: str, number: int) -> Record:
    def fail(problem: str) -> FortranRunError:
        return FortranRunError(f"malformed trace line {number} ({problem}): {_snippet(line)!r}")

    if len(line) > MAX_LINE_LENGTH:
        raise fail(f"longer than {MAX_LINE_LENGTH} characters")
    record_type, _, rest = line.partition(",")
    if not _RECORD_TYPE.match(record_type):
        raise fail("the first field must be an upper-case record type")
    message: str | None = None
    if record_type == ERROR:
        # The message is free text up to the end of the line (the drivers avoid commas in it,
        # but a stray comma must not split it).
        head, marker, tail = rest.partition("message=")
        if marker and (not head or head.endswith(",")):
            rest, message = head.removesuffix(","), tail
    fields: dict[str, TraceValue] = {}
    for item in rest.split(",") if rest else ():
        key, eq, raw = item.partition("=")
        if not eq or not _KEY.match(key):
            raise fail(f"field {item!r} is not key=value with a lower-case key")
        if key in fields:
            raise fail(f"duplicate field {key!r}")
        if raw != raw.strip() or not raw:
            raise fail(f"field {key!r} has an empty or padded value")
        fields[key] = parse_value(raw)
    if message is not None:
        if "message" in fields:
            raise fail("duplicate field 'message'")
        fields["message"] = message.strip()
    return Record(type=record_type, fields=MappingProxyType(fields), line=number)


def _check_terminal(records: list[Record]) -> None:
    terminals = [r for r in records if r.type in (RESULT, ERROR)]
    if not terminals:
        raise FortranRunError("trace has no RESULT or ERROR record (driver ended early?)")
    if len(terminals) > 1:
        raise FortranRunError(
            f"trace has {len(terminals)} RESULT/ERROR records (lines "
            + ", ".join(str(r.line) for r in terminals)
            + "); exactly one is allowed"
        )
    last = records[-1]
    if last is not terminals[0]:
        raise FortranRunError(
            f"trace line {terminals[0].line}: {terminals[0].type} must be the last record"
        )
    if last.type == RESULT:
        last.real("value")
        last.logical("converged")
        last.integer("iterations")
    else:
        last.text("code")
        last.text("message")


def parse_trace(text: str) -> Trace:
    """Parse a complete ``--trace`` output; raise :class:`FortranRunError` on any violation.

    Blank lines and trailing whitespace (Fortran pads records) are ignored. The output must end
    with exactly one ``RESULT`` (with ``value``, ``converged``, ``iterations``) or ``ERROR``
    (with ``code`` and ``message``) record.
    """
    records: list[Record] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        if not line:
            continue
        records.append(_parse_line(line, number))
    if not records:
        raise FortranRunError("empty trace: the driver printed no records")
    _check_terminal(records)
    return Trace(tuple(records))
