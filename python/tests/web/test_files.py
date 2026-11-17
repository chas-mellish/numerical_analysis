"""``GET /files/{program_id}/{kind}``: whitelist, content types and traversal attempts."""

import pytest
from fastapi.testclient import TestClient

from gerald_na.registry import get_registry
from tests.web.conftest import BISECTION


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


def test_missing_scan_and_missing_files(lagrange_client: TestClient) -> None:
    assert lagrange_client.get("/files/lagrange_interpolation/scan").status_code == 404
    assert lagrange_client.get("/files/lagrange_interpolation/fortran_module").status_code == 404
    response = lagrange_client.get("/files/lagrange_interpolation/legacy")
    assert response.status_code == 200
    assert "PROGRAM LAGRAN" in response.text
