"""``gerald-na`` command-line interface."""

import argparse
from collections.abc import Sequence

from gerald_na import __version__
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
    return parser


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
