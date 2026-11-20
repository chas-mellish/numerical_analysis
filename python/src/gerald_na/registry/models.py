"""Pydantic models of one ``catalog/*.toml`` program entry.

The catalog is the extension contract of the project: a new book program is one TOML file
validated by :class:`CatalogEntry` plus a Fortran module/driver and a Python function. Every model
is frozen and rejects unknown keys, so a typo in a catalog file is a validation error rather than
a silently ignored field. The field reference lives in ``docs/architecture.md`` ("Catalog schema").
"""

import math
import re
from collections.abc import Iterator, Sequence
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

__all__ = [
    "ANSWER_FIELDS",
    "BookRef",
    "CatalogEntry",
    "CatalogInput",
    "Chart",
    "ChartKind",
    "DataCard",
    "Erratum",
    "ErratumKind",
    "Expected",
    "ExpectedKind",
    "FilesRef",
    "FunctionSpec",
    "InputType",
    "InputValue",
    "PracticeQuestion",
    "Preset",
    "ResultExtra",
    "StepColumn",
    "TraceRecord",
    "TraceSpec",
    "parse_data_card_token",
]

type InputType = Literal["real", "int", "real_list", "point_list"]
type ExpectedKind = Literal["real", "int", "text", "table", "rows"]
type ChartKind = Literal[
    "bracket",
    "abs_residual",
    "romberg_heatmap",
    "integrand_panels",
    "factors",
    "interpolant",
    "convergence",
]
type ErratumKind = Literal[
    "ocr_slip", "original_bug", "original_quirk", "rewrite_drift", "modernization"
]
type Number = int | float
type InputValue = int | float | tuple[float, ...] | tuple[tuple[float, float], ...]
type Cell = int | float
type BookValue = int | float | str | tuple[tuple[Cell, ...], ...]
type Tolerance = float | dict[str, float]
type OptionValue = str | int | float | bool | list[str] | list[float]

ANSWER_FIELDS: frozenset[str] = frozenset({"value", "iterations", "converged"})
"""Result attributes every engine result exposes (practice answers may also use result extras)."""

_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_PROGRAM_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_RECORD_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_FORMAT = re.compile(r"^(I\d+|F\d+\.\d+|E\d+\.\d+|ES\d+\.\d+|G0|L\d+|A\d*)$")
_CALLABLE = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)*:[A-Za-z_][\w]*$")
_EXECUTABLE = re.compile(r"^[a-z0-9_]+$")
_FORTRAN_INT = re.compile(r"^[+-]?\d+$")
_FORTRAN_REAL = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([EeDd][+-]?\d+)?$")
_CARD_SEPARATOR = re.compile(r"[\s,]+")


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0) or a == b


def parse_data_card_token(token: str, *, integer: bool) -> Number:
    """Parse one list-directed data-card field (``0.``, ``1.E-5``, ``.5``, ``1.D-3``, ``20``).

    Raises :class:`ValueError` if the token is not a valid Fortran number (or not an integer
    literal when ``integer`` is true).
    """
    if integer:
        if not _FORTRAN_INT.match(token):
            raise ValueError(f"data card field {token!r} is not an integer")
        return int(token)
    if not _FORTRAN_REAL.match(token):
        raise ValueError(f"data card field {token!r} is not a Fortran real")
    return float(token.replace("D", "E").replace("d", "e"))


def _check_relative_path(value: str) -> str:
    """Catalog paths are relative POSIX paths below the repository root (no ``..``)."""
    if not value or value != value.strip():
        raise ValueError("path must be non-empty without surrounding whitespace")
    if "\\" in value:
        raise ValueError(f"path {value!r} must use forward slashes")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("~") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"path {value!r} must be relative to the repository root")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"path {value!r} must not contain '.' or '..' segments")
    return value


# ---------------------------------------------------------------- book reference


class BookRef(_Model):
    """Where the program appears in the book. Every field is optional (DD1)."""

    chapter: int | None = Field(default=None, ge=1)
    program: int | None = Field(default=None, ge=1)
    page: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, description="Chapter title as printed")


# ---------------------------------------------------------------- inputs and data card


