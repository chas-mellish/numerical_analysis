"""Settings: defaults, TOML file, environment overrides and repository-root detection."""

import os
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from gerald_na.settings import (
    CONFIG_FILE,
    Settings,
    find_repo_root,
    get_settings,
    list_executables,
)


def make_repo(root: Path, toml: str | None = None) -> Path:
    (root / "config").mkdir(parents=True)
    (root / CONFIG_FILE).write_text(toml or "", encoding="utf-8")
    return root


def test_repository_settings_file_matches_documented_defaults(
    clean_env: pytest.MonkeyPatch, repo_root: Path
) -> None:
    settings = Settings()
    assert settings.repo_root == repo_root
    assert settings.config_file.is_file()
    assert settings.fortran_bin_dir == Path("build/bin")
    assert settings.fortran_bin_path == repo_root / "build" / "bin"
    assert settings.run_timeout_s == 5.0
    assert settings.engines_enabled == ("python", "fortran")
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_field_defaults_apply_when_toml_is_empty(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = make_repo(tmp_path)
    settings = Settings(repo_root=root)
    assert settings.repo_root == root
    assert settings.fortran_bin_dir == Path("build/bin")
    assert settings.run_timeout_s == 5.0
    assert settings.engines_enabled == ("python", "fortran")
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_toml_values_are_read(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        'fortran_bin_dir = "build/single/bin"\nrun_timeout_s = 2.5\n'
        'engines_enabled = ["python"]\nhost = "0.0.0.0"\nport = 9001\n',
    )
    settings = Settings(repo_root=root)
    assert settings.fortran_bin_path == root / "build" / "single" / "bin"
    assert settings.run_timeout_s == 2.5
    assert settings.engines_enabled == ("python",)
    assert settings.host == "0.0.0.0"  # noqa: S104 - value under test, not a bind
    assert settings.port == 9001


def test_environment_overrides_toml(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = make_repo(tmp_path, "port = 9001\nrun_timeout_s = 2.5\n")
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(root))
    clean_env.setenv("GERALD_NA_PORT", "9100")
    clean_env.setenv("GERALD_NA_ENGINES_ENABLED", '["fortran"]')
    settings = Settings()
    assert settings.repo_root == root
    assert settings.port == 9100
    assert settings.run_timeout_s == 2.5
    assert settings.engines_enabled == ("fortran",)


def test_keyword_arguments_override_environment(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = make_repo(tmp_path, "port = 9001\n")
    clean_env.setenv("GERALD_NA_PORT", "9100")
    assert Settings(repo_root=root, port=9200).port == 9200


def test_absolute_fortran_bin_dir_is_kept(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = make_repo(tmp_path / "repo")
    bin_dir = tmp_path / "elsewhere"
    assert Settings(repo_root=root, fortran_bin_dir=bin_dir).fortran_bin_path == bin_dir


@pytest.mark.parametrize(
    ("field", "value"),
    [("port", 0), ("port", 70000), ("run_timeout_s", 0), ("engines_enabled", ["cobol"])],
)
def test_invalid_values_are_rejected(
    clean_env: pytest.MonkeyPatch, tmp_path: Path, field: str, value: object
) -> None:
    root = make_repo(tmp_path)
    with pytest.raises(ValidationError):
        Settings.model_validate({"repo_root": root, field: value})


def test_find_repo_root_walks_up_to_config_file(tmp_path: Path) -> None:
    root = make_repo(tmp_path / "repo")
    nested = root / "python" / "src" / "pkg"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == root


def test_find_repo_root_accepts_catalog_dir(tmp_path: Path) -> None:
    (tmp_path / "catalog").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == tmp_path


def test_find_repo_root_defaults_to_package_location(repo_root: Path) -> None:
    assert (repo_root / CONFIG_FILE).is_file()
    assert (repo_root / "python" / "pyproject.toml").is_file()


def test_list_executables_only_reports_executable_files(tmp_path: Path) -> None:
    assert list_executables(tmp_path / "missing") == []
    runnable = tmp_path / "ch01_p01_bisection"
    runnable.write_text("#!/bin/sh\n", encoding="utf-8")
    runnable.chmod(runnable.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "notes.txt").write_text("not a program", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    assert list_executables(tmp_path) == ["ch01_p01_bisection"]
    assert os.access(runnable, os.X_OK)


def test_get_settings_is_cached(clean_env: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert get_settings() is first
    get_settings.cache_clear()
    assert get_settings() is not first
