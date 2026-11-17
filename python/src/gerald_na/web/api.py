"""JSON API: ``/api/programs``, ``/api/programs/{id}`` and ``POST /api/programs/{id}/run``.

Error scheme (also in ``docs/architecture.md``): a request problem is a 4xx/503 response whose
body is ``{"error": {"code": ..., "message": ..., ...}}``; a run that executed is 200 with
``"ok"`` telling whether the program produced a result or stopped on one of its typed error
paths (``status``/``error.code`` = ``BRACKET``, ``NON_CONVERGENT``, ``FORTRAN_RUN``, ...).

=====  ==========================  =========================================================
HTTP   ``error.code``              when
=====  ==========================  =========================================================
404    ``NOT_FOUND``               unknown program id (or unknown ``/api`` path)
422    ``VALIDATION``              body does not match the schema (unknown engine, wrong JSON
                                   types, unknown keys); ``details`` lists the problems
422    ``INPUT``                   input values invalid; ``fields`` maps input -> message;
                                   also unknown preset, preset with expression
422    ``EXPRESSION``              custom expression does not parse/validate; ``position``
                                   is the 1-based column
422    ``CUSTOM_FUNCTION_ENGINE``  custom expression with the fortran or compare engine
503    ``ENGINE_UNAVAILABLE``      engine disabled, Fortran driver not built, no adapter
200    --                          the run completed: ``ok`` true or false
=====  ==========================  =========================================================
"""

from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from gerald_na.engines import CompareReport
from gerald_na.errors import EngineUnavailableError, ExpressionError, InputError
from gerald_na.web.charts import json_safe
from gerald_na.web.services import (
    FieldErrors,
    ProgramNotFound,
    entry_detail,
    entry_summary,
)
from gerald_na.web.templating import get_state

__all__ = ["ApiError", "RunBody", "error_body", "router"]

router = APIRouter(prefix="/api", tags=["api"])


class ApiError(Exception):
    """An API request problem, rendered as ``{"error": {...}}`` with ``status_code``."""

    def __init__(self, status_code: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """The JSON body of an API error."""
    return {"error": {"code": code, "message": message, **json_safe(extra)}}


class RunBody(BaseModel):
    """``POST /api/programs/{id}/run`` request body.

    Inputs left out take the book data card's value. ``preset`` and ``expression`` are
    mutually exclusive; ``expression`` needs ``engine = "python"``.
    """

    model_config = ConfigDict(extra="forbid")

    engine: Literal["python", "fortran", "compare"] = "python"
    inputs: dict[str, Any] = Field(default_factory=dict)
    preset: int | None = Field(default=None, ge=1)
    expression: str | None = Field(default=None, min_length=1)
    verbose: bool = False


def _entry_or_404(request: Request, program_id: str) -> Any:
    try:
        return get_state(request).entry(program_id)
    except ProgramNotFound as exc:
        raise ApiError(404, ProgramNotFound.code, str(exc)) from None


@router.get("/programs")
def list_programs(request: Request) -> list[dict[str, Any]]:
    """Every catalog program: id, title, book reference, inputs, presets, available engines."""
    state = get_state(request)
    return [json_safe(entry_summary(state, entry)) for entry in state.registry.programs]


@router.get("/programs/{program_id}")
def get_program(request: Request, program_id: str) -> dict[str, Any]:
    """The full catalog entry; file paths are replaced by ``/files/...`` URLs."""
    entry = _entry_or_404(request, program_id)
    detail: dict[str, Any] = json_safe(entry_detail(get_state(request), entry))
    return detail


@router.post("/programs/{program_id}/run")
async def run_program(request: Request, program_id: str, body: RunBody) -> JSONResponse:
    """Run a program on ``python``, ``fortran`` or ``compare`` (see the module error scheme)."""
    state = get_state(request)
    entry = _entry_or_404(request, program_id)
    inputs: dict[str, Any] = dict(entry.defaults())
    inputs.update(body.inputs)
    try:
        run_request = state.build_request(
            entry,
            body.engine,
            inputs,
            preset=body.preset,
            expression=body.expression,
            verbose=body.verbose,
        )
    except FieldErrors as exc:
        raise ApiError(422, exc.code, exc.message, fields=exc.fields) from None
    except ExpressionError as exc:
        raise ApiError(422, exc.code, exc.message, position=exc.position) from None
    except InputError as exc:
        raise ApiError(422, exc.code, exc.message) from None
    try:
        outcome = await run_in_threadpool(state.run, entry, body.engine, run_request)
    except EngineUnavailableError as exc:
        raise ApiError(503, exc.code, exc.message) from None
    if isinstance(outcome, CompareReport):
        data = {
            "mode": "compare",
            "ok": outcome.left.ok and outcome.right.ok,
            **outcome.to_dict(),
        }
    else:
        data = {"mode": body.engine, "ok": outcome.ok, **outcome.to_dict()}
    return JSONResponse(json_safe(data))
