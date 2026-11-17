"""Cross-engine parity: ``FortranRunner`` (default real64 build) versus the Python engine.

For every catalog entry and every function preset, the book data card plus a deterministic set
of random inputs within the catalog ``min``/``max`` run through both engines, which must agree:

* the same outcome (``OK`` or the same error code) and, for book error paths, the same message;
* the same number of iteration rows and iterations, integer columns exactly equal;
* every real value (steps and result fields) within 1e-12 relative -- both sides compute in
  real64 and the trace prints ``ES25.17E3``, so in practice they agree bit for bit;
* the same book text, and for the data card the Python ``book_text(carriage_control=True)``
  equals the driver's stdout character for character.

Inputs are generated per input type from a seed derived from the program id, half of them near
the book data card (where the iterations are interesting) and half across the full catalog range
(log-uniform for positive ranges spanning decades, such as tolerances). Programs whose inputs are
coupled (for example Lagrange's ``n`` and its point count) register a generator in
``CUSTOM_GENERATORS``. Skipped with the ``fortran`` marker when the drivers are not built.
"""

import math
import random
import zlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import fields, is_dataclass
from typing import Any

import pytest

from gerald_na.engines import FortranRunner, PythonEngine, RunOutcome, RunRequest, diff_outcomes
from gerald_na.registry import CatalogEntry, CatalogInput, get_registry
from gerald_na.settings import Settings

pytestmark = pytest.mark.fortran

REL_TOL = 1e-12
RANDOM_CASES = 24
"""Random input sets per (program, preset), in addition to the book data card."""

BOOK_ERROR_CODES = frozenset({"BRACKET", "ZERO_PRODUCT", "NON_CONVERGENT", "ODD_PANELS", "DEGREE"})
"""Errors whose message is the book's text, identical on both engines (INPUT messages differ)."""

type Inputs = dict[str, Any]
type Generator = Callable[[CatalogEntry, random.Random], Inputs]

CUSTOM_GENERATORS: dict[str, Generator] = {}
"""Program id -> input generator, for programs whose inputs constrain each other."""


def _bounds(item: CatalogInput, default: float) -> tuple[float, float]:
    spread = 10.0 * max(1.0, abs(default))
    low = item.min if item.min is not None else default - spread
    high = item.max if item.max is not None else default + spread
    return low, high


def _random_number(item: CatalogInput, default: float, rng: random.Random, near: bool) -> float:
    low, high = _bounds(item, default)
    if near:
        if low > 0 and high / low >= 1e3:  # tolerances: a few decades around the default
            value = default * 10.0 ** float(rng.uniform(-3.0, 3.0))
        else:
            value = default + rng.uniform(-0.6, 0.6) * max(1.0, abs(default))
    elif low > 0 and high / low >= 1e3:
        value = float(10.0 ** rng.uniform(math.log10(low), math.log10(high)))
    else:
        value = rng.uniform(low, high)
    return float(min(max(value, low), high))


def _random_value(item: CatalogInput, rng: random.Random, near: bool) -> Any:
    default = item.default
    match item.type:
        case "int":
            assert isinstance(default, int)
            low, high = _bounds(item, default)
            if near:
                low, high = max(low, default - 3), min(high, default + 3)
            return rng.randint(math.ceil(low), math.floor(high))
        case "real":
            assert isinstance(default, int | float)
            return _random_number(item, float(default), rng, near)
        case "real_list" | "point_list":
            assert isinstance(default, tuple)
            return [
                [_random_number(item, float(c), rng, near) for c in element]
                if isinstance(element, tuple)
                else _random_number(item, float(element), rng, near)
                for element in default
            ]
    raise AssertionError(item.type)  # pragma: no cover


def generic_inputs(entry: CatalogEntry, rng: random.Random) -> Inputs:
    near = rng.random() < 0.5
    return {item.name: _random_value(item, rng, near) for item in entry.inputs}


def input_sets(entry: CatalogEntry) -> Iterator[tuple[str, Inputs]]:
    """The data card and ``RANDOM_CASES`` reproducible random input sets."""
    yield "card", dict(entry.data_card.values)
    rng = random.Random(zlib.crc32(entry.id.encode()))  # noqa: S311 - reproducible test data
    generate = CUSTOM_GENERATORS.get(entry.id, generic_inputs)
    for index in range(RANDOM_CASES):
        yield f"r{index:02d}", generate(entry, rng)


