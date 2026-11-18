"""``GET /files/{program_id}/{kind}``: catalog files through a whitelist (DD5).

Only the kinds in :data:`~gerald_na.web.services.SERVED_FILE_KINDS` are served, and only the
path the catalog names for that program (``Registry.resolve_path``, which also refuses paths
escaping the repository root). No part of the URL is used as a path. Anything else is a 404.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from gerald_na.registry import CatalogPathError
from gerald_na.web.services import SERVED_FILE_KINDS, ProgramNotFound, is_pdf_path
from gerald_na.web.templating import get_state

__all__ = ["router"]

router = APIRouter(tags=["files"])

TEXT_PLAIN = "text/plain; charset=utf-8"


@router.get("/files/{program_id}/{kind}", name="program_file")
def program_file(
    request: Request,
    program_id: str,
    kind: str,
    index: str = "0",
) -> FileResponse:
    """Serve one catalog file: the PDF scan as ``application/pdf``, sources as text.

    ``index`` selects one of several legacy files; a malformed index is a 404 like every other
    request outside the whitelist.
    """
    state = get_state(request)
    if kind not in SERVED_FILE_KINDS or not (index.isascii() and index.isdigit()) or len(index) > 2:
        raise HTTPException(status_code=404, detail="file not found")
    try:
        entry = state.entry(program_id)
        path = state.resolve_file(entry, kind, int(index))
    except ProgramNotFound, CatalogPathError:
        raise HTTPException(status_code=404, detail="file not found") from None
    media_type = "application/pdf" if kind == "scan" or is_pdf_path(path) else TEXT_PLAIN
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="inline",
    )
