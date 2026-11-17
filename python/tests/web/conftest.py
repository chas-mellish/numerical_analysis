"""Fixtures for the web tests: app clients and a temporary Lagrange-like catalog.

The real Lagrange program lives on another branch, so ``lagrange_repo`` writes a catalog entry
with the same shape (no scan, unconfirmed book reference, ``point_list`` input, ``interpolant``
chart) into a temporary repository. ``lagrange_adapter`` registers a small test adapter for it so
the point-list form, the run fragment and the chart can be exercised end to end.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from gerald_na.engines import adapters as adapter_registry
from gerald_na.engines.programs import Function, ProgramAdapter
from gerald_na.engines.trace import Trace
from gerald_na.registry import CatalogEntry, Registry
from gerald_na.registry.models import InputValue
from gerald_na.settings import Settings
from gerald_na.web.app import create_app

BISECTION = "ch01_p01"
HX = {"hx-request": "true"}

LAGRANGE_TOML = """
id = "lagrange_interpolation"
title = "Lagrangian interpolation"
method = "Lagrange polynomial"
summary = "Interpolates y at XIN through n points with the Lagrange form."
book_ref_confirmed = false
precision_notes = "Synthetic test entry."
book_output = "2.3119"

[book_ref]
chapter = 2

[[inputs]]
name = "n"
type = "int"
label = "N"
default = 3
min = 2
max = 10
help = "Number of points."
card = 1

[[inputs]]
name = "points"
type = "point_list"
label = "Points"
default = [[1.0, 1.0], [2.0, 4.0], [4.0, 16.0]]
min = -100.0
max = 100.0
help = "The (x, y) data."
card = 2

[[inputs]]
name = "xin"
type = "real"
label = "XIN"
default = 3.0
min = -100.0
max = 100.0
help = "Where to interpolate."
card = 3

[data_card]
text = "3\\n1. 1.\\n2. 4.\\n4. 16.\\n3."
values = { n = 3, points = [[1.0, 1.0], [2.0, 4.0], [4.0, 16.0]], xin = 3.0 }

[function]
takes_function = false

[trace]
step_columns = [
    { key = "i", label = "I", format = "I3" },
    { key = "x", label = "X", format = "F10.4" },
    { key = "y", label = "Y", format = "F10.4" },
    { key = "term", label = "TERM", format = "F12.6" },
    { key = "partial", label = "SUM", format = "F12.6" },
]

[[expected]]
name = "value"
kind = "real"
book_value = 9.0
tol_real64 = 1e-6
tol_real32 = 1e-5

[files]
legacy = ["legacy_code/fortran/chapter_2/lagrange.f90"]
fortran_module = "fortran/src/lagrange_mod.f90"
fortran_app = "fortran/app/lagrange_interpolation.f90"
fortran_executable = "lagrange_interpolation"
python_callable = "gerald_na.algorithms.lagrange:lagrange"
study_page = "content/lagrange_interpolation.md"

[chart]
kind = "interpolant"

