"""Compare mode: run one request on two engines and diff the traces step by step.

The diff is driven by the catalog's ``step_columns``: for every column it reports the largest
absolute and relative difference and the first row where the engines differ, and it flags
mismatched iteration counts, step counts and outcomes (``OK`` versus an error code). Integer
columns (``I`` edit descriptors) must agree exactly. This is how the UI shows precision effects.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from gerald_na.engines.base import RunOutcome, step_to_dict
from gerald_na.registry import CatalogEntry

__all__ = ["CellDiff", "ColumnDiff", "CompareReport", "diff_outcomes"]


@dataclass(frozen=True, slots=True)
class CellDiff:
    """One differing cell: row index (0-based), column key and both values."""

    row: int
    key: str
    left: float
    right: float
    abs_diff: float
    rel_diff: float


@dataclass(frozen=True, slots=True)
class ColumnDiff:
    """Summary of one step column over the rows both engines produced."""

    key: str
    label: str
    integer: bool
    max_abs_diff: float
    max_rel_diff: float
    first_differing_row: int | None
    differing_rows: int


@dataclass(frozen=True)
class CompareReport:
    """Step-by-step differences between two outcomes of the same request.

    ``left`` and ``right`` are the outcomes (by default Python and Fortran). Rows are compared
    pairwise up to the shorter trace; ``first_differing_row`` is the first row index where any
    column differs beyond the tolerances (or where one trace has a row the other lacks).
    """

    program_id: str
    left: RunOutcome
    right: RunOutcome
    rel_tol: float
    abs_tol: float
    columns: tuple[ColumnDiff, ...]
    cells: tuple[CellDiff, ...]
    first_differing_row: int | None
    value_abs_diff: float | None
    value_rel_diff: float | None
    notes: tuple[str, ...] = field(default=())

    @property
    def same_status(self) -> bool:
        """Both succeeded, or both failed with the same error code."""
        return self.left.status == self.right.status

    @property
    def same_iterations(self) -> bool:
        """Same iteration count (both results) or same number of partial steps (errors)."""
        return self._iterations(self.left) == self._iterations(self.right)

    @property
    def same_step_count(self) -> bool:
        """Both traces have the same number of rows."""
        return len(self.left.steps) == len(self.right.steps)

    @property
    def max_abs_diff(self) -> float:
        """Largest absolute difference over all compared cells (0.0 when identical)."""
        return max((c.max_abs_diff for c in self.columns), default=0.0)

    @property
    def max_rel_diff(self) -> float:
        """Largest relative difference over all compared cells (0.0 when identical)."""
        return max((c.max_rel_diff for c in self.columns), default=0.0)

    @property
    def matches(self) -> bool:
        """Same outcome, iteration and row counts, and every cell within the tolerances."""
        return (
            self.same_status
            and self.same_iterations
            and self.same_step_count
            and self.first_differing_row is None
            and (
                self.value_abs_diff is None
                or self._within(self.value_abs_diff, self.value_rel_diff)
            )
        )

    def _within(self, abs_diff: float, rel_diff: float | None) -> bool:
        return abs_diff <= self.abs_tol or (rel_diff is not None and rel_diff <= self.rel_tol)

    @staticmethod
    def _iterations(outcome: RunOutcome) -> int:
        if outcome.result is not None:
            return int(outcome.result.iterations)
        return len(outcome.steps)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready view for the web API and ``gerald-na run --engine compare``."""
        return {
            "program_id": self.program_id,
            "engines": [self.left.engine, self.right.engine],
            "status": [self.left.status, self.right.status],
            "iterations": [self._iterations(self.left), self._iterations(self.right)],
            "step_counts": [len(self.left.steps), len(self.right.steps)],
            "same_status": self.same_status,
            "same_iterations": self.same_iterations,
            "matches": self.matches,
            "rel_tol": self.rel_tol,
            "abs_tol": self.abs_tol,
            "first_differing_row": self.first_differing_row,
            "max_abs_diff": self.max_abs_diff,
            "max_rel_diff": self.max_rel_diff,
            "value_abs_diff": self.value_abs_diff,
            "value_rel_diff": self.value_rel_diff,
            "columns": [
                {
                    "key": c.key,
                    "label": c.label,
                    "integer": c.integer,
                    "max_abs_diff": c.max_abs_diff,
                    "max_rel_diff": c.max_rel_diff,
                    "first_differing_row": c.first_differing_row,
                    "differing_rows": c.differing_rows,
                }
                for c in self.columns
            ],
            "cells": [
                {
                    "row": c.row,
                    "key": c.key,
                    "left": c.left,
                    "right": c.right,
                    "abs_diff": c.abs_diff,
                    "rel_diff": c.rel_diff,
                }
                for c in self.cells
            ],
            "notes": list(self.notes),
            "outcomes": [self.left.to_dict(), self.right.to_dict()],
        }


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _differences(left: float, right: float) -> tuple[float, float]:
    """Absolute and relative difference; equal values (including equal infinities) give 0."""
    if left == right or (math.isnan(left) and math.isnan(right)):
        return 0.0, 0.0
    abs_diff = abs(left - right)
    scale = max(abs(left), abs(right))
    rel_diff = abs_diff / scale if scale > 0 and math.isfinite(scale) else math.inf
    return abs_diff, rel_diff