def parity_cases() -> Iterator[Any]:
    for entry in get_registry().programs:
        presets: list[int | None] = (
            [preset.id for preset in entry.function.presets]
            if entry.function.takes_function
            else [None]
        )
        for preset in presets:
            for label, inputs in input_sets(entry):
                case_id = f"{entry.id}-p{preset}-{label}" if preset else f"{entry.id}-{label}"
                yield pytest.param(entry, preset, label, inputs, id=case_id)


@pytest.fixture(scope="module")
def fortran() -> FortranRunner:
    return FortranRunner(Settings())


def _close(a: object, b: object, what: str) -> None:
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, int | float):
        assert a == b, f"{what}: {a!r} != {b!r}"
        return
    assert isinstance(b, int | float)
    if isinstance(a, int) and isinstance(b, int):
        assert a == b, f"{what}: {a} != {b}"
        return
    if math.isnan(a) and math.isnan(b):
        return
    assert math.isclose(a, b, rel_tol=REL_TOL, abs_tol=0.0) or a == b, (
        f"{what}: python {a!r} vs fortran {b!r}"
    )


def _compare_fields(left: object, right: object, what: str) -> None:
    """Recursively compare two result dataclasses field by field."""
    if is_dataclass(left) and not isinstance(left, type):
        assert type(left) is type(right), f"{what}: {type(left)} vs {type(right)}"
        for f in fields(left):
            _compare_fields(getattr(left, f.name), getattr(right, f.name), f"{what}.{f.name}")
    elif isinstance(left, tuple | list):
        assert isinstance(right, tuple | list), f"{what}: {right!r} is not a sequence"
        assert len(left) == len(right), f"{what}: length"
        for i, (a, b) in enumerate(zip(left, right, strict=True)):
            _compare_fields(a, b, f"{what}[{i}]")
    elif isinstance(left, Mapping):
        assert isinstance(right, Mapping), f"{what}: {right!r} is not a mapping"
        assert set(left) == set(right), f"{what}: keys"
        for key in left:
            _compare_fields(left[key], right[key], f"{what}[{key!r}]")
    else:
        _close(left, right, what)


def assert_parity(entry: CatalogEntry, py: RunOutcome, ft: RunOutcome) -> None:
    assert py.status == ft.status, (
        f"python {py.status} ({py.error}) vs fortran {ft.status} ({ft.error})"
    )
    report = diff_outcomes(entry, py, ft, rel_tol=REL_TOL)
    assert report.same_step_count, report.notes
    assert report.same_iterations, report.notes
    assert report.matches, f"first differing row {report.first_differing_row}: " + "; ".join(
        f"row {c.row} {c.key}: {c.left!r} vs {c.right!r}" for c in report.cells[:5]
    )
    if py.result is not None:
        _compare_fields(py.result, ft.result, "result")
    else:
        assert py.error is not None
        assert ft.error is not None
        if py.status in BOOK_ERROR_CODES:
            assert py.error.message == ft.error.message
        _compare_fields(py.error.steps, ft.error.steps, "error.steps")
    assert py.book_text == ft.book_text


@pytest.mark.parametrize(("entry", "preset", "label", "inputs"), list(parity_cases()))
def test_engines_agree(
    fortran: FortranRunner,
    entry: CatalogEntry,
    preset: int | None,
    label: str,
    inputs: Inputs,
) -> None:
    if not fortran.is_available(entry):
        pytest.skip(f"{entry.files.fortran_executable} not built: run `make build-fortran`")
    request = RunRequest.for_entry(entry, inputs, preset=preset)
    py = PythonEngine().run(entry, request)
    ft = fortran.run(entry, request)
    assert ft.status != "FORTRAN_RUN", ft.error
    assert_parity(entry, py, ft)
    if label == "card" and py.result is not None:
        # the driver's stdout, carriage-control column included, is the Python book text
        assert py.result.book_text(carriage_control=True) == ft.raw_stdout


def test_random_inputs_cover_both_outcomes() -> None:
    """The generated sets exercise successes and error paths, not just one of them."""
    entry = get_registry().get("ch01_p01")
    statuses = {
        PythonEngine().run(entry, RunRequest.for_entry(entry, inputs, preset=preset)).status
        for preset in (1, 2, 3)
        for _, inputs in input_sets(entry)
    }
    assert "OK" in statuses
    assert statuses - {"OK"}, statuses
