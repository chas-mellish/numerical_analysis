"""View models for the results fragment: tables, extras, figures and compare highlighting.

Everything here is generic over catalog programs. The iteration table comes from the catalog
``trace.step_columns`` (cells formatted with the column's Fortran edit descriptor, the full value
in the tooltip). The "result details" are every field of the result dataclass other than
``value``, ``converged``, ``iterations`` and ``steps``, rendered by shape: scalars, number lists,
ragged tables (Romberg's triangle), and lists of records (Bairstow's factors).
"""

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Literal

from gerald_na.engines import CompareReport, RunOutcome, get_adapter
from gerald_na.engines.base import step_to_dict
from gerald_na.engines.python import compile_function
from gerald_na.errors import ExpressionError, GeraldNAError
from gerald_na.registry import CatalogEntry, StepColumn
from gerald_na.web.charts import ChartInput, Figure, build_figures

__all__ = [
    "CellView",
    "CompareView",
    "ExtraView",
    "OutcomeView",
    "TableView",
    "compare_view",
    "format_cell",
    "format_value",
    "outcome_view",
]

_CORE_FIELDS = frozenset({"value", "converged", "iterations", "steps"})
_FORMAT = re.compile(r"^(I|F|ES|E|G|L|A)(\d*)(?:\.(\d+))?$")


def format_value(value: object) -> str:
    """Full-precision text of a result value (shortest round-tripping repr for floats)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else str(value)
    if isinstance(value, complex):
        return f"{value.real!r} {'+' if value.imag >= 0 else '-'} {abs(value.imag)!r}i"
    if isinstance(value, list | tuple):
        return ", ".join(format_value(item) for item in value)
    return str(value)


def format_cell(value: object, edit_descriptor: str) -> str:
    """``value`` formatted per a catalog edit descriptor (``I3``, ``F10.7``, ``E15.7``, ``G0``)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "T" if value else "F"
    if not isinstance(value, int | float):
        return str(value)
    match = _FORMAT.match(edit_descriptor)
    if match is None or not math.isfinite(float(value)):
        return format_value(value)
    letter, _, decimals = match.groups()
    digits = int(decimals) if decimals else None
    if letter == "I":
        return str(int(value))
    if letter == "F" and digits is not None:
        return f"{float(value):.{digits}f}"
    if letter == "ES" and digits is not None:
        return f"{float(value):.{digits}E}"
    if letter == "E" and digits is not None:
        return f"{float(value):.{max(digits - 1, 0)}E}"
    return format_value(value)


@dataclass
class CellView:
    """One table cell: display text, full value tooltip and compare-mode difference."""

    key: str
    text: str
    title: str
    diff: str | None = None


@dataclass
class TableView:
    """The iteration table of one outcome."""

    columns: list[tuple[str, str]]
    rows: list[list[CellView]]