class CatalogInput(_Model):
    """One data-card field (or list of fields) in the book's reading order."""

    name: str = Field(pattern=_IDENT.pattern)
    type: InputType
    label: str = Field(min_length=1)
    default: InputValue
    min: float | None = None
    max: float | None = None
    help: str = Field(min_length=1)
    card: int = Field(ge=1, description="Data card number (1-based) holding this field")
    length: int | None = Field(default=None, ge=1, description="Fixed length of a list input")

    @field_validator("default", mode="after")
    @classmethod
    def _default_matches_type(cls, value: InputValue, info: ValidationInfo) -> InputValue:
        input_type = info.data.get("type")
        if input_type is None:  # type itself failed validation; that error is reported
            return value
        return _coerce_value(input_type, value)

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if self.type in ("real", "int") and self.length is not None:
            raise ValueError(f"input {self.name!r}: 'length' only applies to list inputs")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"input {self.name!r}: min {self.min} exceeds max {self.max}")
        problem = self.check_value(self.default)
        if problem is not None:
            raise ValueError(f"input {self.name!r} default: {problem}")
        return self

    def coerce(self, value: object) -> InputValue:
        """Return ``value`` converted to this input's type, or raise :class:`ValueError`."""
        return _coerce_value(self.type, value)

    def numbers(self, value: InputValue) -> list[float]:
        """The flat list of numbers that ``value`` contributes to the data card."""
        if isinstance(value, tuple):
            flat: list[float] = []
            for item in value:
                if isinstance(item, tuple):
                    flat.extend(item)
                else:
                    flat.append(item)
            return flat
        return [value]

    def check_value(self, value: object) -> str | None:
        """Why ``value`` is not acceptable for this input (type, length, min/max), or ``None``."""
        try:
            coerced = self.coerce(value)
        except ValueError as exc:
            return str(exc)
        if self.length is not None and isinstance(coerced, tuple) and len(coerced) != self.length:
            return f"expected {self.length} items, got {len(coerced)}"
        for number in self.numbers(coerced):
            if self.min is not None and number < self.min:
                return f"{number} is below the minimum {self.min}"
            if self.max is not None and number > self.max:
                return f"{number} is above the maximum {self.max}"
        return None


def _coerce_value(input_type: InputType, value: object) -> InputValue:
    match input_type:
        case "real":
            if not _is_number(value):
                raise ValueError(f"expected a real number, got {value!r}")
            return float(value)  # type: ignore[arg-type]
        case "int":
            if isinstance(value, bool) or not isinstance(value, int):
                if isinstance(value, float) and value.is_integer():
                    return int(value)
                raise ValueError(f"expected an integer, got {value!r}")
            return value
        case "real_list":
            if not isinstance(value, Sequence) or isinstance(value, str):
                raise ValueError(f"expected a list of real numbers, got {value!r}")
            if not all(_is_number(item) for item in value):
                raise ValueError(f"expected a list of real numbers, got {value!r}")
            return tuple(float(item) for item in value)
        case "point_list":
            if not isinstance(value, Sequence) or isinstance(value, str):
                raise ValueError(f"expected a list of [x, y] pairs, got {value!r}")
            points: list[tuple[float, float]] = []
            for item in value:
                if (
                    not isinstance(item, Sequence)
                    or isinstance(item, str)
                    or len(item) != 2
                    or not all(_is_number(coordinate) for coordinate in item)
                ):
                    raise ValueError(f"expected an [x, y] pair, got {item!r}")
                points.append((float(item[0]), float(item[1])))
            return tuple(points)


class DataCard(_Model):
    """The book's data card: verbatim text plus the values parsed from it."""

    text: str = Field(min_length=1, description="Data card exactly as printed in the scan")
    values: dict[str, InputValue] = Field(description="Parsed values, keyed by input name")
    note: str | None = None

    def tokens(self) -> list[str]:
        """The list-directed fields of :attr:`text`, in reading order."""
        return [token for token in _CARD_SEPARATOR.split(self.text.strip()) if token]


# ---------------------------------------------------------------- function presets


