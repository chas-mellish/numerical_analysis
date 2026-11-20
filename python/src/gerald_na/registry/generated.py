"""Markdown generated from the catalog: the README program index and run commands, and the
study-page errata tables.

The catalog is the single source of truth (DD9), so text that restates it is generated rather
than edited by hand. Each generated block sits between two HTML-comment markers in its file:

* ``README.md``: :data:`INDEX_START` / :data:`INDEX_END` hold :func:`render_program_index`, and
  :data:`RUN_COMMANDS_START` / :data:`RUN_COMMANDS_END` hold :func:`render_run_commands` (a
  copy-paste command per program for the compiled Fortran driver, fed the catalog's data card,
  and for the Python port, plus the catalog's expected results);
* every study page (``content/*.md``): :data:`ERRATA_START` / :data:`ERRATA_END` hold
  :func:`render_errata_table` for that program, so the table carries every catalog erratum with
  its id, kind and wording.

``gerald-na catalog index --write`` (``make readme-index``) rewrites the blocks;
``gerald-na catalog index --check`` and ``python/tests/unit/test_generated_docs.py`` fail when a
block is out of date. The web layer drops the marker lines when it renders a study page.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from gerald_na.registry.loader import CatalogError, Registry
from gerald_na.registry.models import BookValue, CatalogEntry, ErratumKind, Expected

__all__ = [
    "ERRATA_END",
    "ERRATA_START",
    "INDEX_END",
    "INDEX_START",
    "KIND_LABELS",
    "README_PATH",
    "RUN_COMMANDS_END",
    "RUN_COMMANDS_START",
    "GeneratedBlockError",
    "GeneratedFile",
    "book_reference",
    "escape_cell",
    "format_expected_value",
    "generated_files",
    "printf_argument",
    "printf_command",
    "render_errata_table",
    "render_program_index",
    "render_run_commands",
    "replace_block",
]

INDEX_START = "<!-- PROGRAM_INDEX_START -->"
INDEX_END = "<!-- PROGRAM_INDEX_END -->"
RUN_COMMANDS_START = "<!-- RUN_COMMANDS_START -->"
RUN_COMMANDS_END = "<!-- RUN_COMMANDS_END -->"
ERRATA_START = "<!-- ERRATA_TABLE_START -->"
ERRATA_END = "<!-- ERRATA_TABLE_END -->"

README_PATH = Path("README.md")
"""The README, relative to the repository root."""

KIND_LABELS: dict[ErratumKind, str] = {
    "ocr_slip": "OCR slip",
    "original_bug": "original bug",
    "original_quirk": "original quirk",
    "rewrite_drift": "rewrite drift",
    "modernization": "modernization",
}
"""How each catalog erratum ``kind`` is shown in the errata tables."""

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>|~&#])")
_WHITESPACE = re.compile(r"\s+")


class GeneratedBlockError(CatalogError):
    """A file lacks the start/end markers of its generated block (or has them out of order)."""

    code = "CATALOG_GENERATED"


def escape_cell(text: str) -> str:
    """``text`` as one Markdown table cell: whitespace collapsed, Markdown syntax escaped."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", _WHITESPACE.sub(" ", text).strip())


def book_reference(entry: CatalogEntry) -> str:
    """``Ch. 1, Prog. 1, p. 24``; ``unconfirmed`` when the catalog does not confirm it (DD1)."""
    ref = entry.book_ref
    if not entry.book_ref_confirmed or ref is None:
        return "unconfirmed"
    parts = [f"Ch. {ref.chapter}", f"Prog. {ref.program}"]
    if ref.page is not None:
        parts.append(f"p. {ref.page}")
    return ", ".join(parts)


