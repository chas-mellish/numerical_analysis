"""Engine API: request validation, data-card serialization, the Python engine, compare diffs."""

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from gerald_na.algorithms.bisection import BisectionResult, BisectionStep
from gerald_na.engines import (
    ENGINE_NAMES,
    FortranRunner,
    PythonEngine,
    RunOutcome,
    RunRequest,
    available_engines,
    compare,
    diff_outcomes,
    get_adapter,
    get_engine,
    register_adapter,
    run_program,
    serialize_card,
    validate_inputs,
)
from gerald_na.engines.adapters import BisectionAdapter, adapters
from gerald_na.engines.base import consume_carriage_control, resolve_preset, result_to_dict
from gerald_na.engines.programs import card_number, steps_from_records
from gerald_na.engines.trace import parse_trace
from gerald_na.errors import (
    BracketError,
    EngineError,
    EngineUnavailableError,
    ExpressionError,
    FortranRunError,
    InputError,
    NonConvergenceError,
)
from gerald_na.registry import CatalogEntry, Registry, get_registry
from gerald_na.settings import Settings


@pytest.fixture(scope="module")
def bisection_entry() -> CatalogEntry:
    return get_registry().get("ch01_p01")


@pytest.fixture(scope="module")
def lagrange_like(repo_root: Path) -> CatalogEntry:
    """A data-only fixture entry with an int, a point list and a real (registry tests' fixture)."""
    from gerald_na.registry import load_entry

    path = Path(__file__).parent / "fixtures" / "registry" / "lagrange_like.toml"
    return load_entry(path)


def book_request(entry: CatalogEntry, **overrides: Any) -> RunRequest:
    return RunRequest.for_entry(entry, overrides)


# ---------------------------------------------------------------- request validation


def test_for_entry_fills_the_book_data_card(bisection_entry: CatalogEntry) -> None:
    request = RunRequest.for_entry(bisection_entry, {"tol": 1e-3})
    assert request.inputs == {"x1": 0.0, "x2": 1.0, "tol": 1e-3}
    assert request.preset is None
    assert not request.custom_function


def test_preset_and_expression_are_exclusive() -> None:
    with pytest.raises(ValidationError, match="either a preset or a custom expression"):
        RunRequest(preset=1, expression="x")
    with pytest.raises(ValidationError):
        RunRequest(preset=0)
    with pytest.raises(ValidationError):
        RunRequest(expression="")
    with pytest.raises(ValidationError):
        RunRequest(unknown=1)  # type: ignore[call-arg]


def test_valid_inputs_are_typed_in_card_order(bisection_entry: CatalogEntry) -> None:
    values = validate_inputs(bisection_entry, {"tol": 1e-5, "x2": 1, "x1": -0.5})
    assert values == {"x1": -0.5, "x2": 1.0, "tol": 1e-5}
    assert list(values) == ["x1", "x2", "tol"]
    assert all(type(v) is float for v in values.values())


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({"x1": 0.0, "x2": 1.0}, "missing input 'tol'"),
        ({"x1": 0.0, "x2": 1.0, "tol": 1e-5, "x3": 1.0}, "unknown input"),
        ({"x1": "0.5", "x2": 1.0, "tol": 1e-5}, "'x1'.*expected a real"),
        ({"x1": True, "x2": 1.0, "tol": 1e-5}, "'x1'.*expected a real"),
        ({"x1": None, "x2": 1.0, "tol": 1e-5}, "'x1'"),
        ({"x1": [0.0], "x2": 1.0, "tol": 1e-5}, "'x1'"),
        ({"x1": math.nan, "x2": 1.0, "tol": 1e-5}, "'x1'.*not a finite number"),
        ({"x1": 0.0, "x2": math.inf, "tol": 1e-5}, "'x2'.*not a finite number"),
        ({"x1": 0.0, "x2": -math.inf, "tol": 1e-5}, "'x2'.*not a finite number"),
        ({"x1": -1000.5, "x2": 1.0, "tol": 1e-5}, "'x1'.*below the minimum"),
        ({"x1": 0.0, "x2": 1.0, "tol": 2.0}, "'tol'.*above the maximum"),
        ({"x1": 0.0, "x2": 1.0, "tol": 0.0}, "'tol'.*below the minimum"),
    ],
)
def test_invalid_inputs_are_rejected(
    bisection_entry: CatalogEntry, raw: dict[str, object], match: str
) -> None:
    with pytest.raises(InputError, match=match):
        validate_inputs(bisection_entry, raw)