@dataclass
class ExtraView:
    """One extra result field, rendered according to its shape."""

    name: str
    kind: Literal["scalar", "numbers", "matrix", "records"]
    text: str = ""
    values: list[str] = field(default_factory=list)
    matrix: list[list[str]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    records: list[list[str]] = field(default_factory=list)


@dataclass
class OutcomeView:
    """Everything the results fragment shows for one engine run."""

    engine: str
    ok: bool
    status: str
    error_code: str | None
    error_message: str | None
    value_text: str
    converged: bool | None
    iterations: int | None
    table: TableView
    extras: list[ExtraView]
    book_text: str
    verbose_text: str
    elapsed_ms: float
    figures: list[Figure]


@dataclass
class CompareView:
    """Both outcomes of compare mode plus the difference summary."""

    left: OutcomeView
    right: OutcomeView
    matches: bool
    same_status: bool
    same_iterations: bool
    iterations: tuple[int, int]
    max_abs_diff: float
    max_rel_diff: float
    value_abs_diff: float | None
    value_rel_diff: float | None
    differing_cells: int
    first_differing_row: int | None
    columns: list[dict[str, Any]]
    notes: list[str]


def _as_mapping(item: object) -> Mapping[str, Any] | None:
    if isinstance(item, Mapping):
        return item
    if is_dataclass(item) and not isinstance(item, type):
        return {f.name: getattr(item, f.name) for f in fields(item)}
    return None


def _is_number(value: object) -> bool:
    return isinstance(value, int | float | complex) and not isinstance(value, bool)


def _extra(name: str, value: object) -> ExtraView:
    if isinstance(value, list | tuple):
        items = list(value)
        if items and all(_is_number(item) for item in items):
            return ExtraView(name, "numbers", values=[format_value(item) for item in items])
        if items and all(
            isinstance(row, list | tuple) and all(_is_number(cell) for cell in row) for row in items
        ):
            return ExtraView(
                name,
                "matrix",
                matrix=[[format_value(cell) for cell in row] for row in items],
            )
        mappings = [_as_mapping(item) for item in items]
        if items and all(mapping is not None for mapping in mappings):
            columns: list[str] = []
            for mapping in mappings:
                for key in mapping or {}:
                    if key not in columns:
                        columns.append(str(key))
            records = [
                [format_value((mapping or {}).get(column, "")) for column in columns]
                for mapping in mappings
            ]
            return ExtraView(name, "records", columns=columns, records=records)
        if not items:
            return ExtraView(name, "scalar", text="(none)")
    return ExtraView(name, "scalar", text=format_value(value))


def _extras(result: object) -> list[ExtraView]:
    if not is_dataclass(result) or isinstance(result, type):
        return []
    return [
        _extra(f.name, getattr(result, f.name))
        for f in fields(result)
        if f.name not in _CORE_FIELDS
    ]


def _table(
    columns: Sequence[StepColumn],
    steps: Sequence[object],
    diffs: Mapping[tuple[int, str], str] | None = None,
) -> TableView:
    rows: list[list[CellView]] = []
    for index, step in enumerate(steps):
        data = step_to_dict(step)
        row: list[CellView] = []
        for column in columns:
            value = data.get(column.key)
            title = format_value(value) if value is not None else ""
            diff = (diffs or {}).get((index, column.key))
            row.append(CellView(column.key, format_cell(value, column.format), title, diff))
        rows.append(row)
    return TableView([(column.key, column.label) for column in columns], rows)


def _function(entry: CatalogEntry, outcome: RunOutcome) -> Callable[[float], float] | None:
    """F(x) for the charts, evaluated the way the program does.

    Points where the program substitutes a value (Simpson's and Romberg's book seed F(0) = 1
    for SIN(X)/X, :meth:`~gerald_na.engines.programs.ProgramAdapter.substituted_ordinates`)
    return that value instead of evaluating the expression.
    """
    try:
        function = compile_function(entry, outcome.preset, outcome.expression)
    except ExpressionError, GeraldNAError, KeyError:
        return None
    if function is None:
        return None
    try:
        fixed = get_adapter(entry.id).substituted_ordinates(entry, function)
    except GeraldNAError:
        fixed = {}
    if not fixed:
        return function
    compiled = function

    def substituted(x: float) -> float:
        return fixed[x] if x in fixed else compiled(x)

    return substituted


def figures_for(entry: CatalogEntry, outcome: RunOutcome) -> list[Figure]:
    """The chart figures of ``outcome`` (catalog ``[chart]`` kind and options)."""
    result: Mapping[str, Any] | None = None
    if outcome.result is not None:
        mapping = _as_mapping(outcome.result)
        result = dict(mapping) if mapping is not None else None
    data = ChartInput(
        kind=entry.chart.kind,
        options=entry.chart.options,
        steps=[step_to_dict(step) for step in outcome.steps],
        result=result,
        inputs=dict(outcome.inputs),
        function=_function(entry, outcome),
        labels={column.key: column.label for column in entry.trace.step_columns},
    )
    return build_figures(data)


def outcome_view(
    entry: CatalogEntry,
    outcome: RunOutcome,
    *,
    diffs: Mapping[tuple[int, str], str] | None = None,
    with_figures: bool = True,
) -> OutcomeView:
    """The view model of one engine outcome."""
    result = outcome.result
    return OutcomeView(
        engine=outcome.engine,
        ok=outcome.ok,
        status=outcome.status,
        error_code=outcome.error.code if outcome.error is not None else None,
        error_message=outcome.error.message if outcome.error is not None else None,
        value_text=format_value(result.value) if result is not None else "",
        converged=bool(result.converged) if result is not None else None,
        iterations=int(result.iterations) if result is not None else None,
        table=_table(entry.trace.step_columns, outcome.steps, diffs),
        extras=_extras(result) if result is not None else [],
        book_text=outcome.book_text,
        verbose_text=outcome.verbose_text,
        elapsed_ms=outcome.elapsed_ms,
        figures=figures_for(entry, outcome) if with_figures else [],
    )


def _diff_text(abs_diff: float, rel_diff: float) -> str:
    return f"abs diff {abs_diff:.3e}, rel diff {rel_diff:.3e}"


def compare_view(entry: CatalogEntry, report: CompareReport) -> CompareView:
    """Side-by-side view of a compare report with the differing cells marked on both sides."""
    diffs = {
        (cell.row, cell.key): _diff_text(cell.abs_diff, cell.rel_diff) for cell in report.cells
    }
    data = report.to_dict()
    left_iterations, right_iterations = data["iterations"]
    return CompareView(
        left=outcome_view(entry, report.left, diffs=diffs),
        right=outcome_view(entry, report.right, diffs=diffs, with_figures=False),
        matches=report.matches,
        same_status=report.same_status,
        same_iterations=report.same_iterations,
        iterations=(int(left_iterations), int(right_iterations)),
        max_abs_diff=report.max_abs_diff,
        max_rel_diff=report.max_rel_diff,
        value_abs_diff=report.value_abs_diff,
        value_rel_diff=report.value_rel_diff,
        differing_cells=len(report.cells),
        first_differing_row=report.first_differing_row,
        columns=list(data["columns"]),
        notes=list(report.notes),
    )