[[practice]]
id = "value-at-3"
prompt = "What is P(3)?"
answer_field = "value"
answer = 9.0
tolerance = 1e-6
explanation = "The parabola y = x**2 passes through the three points."
"""


@dataclass(frozen=True, slots=True)
class LagrangeStep:
    i: int
    x: float
    y: float
    term: float
    partial: float


@dataclass(frozen=True, slots=True)
class LagrangeResult:
    value: float
    converged: bool
    iterations: int
    steps: tuple[LagrangeStep, ...]
    xin: float
    terms: tuple[float, ...]

    def book_text(self, *, carriage_control: bool = False) -> str:
        prefix = " " if carriage_control else ""
        return f"{prefix}X = {self.xin:8.4f}  Y = {self.value:10.4f}\n"


class FakeLagrangeAdapter(ProgramAdapter):
    """Test adapter: Lagrange interpolation on the first n points."""

    program_id: ClassVar[str] = "lagrange_interpolation"
    result_type: ClassVar[type] = LagrangeResult
    step_type: ClassVar[type] = LagrangeStep

    def run_python(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], function: Function | None
    ) -> LagrangeResult:
        points = inputs["points"]
        n = inputs["n"]
        xin = inputs["xin"]
        assert isinstance(points, tuple)
        assert isinstance(n, int)
        assert isinstance(xin, float)
        nodes = [p for p in points if isinstance(p, tuple)][:n]
        steps: list[LagrangeStep] = []
        total = 0.0
        for i, (xi, yi) in enumerate(nodes):
            term = yi
            for j, (xj, _) in enumerate(nodes):
                if i != j:
                    term *= (xin - xj) / (xi - xj)
            total += term
            steps.append(LagrangeStep(i + 1, xi, yi, term, total))
        return LagrangeResult(
            total, True, len(steps), tuple(steps), xin, tuple(s.term for s in steps)
        )

    def result_from_trace(
        self, entry: CatalogEntry, inputs: Mapping[str, InputValue], trace: Trace
    ) -> Any:
        raise NotImplementedError


def make_settings(root: Path, **overrides: object) -> Settings:
    """Settings rooted at ``root`` (which needs ``config/settings.toml``)."""
    return Settings.model_validate({"repo_root": root, **overrides})


@pytest.fixture
def client(clean_env: pytest.MonkeyPatch) -> TestClient:
    """The app on the repository's own catalog and settings."""
    return TestClient(create_app())


@pytest.fixture
def python_only_client(clean_env: pytest.MonkeyPatch, repo_root: Path) -> TestClient:
    """The app with the Fortran engine disabled (as when the drivers are not built)."""
    return TestClient(create_app(make_settings(repo_root, engines_enabled=["python"])))


@pytest.fixture
def no_binaries_client(
    clean_env: pytest.MonkeyPatch, repo_root: Path, tmp_path: Path
) -> TestClient:
    """The app with Fortran enabled but an empty driver directory."""
    settings = make_settings(repo_root, fortran_bin_dir=tmp_path / "empty-bin")
    return TestClient(create_app(settings))


@pytest.fixture
def lagrange_repo(tmp_path: Path) -> Path:
    """A temporary repository whose catalog holds the Lagrange-like entry."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.toml").write_text("", encoding="utf-8")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "lagrange_interpolation.toml").write_text(
        LAGRANGE_TOML, encoding="utf-8"
    )
    legacy = tmp_path / "legacy_code" / "fortran" / "chapter_2"
    legacy.mkdir(parents=True)
    (legacy / "lagrange.f90").write_text("      PROGRAM LAGRAN\n<b>raw</b>\n", encoding="utf-8")
    content = tmp_path / "content"
    content.mkdir()
    (content / "lagrange_interpolation.md").write_text(
        "# Lagrange\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def lagrange_client(clean_env: pytest.MonkeyPatch, lagrange_repo: Path) -> TestClient:
    """The app on the temporary Lagrange-like catalog (no adapter registered)."""
    settings = make_settings(lagrange_repo)
    return TestClient(create_app(settings, registry=Registry.load(lagrange_repo)))


@pytest.fixture
def lagrange_adapter(monkeypatch: pytest.MonkeyPatch) -> FakeLagrangeAdapter:
    """Register :class:`FakeLagrangeAdapter` for the duration of the test."""
    adapter = FakeLagrangeAdapter()
    monkeypatch.setitem(adapter_registry._ADAPTERS, adapter.program_id, adapter)
    return adapter


def book_form(engine: str = "python", **overrides: str) -> dict[str, str]:
    """The bisection run form with the book data card."""
    form = {
        "in_x1": "0.",
        "in_x2": "1.",
        "in_tol": "1.E-5",
        "function": "1",
        "expression": "",
        "engine": engine,
    }
    form.update(overrides)
    return form
