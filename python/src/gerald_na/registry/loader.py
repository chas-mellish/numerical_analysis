"""Load ``catalog/*.toml`` into a :class:`Registry`, resolve catalog paths, check integrity."""

import importlib
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, get_args

from pydantic import ValidationError

from gerald_na.errors import GeraldNAError
from gerald_na.expr import ExpressionError, compile_expr
from gerald_na.registry.models import CatalogEntry
from gerald_na.settings import get_settings

__all__ = [
    "CATALOG_DIR",
    "PYTHON_SOURCE_DIR",
    "CatalogError",
    "CatalogPathError",
    "FileKind",
    "IntegrityProblem",
    "Registry",
    "get_registry",
    "load_entry",
]

CATALOG_DIR = Path("catalog")
"""Catalog directory, relative to the repository root."""

PYTHON_SOURCE_DIR = Path("python") / "src"
"""Root of the Python sources, relative to the repository root (``python`` file kind)."""

type FileKind = Literal[
    "catalog", "scan", "legacy", "fortran_module", "fortran_app", "python", "study"
]
FILE_KINDS: tuple[str, ...] = get_args(FileKind.__value__)


class CatalogError(GeraldNAError):
    """A catalog file is missing, unreadable, not valid TOML or fails schema validation."""

    code = "CATALOG"


class CatalogPathError(CatalogError, LookupError):
    """A requested catalog file kind does not exist for the program or escapes the repo root."""

    code = "CATALOG_PATH"


@dataclass(frozen=True, slots=True)
class IntegrityProblem:
    """One problem found by :meth:`Registry.check_integrity`."""

    program_id: str
    check: str
    message: str

    def __str__(self) -> str:
        return f"{self.program_id}: [{self.check}] {self.message}"


