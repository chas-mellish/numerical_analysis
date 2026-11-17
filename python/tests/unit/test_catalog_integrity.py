"""The real ``catalog/`` loads, validates and references only files that exist.

This is the "every catalog entry resolves its referenced files" quality gate of the testing
strategy: it fails until every program's legacy file, scan, Fortran module and driver, Python
callable and study page are in place.
"""

from pathlib import Path

import pytest

from gerald_na.registry import Registry

EXPECTED_IDS = {"ch01_p01"}
"""Programs that must be catalogued (grows as programs land)."""


@pytest.fixture(scope="module")
def registry(repo_root: Path) -> Registry:
    return Registry.load(repo_root)


def test_catalog_contains_the_migrated_programs(registry: Registry) -> None:
    assert {entry.id for entry in registry.programs} >= EXPECTED_IDS


def test_catalog_integrity(registry: Registry) -> None:
    problems = registry.check_integrity()
    assert problems == [], "catalog problems:\n" + "\n".join(str(p) for p in problems)


def test_study_pages_reference_every_practice_question(registry: Registry) -> None:
    for entry in registry.programs:
        if not entry.practice:
            continue
        page = registry.resolve_path(entry, "study")
        if not page.is_file():
            pytest.fail(f"{entry.id}: study page {entry.files.study_page} is missing")
        text = page.read_text(encoding="utf-8")
        missing = [q.id for q in entry.practice if f"[{q.id}]" not in text]
        assert missing == [], f"{entry.id}: study page lacks practice ids {missing}"


def test_bisection_entry_matches_the_book(registry: Registry) -> None:
    entry = registry.get("ch01_p01")
    assert entry.data_card.tokens() == ["0.", "1.", "1.E-5"]
    assert entry.defaults() == {"x1": 0.0, "x2": 1.0, "tol": 1e-5}
    expected = {item.name: item for item in entry.expected}
    assert expected["root"].book_value == pytest.approx(0.4435729)
    assert expected["iterations"].book_value == 15
    rows = expected["steps"].book_value
    assert isinstance(rows, tuple)
    assert len(rows) == 15
    assert [row[0] for row in rows] == list(range(1, 16))
    assert entry.book_output.strip().splitlines()[-1] == (
        "THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED."
    )
    assert entry.function.preset(1).expr == "EXP(-X) - SIN(3.1415926*X/2.)"
    assert [column.key for column in entry.trace.step_columns] == ["k", "x1", "x2", "x", "fx"]
