"""The Python engine: runs the standard-library algorithms of :mod:`gerald_na.algorithms`.

Functions come from the catalog presets (the same expression text the Fortran ``select case``
implements, compiled by :mod:`gerald_na.expr`) or from a learner's custom expression, which only
this engine accepts (DD3).
"""

import time
from functools import lru_cache
from typing import Any, ClassVar

from gerald_na.engines.adapters import get_adapter
from gerald_na.engines.base import Engine, RunOutcome, RunRequest, validate_request
from gerald_na.engines.programs import Function
from gerald_na.errors import EngineError, ExpressionError, GeraldNAError, InputError
from gerald_na.expr import CompiledExpr, compile_expr
from gerald_na.registry import CatalogEntry

__all__ = ["PythonEngine", "compile_function"]


@lru_cache(maxsize=256)
def _compile(source: str) -> CompiledExpr:
    return compile_expr(source)


def compile_function(
    entry: CatalogEntry, preset_id: int | None, expression: str | None
) -> Function | None:
    """The callable for a request: the catalog preset, the custom expression, or ``None``.

    Raises :class:`ExpressionError` for an invalid custom expression.
    """
    if not entry.function.takes_function:
        return None
    if expression is not None:
        return _compile(expression)
    if preset_id is None:
        raise InputError(f"{entry.id}: no preset selected")
    return _compile(entry.function.preset(preset_id).expr)


def _as_input_error(exc: ExpressionError) -> InputError:
    """A preset that cannot be evaluated at the given inputs is an input problem (code INPUT).

    The Fortran drivers report the same situation (for example F(X) overflowing) as
    ``ERROR,code=INPUT``; ``EXPRESSION`` stays reserved for the learner's own function.
    """
    return InputError(exc.message, steps=exc.steps, book_output=exc.book_output)


class PythonEngine(Engine):
    """Run a catalog program with its pure-Python algorithm."""

    name: ClassVar[str] = "python"

    def run(self, entry: CatalogEntry, request: RunRequest) -> RunOutcome:
        inputs, preset_id = validate_request(entry, request)
        adapter = get_adapter(entry.id)
        function = compile_function(entry, preset_id, request.expression)
        start = time.perf_counter()
        result: Any = None
        error: GeraldNAError | None = None
        try:
            result = adapter.run_python(entry, inputs, function)
        except ExpressionError as exc:
            error = exc if request.expression is not None else _as_input_error(exc)
        except GeraldNAError as exc:
            error = exc
        except Exception as exc:  # an algorithm bug must not take the web worker down
            error = EngineError(f"python engine failed: {type(exc).__name__}: {exc}")
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if error is not None:
            return RunOutcome(
                engine=self.name,
                program_id=entry.id,
                inputs=inputs,
                preset=preset_id,
                expression=request.expression,
                error=error,
                book_text=error.book_output or "",
                elapsed_ms=elapsed_ms,
            )
        adapter.check_result_type(result)
        verbose = adapter.verbose_text(entry, inputs, result) if request.verbose else ""
        return RunOutcome(
            engine=self.name,
            program_id=entry.id,
            inputs=inputs,
            preset=preset_id,
            expression=request.expression,
            result=result,
            book_text=result.book_text(),
            elapsed_ms=elapsed_ms,
            verbose_text=verbose,
        )
