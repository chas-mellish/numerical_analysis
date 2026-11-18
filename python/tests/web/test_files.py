"""``GET /files/{program_id}/{kind}``: whitelist, content types and traversal attempts."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gerald_na.registry import Registry, get_registry
from gerald_na.web.app import create_app
from tests.web.conftest import BISECTION, LAGRANGE_TOML, make_settings


def test_scan_is_pdf(client: TestClient) -> None:
    response = client.get(f"/files/{BISECTION}/scan")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("kind", "needle"),
    [
        ("legacy", "program"),
        ("fortran_module", "module bisection_mod"),
        ("fortran_app", "ch01_p01"),
        ("python", "def bisection("),
        ("study", "# Chapter 1, Program 1"),
    ],
)
def test_text_kinds(client: TestClient, kind: str, needle: str) -> None:
    response = client.get(f"/files/{BISECTION}/{kind}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert needle.lower() in response.text.lower()


def test_served_file_matches_catalog(client: TestClient) -> None:
    registry = get_registry()
    path = registry.resolve_path(BISECTION, "fortran_app")
    assert client.get(f"/files/{BISECTION}/fortran_app").content == path.read_bytes()


@pytest.mark.parametrize(
    "url",
    [
        f"/files/{BISECTION}/catalog",  # registry kind, but not served
        f"/files/{BISECTION}/passwd",
        f"/files/{BISECTION}/..%2F..%2Fetc%2Fpasswd",
        f"/files/{BISECTION}/%2e%2e",
        f"/files/{BISECTION}/scan%2F..%2F..%2Fpyproject.toml",
        "/files/..%2F..%2Fetc/scan",
        "/files/%2e%2e/legacy",
        "/files/nope/scan",
        f"/files/{BISECTION}/legacy?index=1",
        f"/files/{BISECTION}/legacy?index=-1",
        f"/files/{BISECTION}/legacy?index=abc",
        f"/files/{BISECTION}/scan?index=1",
        f"/files/{BISECTION}/../../pyproject.toml",
        f"/files/{BISECTION}",
        "/files/../config/settings.toml",
    ],
)
def test_everything_else_is_404(client: TestClient, url: str) -> None:
    response = client.get(url)
    assert response.status_code == 404, url


def test_missing_scan_and_missing_files(synthetic_client: TestClient) -> None:
    assert synthetic_client.get("/files/synthetic_points/scan").status_code == 404
    assert synthetic_client.get("/files/synthetic_points/fortran_module").status_code == 404
    response = synthetic_client.get("/files/synthetic_points/legacy")
    assert response.status_code == 200
    assert "PROGRAM LAGRAN" in response.text


def test_legacy_pdf_is_served_as_pdf_and_linked_not_shown(
    clean_env: pytest.MonkeyPatch, synthetic_repo: Path
) -> None:
    """A legacy file that is a scanned page (no OCR text) is linked, not dumped as text."""
    catalog = synthetic_repo / "catalog" / "synthetic_points.toml"
    catalog.write_text(
        LAGRANGE_TOML.replace(
            'legacy = ["legacy_code/fortran/chapter_2/lagrange.f90"]',
            'legacy = ["legacy_code/fortran/chapter_2/lagrange.f90",'
            ' "legacy_code/fortran/chapter_2/page.PDF"]',
        ),
        encoding="utf-8",
    )
    (synthetic_repo / "legacy_code" / "fortran" / "chapter_2" / "page.PDF").write_bytes(
        b"%PDF-1.4\n\xff\xfe binary\n"
    )
    client = TestClient(
        create_app(make_settings(synthetic_repo), registry=Registry.load(synthetic_repo))
    )
    response = client.get("/files/synthetic_points/legacy?index=1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    text = client.get("/files/synthetic_points/legacy").headers["content-type"]
    assert text.startswith("text/plain")
    html = client.get("/programs/synthetic_points").text
    assert 'data-testid="legacy-source-0"' in html
    assert 'data-testid="legacy-source-1-pdf"' in html
    assert 'data-testid="legacy-source-1"' not in html
    assert 'href="/files/synthetic_points/legacy?index=1"' in html
    assert "binary" not in html