def render_program_index(registry: Registry) -> str:
    """The README program index: one row per catalog entry, in book order."""
    lines = [
        "| Program id | Book reference | Method | Scan available? | Fortran executable "
        "| Python function | Study page |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in registry.programs:
        files = entry.files
        scan = f"[yes]({files.scan_pdf})" if files.scan_pdf is not None else "**no**"
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{entry.id}`",
                    book_reference(entry),
                    escape_cell(entry.title),
                    scan,
                    f"[`{files.fortran_executable}`]({files.fortran_app})",
                    f"`{files.python_callable}`",
                    f"[{files.study_page}]({files.study_page})",
                )
            )
            + " |"
        )
    missing = [entry.id for entry in registry.programs if entry.files.scan_pdf is None]
    unconfirmed = [entry.id for entry in registry.programs if not entry.book_ref_confirmed]
    lines.append("")
    lines.append(
        f"{len(registry)} programs. Without a scan: "
        + (", ".join(f"`{pid}`" for pid in missing) if missing else "none")
        + ". Book reference unconfirmed: "
        + (", ".join(f"`{pid}`" for pid in unconfirmed) if unconfirmed else "none")
        + "."
    )
    return "\n".join(lines) + "\n"


def printf_argument(card: str) -> str:
    r"""``card`` as the single-quoted format argument of ``printf`` in ``sh``.

    Leading and trailing blank lines are dropped; the remaining lines keep their column spacing
    verbatim and each ends in ``\n``. ``\`` and ``%`` are doubled so ``printf`` prints them
    literally, and ``'`` is written as ``'\''`` (close quote, escaped quote, reopen).
    """
    lines = card.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    escaped = (
        line.replace("\\", "\\\\").replace("%", "%%").replace("'", "'\\''") for line in lines
    )
    return "'" + "".join(f"{line}\\n" for line in escaped) + "'"


def printf_command(card: str, executable: str) -> str:
    r"""The ``printf <arg> | build/bin/<executable>`` line for the README run block.

    A ``--`` end-of-options marker is inserted when ``card``'s first non-blank line starts with
    ``-``; without it, ``sh``'s ``printf`` would read the card as an option (e.g. ``-1.0``).
    Current catalog cards all start with a digit, so no README output changes today.
    """
    arg = printf_argument(card)
    end_of_options = "-- " if arg.startswith("'-") else ""
    return f"printf {end_of_options}{arg} | build/bin/{executable}"


def format_expected_value(value: BookValue) -> str:
    """A scalar expected value as a code span: shortest round-trip ``repr`` for reals.

    The drivers print these values truncated to their FORMAT width (round toward zero), so each
    printed number is a prefix of the digits shown here (``0.443572998046875`` prints as
    ``.4435729``, ``1.0000000031710762e-20`` as ``1.0000000E-20``).
    """
    if isinstance(value, str):
        return escape_cell(value)
    if isinstance(value, tuple):
        return "-"
    return f"`{value!r}`"


def _expected_row(entry: CatalogEntry, expected: Expected) -> str:
    if expected.kind in ("rows", "table"):
        book = real64 = "-"
    else:
        book = format_expected_value(expected.book_value)
        modern = expected.real64_value if expected.real64_value is not None else expected.book_value
        real64 = format_expected_value(modern)
    description = escape_cell(expected.description) if expected.description is not None else ""
    return f"| `{entry.id}` | `{expected.name}` | {book} | {real64} | {description} |"


def render_run_commands(registry: Registry) -> str:
    """The README run commands: per program, in book order, the compiled Fortran driver fed the
    catalog's data card, the Python-port command, and a table of the catalog's expected results.
    """
    lines = [
        "Compiled Fortran drivers, from the repository root (each command feeds the catalog's "
        "data card on standard input; use `build/single/bin/` for the single-precision build):",
        "",
        "```sh",
    ]
    for entry in registry.programs:
        lines.append(f"# {entry.id}: {entry.title}")
        lines.append(printf_command(entry.data_card.text, entry.files.fortran_executable))
    lines += ["```", "", "Python port, from `python/` (the same data card is the default input):"]
    lines += ["", "```sh"]
    for entry in registry.programs:
        lines.append(f"# {entry.id}: {entry.title}")
        lines.append(f"uv run gerald-na run {entry.id}")
    lines += [
        "```",
        "",
        "Expected results from the catalog's `[[expected]]` entries. *Book* is the value "
        "transcribed from the scan, *real64* the value of the default (double-precision) build; "
        "the drivers print it truncated to the book's FORMAT, so their significant digits are the "
        "leading digits of the value shown. Rows and tables are described in the last column.",
        "",
        "| Program id | Quantity | Book | real64 | What the book prints |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        _expected_row(entry, expected) for entry in registry.programs for expected in entry.expected
    )
    return "\n".join(lines) + "\n"


def render_errata_table(entry: CatalogEntry) -> str:
    """The study-page errata table: every catalog erratum, in catalog order, verbatim."""
    if not entry.errata:
        return "No errata are recorded for this program.\n"
    lines = [
        "| Id | Kind | Original | Corrected | Note |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        "| "
        + " | ".join(
            (
                f"`{erratum.id}`",
                KIND_LABELS[erratum.kind],
                escape_cell(erratum.original),
                escape_cell(erratum.corrected),
                escape_cell(erratum.note),
            )
        )
        + " |"
        for erratum in entry.errata
    )
    return "\n".join(lines) + "\n"


def replace_block(text: str, start: str, end: str, body: str, *, where: str) -> str:
    """``text`` with the lines between the ``start`` and ``end`` marker lines replaced by ``body``.

    Raises :class:`GeneratedBlockError` when either marker is missing, repeated or out of order.
    """
    if text.count(start) != 1 or text.count(end) != 1:
        raise GeneratedBlockError(f"{where}: needs exactly one {start} and one {end} line")
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    if end in head:
        raise GeneratedBlockError(f"{where}: {end} comes before {start}")
    return f"{head}{start}\n{body}{end}{tail}"


def _block_name(start: str) -> str:
    """``RUN_COMMANDS`` for ``<!-- RUN_COMMANDS_START -->``."""
    return start.removeprefix("<!-- ").removesuffix(" -->").removesuffix("_START")


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """A file holding a generated block: its current and its expected content."""

    relative: str
    path: Path
    current: str
    expected: str
    stale_blocks: tuple[str, ...] = ()
    """Names of the out-of-date blocks (marker name without ``_START``, e.g. ``RUN_COMMANDS``)."""

    @property
    def stale(self) -> bool:
        """True when the file's generated block differs from the catalog."""
        return self.current != self.expected


def generated_files(registry: Registry) -> list[GeneratedFile]:
    """README.md (both of its blocks) and every study page, with the content they should have.

    Raises :class:`GeneratedBlockError` if a file lacks its markers, and :class:`CatalogError`
    if a file cannot be read.
    """
    targets: list[tuple[str, Path, list[tuple[str, str, str]]]] = [
        (
            README_PATH.as_posix(),
            registry.repo_root / README_PATH,
            [
                (INDEX_START, INDEX_END, render_program_index(registry)),
                (RUN_COMMANDS_START, RUN_COMMANDS_END, render_run_commands(registry)),
            ],
        )
    ]
    targets.extend(
        (
            entry.files.study_page,
            registry.resolve_path(entry, "study"),
            [(ERRATA_START, ERRATA_END, render_errata_table(entry))],
        )
        for entry in registry.programs
    )
    result: list[GeneratedFile] = []
    for relative, path, blocks in targets:
        try:
            current = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CatalogError(f"{relative}: cannot read: {exc}") from exc
        expected = current
        stale_blocks: list[str] = []
        for start, end, body in blocks:
            replaced = replace_block(expected, start, end, body, where=relative)
            if replaced != expected:
                stale_blocks.append(_block_name(start))
            expected = replaced
        result.append(GeneratedFile(relative, path, current, expected, tuple(stale_blocks)))
    return result
