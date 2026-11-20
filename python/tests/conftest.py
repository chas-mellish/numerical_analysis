"""Shared fixtures for the gerald_na test suite.

Tests marked ``@pytest.mark.fortran`` need the compiled Fortran drivers. They are skipped with an
explicit reason when ``fortran_bin_dir`` (from settings) holds no executables; use the
``fortran_executable`` fixture to require one specific driver.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from gerald_na.settings import ENV_PREFIX, Settings, find_repo_root, get_settings

FORTRAN_SKIP_REASON = "Fortran binaries not built: run `make build-fortran`"


def fortran_skip_reason(settings: Settings, executable: str | None = None) -> str | None:
    """Why Fortran-dependent tests must be skipped, or ``None`` when the binaries are present."""
    available = settings.fortran_executables()
    if not available:
        return f"{FORTRAN_SKIP_REASON} (no executables in {settings.fortran_bin_path})"
    if executable is not None and executable not in available:
        return f"{FORTRAN_SKIP_REASON} ({executable} missing from {settings.fortran_bin_path})"
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every ``fortran``-marked test when no Fortran driver has been built."""
    reason = fortran_skip_reason(Settings())
    if reason is None:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("fortran") is not None:
            item.add_marker(skip)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Remove every ``GERALD_NA_*`` variable and reset the cached settings around the test."""
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The repository root (the directory holding ``config/settings.toml``)."""
    return find_repo_root()


@pytest.fixture
def settings() -> Settings:
    """Settings as the application would load them (TOML file plus environment)."""
    return Settings()


@pytest.fixture
def fortran_bin_dir(settings: Settings) -> Path:
    """Directory of the compiled Fortran drivers; skips the test when none are built."""
    reason = fortran_skip_reason(settings)
    if reason is not None:
        pytest.skip(reason)
    return settings.fortran_bin_path


@pytest.fixture
def fortran_executable(settings: Settings) -> Callable[[str], Path]:
    """Return a function mapping a driver name to its path, skipping the test if it is absent."""

    def require(name: str) -> Path:
        reason = fortran_skip_reason(settings, name)
        if reason is not None:
            pytest.skip(reason)
        return settings.fortran_bin_path / name

    return require
