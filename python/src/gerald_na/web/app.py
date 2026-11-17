"""FastAPI application factory for the web learning tool.

Routes: ``/healthz``; the HTML pages and HTMX fragments (:mod:`gerald_na.web.pages`); the JSON
API under ``/api`` (:mod:`gerald_na.web.api`); the whitelisted file route ``/files/{id}/{kind}``
(:mod:`gerald_na.web.files`); vendored static assets under ``/static`` (HTMX and Plotly.js are
served locally, so the app works offline).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from gerald_na import __version__
from gerald_na.registry import Registry
from gerald_na.settings import Settings, get_settings
from gerald_na.web import api, files, pages
from gerald_na.web.api import ApiError, error_body
from gerald_na.web.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from gerald_na.web.services import WebState
from gerald_na.web.templating import STATIC_DIR, templates

__all__ = ["create_app"]

_HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "TOO_LARGE"}


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/") or request.url.path == "/api"


def create_app(settings: Settings | None = None, *, registry: Registry | None = None) -> FastAPI:
    """Create the web application.

    ``settings`` defaults to :func:`get_settings`; ``registry`` defaults to the catalog under
    ``settings.repo_root``, loaded on first use (so ``/healthz`` works without a catalog).
    """
    app = FastAPI(
        title="gerald-na",
        version=__version__,
        description="Numerical methods from C. F. Gerald, Applied Numerical Analysis.",
    )
    current_settings = settings if settings is not None else get_settings()
    app.state.settings = current_settings
    app.state.web = WebState(current_settings, registry)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)

    @app.get("/healthz", tags=["meta"])
    def healthz(request: Request) -> dict[str, Any]:
        """Liveness check plus which engines can currently run."""
        current: Settings = request.app.state.settings
        enabled = current.engines_enabled
        return {
            "status": "ok",
            "version": __version__,
            "engines": {
                "python": "python" in enabled,
                "fortran": "fortran" in enabled and bool(current.fortran_executables()),
            },
        }

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> Response:
        return JSONResponse(
            error_body(exc.code, exc.message, **exc.extra), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        details = jsonable_encoder(exc.errors(), exclude={"input", "ctx", "url"})
        first = details[0]["msg"] if details else "invalid request"
        return JSONResponse(
            error_body("VALIDATION", f"invalid request: {first}", details=details),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = str(exc.detail)
        if _is_api(request):
            return JSONResponse(error_body(code, message), status_code=exc.status_code)
        accepts_html = "text/html" in request.headers.get("accept", "")
        if accepts_html and not request.url.path.startswith("/files/"):
            response: HTMLResponse = templates.TemplateResponse(
                request,
                "error.html",
                {"status_code": exc.status_code, "message": message},
                status_code=exc.status_code,
            )
            return response
        return PlainTextResponse(message, status_code=exc.status_code)

    app.include_router(pages.router)
    app.include_router(api.router)
    app.include_router(files.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