def load_entry(path: Path) -> CatalogEntry:
    """Parse and validate one catalog TOML file; raises :class:`CatalogError` on failure."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise CatalogError(f"{path.name}: cannot read catalog file: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CatalogError(f"{path.name}: invalid TOML: {exc}") from exc
    try:
        return CatalogEntry.model_validate(data)
    except ValidationError as exc:
        raise CatalogError(f"{path.name}: invalid catalog entry:\n{exc}") from exc


class Registry:
    """All catalog entries of a repository, ordered by book reference (unconfirmed last)."""

    def __init__(self, repo_root: Path, entries: list[tuple[Path, CatalogEntry]]) -> None:
        self._root = repo_root.resolve()
        self._sources = sorted(entries, key=lambda pair: (pair[1].sort_key, pair[0].name))
        self._by_id: dict[str, tuple[Path, CatalogEntry]] = {}
        for source, entry in self._sources:
            self._by_id.setdefault(entry.id, (source, entry))

    @classmethod
    def load(cls, repo_root: Path) -> Registry:
        """Load every ``catalog/*.toml`` below ``repo_root``.

        Raises :class:`CatalogError` if the catalog directory is missing or any file is invalid.
        Duplicate ids and file-name mismatches are reported by :meth:`check_integrity`.
        """
        directory = repo_root / CATALOG_DIR
        if not directory.is_dir():
            raise CatalogError(f"catalog directory {CATALOG_DIR} not found under the repo root")
        entries = [(path, load_entry(path)) for path in sorted(directory.glob("*.toml"))]
        return cls(repo_root, entries)

    # ------------------------------------------------------------ lookup

    @property
    def repo_root(self) -> Path:
        """The resolved repository root that catalog paths are relative to."""
        return self._root

    @property
    def programs(self) -> tuple[CatalogEntry, ...]:
        """Entries ordered by (chapter, program); unconfirmed references last, by id."""
        return tuple(entry for _, entry in self._sources)

    def __len__(self) -> int:
        return len(self._sources)

    def __iter__(self) -> Iterator[CatalogEntry]:
        return iter(self.programs)

    def __contains__(self, program_id: object) -> bool:
        return program_id in self._by_id

    def get(self, program_id: str) -> CatalogEntry:
        """The entry with ``program_id``; raises :class:`KeyError` if it is not catalogued."""
        return self._by_id[program_id][1]

    def by_chapter(self) -> dict[int | None, tuple[CatalogEntry, ...]]:
        """Entries grouped by confirmed chapter, in order; key ``None`` holds unconfirmed ones."""
        groups: dict[int | None, list[CatalogEntry]] = {}
        for entry in self.programs:
            groups.setdefault(entry.chapter, []).append(entry)
        return {chapter: tuple(items) for chapter, items in groups.items()}

    # ------------------------------------------------------------ whitelisted paths

    def catalog_path(self, entry: CatalogEntry | str, kind: FileKind, index: int = 0) -> str:
        """The repo-relative path that the catalog names for ``kind`` (no filesystem access).

        ``index`` selects one of several legacy files. Raises :class:`CatalogPathError` when the
        program is not catalogued or has no file of that kind (for example no scan).
        """
        source, found = self._lookup(entry)
        files = found.files
        match kind:
            case "catalog":
                return (CATALOG_DIR / source.name).as_posix()
            case "scan":
                if files.scan_pdf is None:
                    raise CatalogPathError(f"{found.id}: no scan is available")
                return files.scan_pdf
            case "legacy":
                if not 0 <= index < len(files.legacy):
                    raise CatalogPathError(f"{found.id}: no legacy file #{index}")
                return files.legacy[index]
            case "fortran_module":
                return files.fortran_module
            case "fortran_app":
                return files.fortran_app
            case "python":
                return self._python_source(files.python_module)
            case "study":
                return files.study_page
            case _:  # pragma: no cover - guarded by the Literal type
                raise CatalogPathError(f"unknown file kind {kind!r}")

    def resolve_path(self, entry: CatalogEntry | str, kind: FileKind, index: int = 0) -> Path:
        """Absolute path of a catalog-referenced file, guaranteed to lie under the repo root.

        Only paths named by a catalogued entry can be produced (no caller-supplied paths), and
        the resolved path, after following symlinks, must stay inside :attr:`repo_root`;
        otherwise :class:`CatalogPathError` is raised. The file itself may not exist.
        """
        if kind not in FILE_KINDS:
            raise CatalogPathError(f"unknown file kind {kind!r}")
        relative = self.catalog_path(entry, kind, index)
        resolved = (self._root / relative).resolve()
        if not resolved.is_relative_to(self._root):
            raise CatalogPathError(f"{relative!r} escapes the repository root")
        return resolved

    def _lookup(self, entry: CatalogEntry | str) -> tuple[Path, CatalogEntry]:
        program_id = entry if isinstance(entry, str) else entry.id
        try:
            source, found = self._by_id[program_id]
        except KeyError:
            raise CatalogPathError(f"program {program_id!r} is not catalogued") from None
        if not isinstance(entry, str) and entry != found:
            raise CatalogPathError(f"entry {program_id!r} does not belong to this registry")
        return source, found

    def _python_source(self, module: str) -> str:
        base = PYTHON_SOURCE_DIR.joinpath(*module.split("."))
        package_init = base / "__init__.py"
        if (self._root / package_init).is_file():
            return package_init.as_posix()
        return base.with_suffix(".py").as_posix()

    # ------------------------------------------------------------ integrity

    def check_integrity(self) -> list[IntegrityProblem]:
        """Every problem with the catalog; an empty list means the catalog is consistent.

        Checks: unique ids, file names starting with the id, unique Fortran executables, every
        referenced file present under the repo root (legacy files, the scan if one is named,
        Fortran module and driver, study page), the Python callable importable and callable,
        preset expressions non-blank and compiling with :mod:`gerald_na.expr`, defaults and
        practice overrides within min/max. Files that no entry references (such as un-migrated
        scans) are never inspected.
        """
        problems: list[IntegrityProblem] = []
        seen_ids: dict[str, str] = {}
        seen_exes: dict[str, str] = {}
        for source, entry in self._sources:
            pid = entry.id
            if pid in seen_ids:
                problems.append(
                    IntegrityProblem(
                        pid, "unique_id", f"{source.name} repeats the id of {seen_ids[pid]}"
                    )
                )
            else:
                seen_ids[pid] = source.name
            stem = source.stem
            if stem != pid and not stem.startswith(f"{pid}_"):
                problems.append(
                    IntegrityProblem(
                        pid, "file_name", f"{source.name} must be named {pid}[_name].toml"
                    )
                )
            exe = entry.files.fortran_executable
            if exe in seen_exes and seen_exes[exe] != pid:
                problems.append(
                    IntegrityProblem(
                        pid, "unique_executable", f"{exe} is also used by {seen_exes[exe]}"
                    )
                )
            seen_exes.setdefault(exe, pid)
            if self._by_id[pid][0] != source:
                continue  # duplicate id: its files cannot be resolved unambiguously
            problems.extend(self._check_files(entry))
            problems.extend(_check_callable(entry))
            problems.extend(_check_values(entry))
        return problems

    def _check_files(self, entry: CatalogEntry) -> Iterator[IntegrityProblem]:
        wanted: list[tuple[FileKind, int]] = [("legacy", i) for i in range(len(entry.files.legacy))]
        if entry.files.scan_pdf is not None:
            wanted.append(("scan", 0))
        wanted += [("fortran_module", 0), ("fortran_app", 0), ("study", 0)]
        for kind, index in wanted:
            try:
                path = self.resolve_path(entry, kind, index)
            except CatalogPathError as exc:
                yield IntegrityProblem(entry.id, "path", str(exc))
                continue
            if not path.is_file():
                relative = self.catalog_path(entry, kind, index)
                yield IntegrityProblem(
                    entry.id, "missing_file", f"{kind} file {relative} not found"
                )


def _check_callable(entry: CatalogEntry) -> Iterator[IntegrityProblem]:
    files = entry.files
    try:
        module = importlib.import_module(files.python_module)
    except Exception as exc:
        yield IntegrityProblem(
            entry.id, "python_callable", f"cannot import {files.python_module}: {exc}"
        )
        return
    target = getattr(module, files.python_attribute, None)
    if target is None:
        yield IntegrityProblem(
            entry.id, "python_callable", f"{files.python_callable} does not exist"
        )
    elif not callable(target):
        yield IntegrityProblem(
            entry.id, "python_callable", f"{files.python_callable} is not callable"
        )


def _check_values(entry: CatalogEntry) -> Iterator[IntegrityProblem]:
    for preset in entry.function.presets:
        if not preset.expr.strip():
            yield IntegrityProblem(entry.id, "preset", f"preset {preset.id} has a blank expression")
            continue
        try:
            compile_expr(preset.expr)
        except ExpressionError as exc:
            yield IntegrityProblem(
                entry.id, "preset", f"preset {preset.id} does not compile: {exc}"
            )
    for item in entry.inputs:
        problem = item.check_value(item.default)
        if problem is not None:
            yield IntegrityProblem(entry.id, "default", f"input {item.name}: {problem}")
    for question in entry.practice:
        for name, value in question.inputs.items():
            problem = entry.input(name).check_value(value)
            if problem is not None:
                yield IntegrityProblem(entry.id, "practice", f"{question.id}: {name}: {problem}")


@lru_cache(maxsize=1)
def get_registry() -> Registry:
    """Process-wide registry for ``get_settings().repo_root``; ``cache_clear()`` to reload."""
    return Registry.load(get_settings().repo_root)
