"""HTML pages and HTMX fragments.

* ``GET /`` -- programs grouped by chapter.
* ``GET /programs/{id}`` -- form, engine selector, results area, tabs and practice questions.
* ``GET /programs/{id}/form`` -- the run form prefilled with the book card (reset button).
* ``POST /programs/{id}/run`` -- the results fragment (the full page when not sent by HTMX).
  422 for invalid input, 503 for an unavailable engine, 200 for every completed run (including
  the book's error paths, shown with their code).
* ``POST /programs/{id}/practice/{question_id}`` -- the feedback fragment of a practice answer.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from gerald_na.engines import CompareReport
from gerald_na.errors import EngineUnavailableError, ExpressionError, InputError
from gerald_na.registry import CatalogEntry
from gerald_na.web.forms import (
    CUSTOM_FUNCTION,
    FormValues,
    default_form_values,
    parse_run_form,
)
from gerald_na.web.markdown import render_markdown
from gerald_na.web.practice import check_practice
from gerald_na.web.presenters import compare_view, outcome_view
from gerald_na.web.services import (
    FieldErrors,
    ProgramNotFound,
    WebState,
    field_problems,
)
from gerald_na.web.templating import get_state, templates

__all__ = ["router"]

router = APIRouter(include_in_schema=False)

TABS: tuple[tuple[str, str], ...] = (
    ("scan", "Original scan"),
    ("legacy", "Legacy OCR text"),
    ("fortran", "Modern Fortran"),
    ("python", "Python"),
    ("study", "Study page"),
)


def _entry(state: WebState, program_id: str) -> CatalogEntry:
    try:
        return state.entry(program_id)
    except ProgramNotFound:
        raise HTTPException(status_code=404, detail=f"unknown program {program_id!r}") from None


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request) -> HTMLResponse:
    """Programs grouped by chapter; unconfirmed book references last."""
    state = get_state(request)
    groups = []
    for chapter, entries in state.registry.by_chapter().items():
        title = None
        if chapter is not None:
            title = next(
                (e.book_ref.title for e in entries if e.book_ref and e.book_ref.title), None
            )
        groups.append(
            {
                "chapter": chapter,
                "title": title,
                "programs": [
                    {
                        "entry": entry,
                        "scan": state.scan_available(entry),
                        "engines": state.available_engines(entry),
                    }
                    for entry in entries
                ],
            }
        )
    return templates.TemplateResponse(request, "home.html", {"groups": groups})


def _form_context(
    state: WebState, entry: CatalogEntry, values: FormValues | None = None
) -> dict[str, Any]:
    return {
        "entry": entry,
        "values": values if values is not None else default_form_values(entry),
        "engines": state.engine_statuses(entry),
        "custom_function": CUSTOM_FUNCTION,
        "count_inputs": state.count_inputs(entry),
    }


def _page_context(state: WebState, entry: CatalogEntry) -> dict[str, Any]:
    study = state.source_files(entry, "study")[0]
    return {
        **_form_context(state, entry),
        "tabs": TABS,
        "scan_available": state.scan_available(entry),
        "scan_url": state.file_url(entry, "scan"),
        "legacy_files": state.source_files(entry, "legacy"),
        "fortran_files": [
            ("Module", state.source_files(entry, "fortran_module")[0]),
            ("Driver", state.source_files(entry, "fortran_app")[0]),
        ],
        "python_file": state.source_files(entry, "python")[0],
        "study_file": study,
        "study_html": render_markdown(study.text) if study.text is not None else None,
        "results": None,
    }


@router.get("/programs/{program_id}", response_class=HTMLResponse, name="program_page")
def program_page(request: Request, program_id: str) -> HTMLResponse:
    """The program page."""
    state = get_state(request)
    entry = _entry(state, program_id)
    return templates.TemplateResponse(request, "program.html", _page_context(state, entry))


@router.get("/programs/{program_id}/form", response_class=HTMLResponse, name="program_form")
def program_form(request: Request, program_id: str) -> HTMLResponse:
    """The run form reset to the book data card."""
    state = get_state(request)
    entry = _entry(state, program_id)
    return templates.TemplateResponse(
        request, "partials/run_form.html", _form_context(state, entry)
    )


def _results(
    request: Request,
    state: WebState,
    entry: CatalogEntry,
    results: dict[str, Any],
    values: FormValues,
    status_code: int,
) -> HTMLResponse:
    if _is_htmx(request):
        return templates.TemplateResponse(
            request,
            "partials/results.html",
            {"entry": entry, "results": results},
            status_code=status_code,
        )
    context = _page_context(state, entry)
    context.update(_form_context(state, entry, values))
    context["results"] = results
    return templates.TemplateResponse(request, "program.html", context, status_code=status_code)


@router.post("/programs/{program_id}/run", response_class=HTMLResponse, name="program_run")
async def program_run(request: Request, program_id: str) -> HTMLResponse:
    """Run the submitted form and return the results fragment."""
    state = get_state(request)
    entry = _entry(state, program_id)
    form = await request.form()
    parsed = parse_run_form(entry, form)
    errors = {
        name: message
        for name, message in field_problems(entry, parsed.inputs).items()
        if name not in parsed.errors and name != "_unknown"
    }
    errors.update(parsed.errors)
    mode = parsed.engine
    base: dict[str, Any] = {
        "kind": "invalid",
        "mode": mode,
        "fields": errors,
        "message": None,
        "code": "INPUT",
        "position": None,
        "source": None,
    }
    if errors:
        base["message"] = "Please correct the highlighted values."
        return _results(request, state, entry, base, parsed.values, 422)
    try:
        run_request = state.build_request(
            entry, mode, parsed.inputs, preset=parsed.preset, expression=parsed.expression
        )
    except FieldErrors as exc:
        base.update(fields=exc.fields, message="Please correct the highlighted values.")
        return _results(request, state, entry, base, parsed.values, 422)
    except ExpressionError as exc:
        base.update(
            code=exc.code,
            message=exc.message,
            fields={"expression": exc.message},
            position=exc.position,
            source=exc.source,
        )
        return _results(request, state, entry, base, parsed.values, 422)
    except InputError as exc:
        base.update(code=exc.code, message=exc.message)
        return _results(request, state, entry, base, parsed.values, 422)
    try:
        outcome = await run_in_threadpool(state.run, entry, mode, run_request)
    except EngineUnavailableError as exc:
        unavailable: dict[str, Any] = {
            "kind": "unavailable",
            "mode": mode,
            "code": exc.code,
            "message": exc.message,
        }
        return _results(request, state, entry, unavailable, parsed.values, 503)
    results: dict[str, Any]
    if isinstance(outcome, CompareReport):
        results = {"kind": "compare", "mode": mode, "view": compare_view(entry, outcome)}
    else:
        results = {"kind": "single", "mode": mode, "view": outcome_view(entry, outcome)}
    return _results(request, state, entry, results, parsed.values, 200)


@router.post(
    "/programs/{program_id}/practice/{question_id}",
    response_class=HTMLResponse,
    name="practice_check",
)
async def practice_check(request: Request, program_id: str, question_id: str) -> HTMLResponse:
    """Check a practice answer; 422 when the answer cannot be read."""
    state = get_state(request)
    entry = _entry(state, program_id)
    question = next((q for q in entry.practice if q.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail=f"unknown practice question {question_id!r}")
    form = await request.form()
    raw = form.get("answer")
    answer = raw if isinstance(raw, str) else ""
    check = await run_in_threadpool(check_practice, state, entry, question, answer)
    return templates.TemplateResponse(
        request,
        "partials/practice_feedback.html",
        {"entry": entry, "check": check},
        status_code=200 if check.readable else 422,
    )