def _value_diff(left: RunOutcome, right: RunOutcome) -> tuple[float | None, float | None]:
    if left.result is None or right.result is None:
        return None, None
    a, b = _number(left.result.value), _number(right.result.value)
    if a is None or b is None:
        return None, None
    return _differences(a, b)


def diff_outcomes(
    entry: CatalogEntry,
    left: RunOutcome,
    right: RunOutcome,
    *,
    rel_tol: float = 0.0,
    abs_tol: float = 0.0,
) -> CompareReport:
    """Diff two outcomes of ``entry`` column by column (see :class:`CompareReport`).

    A real cell "differs" when its absolute difference exceeds ``abs_tol`` and its relative
    difference exceeds ``rel_tol``; integer columns differ on any inequality. With the default
    zero tolerances every bit of difference is reported.
    """
    left_rows: Sequence[dict[str, Any]] = [step_to_dict(step) for step in left.steps]
    right_rows: Sequence[dict[str, Any]] = [step_to_dict(step) for step in right.steps]
    shared = min(len(left_rows), len(right_rows))
    cells: list[CellDiff] = []
    columns: list[ColumnDiff] = []
    first_row: int | None = None
    for column in entry.trace.step_columns:
        max_abs = max_rel = 0.0
        first: int | None = None
        count = 0
        for index in range(shared):
            a = _number(left_rows[index].get(column.key))
            b = _number(right_rows[index].get(column.key))
            if a is None or b is None:
                continue
            abs_diff, rel_diff = _differences(a, b)
            if abs_diff == 0.0:
                continue
            max_abs, max_rel = max(max_abs, abs_diff), max(max_rel, rel_diff)
            differs = column.is_integer or (abs_diff > abs_tol and rel_diff > rel_tol)
            if differs:
                count += 1
                first = index if first is None else first
                cells.append(CellDiff(index, column.key, a, b, abs_diff, rel_diff))
        if first is not None:
            first_row = first if first_row is None else min(first_row, first)
        columns.append(
            ColumnDiff(
                key=column.key,
                label=column.label,
                integer=column.is_integer,
                max_abs_diff=max_abs,
                max_rel_diff=max_rel,
                first_differing_row=first,
                differing_rows=count,
            )
        )
    notes: list[str] = []
    if len(left_rows) != len(right_rows):
        notes.append(
            f"{left.engine} has {len(left_rows)} rows, {right.engine} has {len(right_rows)}"
        )
        first_row = shared if first_row is None else min(first_row, shared)
    if left.status != right.status:
        notes.append(f"{left.engine} ended {left.status}, {right.engine} ended {right.status}")
    value_abs, value_rel = _value_diff(left, right)
    cells.sort(key=lambda cell: (cell.row, cell.key))
    return CompareReport(
        program_id=entry.id,
        left=left,
        right=right,
        rel_tol=rel_tol,
        abs_tol=abs_tol,
        columns=tuple(columns),
        cells=tuple(cells),
        first_differing_row=first_row,
        value_abs_diff=value_abs,
        value_rel_diff=value_rel,
        notes=tuple(notes),
    )
