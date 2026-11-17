"""Engines that run a catalog program: the pure Python engine and the Fortran subprocess runner.

>>> from gerald_na.engines import RunRequest, run_program
>>> outcome = run_program("ch01_p01", RunRequest(inputs={"x1": 0.0, "x2": 1.0, "tol": 1e-5}))
>>> outcome.result.iterations, outcome.result.value
(15, 0.443572998046875)

Both engines return the same result dataclass per program; see ``docs/architecture.md``
("Engines") for the request/outcome contract, the trace protocol and the runner's safety rules.
"""

from collections.abc import Sequence

from gerald_na.engines.adapters import get_adapter, register_adapter
from gerald_na.engines.base import (
    Engine,
    ProgramResult,
    RunOutcome,
    RunRequest,
    validate_inputs,
    validate_request,
)
from gerald_na.engines.compare import CellDiff, ColumnDiff, CompareReport, diff_outcomes
from gerald_na.engines.fortran import DriverRun, FortranRunner
from gerald_na.engines.programs import ProgramAdapter, serialize_card
from gerald_na.engines.python import PythonEngine
from gerald_na.engines.trace import Record, Trace, parse_trace
from gerald_na.errors import EngineUnavailableError, InputError
from gerald_na.registry import CatalogEntry, Registry, get_registry
from gerald_na.settings import EngineName, Settings, get_settings

__all__ = [
    "ENGINE_NAMES",
    "CellDiff",
    "ColumnDiff",
    "CompareReport",
    "DriverRun",
    "Engine",
    "FortranRunner",
    "ProgramAdapter",
    "ProgramResult",
    "PythonEngine",
    "Record",
    "RunOutcome",
    "RunRequest",
    "Trace",
    "available_engines",
    "compare",
    "diff_outcomes",
    "get_adapter",
    "get_engine",
    "parse_trace",
    "register_adapter",
    "run_program",
    "serialize_card",
    "validate_inputs",
    "validate_request",
]

ENGINE_NAMES: tuple[EngineName, ...] = ("python", "fortran")


def get_engine(
    name: str, settings: Settings | None = None, *, check_enabled: bool = True
) -> Engine:
    """The engine called ``name`` (``python`` or ``fortran``).

    Raises :class:`EngineUnavailableError` for an unknown name or, with ``check_enabled``, an
    engine missing from ``settings.engines_enabled``.
    """
    settings = settings if settings is not None else get_settings()
    if name not in ENGINE_NAMES:
        raise EngineUnavailableError(
            f"unknown engine {name!r} (choose from {', '.join(ENGINE_NAMES)})"
        )
    if check_enabled and name not in settings.engines_enabled:
        raise EngineUnavailableError(f"engine {name!r} is disabled in the settings")
    if name == "python":
        return PythonEngine()
    return FortranRunner(settings)


def available_engines(
    settings: Settings | None = None, entry: CatalogEntry | None = None
) -> tuple[EngineName, ...]:
    """Enabled engines that can run now: Python always, Fortran when its drivers are built.

    With ``entry``, Fortran counts only if that program's driver is present.
    """
    settings = settings if settings is not None else get_settings()
    names: list[EngineName] = []
    for name in settings.engines_enabled:
        if name == "python":
            names.append(name)
            continue
        runner = FortranRunner(settings)
        usable = runner.is_available(entry) if entry is not None else runner.any_available()
        if usable:
            names.append(name)
    return tuple(names)


def _entry(program_id: str | CatalogEntry, registry: Registry | None) -> CatalogEntry:
    if isinstance(program_id, CatalogEntry):
        return program_id
    catalog = registry if registry is not None else get_registry()
    try:
        return catalog.get(program_id)
    except KeyError:
        raise InputError(f"unknown program {program_id!r}") from None


def _engine(engine: str | Engine, settings: Settings | None) -> Engine:
    return engine if isinstance(engine, Engine) else get_engine(engine, settings)


def run_program(
    program_id: str | CatalogEntry,
    request: RunRequest,
    engine: str | Engine = "python",
    *,
    registry: Registry | None = None,
    settings: Settings | None = None,
) -> RunOutcome:
    """Run one catalog program on one engine (see :class:`Engine` for the error contract)."""
    return _engine(engine, settings).run(_entry(program_id, registry), request)


def compare(
    program_id: str | CatalogEntry,
    request: RunRequest,
    engines: Sequence[str | Engine] = ("python", "fortran"),
    *,
    rel_tol: float = 0.0,
    abs_tol: float = 0.0,
    registry: Registry | None = None,
    settings: Settings | None = None,
) -> CompareReport:
    """Run ``request`` on two engines and return the step-by-step diff (compare mode).

    Request problems (:class:`InputError`, :class:`EngineUnavailableError`, including a custom
    expression, which the Fortran engine refuses) are raised before either engine runs.
    """
    if len(engines) != 2:
        raise ValueError("compare needs exactly two engines")
    entry = _entry(program_id, registry)
    left_engine, right_engine = (_engine(engine, settings) for engine in engines)
    for engine in (left_engine, right_engine):
        if isinstance(engine, FortranRunner):
            if request.expression is not None:
                raise InputError(
                    "compare mode needs the Fortran engine, which runs catalog presets only"
                )
            engine.executable_path(entry)
    left = left_engine.run(entry, request)
    right = right_engine.run(entry, request)
    return diff_outcomes(entry, left, right, rel_tol=rel_tol, abs_tol=abs_tol)
