"""``gerald-na`` command-line interface."""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from gerald_na import __version__
from gerald_na.errors import EngineUnavailableError, InputError
from gerald_na.registry import CatalogEntry, CatalogError, CatalogInput, Registry
from gerald_na.registry.models import parse_data_card_token
from gerald_na.settings import get_settings

if TYPE_CHECKING:
    from gerald_na.engines import CompareReport, RunOutcome

__all__ = ["build_parser", "main", "parse_input_text"]

APP_FACTORY = "gerald_na.web.app:create_app"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``gerald-na``."""
    parser = argparse.ArgumentParser(
        prog="gerald-na",
        description=(
            "Numerical methods from C. F. Gerald, Applied Numerical Analysis: "
            "Python and Fortran engines plus a web learning tool."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    serve = commands.add_parser(
        "serve",
        help="run the web learning tool with Uvicorn",
        description="Serve the web learning tool. Defaults come from config/settings.toml.",
    )
    serve.add_argument("--host", help="bind address (default: settings host)")
    serve.add_argument("--port", type=int, help="port (default: settings port)")
    serve.add_argument(
        "--reload", action="store_true", help="restart the server when source files change"
    )
    serve.set_defaults(handler=_serve)

    run = commands.add_parser(
        "run",
        help="run a catalog program on an engine and print the book text",
        description=(
            "Run a catalog program with the book data card, optionally overriding inputs, and "
            "print its line-printer text (or JSON). Exit status: 0 success, 1 the program "
            "stopped on an error path (or an engine failed), 2 invalid request."
        ),
    )
    run.add_argument("program_id", help="catalog id, for example ch01_p01")
    run.add_argument(
        "--engine",
        choices=("python", "fortran", "compare"),
        default="python",
        help="engine to use; compare runs Python and Fortran and diffs the traces",
    )
    run.add_argument("--preset", type=int, help="catalog function preset (default: the book's)")
    run.add_argument("--expr", dest="expression", help="custom function of x (Python engine only)")
    run.add_argument(
        "--input",
        dest="inputs",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override one data-card input; lists as comma-separated numbers (repeatable)",
    )
    run.add_argument("--verbose", action="store_true", help="add the engine's extras")
    run.add_argument(
        "--trace-json", action="store_true", help="print the full outcome as JSON instead"
    )
    run.add_argument(
        "--bin-dir",
        help="Fortran driver directory (default: settings fortran_bin_dir), "
        "for example build/single/bin",
    )
    run.set_defaults(handler=_run)

    catalog = commands.add_parser(
        "catalog",
        help="inspect and validate the program catalog",
        description="Inspect and validate catalog/*.toml (see docs/architecture.md).",
    )
    catalog_commands = catalog.add_subparsers(dest="catalog_command", metavar="ACTION")
    catalog.set_defaults(handler=lambda _args: _print_help(catalog))
    catalog_list = catalog_commands.add_parser("list", help="list the catalogued programs")
    catalog_list.set_defaults(handler=_catalog_list)
    catalog_check = catalog_commands.add_parser(
        "check",
        help="verify every catalog entry and its referenced files (exit 1 on problems)",
    )
    catalog_check.set_defaults(handler=_catalog_check)
    catalog_index = catalog_commands.add_parser(
        "index",
        help="print the README generated blocks; --check/--write the generated Markdown blocks",
        description=(
            "Render the Markdown generated from the catalog: the program index between the "
            "PROGRAM_INDEX markers and the per-program run commands and expected results between "
            "the RUN_COMMANDS markers of README.md, and the errata table between the "
            "ERRATA_TABLE markers of every study page. Without options both README blocks are "
            "printed (the index, a blank line, then the run commands). --check exits with "
            "status 1 when a block is out of date or its markers are missing; --write rewrites "
            "the stale blocks (make readme-index)."
        ),
    )
    mode = catalog_index.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="exit 1 if README.md or a study page is stale"
    )
    mode.add_argument("--write", action="store_true", help="update README.md and the study pages")
    catalog_index.set_defaults(handler=_catalog_index)
    return parser


def _print_help(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    return 0


def _book_reference(entry: CatalogEntry) -> str:
    ref = entry.book_ref
    if not entry.book_ref_confirmed or ref is None:
        return "unconfirmed"
    return f"ch {ref.chapter} prog {ref.program} p.{ref.page}"


def _catalog_list(_args: argparse.Namespace) -> int:
    try:
        registry = Registry.load(get_settings().repo_root)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for entry in registry.programs:
        scan = "scan" if entry.files.scan_pdf is not None else "no scan"
        print(f"{entry.id:<24} {_book_reference(entry):<22} {scan:<8} {entry.title}")
    print(f"{len(registry)} program(s)")
    return 0


def _catalog_check(_args: argparse.Namespace) -> int:
    try:
        registry = Registry.load(get_settings().repo_root)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    problems = registry.check_integrity()
    if problems:
        print(f"{len(problems)} catalog problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"catalog OK: {len(registry)} program(s), every referenced file present")
    return 0


def _catalog_index(args: argparse.Namespace) -> int:
    from gerald_na.registry.generated import (
        generated_files,
        render_program_index,
    )

    try:
        registry = Registry.load(get_settings().repo_root)
        if not (args.check or args.write):
            sys.stdout.write(render_program_index(registry))
            return 0
        files = generated_files(registry)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    stale = [item for item in files if item.stale]
    if args.check:
        if stale:
            print(
                "out of date (run `make readme-index`): "
                + ", ".join(f"{item.relative} ({', '.join(item.stale_blocks)})" for item in stale),
                file=sys.stderr,
            )
            return 1
        print(f"generated Markdown up to date in {len(files)} file(s)")
        return 0
    for item in stale:
        item.path.write_text(item.expected, encoding="utf-8")
        print(f"updated {item.relative}")
    if not stale:
        print(f"generated Markdown already up to date in {len(files)} file(s)")
    return 0


_LIST_SEPARATOR = re.compile(r"[\s,;]+")


def parse_input_text(item: CatalogInput, text: str) -> object:
    """Parse the text of a ``--input NAME=VALUE`` option for ``item`` (numbers only).

    Reals accept Python and Fortran spellings (``1e-5``, ``1.E-5``, ``1.D-5``); lists are
    comma- or blank-separated, and a ``point_list`` is the flat sequence ``x1,y1,x2,y2,...``.
    Raises :class:`InputError`; range checks happen in the engines.
    """
    tokens = [token for token in _LIST_SEPARATOR.split(text.strip()) if token]
    integer = item.type == "int"
    try:
        numbers = [parse_data_card_token(token, integer=integer) for token in tokens]
    except ValueError as exc:
        raise InputError(f"input {item.name!r}: {exc}") from None
    if item.type in ("real", "int"):
        if len(numbers) != 1:
            raise InputError(f"input {item.name!r} takes one number, got {text!r}")
        return numbers[0]
    if item.type == "point_list":
        if len(numbers) % 2:
            raise InputError(f"input {item.name!r} needs x,y pairs, got {len(numbers)} numbers")
        return [numbers[i : i + 2] for i in range(0, len(numbers), 2)]
    return numbers


def _parse_overrides(entry: CatalogEntry, items: Sequence[str]) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for item in items:
        name, eq, text = item.partition("=")
        if not eq:
            raise InputError(f"--input needs NAME=VALUE, got {item!r}")
        try:
            spec = entry.input(name.strip())
        except KeyError:
            raise InputError(
                f"unknown input {name!r} for {entry.id} (inputs: {', '.join(entry.input_names)})"
            ) from None
        overrides[spec.name] = parse_input_text(spec, text)
    return overrides


def _print_outcome_text(outcome: RunOutcome) -> None:
    sys.stdout.write(outcome.book_text)
    if outcome.verbose_text:
        sys.stdout.write("\n" + outcome.verbose_text)
    if outcome.error is not None:
        print(f"{outcome.engine}: {outcome.error.code}: {outcome.error.message}", file=sys.stderr)


def _run(args: argparse.Namespace) -> int:
    from gerald_na.engines import FortranRunner, RunRequest, compare, run_program

    settings = get_settings()
    try:
        registry = Registry.load(settings.repo_root)
        try:
            entry = registry.get(args.program_id)
        except KeyError:
            raise InputError(
                f"unknown program {args.program_id!r} "
                f"(known: {', '.join(e.id for e in registry.programs)})"
            ) from None
        request = RunRequest.for_entry(
            entry,
            _parse_overrides(entry, args.inputs),
            preset=args.preset,
            expression=args.expression,
            verbose=args.verbose,
        )
        fortran = FortranRunner(
            settings, bin_dir=Path(args.bin_dir) if args.bin_dir else None, registry=registry
        )
        if args.engine == "compare":
            report = compare(entry, request, ("python", fortran), registry=registry)
            if args.trace_json:
                print(json.dumps(report.to_dict(), indent=2))
            else:
                _print_compare(report)
            return 0 if report.left.ok and report.right.ok else 1
        engine = fortran if args.engine == "fortran" else "python"
        outcome = run_program(entry, request, engine, registry=registry, settings=settings)
    except (InputError, EngineUnavailableError, CatalogError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:  # RunRequest validation (for example --preset with --expr)
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.trace_json:
        print(json.dumps(outcome.to_dict(), indent=2))
        if outcome.error is not None:
            print(f"{outcome.error.code}: {outcome.error.message}", file=sys.stderr)
    else:
        _print_outcome_text(outcome)
    return 0 if outcome.ok else 1


def _print_compare(report: CompareReport) -> None:
    for outcome in (report.left, report.right):
        print(f"=== {outcome.engine}: {outcome.status} ({outcome.elapsed_ms:.1f} ms)")
        _print_outcome_text(outcome)
    print("=== differences")
    print(f"same outcome: {report.same_status}  same iterations: {report.same_iterations}")
    for column in report.columns:
        first = "-" if column.first_differing_row is None else column.first_differing_row + 1
        print(
            f"{column.label:>8}: max abs {column.max_abs_diff:.3e}  "
            f"max rel {column.max_rel_diff:.3e}  first differing row {first}"
        )
    for note in report.notes:
        print(note)


def _serve(args: argparse.Namespace) -> int:
    import uvicorn  # imported lazily: only `serve` needs the server

    settings = get_settings()
    host: str = args.host if args.host is not None else settings.host
    port: int = args.port if args.port is not None else settings.port
    uvicorn.run(APP_FACTORY, factory=True, host=host, port=port, reload=args.reload)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``gerald-na`` console script; returns the process exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    status: int = args.handler(args)
    return status


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
