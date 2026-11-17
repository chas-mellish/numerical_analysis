"""Helpers shared by several engine adapters.

* :func:`real_input` / :func:`int_input`: typed access to validated inputs.
* :func:`is_book_function` / :func:`book_seed_for`: recognize the book's own integrand. The
  Simpson (``ch03_p01``) and Romberg (``ch03_p02``) listings seed their sums with the literal
  ``1.0``, the limit of SIN(X)/X at X = 0, because the integrand cannot be evaluated there. The
  Fortran preset (``functions_mod: f_sinc``) returns exactly 1 at 0, but the catalog expression
  ``SIN(X)/X`` compiled by :mod:`gerald_na.expr` divides by zero. So when the function is the
  book's integrand -- the default preset, or a learner expression that normalizes to the same
  text, such as ``SINF(X) / X`` -- the adapter passes the book's seed as ``f0``; every other
  function supplies its own ordinate ``f(0)`` (a learner function undefined at 0 is reported as
  an expression error at X = 0).
* :class:`BookSeededIntegrandAdapter`: the base class of those two adapters, which also reports
  the seed through :meth:`~gerald_na.engines.programs.ProgramAdapter.substituted_ordinates` so
  the web chart draws F(0) the way the program uses it.
* :func:`trace_real` / :func:`trace_logical` / :func:`verbose_header`: the pieces of the drivers'
  ``--verbose`` extras (``book_format_mod`` and the common first records of ``write_verbose``),
  so the adapters' ``verbose_text`` reproduces them character for character (real64 build).
"""

from collections.abc import Mapping
from functools import lru_cache
from typing import ClassVar

from gerald_na.algorithms import format_es
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.expr import CompiledExpr, compile_expr
from gerald_na.registry import CatalogEntry
from gerald_na.registry.models import InputValue

__all__ = [
    "BookSeededIntegrandAdapter",
    "book_integrand",
    "book_seed_for",
    "int_input",
    "is_book_function",
    "real_input",
    "trace_logical",
    "trace_real",
    "verbose_header",
]


def real_input(inputs: Mapping[str, InputValue], name: str) -> float:
    """Input ``name`` as a float (``TypeError`` if it is not a number)."""
    value = inputs[name]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"input {name!r} must be a number, got {value!r}")
    return float(value)


def int_input(inputs: Mapping[str, InputValue], name: str) -> int:
    """Input ``name`` as an int (``TypeError`` if it is not an integer)."""
    value = inputs[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"input {name!r} must be an integer, got {value!r}")
    return value


def trace_real(x: float) -> str:
    """``book_format_mod: trace_real``: ``ES25.17E3`` with the leading blanks removed."""
    return format_es(x, 25, 17, 3).lstrip()


def trace_logical(value: bool) -> str:
    """``book_format_mod: trace_logical``: ``T`` or ``F``."""
    return "T" if value else "F"


def verbose_header(
    entry: CatalogEntry,
    preset: int | None,
    function: Function | None,
    *,
    suffix: str = "",
) -> list[str]:
    """The first records of a driver's ``write_verbose`` (carriage-control column included).

    The title, then for a program that takes a function its line ``PRESET n: F(X) = EXPR``
    (the catalog expression in upper case, the text ``functions_mod`` prints; ``suffix`` is
    appended, such as Romberg's `` ON [0, B]``), then the working precision (the Python engine
    computes in real64, like the default build). A learner's expression, which only the Python
    engine runs, is shown as ``EXPRESSION: F(X) = <text as entered>``.
    """
    records = [" VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)"]
    if preset is not None:
        expr = entry.function.preset(preset).expr.upper()
        records.append(f" PRESET {preset}: F(X) = {expr}{suffix}")
    elif isinstance(function, CompiledExpr):
        records.append(f" EXPRESSION: F(X) = {function.source.strip()}{suffix}")
    records.append(" WORKING PRECISION: REAL64")
    return records


@lru_cache(maxsize=16)
def _normalized(source: str) -> str:
    return compile_expr(source).normalized


def is_book_function(entry: CatalogEntry, function: Function) -> bool:
    """True when ``function`` is the entry's default (book) preset, compared as normalized text.

    Only functions compiled by :mod:`gerald_na.expr` can be recognized; any other callable is
    not the book's function.
    """
    if not isinstance(function, CompiledExpr) or entry.function.default_preset is None:
        return False
    book = entry.function.preset(entry.function.default_preset).expr
    return function.normalized == _normalized(book)


def book_seed_for(entry: CatalogEntry, function: Function, seed: float) -> float | None:
    """``seed`` (the book's literal F(0)) when ``function`` is the book's integrand, else ``None``.

    The result is meant for the algorithms' optional ``f0`` argument: ``None`` means "evaluate
    ``f(0)``".
    """
    return seed if is_book_function(entry, function) else None


def book_integrand(entry: CatalogEntry, function: Function, seed: float) -> Function:
    """The function the algorithm calls: the book's integrand gives ``seed`` at X = 0.

    Any other function is returned unchanged.
    """
    if book_seed_for(entry, function, seed) is None:
        return function

    def seeded(x: float) -> float:
        return seed if x == 0.0 else function(x)

    return seeded


class BookSeededIntegrandAdapter(ProgramAdapter):
    """Adapter base for integration programs whose sum starts with the book's F(0) literal."""

    book_seed: ClassVar[float]
    """The literal the listing uses for F(0) of its own integrand."""

    def seed(self, entry: CatalogEntry, function: Function) -> float | None:
        """The ``f0`` to pass to the algorithm (see :func:`book_seed_for`)."""
        return book_seed_for(entry, function, self.book_seed)

    def integrand(self, entry: CatalogEntry, function: Function) -> Function:
        """The function to integrate (see :func:`book_integrand`)."""
        return book_integrand(entry, function, self.book_seed)

    def substituted_ordinates(self, entry: CatalogEntry, function: Function) -> dict[float, float]:
        seed = self.seed(entry, function)
        return {} if seed is None else {0.0: seed}
