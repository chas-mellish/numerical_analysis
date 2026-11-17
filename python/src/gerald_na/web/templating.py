"""Jinja2 environment of the web UI (autoescaping always on) and request helpers."""

import math
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from gerald_na import __version__
from gerald_na.expr import CONSTANTS, FUNCTIONS
from gerald_na.web.forms import format_number
from gerald_na.web.services import WebState, describe_book_ref

__all__ = ["STATIC_DIR", "TEMPLATE_DIR", "get_state", "templates"]

WEB_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def _sci(value: object, digits: int = 3) -> str:
    """Scientific notation for difference summaries (``-`` for missing values)."""
    if value is None or isinstance(value, bool) or not isinstance(value, int | float):
        return "-"
    if not math.isfinite(float(value)):
        return str(value)
    return f"{float(value):.{digits}e}"


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,  # every template, whatever its extension
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["sci"] = _sci
    env.filters["number"] = format_number
    env.globals["book_ref_text"] = describe_book_ref
    env.globals["app_version"] = __version__
    env.globals["expr_functions"] = ", ".join(sorted(FUNCTIONS))
    env.globals["expr_constants"] = ", ".join(sorted(CONSTANTS))
    return env


templates = Jinja2Templates(env=_environment())


def get_state(request: Request) -> WebState:
    """The :class:`WebState` of the application serving ``request``."""
    state: WebState = request.app.state.web
    return state
