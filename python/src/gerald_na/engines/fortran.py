"""The Fortran engine: runs the compiled book drivers as subprocesses (DD2, DD3, DD7).

Safety rules (``docs/architecture.md``, "Runner safety"):

* **Executable whitelist.** Only the ``files.fortran_executable`` names of the loaded catalog
  can run, and only from the configured binary directory (``settings.fortran_bin_dir``, or an
  explicit ``bin_dir`` such as ``build/single/bin``). The entry passed in must be the catalog's
  own entry for its id, so a forged entry cannot name another program.
* **No shell, validated stdin.** The argument vector is fixed (``--trace``, ``--verbose``,
  ``--preset <int>``); the data card written to stdin is produced from inputs that were
  validated against the catalog (finite numbers within ``min``/``max``).
* **Bounded runs.** Each run has the ``run_timeout_s`` timeout (the process is killed when it
  expires) and its output is limited to ``max_output_bytes``; the environment is reduced to a
  fixed minimum.

Each request runs the driver twice: once with ``--trace`` (parsed into the result dataclass),
once in book mode to capture the driver's own line-printer text (``raw_stdout``; ``book_text``
is the same with the carriage-control column consumed). A ``verbose`` request adds a third run
with ``--verbose`` whose extras land in ``verbose_text``. The runs take milliseconds.

Exit status in trace mode: 0 with a ``RESULT`` record is success, 2 with an ``ERROR`` record is
the typed book error (``BRACKET``, ``NON_CONVERGENT``, ...), anything else -- or output that
violates the protocol -- is a :class:`FortranRunError`. In book mode 0 and 1 (book error path)
are expected.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from gerald_na.engines.adapters import get_adapter
from gerald_na.engines.base import (
    Engine,
    RunOutcome,
    RunRequest,
    consume_carriage_control,
    validate_request,
)
from gerald_na.engines.programs import ProgramAdapter
from gerald_na.engines.trace import Trace, parse_trace
from gerald_na.errors import (
    TRACE_ERROR_CODES,
    EngineUnavailableError,
    FortranRunError,
    GeraldNAError,
    InputError,
)
from gerald_na.registry import CatalogEntry, Registry
from gerald_na.registry.models import InputValue
from gerald_na.settings import Settings, get_settings, list_executables

__all__ = [
    "DEFAULT_MAX_OUTPUT_BYTES",
    "EXIT_BOOK_ERROR",
    "EXIT_OK",
    "EXIT_TRACE_ERROR",
    "DriverRun",
    "FortranRunner",
]

DEFAULT_MAX_OUTPUT_BYTES = 1_000_000
"""Largest accepted stdout + stderr of one driver run (a book run prints a few kilobytes)."""

EXIT_OK = 0
EXIT_BOOK_ERROR = 1
EXIT_TRACE_ERROR = 2

_KEPT_ENVIRONMENT = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "SYSTEMROOT")
"""Variables passed through to the driver (shared-library lookup); everything else is dropped,
so ``GFORTRAN_*`` runtime settings of the server cannot change the drivers' behaviour."""

_STDERR_TAIL = 400


@dataclass(frozen=True, slots=True)
class DriverRun:
    """One completed driver process: its flags, exit status and decoded output."""

    executable: str
    flags: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float

    def describe(self) -> str:
        """``name --flag ...`` for messages."""
        return " ".join((self.executable, *self.flags))

    def stderr_tail(self) -> str:
        """The end of stderr, for error messages."""
        tail = self.stderr.strip()
        return tail if len(tail) <= _STDERR_TAIL else "..." + tail[-_STDERR_TAIL:]


def _check_status(run: DriverRun, expected: tuple[int, ...]) -> None:
    """Raise :class:`FortranRunError` unless ``run`` exited with one of ``expected``."""
    if run.returncode in expected:
        return
    how = (
        f"was killed by signal {-run.returncode}"
        if run.returncode < 0
        else f"exited with status {run.returncode}"
    )
    detail = run.stderr_tail()
    raise FortranRunError(f"{run.describe()} {how}" + (f": {detail}" if detail else ""))


def _driver_environment() -> dict[str, str]:
    env = {"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"}
    env.update({name: os.environ[name] for name in _KEPT_ENVIRONMENT if name in os.environ})
    return env