def test_list_and_int_inputs_are_validated(lagrange_like: CatalogEntry) -> None:
    good = lagrange_like.defaults()
    values = validate_inputs(lagrange_like, good)
    assert values == good
    names = lagrange_like.input_names
    point_list = next(i for i in lagrange_like.inputs if i.type == "point_list").name
    integer = next(i for i in lagrange_like.inputs if i.type == "int").name
    with pytest.raises(InputError, match=point_list):
        validate_inputs(lagrange_like, {**good, point_list: [[1.0, math.nan]]})
    with pytest.raises(InputError, match=point_list):
        validate_inputs(lagrange_like, {**good, point_list: [[1.0, 2.0, 3.0]]})
    with pytest.raises(InputError, match=integer):
        validate_inputs(lagrange_like, {**good, integer: 2.5})
    assert len(names) == len(values)


def test_unbounded_integers_must_fit_fortran(lagrange_like: CatalogEntry) -> None:
    integer = next(i for i in lagrange_like.inputs if i.type == "int")
    unbounded = integer.model_copy(update={"min": None, "max": None})
    entry = lagrange_like.model_copy(
        update={
            "inputs": tuple(
                unbounded if i.name == integer.name else i for i in lagrange_like.inputs
            )
        }
    )
    with pytest.raises(InputError, match="does not fit a Fortran integer"):
        validate_inputs(entry, {**entry.defaults(), integer.name: 2**40})


def test_presets_are_resolved(bisection_entry: CatalogEntry, lagrange_like: CatalogEntry) -> None:
    assert resolve_preset(bisection_entry, RunRequest()) == 1
    assert resolve_preset(bisection_entry, RunRequest(preset=3)) == 3
    assert resolve_preset(bisection_entry, RunRequest(expression="x")) is None
    with pytest.raises(InputError, match="unknown preset 9"):
        resolve_preset(bisection_entry, RunRequest(preset=9))
    assert resolve_preset(lagrange_like, RunRequest()) is None
    with pytest.raises(InputError, match="takes data, not a function"):
        resolve_preset(lagrange_like, RunRequest(preset=1))


# ---------------------------------------------------------------- data card


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0.0, "0.0"),
        (1e-5, "1e-05"),
        (-1000.0, "-1000.0"),
        (0.1, "0.1"),
        (7, "7"),
        (1 / 3, "0.3333333333333333"),
    ],
)
def test_card_numbers_round_trip(value: float, text: str) -> None:
    assert card_number(value) == text
    assert float(text) == value


def test_card_numbers_reject_booleans() -> None:
    with pytest.raises(TypeError):
        card_number(True)


def test_bisection_card_is_one_line_in_book_order(bisection_entry: CatalogEntry) -> None:
    card = serialize_card(bisection_entry, {"x1": 0.0, "x2": 1.0, "tol": 1e-5})
    assert card == "0.0 1.0 1e-05\n"
    # the generic card reads back as the catalog's printed card
    assert [float(t) for t in card.split()] == [
        float(t.replace("D", "E")) for t in bisection_entry.data_card.tokens()
    ]
    assert get_adapter("ch01_p01").data_card(bisection_entry, bisection_entry.defaults()) == card


def test_multi_card_lists_and_points(lagrange_like: CatalogEntry) -> None:
    values = validate_inputs(lagrange_like, lagrange_like.defaults())
    card = serialize_card(lagrange_like, values)
    lines = card.splitlines()
    point_input = next(i for i in lagrange_like.inputs if i.type == "point_list")
    points = values[point_input.name]
    assert isinstance(points, tuple)
    for point in points:
        assert isinstance(point, tuple)
        assert " ".join(card_number(c) for c in point) in lines
    flat = [float(t) for t in card.split()]
    expected = [
        n for item in lagrange_like.ordered_inputs() for n in item.numbers(values[item.name])
    ]
    assert flat == expected
    assert card.endswith("\n")


# ---------------------------------------------------------------- adapters


def test_adapter_registry() -> None:
    assert isinstance(get_adapter("ch01_p01"), BisectionAdapter)
    assert "ch01_p01" in adapters()
    with pytest.raises(EngineUnavailableError, match="no engine adapter"):
        get_adapter("ch99_p99")
    with pytest.raises(ValueError, match="already registered"):
        register_adapter(BisectionAdapter())
    register_adapter(BisectionAdapter(), replace=True)
    assert BisectionAdapter.result_fields()[:3] == ("value", "converged", "iterations")