class Preset(_Model):
    """A book (or extra) function selectable on both engines (``--preset N`` on Fortran)."""

    id: int = Field(ge=1)
    label: str = Field(min_length=1)
    expr: str = Field(min_length=1, description="Expression compiled by gerald_na.expr")
    fortran_preset: int = Field(ge=1, description="Value passed to the driver's --preset flag")
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.expr.strip():
            raise ValueError(f"preset {self.id}: expression is blank")
        if self.fortran_preset != self.id:
            raise ValueError(f"preset {self.id}: fortran_preset must equal id")
        return self


class FunctionSpec(_Model):
    """Whether the program takes a function F(X), and which presets it offers (DD3)."""

    takes_function: bool
    variable: str = Field(default="x", pattern=_IDENT.pattern)
    default_preset: int | None = None
    presets: tuple[Preset, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [preset.id for preset in self.presets]
        if len(ids) != len(set(ids)):
            raise ValueError("preset ids must be unique")
        if self.takes_function:
            if not self.presets:
                raise ValueError("a program that takes a function needs at least one preset")
            if self.default_preset not in ids:
                raise ValueError(f"default_preset {self.default_preset} is not a preset id")
        elif self.presets or self.default_preset is not None:
            raise ValueError("presets are only allowed when takes_function is true")
        return self

    def preset(self, preset_id: int) -> Preset:
        """The preset with ``preset_id``; raises :class:`KeyError` if absent."""
        for preset in self.presets:
            if preset.id == preset_id:
                return preset
        raise KeyError(preset_id)


# ---------------------------------------------------------------- trace protocol (DD2)


class StepColumn(_Model):
    """One ``STEP`` key: Python step attribute == trace key == UI column."""

    key: str = Field(pattern=_IDENT.pattern)
    label: str = Field(min_length=1)
    format: str = Field(pattern=_FORMAT.pattern, description="Fortran edit descriptor, e.g. F10.7")

    @property
    def is_integer(self) -> bool:
        """True for integer columns (``I`` edit descriptors), which are compared exactly."""
        return self.format.startswith("I")


class TraceRecord(_Model):
    """A documented trace record type other than ``STEP``/``RESULT``/``ERROR``."""

    type: str = Field(pattern=_RECORD_TYPE.pattern)
    fields: tuple[str, ...] = ()
    description: str = Field(min_length=1)


class ResultExtra(_Model):
    """An extra ``RESULT`` key (e.g. ``root_at_endpoint``, ``subintervals``)."""

    key: str = Field(pattern=_IDENT.pattern)
    type: Literal["real", "int", "bool", "text"]
    description: str = Field(min_length=1)


_RESERVED_RESULT_KEYS = frozenset({"value", "converged", "iterations"})


class TraceSpec(_Model):
    """The program's ``--trace`` layout."""

    step_columns: tuple[StepColumn, ...] = Field(min_length=1)
    records: tuple[TraceRecord, ...] = ()
    result_extras: tuple[ResultExtra, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Self:
        _require_unique("step column key", [column.key for column in self.step_columns])
        _require_unique("trace record type", [record.type for record in self.records])
        extras = [extra.key for extra in self.result_extras]
        _require_unique("result extra key", extras)
        if clash := _RESERVED_RESULT_KEYS.intersection(extras):
            raise ValueError(f"result extras may not redefine {sorted(clash)}")
        return self

    def column(self, key: str) -> StepColumn:
        """The step column ``key``; raises :class:`KeyError` if absent."""
        for column in self.step_columns:
            if column.key == key:
                return column
        raise KeyError(key)


# ---------------------------------------------------------------- golden expectations (DD4)


def _shape(value: object) -> tuple[int, ...] | None:
    if isinstance(value, tuple) and all(isinstance(row, tuple) for row in value):
        return tuple(len(row) for row in value)
    return None


class Expected(_Model):
    """One golden expectation transcribed from the scan (tolerance policy DD4)."""

    name: str = Field(pattern=_IDENT.pattern)
    kind: ExpectedKind
    field: str | None = Field(
        default=None, description="Result attribute compared (defaults to name)"
    )
    description: str | None = None
    book_value: BookValue
    columns: tuple[str, ...] | None = Field(
        default=None, description="Step keys of each row (kind = rows)"
    )
    tol_real64: Tolerance | None = Field(default=None)
    tol_real32: Tolerance | None = Field(default=None)
    real64_value: BookValue | None = None
    tol_real64_value: float | None = Field(default=None, ge=0)

    @property
    def result_field(self) -> str:
        """The result attribute that holds the compared value."""
        return self.field if self.field is not None else self.name

    @model_validator(mode="after")
    def _check(self) -> Self:
        exact = self.kind in ("int", "text")
        tolerances = (self.tol_real64, self.tol_real32)
        if exact:
            if any(tol is not None for tol in tolerances) or self.real64_value is not None:
                raise ValueError(f"{self.name}: {self.kind} expectations are exact (no tolerances)")
        elif any(tol is None for tol in tolerances):
            raise ValueError(f"{self.name}: tol_real64 and tol_real32 are required")
        for tol in tolerances:
            values = tol.values() if isinstance(tol, dict) else [tol] if tol is not None else []
            if any(t < 0 for t in values):
                raise ValueError(f"{self.name}: tolerances must be non-negative")
        if (self.real64_value is None) != (self.tol_real64_value is None):
            raise ValueError(f"{self.name}: real64_value and tol_real64_value go together")
        if self.kind != "rows" and self.columns is not None:
            raise ValueError(f"{self.name}: 'columns' only applies to kind = rows")
        if self.kind != "rows" and any(isinstance(tol, dict) for tol in tolerances):
            raise ValueError(f"{self.name}: per-column tolerances only apply to kind = rows")
        value = self.book_value
        match self.kind:
            case "real":
                if not _is_number(value):
                    raise ValueError(f"{self.name}: book_value must be a number")
                if self.real64_value is not None and not _is_number(self.real64_value):
                    raise ValueError(f"{self.name}: real64_value must be a number")
            case "int":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"{self.name}: book_value must be an integer")
            case "text":
                if not isinstance(value, str):
                    raise ValueError(f"{self.name}: book_value must be a string")
            case "table" | "rows":
                shape = _shape(value)
                if shape is None or not shape:
                    raise ValueError(f"{self.name}: book_value must be a non-empty list of rows")
                if self.real64_value is not None and _shape(self.real64_value) != shape:
                    raise ValueError(f"{self.name}: real64_value must have book_value's shape")
                if self.kind == "rows":
                    if not self.columns:
                        raise ValueError(f"{self.name}: kind = rows needs 'columns'")
                    _require_unique(f"{self.name} column", list(self.columns))
                    if any(width != len(self.columns) for width in shape):
                        raise ValueError(f"{self.name}: every row needs {len(self.columns)} cells")
                    for tol in tolerances:
                        if isinstance(tol, dict) and (unknown := set(tol) - set(self.columns)):
                            raise ValueError(f"{self.name}: tolerance for unknown {unknown}")
        return self

    def tolerance(self, precision: Literal["real64", "real32"], column: str | None = None) -> float:
        """Absolute tolerance for ``precision`` (and ``column`` of a rows expectation).

        Exact expectations (and rows columns without a tolerance entry) return 0.0.
        """
        tol = self.tol_real64 if precision == "real64" else self.tol_real32
        if tol is None:
            return 0.0
        if isinstance(tol, dict):
            return tol.get(column, 0.0) if column is not None else 0.0
        return tol


# ---------------------------------------------------------------- files, chart, practice, errata


class FilesRef(_Model):
    """Files belonging to the program, relative to the repository root."""

    legacy: tuple[str, ...] = Field(min_length=1)
    scan_pdf: str | None = None
    fortran_module: str
    fortran_app: str
    fortran_executable: str = Field(pattern=_EXECUTABLE.pattern)
    python_callable: str = Field(pattern=_CALLABLE.pattern)
    study_page: str

    @field_validator("legacy", mode="after")
    @classmethod
    def _legacy_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _require_unique("legacy file", list(value))
        return tuple(_check_relative_path(item) for item in value)

    @field_validator("scan_pdf", "fortran_module", "fortran_app", "study_page", mode="after")
    @classmethod
    def _paths(cls, value: str | None) -> str | None:
        return None if value is None else _check_relative_path(value)

    @property
    def python_module(self) -> str:
        """Dotted module part of :attr:`python_callable`."""
        return self.python_callable.partition(":")[0]

    @property
    def python_attribute(self) -> str:
        """Attribute part of :attr:`python_callable`."""
        return self.python_callable.partition(":")[2]


class Chart(_Model):
    """Chart the UI draws from a result (kind) plus free-form rendering options."""

    kind: ChartKind
    options: dict[str, OptionValue] = Field(default_factory=dict)


class PracticeQuestion(_Model):
    """A practice question; the answer is checked by running an engine with the overrides."""

    id: str = Field(pattern=_SLUG.pattern)
    prompt: str = Field(min_length=1)
    inputs: dict[str, InputValue] = Field(
        default_factory=dict, description="Overrides of the data-card defaults"
    )
    preset: int | None = Field(default=None, description="Function preset (default: the book's)")
    answer_field: str = Field(pattern=_IDENT.pattern, description="Result attribute to check")
    answer: int | float | bool | None = Field(
        default=None, description="Reference answer, as computed by the engines"
    )
    tolerance: float = Field(default=0.0, ge=0)
    explanation: str = Field(min_length=1)


class Erratum(_Model):
    """A recorded deviation, mirrored on the study page and in the Fortran ERRATA header."""

    id: str = Field(pattern=_SLUG.pattern)
    kind: ErratumKind
    original: str = Field(min_length=1)
    corrected: str = Field(min_length=1)
    note: str = Field(min_length=1)


# ---------------------------------------------------------------- the entry


def _require_unique(what: str, items: list[str] | list[int]) -> None:
    seen: set[object] = set()
    for item in items:
        if item in seen:
            raise ValueError(f"duplicate {what} {item!r}")
        seen.add(item)


class CatalogEntry(_Model):
    """One book program: the whole content of a ``catalog/*.toml`` file."""

    id: str = Field(pattern=_PROGRAM_ID.pattern)
    title: str = Field(min_length=1)
    method: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    book_ref: BookRef | None = None
    book_ref_confirmed: bool
    precision_notes: str = Field(min_length=1)
    book_output: str = Field(min_length=1, description="Line-printer output as printed")
    inputs: tuple[CatalogInput, ...] = Field(min_length=1)
    data_card: DataCard
    function: FunctionSpec
    trace: TraceSpec
    expected: tuple[Expected, ...] = Field(min_length=1)
    files: FilesRef
    chart: Chart
    practice: tuple[PracticeQuestion, ...] = ()
    errata: tuple[Erratum, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._check_identity()
        _require_unique("input name", [item.name for item in self.inputs])
        _require_unique("expected name", [item.name for item in self.expected])
        _require_unique("practice id", [item.id for item in self.practice])
        _require_unique("erratum id", [item.id for item in self.errata])
        self._check_data_card()
        self._check_expected()
        self._check_practice()
        return self

    def _check_identity(self) -> None:
        if self.book_ref_confirmed:
            ref = self.book_ref
            if ref is None or ref.chapter is None or ref.program is None or ref.page is None:
                raise ValueError("a confirmed book_ref needs chapter, program and page")
            expected_id = f"ch{ref.chapter:02d}_p{ref.program:02d}"
            if self.id != expected_id:
                raise ValueError(f"id {self.id!r} must be {expected_id!r} for its book_ref")
        exe = self.files.fortran_executable
        if exe != self.id and not exe.startswith(f"{self.id}_"):
            raise ValueError(f"fortran_executable {exe!r} must be the id or start with 'id_'")

    def _check_data_card(self) -> None:
        names = [item.name for item in self.inputs]
        if set(self.data_card.values) != set(names):
            raise ValueError(f"data_card.values keys must be exactly the inputs {names}")
        cards = sorted({item.card for item in self.inputs})
        if cards != list(range(1, len(cards) + 1)):
            raise ValueError(f"input card numbers must run 1..n without gaps, got {cards}")
        expected_numbers: list[tuple[str, float, bool]] = []
        for item in self.ordered_inputs():
            problem = item.check_value(self.data_card.values[item.name])
            if problem is not None:
                raise ValueError(f"data_card.values[{item.name!r}]: {problem}")
            value = item.coerce(self.data_card.values[item.name])
            if value != item.default:
                raise ValueError(
                    f"data_card.values[{item.name!r}] = {value!r} differs from the default"
                    f" {item.default!r}"
                )
            integer = item.type == "int"
            expected_numbers.extend((item.name, n, integer) for n in item.numbers(value))
        tokens = self.data_card.tokens()
        if len(tokens) != len(expected_numbers):
            raise ValueError(
                f"data_card.text has {len(tokens)} fields but the inputs need"
                f" {len(expected_numbers)}"
            )
        for token, (name, number, integer) in zip(tokens, expected_numbers, strict=True):
            parsed = parse_data_card_token(token, integer=integer)
            if not _close(float(parsed), number):
                raise ValueError(f"data_card.text field {token!r} does not match {name} = {number}")

    def _check_expected(self) -> None:
        keys = {column.key for column in self.trace.step_columns}
        for item in self.expected:
            if item.kind == "rows" and item.columns is not None:
                if unknown := set(item.columns) - keys:
                    raise ValueError(
                        f"expected {item.name!r}: columns {unknown} not in step_columns"
                    )
                for index, column in enumerate(item.columns):
                    if self.trace.column(column).is_integer and isinstance(item.book_value, tuple):
                        cells = [row[index] for row in item.book_value]
                        if not all(isinstance(cell, int) for cell in cells):
                            raise ValueError(
                                f"expected {item.name!r}: integer column {column!r} needs integers"
                            )

    def _check_practice(self) -> None:
        answer_fields = ANSWER_FIELDS | {extra.key for extra in self.trace.result_extras}
        for question in self.practice:
            for name, value in question.inputs.items():
                if name not in self.input_names:
                    raise ValueError(f"practice {question.id!r}: unknown input {name!r}")
                problem = self.input(name).check_value(value)
                if problem is not None:
                    raise ValueError(f"practice {question.id!r}: input {name!r}: {problem}")
            if question.preset is not None:
                if not self.function.takes_function:
                    raise ValueError(f"practice {question.id!r}: program takes no function")
                try:
                    self.function.preset(question.preset)
                except KeyError:
                    raise ValueError(
                        f"practice {question.id!r}: unknown preset {question.preset}"
                    ) from None
            if question.answer_field not in answer_fields:
                raise ValueError(
                    f"practice {question.id!r}: answer_field {question.answer_field!r} is not one"
                    f" of {sorted(answer_fields)}"
                )

    # ------------------------------------------------------------ helpers for consumers

    @property
    def input_names(self) -> tuple[str, ...]:
        """Input names in declaration order."""
        return tuple(item.name for item in self.inputs)

    def input(self, name: str) -> CatalogInput:
        """The input ``name``; raises :class:`KeyError` if absent."""
        for item in self.inputs:
            if item.name == name:
                return item
        raise KeyError(name)

    def ordered_inputs(self) -> Iterator[CatalogInput]:
        """Inputs in data-card reading order (by card, then declaration order)."""
        return iter(sorted(self.inputs, key=lambda item: item.card))

    def defaults(self) -> dict[str, InputValue]:
        """The book data card as ``{input name: default}``."""
        return {item.name: item.default for item in self.inputs}

    def practice_inputs(self, question: PracticeQuestion) -> dict[str, InputValue]:
        """The defaults with ``question``'s overrides applied (coerced to the input types)."""
        values = self.defaults()
        values.update(
            {name: self.input(name).coerce(value) for name, value in question.inputs.items()}
        )
        return values

    @property
    def sort_key(self) -> tuple[int, int, int, str]:
        """Confirmed programs by (chapter, program); unconfirmed ones last, by id."""
        ref = self.book_ref
        if self.book_ref_confirmed and ref is not None and ref.chapter and ref.program:
            return (0, ref.chapter, ref.program, self.id)
        return (1, 0, 0, self.id)

    @property
    def chapter(self) -> int | None:
        """The confirmed chapter number, or ``None`` for an unconfirmed reference."""
        if self.book_ref_confirmed and self.book_ref is not None:
            return self.book_ref.chapter
        return None
