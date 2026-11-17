"""Golden (book-fidelity) tests: every catalog entry x every engine against its ``[[expected]]``.

Tolerance policy DD4 (``docs/architecture.md``):

* real64 engines (the Python engine and the default Fortran build) are compared against
  ``real64_value`` within ``tol_real64_value`` when present, and against ``book_value`` within
  ``tol_real64``;
* the ``SINGLE`` (real32) Fortran build is compared against ``book_value`` within
  ``tol_real32``;
* ``int`` and ``text`` expectations, and ``rows`` columns without a tolerance entry (the ``I``
  columns), are compared exactly.

The tests are generic: a new catalog file is covered automatically. Its program needs an engine
adapter (``gerald_na.engines.adapters``); without one the Python case fails on purpose, because
a catalogued program is not migrated until both engines run it. Fortran cases are marked
``fortran`` and skipped with an explicit reason when the driver is not built (``make
build-fortran`` for ``build/bin``, ``make build-fortran-single`` for ``build/single/bin``).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import pytest

from gerald_na.engines import Engine, FortranRunner, PythonEngine, RunRequest
from gerald_na.engines.trace import parse_trace
from gerald_na.registry import CatalogEntry, Expected, get_registry
from gerald_na.settings import Settings

type Precision = Literal["real64", "real32"]

ENTRIES = get_registry().programs


@dataclass(frozen=True)
class EngineCase:
    """One engine configuration under test and the precision its results are judged at."""

    id: str
    precision: Precision
    make: Callable[[Settings], Engine]
    build_hint: str = ""


ENGINE_CASES = [
    pytest.param(EngineCase("python", "real64", lambda _s: PythonEngine()), id="python"),
    pytest.param(
        EngineCase(
            "fortran",
            "real64",
            lambda s: FortranRunner(s),
            "make build-fortran",
        ),
        id="fortran",
        marks=pytest.mark.fortran,
    ),
    pytest.param(
        EngineCase(
            "fortran-single",
            "real32",
            lambda s: FortranRunner(s, bin_dir=s.fortran_single_bin_dir, label="fortran (single)"),
            "make build-fortran-single",
        ),
        id="fortran-single",
        marks=pytest.mark.fortran,
    ),
]


def make_engine(case: EngineCase, entry: CatalogEntry) -> Engine:
    """The engine of ``case``; skips with the build command when a Fortran driver is absent."""
    engine = case.make(Settings())
    if isinstance(engine, FortranRunner) and not engine.is_available(entry):
        pytest.skip(
            f"{entry.files.fortran_executable} not built in {engine.bin_dir.name}: "
            f"run `{case.build_hint}`"
        )
    return engine


def data_card_request(entry: CatalogEntry) -> RunRequest:
    """The book's run: the catalog data card and the book's function (default preset)."""
    return RunRequest(inputs=dict(entry.data_card.values))


# ---------------------------------------------------------------- comparison helpers


def _cell(row: object, column: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[column]
    if hasattr(row, column):
        return getattr(row, column)
    if isinstance(row, Sequence):
        return row[index]
    raise AssertionError(f"cannot read column {column!r} from {row!r}")


def _close(actual: float, expected: float, tol: float, what: str) -> None:
    difference = abs(float(actual) - float(expected))
    assert difference <= tol, (
        f"{what}: {actual!r} differs from {expected!r} by {difference:.3e} > {tol:.1e}"
    )


def _check_value(actual: Any, expected: Expected, value: Any, tol: float, what: str) -> None:
    match expected.kind:
        case "real":
            _close(actual, value, tol, what)
        case "table":
            rows = [list(row) for row in actual]
            assert [len(r) for r in rows] == [len(r) for r in value], f"{what}: table shape"
            for i, (got_row, want_row) in enumerate(zip(rows, value, strict=True)):
                for j, (got, want) in enumerate(zip(got_row, want_row, strict=True)):
                    _close(got, want, tol, f"{what}[{i}][{j}]")
        case _:  # pragma: no cover - rows/int/text are handled by the caller
            raise AssertionError(expected.kind)


def _check_rows(
    actual: Sequence[object],
    expected: Expected,
    value: Sequence[Sequence[float]],
    tolerance: Callable[[str], float],
    what: str,
) -> None:
    columns = expected.columns or ()
    assert len(actual) == len(value), f"{what}: {len(actual)} rows, expected {len(value)}"
    for r, (row, want_row) in enumerate(zip(actual, value, strict=True), start=1):
        for index, (column, want) in enumerate(zip(columns, want_row, strict=True)):
            got = _cell(row, column, index)
            tol = tolerance(column)
            if tol == 0.0:
                assert got == want, f"{what} row {r} {column}: {got!r} != {want!r} (exact)"
            else:
                _close(got, want, tol, f"{what} row {r} {column}")


def check_expected(result: object, expected: Expected, precision: Precision) -> None:
    """Assert one ``[[expected]]`` entry against ``result`` under the DD4 policy."""
    actual = getattr(result, expected.result_field)
    what = f"{expected.name} ({precision})"
    match expected.kind:
        case "int" | "text":
            assert actual == expected.book_value, f"{what}: {actual!r} != {expected.book_value!r}"
        case "rows":
            assert isinstance(expected.book_value, tuple)
            _check_rows(
                actual,
                expected,
                expected.book_value,
                lambda column: expected.tolerance(precision, column),
                f"{what} vs book",
            )
            if precision == "real64" and expected.real64_value is not None:
                assert isinstance(expected.real64_value, tuple)
                tight = expected.tol_real64_value or 0.0
                _check_rows(
                    actual,
                    expected,
                    expected.real64_value,
                    lambda column: tight if expected.tolerance("real64", column) else 0.0,
                    f"{what} vs real64_value",
                )
        case _:
            _check_value(
                actual,
                expected,
                expected.book_value,
                expected.tolerance(precision),
                f"{what} vs book",
            )
            if precision == "real64" and expected.real64_value is not None:
                _check_value(
                    actual,
                    expected,
                    expected.real64_value,
                    expected.tol_real64_value or 0.0,
                    f"{what} vs real64_value",
                )


# ---------------------------------------------------------------- tests


@pytest.mark.parametrize("case", ENGINE_CASES)
@pytest.mark.parametrize("entry", ENTRIES, ids=lambda entry: entry.id)
def test_book_data_card_matches_the_scan(entry: CatalogEntry, case: EngineCase) -> None:
    engine = make_engine(case, entry)
    outcome = engine.run(entry, data_card_request(entry))
    assert outcome.ok, f"{entry.id} on {engine.label}: {outcome.status}: {outcome.error}"
    for expected in entry.expected:
        check_expected(outcome.result, expected, case.precision)


@pytest.mark.parametrize("case", ENGINE_CASES[1:])
@pytest.mark.parametrize("entry", ENTRIES, ids=lambda entry: entry.id)
def test_fortran_reads_the_printed_data_card(entry: CatalogEntry, case: EngineCase) -> None:
    """The card exactly as printed in the scan gives the same trace as the generated card."""
    engine = make_engine(case, entry)
    assert isinstance(engine, FortranRunner)
    preset = entry.function.default_preset if entry.function.takes_function else None
    printed = engine.execute(entry, entry.data_card.text + "\n", preset=preset, trace=True)
    assert printed.returncode == 0, printed.stderr
    generated = engine.run(entry, data_card_request(entry))
    assert generated.trace_text is not None
    assert parse_trace(printed.stdout) == parse_trace(generated.trace_text)


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda entry: entry.id)
def test_expected_entries_name_result_fields(entry: CatalogEntry) -> None:
    """Every ``[[expected]]`` field exists on the Python result (catches catalog typos early)."""
    outcome = PythonEngine().run(entry, data_card_request(entry))
    assert outcome.ok, outcome.error
    for expected in entry.expected:
        assert hasattr(outcome.result, expected.result_field), expected.result_field