def test_every_catalog_entry_has_an_adapter() -> None:
    """A catalogued program is not migrated until both engines can run it."""
    for entry in get_registry():
        adapter = get_adapter(entry.id)
        step_fields = set(adapter.step_type.__dataclass_fields__)  # type: ignore[attr-defined]
        assert {c.key for c in entry.trace.step_columns} == step_fields
        result_fields = set(adapter.result_fields())
        extras = {extra.key for extra in entry.trace.result_extras}
        assert extras <= result_fields, f"{entry.id}: RESULT extras missing from the dataclass"


def test_steps_from_records_checks_the_catalog_keys(bisection_entry: CatalogEntry) -> None:
    trace = parse_trace(
        "STEP,k=1,x1=0.0,x2=1.0,x=0.5,fx=-0.1\nRESULT,value=0.5,converged=T,iterations=1\n"
    )
    (step,) = steps_from_records(bisection_entry, trace.steps, BisectionStep)
    assert step == BisectionStep(k=1, x1=0.0, x2=1.0, x=0.5, fx=-0.1)
    bad = parse_trace(
        "STEP,k=1,x=0.5,fx=-0.1,extra=1.0\nRESULT,value=0.5,converged=T,iterations=1\n"
    )
    with pytest.raises(FortranRunError, match=r"missing \['x1', 'x2'\], unexpected \['extra'\]"):
        steps_from_records(bisection_entry, bad.steps, BisectionStep)


def test_bisection_result_from_trace_checks_consistency(bisection_entry: CatalogEntry) -> None:
    adapter = get_adapter("ch01_p01")
    inputs = bisection_entry.defaults()
    trace = parse_trace(
        "STEP,k=1,x1=0.0,x2=1.0,x=0.5,fx=-0.1\n"
        "RESULT,value=0.5,converged=T,iterations=2,root_at_endpoint=F,fx1=1.0,fx2=-0.6\n"
    )
    with pytest.raises(FortranRunError, match="inconsistent"):
        adapter.result_from_trace(bisection_entry, inputs, trace)
    missing = parse_trace("RESULT,value=0.0,converged=T,iterations=0,root_at_endpoint=T\n")
    with pytest.raises(FortranRunError, match="fx1"):
        adapter.result_from_trace(bisection_entry, inputs, missing)


# ---------------------------------------------------------------- Python engine


def test_python_engine_runs_the_book_card(bisection_entry: CatalogEntry) -> None:
    outcome = PythonEngine().run(bisection_entry, book_request(bisection_entry))
    assert outcome.ok
    assert outcome.status == "OK"
    assert isinstance(outcome.result, BisectionResult)
    assert outcome.result.iterations == 15
    assert outcome.result.value == 0.443572998046875
    assert outcome.engine == "python"
    assert outcome.preset == 1
    assert outcome.book_text == outcome.result.book_text()
    assert outcome.book_text.endswith(
        "THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED.\n"
    )
    assert outcome.raw_stdout is None
    assert outcome.trace_text is None
    assert len(outcome.steps) == 15
    assert outcome.elapsed_ms >= 0


def test_python_engine_presets_and_custom_expressions(bisection_entry: CatalogEntry) -> None:
    engine = PythonEngine()
    cubic = engine.run(
        bisection_entry, RunRequest.for_entry(bisection_entry, {"x1": 1.0, "x2": 2.0}, preset=2)
    )
    assert cubic.result.iterations == 18
    custom = engine.run(
        bisection_entry, RunRequest.for_entry(bisection_entry, expression="x - 0.25")
    )
    assert custom.result.value == 0.25
    assert custom.expression == "x - 0.25"
    assert custom.preset is None
    with pytest.raises(ExpressionError):
        engine.run(
            bisection_entry, RunRequest.for_entry(bisection_entry, expression="__import__('os')")
        )


def test_python_engine_reports_book_errors_with_partial_steps(
    bisection_entry: CatalogEntry,
) -> None:
    engine = PythonEngine()
    bracket = engine.run(bisection_entry, book_request(bisection_entry, x1=2.0, x2=3.0))
    assert not bracket.ok
    assert isinstance(bracket.error, BracketError)
    assert bracket.status == "BRACKET"
    assert bracket.book_text.startswith("FUNCTION VALUES WITH INITIAL X VALUES")
    stuck = engine.run(bisection_entry, book_request(bisection_entry, tol=1e-12))
    assert isinstance(stuck.error, NonConvergenceError)
    assert len(stuck.steps) == 25
    assert stuck.book_text.endswith("NON-CONVERGENT IN 25 ITERATIONS.\n")