class FortranRunner(Engine):
    """Run catalog programs through their compiled Fortran drivers.

    ``bin_dir`` overrides ``settings.fortran_bin_dir`` (for example ``build/single/bin`` for the
    ``SINGLE`` build); relative directories are resolved against the repository root.
    ``registry`` is the catalog that defines the executable whitelist (default: the registry of
    ``settings.repo_root``). ``timeout_s`` defaults to ``settings.run_timeout_s``.
    """

    name: ClassVar[str] = "fortran"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        bin_dir: Path | str | None = None,
        registry: Registry | None = None,
        timeout_s: float | None = None,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        label: str | None = None,
    ) -> None:
        self._settings = settings if settings is not None else get_settings()
        self._bin_dir = (
            self._settings.resolve_path(Path(bin_dir))
            if bin_dir is not None
            else self._settings.fortran_bin_path
        )
        self._registry = registry
        self._timeout_s = timeout_s if timeout_s is not None else self._settings.run_timeout_s
        if self._timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        self._max_output_bytes = max_output_bytes
        self._label = label

    # ------------------------------------------------------------ configuration

    @property
    def label(self) -> str:
        return self._label or self.name

    @property
    def bin_dir(self) -> Path:
        """Directory the drivers are run from."""
        return self._bin_dir

    @property
    def timeout_s(self) -> float:
        """Wall-clock limit of one driver run, in seconds."""
        return self._timeout_s

    @property
    def registry(self) -> Registry:
        """The catalog defining the executable whitelist."""
        if self._registry is None:
            self._registry = Registry.load(self._settings.repo_root)
        return self._registry

    def whitelist(self) -> frozenset[str]:
        """Executable names the runner may start: the catalog's ``fortran_executable`` values."""
        return frozenset(entry.files.fortran_executable for entry in self.registry)

    def executable_path(self, entry: CatalogEntry) -> Path:
        """The driver of ``entry`` inside :attr:`bin_dir`, after the whitelist checks.

        Raises :class:`EngineUnavailableError` when the entry is not the catalog's, its
        executable is not whitelisted, or the binary has not been built.
        """
        name = entry.files.fortran_executable
        if entry.id not in self.registry or self.registry.get(entry.id) != entry:
            raise EngineUnavailableError(f"{entry.id}: not a catalog entry of this runner")
        if name not in self.whitelist() or Path(name).name != name:
            raise EngineUnavailableError(f"{name!r} is not a whitelisted Fortran executable")
        path = self._bin_dir / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise EngineUnavailableError(
                f"Fortran driver {name} is not built in {self._display_dir()} "
                "(run `make build-fortran`)"
            )
        return path

    def is_available(self, entry: CatalogEntry) -> bool:
        try:
            self.executable_path(entry)
        except EngineUnavailableError:
            return False
        return True

    def any_available(self) -> bool:
        """True when :attr:`bin_dir` holds at least one whitelisted driver."""
        return bool(self.whitelist() & set(list_executables(self._bin_dir)))

    def _display_dir(self) -> str:
        try:
            return self._bin_dir.relative_to(self._settings.repo_root).as_posix()
        except ValueError:
            return str(self._bin_dir)

    # ------------------------------------------------------------ running

    def execute(
        self,
        entry: CatalogEntry,
        card: str,
        *,
        preset: int | None = None,
        trace: bool = False,
        verbose: bool = False,
    ) -> DriverRun:
        """Run the driver of ``entry`` once with ``card`` on stdin and return its output.

        ``preset`` is the catalog preset id (``--preset`` gets its ``fortran_preset``).
        Raises :class:`EngineUnavailableError` (see :meth:`executable_path`) and
        :class:`FortranRunError` for a timeout, a start failure or oversized output; the exit
        status is not interpreted here.
        """
        path = self.executable_path(entry)
        flags: list[str] = []
        if trace:
            flags.append("--trace")
        if verbose:
            flags.append("--verbose")
        if preset is not None:
            flags += ["--preset", str(int(entry.function.preset(preset).fortran_preset))]
        name = path.name
        start = time.perf_counter()
        try:
            completed = subprocess.run(  # noqa: S603 - whitelisted executable, fixed flags
                [str(path), *flags],
                input=card.encode("ascii"),
                capture_output=True,
                timeout=self._timeout_s,
                shell=False,
                check=False,
                cwd=self._bin_dir,
                env=_driver_environment(),
            )
        except subprocess.TimeoutExpired:
            raise FortranRunError(
                f"Fortran driver {name} did not finish within {self._timeout_s:g} s and was stopped"
            ) from None
        except OSError as exc:
            raise FortranRunError(f"could not start Fortran driver {name}: {exc}") from None
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        size = len(completed.stdout) + len(completed.stderr)
        if size > self._max_output_bytes:
            raise FortranRunError(
                f"Fortran driver {name} wrote {size} bytes, more than the limit of "
                f"{self._max_output_bytes}"
            )
        return DriverRun(
            executable=name,
            flags=tuple(flags),
            returncode=completed.returncode,
            stdout=completed.stdout.decode("utf-8", errors="replace"),
            stderr=completed.stderr.decode("utf-8", errors="replace"),
            elapsed_ms=elapsed_ms,
        )

    def run(self, entry: CatalogEntry, request: RunRequest) -> RunOutcome:
        if request.expression is not None:
            raise InputError(
                "custom functions run only on the Python engine; the Fortran drivers know the "
                "catalog presets only (choose a preset or the Python engine)"
            )
        inputs, preset_id = validate_request(entry, request)
        adapter = get_adapter(entry.id)
        adapter.check_inputs(entry, inputs)
        self.executable_path(entry)  # EngineUnavailableError before anything runs
        card = adapter.data_card(entry, inputs)
        start = time.perf_counter()
        result: Any = None
        error: GeraldNAError | None = None
        trace_text: str | None = None
        raw_stdout: str | None = None
        verbose_text = ""
        try:
            traced = self.execute(entry, card, preset=preset_id, trace=True)
            trace_text = traced.stdout
            _check_status(traced, (EXIT_OK, EXIT_TRACE_ERROR))
            book = self.execute(entry, card, preset=preset_id)
            raw_stdout = book.stdout
            _check_status(book, (EXIT_OK, EXIT_BOOK_ERROR))
            book_text = consume_carriage_control(book.stdout)
            result, error = self._interpret(adapter, entry, inputs, traced, book_text)
            if request.verbose and error is None:
                extra = self.execute(entry, card, preset=preset_id, verbose=True)
                verbose_text = consume_carriage_control(
                    extra.stdout.removeprefix(book.stdout)
                ).lstrip("\n")
        except FortranRunError as exc:
            error = exc
            book_text = consume_carriage_control(raw_stdout) if raw_stdout else ""
            result = None
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return RunOutcome(
            engine=self.name,
            program_id=entry.id,
            inputs=inputs,
            preset=preset_id,
            expression=None,
            result=result,
            error=error,
            book_text=book_text,
            elapsed_ms=elapsed_ms,
            raw_stdout=raw_stdout,
            trace_text=trace_text,
            verbose_text=verbose_text,
        )

    def _interpret(
        self,
        adapter: ProgramAdapter,
        entry: CatalogEntry,
        inputs: dict[str, InputValue],
        run: DriverRun,
        book_text: str,
    ) -> tuple[Any, GeraldNAError | None]:
        """Map a ``--trace`` run to (result, None) or (None, typed error)."""
        trace: Trace = parse_trace(run.stdout)
        if run.returncode == EXIT_OK:
            if trace.result is None:
                raise FortranRunError(f"{run.describe()} exited with status 0 after an ERROR")
            result = adapter.result_from_trace(entry, inputs, trace)
            adapter.check_result_type(result)
            return result, None
        record = trace.error
        if record is None:
            raise FortranRunError(f"{run.describe()} exited with status 2 without an ERROR")
        code, message = record.text("code"), record.text("message")
        cls = TRACE_ERROR_CODES.get(code)
        if cls is None:
            raise FortranRunError(f"unknown trace error code {code!r}: {message}")
        steps = adapter.steps_from_trace(entry, trace)
        return None, cls(message, steps=steps, book_output=book_text)
