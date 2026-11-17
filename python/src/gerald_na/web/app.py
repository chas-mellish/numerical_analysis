"""FastAPI application factory for the web learning tool."""

from typing import Any

from fastapi import FastAPI, Request

from gerald_na import __version__
from gerald_na.settings import Settings, get_settings

__all__ = ["create_app"]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the web application. ``settings`` defaults to :func:`get_settings`."""
    app = FastAPI(
        title="gerald-na",
        version=__version__,
        description="Numerical methods from C. F. Gerald, Applied Numerical Analysis.",
    )
    app.state.settings = settings if settings is not None else get_settings()

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

    return app