def test_preset_overflow_is_an_input_error_but_custom_stays_expression(
    bisection_entry: CatalogEntry,
) -> None:
    engine = PythonEngine()
    preset = engine.run(bisection_entry, book_request(bisection_entry, x1=-1000.0))
    assert preset.status == "INPUT"
    assert type(preset.error) is InputError
    custom = engine.run(
        bisection_entry,
        RunRequest.for_entry(bisection_entry, {"x1": -1000.0}, expression="exp(-x) - 1"),
    )
    assert custom.status == "EXPRESSION"


def test_python_engine_contains_unexpected_failures(
    bisection_entry: CatalogEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = get_adapter("ch01_p01")

    def boom(*_args: object) -> object:
        raise ZeroDivisionError("bug")

    monkeypatch.setattr(adapter, "run_python", boom)
    outcome = PythonEngine().run(bisection_entry, book_request(bisection_entry))
    assert isinstance(outcome.error, EngineError)
    assert "ZeroDivisionError" in outcome.error.message


def test_validation_happens_before_running(bisection_entry: CatalogEntry) -> None:
    with pytest.raises(InputError, match="not a finite number"):
        PythonEngine().run(bisection_entry, book_request(bisection_entry, x1=math.nan))


# ---------------------------------------------------------------- outcomes


def test_outcome_needs_exactly_one_of_result_and_error() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        RunOutcome(engine="python", program_id="x", inputs={}, preset=None, expression=None)


def test_outcome_to_dict_is_json(bisection_entry: CatalogEntry) -> None:
    ok = run_program("ch01_p01", book_request(bisection_entry))
    data = json.loads(json.dumps(ok.to_dict()))
    assert data["status"] == "OK"
    assert data["result"]["iterations"] == 15
    assert "steps" not in data["result"]
    assert data["steps"][0] == {"k": 1, "x1": 0.0, "x2": 1.0, "x": 0.5, "fx": ok.steps[0].fx}
    failed = run_program("ch01_p01", book_request(bisection_entry, x1=2.0, x2=3.0))
    assert failed.to_dict()["error"]["code"] == "BRACKET"
    assert result_to_dict(ok.result)["root_at_endpoint"] is False


def test_consume_carriage_control() -> None:
    assert consume_carriage_control(" A\n B\n\nC\n") == "A\nB\n\nC\n"
    assert consume_carriage_control("") == ""


# ---------------------------------------------------------------- API helpers


def test_get_engine(clean_env: pytest.MonkeyPatch) -> None:
    assert ENGINE_NAMES == ("python", "fortran")
    assert isinstance(get_engine("python"), PythonEngine)
    assert isinstance(get_engine("fortran"), FortranRunner)
    with pytest.raises(EngineUnavailableError, match="unknown engine"):
        get_engine("julia")
    python_only = Settings(engines_enabled=("python",))
    with pytest.raises(EngineUnavailableError, match="disabled"):
        get_engine("fortran", python_only)
    assert isinstance(get_engine("fortran", python_only, check_enabled=False), FortranRunner)


def test_available_engines(
    clean_env: pytest.MonkeyPatch, tmp_path: Path, bisection_entry: CatalogEntry
) -> None:
    empty = Settings(fortran_bin_dir=tmp_path)
    assert available_engines(empty) == ("python",)
    assert available_engines(empty, bisection_entry) == ("python",)
    driver = tmp_path / bisection_entry.files.fortran_executable
    driver.write_text("#!/bin/sh\n", encoding="utf-8")
    driver.chmod(0o755)
    assert available_engines(empty) == ("python", "fortran")
    assert available_engines(empty, bisection_entry) == ("python", "fortran")
    assert available_engines(Settings(engines_enabled=("python",), fortran_bin_dir=tmp_path)) == (
        "python",
    )


def test_run_program_unknown_program(bisection_entry: CatalogEntry) -> None:
    with pytest.raises(InputError, match="unknown program"):
        run_program("ch99_p99", RunRequest())


# ---------------------------------------------------------------- compare


def _outcome(
    engine: str, steps: list[BisectionStep], *, iterations: int | None = None
) -> RunOutcome:
    result = BisectionResult(
        value=steps[-1].x,
        converged=True,
        iterations=len(steps) if iterations is None else iterations,
        steps=tuple(steps),
        root_at_endpoint=False,
        x1=0.0,
        x2=1.0,
        tol=1e-5,
        max_iter=25,
        fx1=1.0,
        fx2=-0.6,
    )
    return RunOutcome(
        engine=engine, program_id="ch01_p01", inputs={}, preset=1, expression=None, result=result
    )


STEPS = [
    BisectionStep(k=1, x1=0.0, x2=1.0, x=0.5, fx=-0.1),
    BisectionStep(k=2, x1=0.0, x2=0.5, x=0.25, fx=0.4),
    BisectionStep(k=3, x1=0.25, x2=0.5, x=0.375, fx=0.13),
]


def test_identical_outcomes_match(bisection_entry: CatalogEntry) -> None:
    report = diff_outcomes(bisection_entry, _outcome("python", STEPS), _outcome("fortran", STEPS))
    assert report.matches
    assert report.same_status
    assert report.same_iterations
    assert report.first_differing_row is None
    assert report.max_abs_diff == 0.0
    assert report.cells == ()
    assert [c.key for c in report.columns] == ["k", "x1", "x2", "x", "fx"]
    assert report.value_abs_diff == 0.0


def test_column_differences_are_located(bisection_entry: CatalogEntry) -> None:
    changed = [STEPS[0], replace(STEPS[1], fx=0.4 + 1e-7), replace(STEPS[2], fx=0.13 * (1 + 1e-15))]
    report = diff_outcomes(bisection_entry, _outcome("python", STEPS), _outcome("fortran", changed))
    assert not report.matches
    assert report.first_differing_row == 1
    fx = next(c for c in report.columns if c.key == "fx")
    assert fx.first_differing_row == 1
    assert fx.differing_rows == 2
    assert fx.max_abs_diff == pytest.approx(1e-7)
    assert fx.max_rel_diff == pytest.approx(1e-7 / (0.4 + 1e-7))
    assert [(c.row, c.key) for c in report.cells] == [(1, "fx"), (2, "fx")]
    # within a relative tolerance only the large difference remains
    loose = diff_outcomes(
        bisection_entry, _outcome("python", STEPS), _outcome("fortran", changed), rel_tol=1e-12
    )
    assert [(c.row, c.key) for c in loose.cells] == [(1, "fx")]
    looser = diff_outcomes(
        bisection_entry, _outcome("python", STEPS), _outcome("fortran", changed), rel_tol=1e-6
    )
    assert looser.matches
    assert looser.max_rel_diff > 0
    data = json.loads(json.dumps(report.to_dict()))
    assert data["first_differing_row"] == 1
    assert data["columns"][4]["differing_rows"] == 2


def test_mismatched_iterations_and_status(bisection_entry: CatalogEntry) -> None:
    short = _outcome("fortran", STEPS[:2])
    report = diff_outcomes(bisection_entry, _outcome("python", STEPS), short)
    assert not report.same_iterations
    assert not report.same_step_count
    assert not report.matches
    assert report.first_differing_row == 2
    assert "python has 3 rows, fortran has 2" in report.notes
    integer = [replace(STEPS[0], k=7), *STEPS[1:]]
    k_report = diff_outcomes(
        bisection_entry, _outcome("python", STEPS), _outcome("fortran", integer), rel_tol=1.0
    )
    assert k_report.first_differing_row == 0  # integer columns compare exactly
    failed = RunOutcome(
        engine="fortran",
        program_id="ch01_p01",
        inputs={},
        preset=1,
        expression=None,
        error=NonConvergenceError("NON-CONVERGENT", steps=STEPS),
    )
    mixed = diff_outcomes(bisection_entry, _outcome("python", STEPS), failed)
    assert not mixed.same_status
    assert mixed.value_abs_diff is None
    assert any("ended OK" in note for note in mixed.notes)


def test_compare_refuses_custom_functions_and_missing_drivers(
    bisection_entry: CatalogEntry, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    runner = FortranRunner(Settings(), bin_dir=tmp_path)
    with pytest.raises(InputError, match="presets only"):
        compare(
            bisection_entry,
            RunRequest(expression="x", inputs=bisection_entry.defaults()),
            ("python", runner),
        )
    with pytest.raises(EngineUnavailableError, match="not built"):
        compare(bisection_entry, book_request(bisection_entry), ("python", runner))
    with pytest.raises(ValueError, match="exactly two"):
        compare(bisection_entry, book_request(bisection_entry), ("python",))


def test_compare_python_with_itself(bisection_entry: CatalogEntry) -> None:
    report = compare("ch01_p01", book_request(bisection_entry), ("python", PythonEngine()))
    assert report.matches
    assert report.left.engine == report.right.engine == "python"


def test_registry_entries_are_the_catalog(repo_root: Path) -> None:
    assert [e.id for e in Registry.load(repo_root)] == [e.id for e in get_registry()]
