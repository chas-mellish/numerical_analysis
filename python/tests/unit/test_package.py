"""Package layout: every documented subpackage is importable and the package is typed."""

import importlib
from importlib import metadata, resources

import pytest

import gerald_na

SUBPACKAGES = ["algorithms", "expr", "engines", "registry", "web"]
MODULES = ["errors", "settings", "cli", "web.app"]


@pytest.mark.parametrize("name", SUBPACKAGES + MODULES)
def test_module_is_importable(name: str) -> None:
    module = importlib.import_module(f"gerald_na.{name}")
    assert module.__doc__


def test_version_matches_distribution_metadata() -> None:
    assert gerald_na.__version__ == metadata.version("gerald-na")


def test_package_ships_py_typed_marker() -> None:
    assert resources.files("gerald_na").joinpath("py.typed").is_file()


def test_console_script_is_registered() -> None:
    scripts = metadata.entry_points(group="console_scripts")
    (entry,) = [ep for ep in scripts if ep.name == "gerald-na"]
    assert entry.value == "gerald_na.cli:main"
