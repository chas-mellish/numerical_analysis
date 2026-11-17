"""Web-layer services shared by the HTML pages and the JSON API.

:class:`WebState` owns the settings and the (lazily loaded) catalog registry of one application,
knows which engines can run a program right now, validates run requests field by field and runs
them on one engine or in compare mode. The HTML routes and the JSON API therefore apply exactly
the same rules and report the same error codes (``docs/architecture.md``, "Web UI and JSON API").

Order of checks for a run (both front ends):

1. unknown program -> :class:`ProgramNotFound` (404);
2. malformed request: unknown run mode, a custom expression with the Fortran or compare engine
   (:class:`CustomFunctionEngineError`), field-level input problems (:class:`FieldErrors`), an
   invalid expression (:class:`~gerald_na.errors.ExpressionError`, with ``position``) -> 422;
3. engine disabled, program without an engine adapter or Fortran driver not built
   (:class:`~gerald_na.errors.EngineUnavailableError`) -> 503;
4. the run itself: a successful call whose outcome is either a result or a typed book error
   (``BRACKET``, ``NON_CONVERGENT``, ``FORTRAN_RUN``, ...) -> 200.
"""

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal, get_args

from pydantic import ValidationError

from gerald_na.engines import (
    CompareReport,
    FortranRunner,
    PythonEngine,
    RunOutcome,
    RunRequest,
    diff_outcomes,
    get_adapter,
    validate_request,
)
from gerald_na.engines.base import MAX_LIST_ITEMS, input_problem
from gerald_na.errors import EngineUnavailableError, InputError
from gerald_na.expr import compile_expr
from gerald_na.registry import CatalogEntry, CatalogPathError, Registry
from gerald_na.registry.loader import FileKind
from gerald_na.settings import Settings

__all__ = [
    "MAX_LIST_ITEMS",
    "RUN_MODES",
    "SERVED_FILE_KINDS",
    "CustomFunctionEngineError",
    "EngineStatus",
    "FieldErrors",
    "ProgramNotFound",
    "RunMode",
    "SourceFile",
    "WebState",
    "field_problems",
]

type RunMode = Literal["python", "fortran", "compare"]
RUN_MODES: tuple[str, ...] = get_args(RunMode.__value__)

SERVED_FILE_KINDS: tuple[FileKind, ...] = (
    "scan",
    "legacy",
    "fortran_module",
    "fortran_app",
    "python",
    "study",
)
"""File kinds served by ``GET /files/{program_id}/{kind}`` (DD5)."""

MAX_SOURCE_BYTES = 512 * 1024
"""Largest source file embedded inline in a program page tab."""


class ProgramNotFound(LookupError):
    """The program id is not in the catalog (HTTP 404)."""

    code: ClassVar[str] = "NOT_FOUND"


class CustomFunctionEngineError(InputError):
    """A custom expression was sent to the Fortran or compare engine (DD3, HTTP 422)."""

    code: ClassVar[str] = "CUSTOM_FUNCTION_ENGINE"


class FieldErrors(InputError):
    """One or more inputs are invalid; ``fields`` maps input names to messages (HTTP 422)."""

    def __init__(self, fields: Mapping[str, str]) -> None:
        details = "; ".join(f"{name}: {message}" for name, message in fields.items())
        super().__init__(f"invalid input: {details}")
        self.fields: dict[str, str] = dict(fields)


