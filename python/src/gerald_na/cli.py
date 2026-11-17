"""``gerald-na`` command-line interface."""

import argparse
import sys
from collections.abc import Sequence

from gerald_na import __version__
from gerald_na.registry import CatalogEntry, CatalogError, Registry
from gerald_na.settings import get_settings

__all__ = ["build_parser", "main"]

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
