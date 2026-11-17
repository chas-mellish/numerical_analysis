"""``GET /healthz``."""

import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gerald_na import __version__
from gerald_na.settings import Settings
from gerald_na.web.app import create_app


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "settings.toml").write_text("", encoding="utf-8")
    return Settings.model_validate({"repo_root": tmp_path, **overrides})


def add_executable(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_healthz_without_fortran_binaries(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = TestClient(create_app(make_settings(tmp_path)))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": __version__,
        "engines": {"python": True, "fortran": False},
    }


def test_healthz_reports_fortran_when_binaries_exist(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    add_executable(tmp_path / "build" / "bin", "ch01_p01_bisection")
    client = TestClient(create_app(make_settings(tmp_path)))
    assert client.get("/healthz").json()["engines"] == {"python": True, "fortran": True}


def test_healthz_respects_disabled_engines(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    add_executable(tmp_path / "build" / "bin", "ch01_p01_bisection")
    settings = make_settings(tmp_path, engines_enabled=["python"])
    client = TestClient(create_app(settings))
    assert client.get("/healthz").json()["engines"] == {"python": True, "fortran": False}


def test_create_app_defaults_to_repository_settings(clean_env: pytest.MonkeyPatch) -> None:
    app = create_app()
    assert isinstance(app.state.settings, Settings)
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