@dataclass(frozen=True, slots=True)
class EngineStatus:
    """Whether one engine (or compare mode) can run a program now, and why not."""

    name: str
    available: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A catalog file read for display in a program-page tab."""

    kind: str
    index: int
    path: str
    url: str
    text: str | None
    missing_reason: str = ""
    is_pdf: bool = False
    """The file is a scanned page (a PDF), shown as a link rather than as text."""


def field_problems(entry: CatalogEntry, raw: Mapping[str, object]) -> dict[str, str]:
    """Per-input problems of ``raw`` (unknown, missing, type, finite, bounds, list length).

    Uses the same per-input checks as :func:`gerald_na.engines.validate_inputs`
    (:func:`~gerald_na.engines.base.input_problem`) but collects every problem keyed by input
    name, so forms and API clients can point at the field. ``_unknown`` collects inputs the
    catalog does not declare.
    """
    problems: dict[str, str] = {}
    unknown = sorted(set(raw) - set(entry.input_names))
    if unknown:
        problems["_unknown"] = (
            f"unknown input(s) {', '.join(unknown)} (expected {', '.join(entry.input_names)})"
        )
    for item in entry.inputs:
        if item.name not in raw:
            problems[item.name] = "missing value"
            continue
        _, problem = input_problem(item, raw[item.name])
        if problem is not None:
            problems[item.name] = problem
    return problems


@dataclass
class WebState:
    """Settings, catalog and engine access of one web application instance."""

    settings: Settings
    _registry: Registry | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------ catalog

    @property
    def registry(self) -> Registry:
        """The catalog of ``settings.repo_root``, loaded on first use."""
        if self._registry is None:
            with self._lock:
                if self._registry is None:
                    self._registry = Registry.load(self.settings.repo_root)
        return self._registry

    def entry(self, program_id: str) -> CatalogEntry:
        """The catalog entry ``program_id``; raises :class:`ProgramNotFound`."""
        try:
            return self.registry.get(program_id)
        except KeyError:
            raise ProgramNotFound(f"unknown program {program_id!r}") from None

    # ------------------------------------------------------------ engines

    def python_engine(self) -> PythonEngine:
        """The Python engine."""
        return PythonEngine()

    def fortran_runner(self) -> FortranRunner:
        """A Fortran runner bound to this application's settings and catalog."""
        return FortranRunner(self.settings, registry=self.registry)

    @classmethod
    def count_inputs(cls, entry: CatalogEntry) -> Mapping[str, str]:
        """The adapter's ``{count input: list input}`` pairs (empty without an adapter)."""
        if not cls.has_adapter(entry):
            return {}
        return get_adapter(entry.id).count_inputs

    @staticmethod
    def has_adapter(entry: CatalogEntry) -> bool:
        """True when the engines know how to run ``entry`` (an adapter is registered)."""
        try:
            get_adapter(entry.id)
        except EngineUnavailableError:
            return False
        return True

    def engine_statuses(self, entry: CatalogEntry) -> dict[str, EngineStatus]:
        """Availability of ``python``, ``fortran`` and ``compare`` for ``entry``."""
        enabled = self.settings.engines_enabled
        adapter = self.has_adapter(entry)
        statuses: dict[str, EngineStatus] = {}
        if "python" not in enabled:
            statuses["python"] = EngineStatus("python", False, "disabled in the settings")
        elif not adapter:
            statuses["python"] = EngineStatus(
                "python", False, "this program has no engine adapter yet"
            )
        else:
            statuses["python"] = EngineStatus("python", True)
        if "fortran" not in enabled:
            statuses["fortran"] = EngineStatus("fortran", False, "disabled in the settings")
        elif not adapter:
            statuses["fortran"] = EngineStatus(
                "fortran", False, "this program has no engine adapter yet"
            )
        else:
            try:
                self.fortran_runner().executable_path(entry)
            except EngineUnavailableError as exc:
                statuses["fortran"] = EngineStatus("fortran", False, exc.message)
            else:
                statuses["fortran"] = EngineStatus("fortran", True)
        if statuses["python"].available and statuses["fortran"].available:
            statuses["compare"] = EngineStatus("compare", True)
        else:
            missing = statuses["fortran"] if statuses["python"].available else statuses["python"]
            statuses["compare"] = EngineStatus(
                "compare", False, f"needs both engines ({missing.name}: {missing.reason})"
            )
        return statuses

    def available_engines(self, entry: CatalogEntry) -> list[str]:
        """Names of the engines (and ``compare``) that can run ``entry`` now."""
        return [name for name, status in self.engine_statuses(entry).items() if status.available]

    # ------------------------------------------------------------ running

    def build_request(
        self,
        entry: CatalogEntry,
        mode: str,
        inputs: Mapping[str, object],
        *,
        preset: int | None = None,
        expression: str | None = None,
        verbose: bool = False,
    ) -> RunRequest:
        """Validate a run request (checks 2 of the module docstring) and return it.

        ``inputs`` must hold every catalog input (merge the book card first if needed).
        Raises :class:`InputError` subclasses: unknown mode, :class:`CustomFunctionEngineError`,
        :class:`FieldErrors` (per-input problems, then the adapter's cross-input
        ``input_problems``), :class:`~gerald_na.errors.ExpressionError`.
        """
        if mode not in RUN_MODES:
            raise InputError(f"unknown engine {mode!r} (choose from {', '.join(RUN_MODES)})")
        if expression is not None and not entry.function.takes_function:
            raise InputError(f"{entry.id} takes data, not a function: no expression allowed")
        if expression is not None and mode != "python":
            raise CustomFunctionEngineError(
                "custom expressions run on the Python engine only; the Fortran drivers (and "
                "therefore compare mode) evaluate the catalog presets"
            )
        problems = field_problems(entry, inputs)
        if problems:
            raise FieldErrors(problems)
        try:
            request = RunRequest(
                inputs=dict(inputs), preset=preset, expression=expression, verbose=verbose
            )
        except ValidationError as exc:  # pydantic: preset and expression together, bad preset
            messages = "; ".join(
                str(err["msg"]).removeprefix("Value error, ") for err in exc.errors()
            )
            raise InputError(messages) from None
        coerced, _ = validate_request(entry, request)  # unknown preset, data-only program
        if self.has_adapter(entry):
            # cross-input rules (Lagrange: n must equal the number of points), keyed by field
            cross = get_adapter(entry.id).input_problems(entry, coerced)
            if cross:
                raise FieldErrors(cross)
        if expression is not None:
            compile_expr(expression)  # ExpressionError with position
        return request

    def check_available(self, entry: CatalogEntry, mode: str) -> None:
        """Raise :class:`EngineUnavailableError` when ``mode`` cannot run ``entry`` now."""
        status = self.engine_statuses(entry).get(mode)
        if status is None:
            raise InputError(f"unknown engine {mode!r}")
        if not status.available:
            raise EngineUnavailableError(f"{mode} engine unavailable: {status.reason}")

    def run(
        self, entry: CatalogEntry, mode: str, request: RunRequest
    ) -> RunOutcome | CompareReport:
        """Run a validated request; compare mode diffs Python against Fortran."""
        self.check_available(entry, mode)
        if mode == "python":
            return self.python_engine().run(entry, request)
        if mode == "fortran":
            return self.fortran_runner().run(entry, request)
        left = self.python_engine().run(entry, request)
        right = self.fortran_runner().run(entry, request)
        return diff_outcomes(entry, left, right)

    # ------------------------------------------------------------ files

    def file_url(self, entry: CatalogEntry, kind: str, index: int = 0) -> str:
        """URL of a catalog file served by the whitelisted file route."""
        suffix = f"?index={index}" if kind == "legacy" and index else ""
        return f"/files/{entry.id}/{kind}{suffix}"

    def resolve_file(self, entry: CatalogEntry, kind: FileKind, index: int = 0) -> Path:
        """The on-disk path of a catalog file (whitelist of :meth:`Registry.resolve_path`).

        Raises :class:`CatalogPathError` when the kind is not served, the program has no such
        file, or the file is missing.
        """
        if kind not in SERVED_FILE_KINDS:
            raise CatalogPathError(f"file kind {kind!r} is not served")
        if kind != "legacy" and index != 0:
            raise CatalogPathError(f"{kind} has a single file")
        path = self.registry.resolve_path(entry, kind, index)
        if not path.is_file():
            raise CatalogPathError(f"{entry.id}: {kind} file is missing")
        return path

    def source_files(self, entry: CatalogEntry, kind: FileKind) -> list[SourceFile]:
        """Text files of ``kind`` for a program-page tab (legacy may list several)."""
        count = len(entry.files.legacy) if kind == "legacy" else 1
        files: list[SourceFile] = []
        for index in range(count):
            try:
                relative = self.registry.catalog_path(entry, kind, index)
            except CatalogPathError as exc:
                files.append(SourceFile(kind, index, "", "", None, exc.message))
                continue
            url = self.file_url(entry, kind, index)
            try:
                path = self.resolve_file(entry, kind, index)
                if is_pdf_path(path):
                    files.append(SourceFile(kind, index, relative, url, None, is_pdf=True))
                    continue
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    files.append(SourceFile(kind, index, relative, url, None, "file too large"))
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except CatalogPathError, OSError:
                files.append(SourceFile(kind, index, relative, url, None, "file not found"))
                continue
            files.append(SourceFile(kind, index, relative, url, text))
        return files

    def scan_available(self, entry: CatalogEntry) -> bool:
        """True when the catalog names a scan and the PDF exists."""
        if entry.files.scan_pdf is None:
            return False
        try:
            self.resolve_file(entry, "scan")
        except CatalogPathError:
            return False
        return True


def is_pdf_path(path: Path) -> bool:
    """True for a PDF file (a scanned page), recognized by its ``.pdf`` suffix."""
    return path.suffix.lower() == ".pdf"


def describe_book_ref(entry: CatalogEntry) -> str:
    """Human-readable book reference, e.g. ``Chapter 1, Program 1, page 24``."""
    ref = entry.book_ref
    if ref is None:
        return "Book reference unknown"
    parts: list[str] = []
    if ref.chapter is not None:
        parts.append(f"Chapter {ref.chapter}")
    if ref.program is not None:
        parts.append(f"Program {ref.program}")
    if ref.page is not None:
        parts.append(f"page {ref.page}")
    text = ", ".join(parts) if parts else "Book reference unknown"
    return f"{text} ({ref.title})" if ref.title else text


def entry_summary(state: WebState, entry: CatalogEntry) -> dict[str, Any]:
    """The program list item of ``GET /api/programs``."""
    return {
        "id": entry.id,
        "title": entry.title,
        "method": entry.method,
        "book_ref": entry.book_ref.model_dump(mode="json") if entry.book_ref else None,
        "confirmed": entry.book_ref_confirmed,
        "book_ref_text": describe_book_ref(entry),
        "chapter": entry.chapter,
        "inputs": [item.model_dump(mode="json") for item in entry.inputs],
        "takes_function": entry.function.takes_function,
        "default_preset": entry.function.default_preset,
        "presets": [preset.model_dump(mode="json") for preset in entry.function.presets],
        "engines": state.available_engines(entry),
        "scan_available": state.scan_available(entry),
        "chart_kind": entry.chart.kind,
        "url": f"/programs/{entry.id}",
        "api_url": f"/api/programs/{entry.id}",
    }


def entry_detail(state: WebState, entry: CatalogEntry) -> dict[str, Any]:
    """The full catalog entry for ``GET /api/programs/{id}``, file paths replaced by URLs."""
    data = entry.model_dump(mode="json")
    files = entry.files
    data["files"] = {
        "scan": state.file_url(entry, "scan") if files.scan_pdf is not None else None,
        "legacy": [state.file_url(entry, "legacy", i) for i in range(len(files.legacy))],
        "fortran_module": state.file_url(entry, "fortran_module"),
        "fortran_app": state.file_url(entry, "fortran_app"),
        "python": state.file_url(entry, "python"),
        "study": state.file_url(entry, "study"),
        "fortran_executable": files.fortran_executable,
        "python_callable": files.python_callable,
    }
    statuses = state.engine_statuses(entry)
    data["engines"] = {
        name: {"available": status.available, "reason": status.reason}
        for name, status in statuses.items()
    }
    data["book_ref_text"] = describe_book_ref(entry)
    data["scan_available"] = state.scan_available(entry)
    return data
