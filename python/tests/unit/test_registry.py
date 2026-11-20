"""``gerald_na.registry``: catalog schema validation, ordering, path whitelist, integrity."""

import copy
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from gerald_na import cli
from gerald_na.registry import (
    CatalogEntry,
    CatalogError,
    CatalogInput,
    CatalogPathError,
    Registry,
    get_registry,
    load_entry,
)
from gerald_na.registry.models import parse_data_card_token

FIXTURES = Path(__file__).parent / "fixtures" / "registry"
SAMPLE = FIXTURES / "ch09_p02_sample.toml"
LAGRANGE_LIKE = FIXTURES / "lagrange_like.toml"

type Data = dict[str, Any]


def _data(path: Path = SAMPLE) -> Data:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _referenced_files(entry: CatalogEntry) -> list[str]:
    files = entry.files
    paths = [*files.legacy, files.fortran_module, files.fortran_app, files.study_page]
    if files.scan_pdf is not None:
        paths.append(files.scan_pdf)
    return paths


def _populate(root: Path, *sources: Path) -> None:
    catalog = root / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copy(source, catalog / source.name)
        for relative in _referenced_files(load_entry(source)):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("placeholder\n", encoding="utf-8")


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A repository with the two fixture entries and every file they reference."""
    root = tmp_path / "repo"
    _populate(root, SAMPLE, LAGRANGE_LIKE)
    return root


def _write_variant(root: Path, name: str, text: str) -> None:
    (root / "catalog" / name).write_text(text, encoding="utf-8")


def _chapter3_variant() -> str:
    text = SAMPLE.read_text(encoding="utf-8")
    text = text.replace("ch09_p02", "ch03_p01").replace("chapter = 9", "chapter = 3")
    return text.replace("program = 2", "program = 1")


# ---------------------------------------------------------------- schema: valid entries


def test_fixture_entries_validate() -> None:
    sample = load_entry(SAMPLE)
    assert sample.id == "ch09_p02"
    assert sample.book_ref is not None
    assert sample.book_ref.page == 300
    assert sample.defaults() == {"x1": 0.0, "x2": 1.0, "n": 20}
    assert isinstance(sample.input("n").default, int)
    assert sample.files.python_module == "gerald_na.cli"
    assert sample.files.python_attribute == "main"
    assert sample.function.preset(1).expr == "x - 0.5"
    assert sample.trace.column("k").is_integer
    assert not sample.trace.column("x").is_integer

    lagrange = load_entry(LAGRANGE_LIKE)
    assert lagrange.book_ref_confirmed is False
    assert lagrange.files.scan_pdf is None
    assert lagrange.function.takes_function is False
    assert lagrange.input("points").default == ((1.0, 2.0), (3.0, 4.0))
    assert lagrange.chapter is None


def test_entries_are_frozen() -> None:
    entry = load_entry(SAMPLE)
    with pytest.raises(ValidationError):
        entry.title = "changed"  # type: ignore[misc]


def test_book_ref_is_optional() -> None:
    data = _data(LAGRANGE_LIKE)
    del data["book_ref"]
    entry = CatalogEntry.model_validate(data)
    assert entry.book_ref is None
    assert entry.sort_key == (1, 0, 0, "lagrange_like")


def test_expected_helpers() -> None:
    entry = load_entry(SAMPLE)
    root, iterations, steps = entry.expected
    assert root.result_field == "value"
    assert iterations.result_field == "iterations"
    assert root.tolerance("real64") == pytest.approx(1e-7)
    assert root.tolerance("real32") == pytest.approx(1e-6)
    assert iterations.tolerance("real64") == 0.0
    assert steps.tolerance("real32", "x") == pytest.approx(1e-6)
    assert steps.tolerance("real32", "k") == 0.0
    assert steps.tolerance("real32") == 0.0


def test_practice_inputs_apply_overrides() -> None:
    entry = load_entry(SAMPLE)
    assert entry.practice_inputs(entry.practice[0]) == {"x1": 0.0, "x2": 2.0, "n": 20}


@pytest.mark.parametrize(
    ("token", "integer", "expected"),
    [
        ("0.", False, 0.0),
        ("1.E-5", False, 1e-5),
        (".5", False, 0.5),
        ("-2.5D+1", False, -25.0),
        ("20", False, 20.0),
        ("20", True, 20),
        ("+3", True, 3),
    ],
)
def test_parse_data_card_token(token: str, integer: bool, expected: float) -> None:
    assert parse_data_card_token(token, integer=integer) == expected


@pytest.mark.parametrize(("token", "integer"), [("1.0", True), ("abc", False), ("1.E", False)])
def test_parse_data_card_token_rejects(token: str, integer: bool) -> None:
    with pytest.raises(ValueError, match="data card field"):
        parse_data_card_token(token, integer=integer)


def test_input_coerce_and_check() -> None:
    entry = load_entry(LAGRANGE_LIKE)
    n = entry.input("n")
    assert n.coerce(3.0) == 3
    with pytest.raises(ValueError, match="integer"):
        n.coerce(2.5)
    with pytest.raises(ValueError, match="integer"):
        n.coerce(True)
    assert n.check_value(11) is not None
    assert n.check_value(5) is None
    points = entry.input("points")
    assert points.check_value([[0.0, 1.0]]) == "expected 2 items, got 1"
    assert points.check_value([[0.0, 1.0, 2.0], [1.0, 1.0]]) is not None
    assert points.check_value("12") is not None
    xin = entry.input("xin")
    assert xin.check_value("x") is not None
    assert xin.check_value(1e9) is None  # no bounds declared
    real_list = CatalogInput(
        name="a", type="real_list", label="A", default=(1.0, 2), help="h", card=1, max=5.0
    )
    assert real_list.default == (1.0, 2.0)
    assert real_list.check_value([1.0, 6.0]) == "6.0 is above the maximum 5.0"
    assert real_list.check_value([1.0, "x"]) is not None
    assert real_list.check_value(3.0) is not None


# ---------------------------------------------------------------- schema: invalid entries


def _set(path: str, value: Any) -> Callable[[Data], None]:
    """Mutation that sets a dotted path (list indexes allowed) to ``value``."""

    def mutate(data: Data) -> None:
        *parents, last = path.split(".")
        node: Any = data
        for part in parents:
            node = node[int(part)] if part.isdigit() else node[part]
        if last.isdigit():
            node[int(last)] = value
        else:
            node[last] = value

    return mutate


def _delete(path: str) -> Callable[[Data], None]:
    def mutate(data: Data) -> None:
        *parents, last = path.split(".")
        node: Any = data
        for part in parents:
            node = node[int(part)] if part.isdigit() else node[part]
        del node[last]

    return mutate


INVALID: dict[str, Callable[[Data], None]] = {
    "unknown top-level key": _set("colour", "red"),
    "unknown input key": _set("inputs.0.colour", "red"),
    "unknown files key": _set("files.binary", "x"),
    "bad input type": _set("inputs.0.type", "complex"),
    "default below min": _set("inputs.0.default", -11.0),
    "min above max": _set("inputs.0.min", 20.0),
    "int default not integer": _set("inputs.2.default", 2.5),
    "length on scalar": _set("inputs.0.length", 2),
    "duplicate input name": _set("inputs.1.name", "x1"),
    "card gap": _set("inputs.2.card", 3),
    "data card text mismatch": _set("data_card.text", "0. 2. 20"),
    "data card bad token": _set("data_card.text", "0. 1. 2O"),
    "data card int token is real": _set("data_card.text", "0. 1. 20."),
    "data card too few fields": _set("data_card.text", "0. 1."),
    "data card values differ from defaults": _set("data_card.values.x2", 2.0),
    "data card values missing key": _delete("data_card.values.n"),
    "confirmed without page": _delete("book_ref.page"),
    "id does not match book_ref": _set("id", "ch09_p03"),
    "executable not prefixed with id": _set("files.fortran_executable", "sample"),
    "absolute path": _set("files.study_page", "/etc/passwd"),
    "traversal path": _set("files.fortran_app", "fortran/../../secret.f90"),
    "dot segment path": _set("files.fortran_app", "./fortran/app/x.f90"),
    "backslash path": _set("files.legacy", ["legacy_code\\sample.f90"]),
    "windows drive path": _set("files.scan_pdf", "C:/docs/sample.pdf"),
    "home path": _set("files.scan_pdf", "~/sample.pdf"),
    "no legacy files": _set("files.legacy", []),
    "bad python callable": _set("files.python_callable", "gerald_na.cli.main"),
    "fortran_preset differs from id": _set("function.presets.0.fortran_preset", 2),
    "blank preset expression": _set("function.presets.0.expr", "   "),
    "default preset missing": _set("function.default_preset", 7),
    "presets without function": _set("function.takes_function", False),
    "bad step format": _set("trace.step_columns.0.format", "X3"),
    "duplicate step key": _set("trace.step_columns.1.key", "k"),
    "reserved result extra": _set("trace.result_extras.0.key", "value"),
    "real expected without tolerance": _delete("expected.0.tol_real32"),
    "negative tolerance": _set("expected.0.tol_real64", -1.0),
    "int expected with tolerance": _set("expected.1.tol_real64", 0.1),
    "int expected with real value": _set("expected.1.book_value", 1.5),
    "real64 value without tolerance": _set("expected.0.real64_value", 0.5),
    "dict tolerance on real": _set("expected.0.tol_real64", {"x": 1.0}),
    "rows wrong width": _set("expected.2.book_value", [[1, 0.5, 9.0]]),
    "rows without columns": _delete("expected.2.columns"),
    "rows unknown column": _set("expected.2.columns", ["k", "fx"]),
    "rows tolerance for unknown column": _set("expected.2.tol_real64", {"y": 1.0}),
    "rows integer column holds real": _set("expected.2.book_value", [[1.5, 0.5]]),
    "columns on real expectation": _set("expected.0.columns", ["k"]),
    "duplicate expected name": _set("expected.1.name", "root"),
    "bad chart kind": _set("chart.kind", "pie"),
    "practice unknown input": _set("practice.0.inputs", {"tol": 1.0}),
    "practice input out of range": _set("practice.0.inputs", {"x2": 99.0}),
    "practice unknown preset": _set("practice.0.preset", 4),
    "practice bad answer field": _set("practice.0.answer_field", "colour"),
    "bad erratum kind": _set("errata.0.kind", "typo"),
    "duplicate erratum id": lambda data: data["errata"].append(copy.deepcopy(data["errata"][0])),
}


@pytest.mark.parametrize("mutation", INVALID.values(), ids=INVALID.keys())
def test_invalid_entries_are_rejected(mutation: Callable[[Data], None]) -> None:
    data = _data()
    mutation(data)
    with pytest.raises(ValidationError):
        CatalogEntry.model_validate(data)


def test_unconfirmed_entry_rejects_function_practice_preset() -> None:
    data = _data(LAGRANGE_LIKE)
    data["practice"] = [
        {"id": "p", "prompt": "q", "preset": 1, "answer_field": "value", "explanation": "e"}
    ]
    with pytest.raises(ValidationError, match="takes no function"):
        CatalogEntry.model_validate(data)


def test_function_program_needs_presets() -> None:
    data = _data()
    data["function"] = {"takes_function": True, "default_preset": 1}
    with pytest.raises(ValidationError, match="at least one preset"):
        CatalogEntry.model_validate(data)


# ---------------------------------------------------------------- loading and ordering


def test_load_orders_by_book_reference_with_unconfirmed_last(fake_repo: Path) -> None:
    _write_variant(fake_repo, "ch03_p01_sample.toml", _chapter3_variant())
    registry = Registry.load(fake_repo)
    assert [entry.id for entry in registry.programs] == ["ch03_p01", "ch09_p02", "lagrange_like"]
    assert list(registry.by_chapter()) == [3, 9, None]
    assert [e.id for e in registry.by_chapter()[None]] == ["lagrange_like"]
    assert len(registry) == 3
    assert [entry.id for entry in registry] == ["ch03_p01", "ch09_p02", "lagrange_like"]
    assert "ch09_p02" in registry
    assert "nope" not in registry
    assert registry.get("lagrange_like").title == "Lagrange-like"
    with pytest.raises(KeyError):
        registry.get("nope")
    assert registry.repo_root == fake_repo.resolve()


def test_load_without_catalog_directory(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="catalog directory"):
        Registry.load(tmp_path)


def test_load_reports_invalid_toml(fake_repo: Path) -> None:
    _write_variant(fake_repo, "broken.toml", "id = [unclosed\n")
    with pytest.raises(CatalogError, match=r"broken\.toml: invalid TOML"):
        Registry.load(fake_repo)


def test_load_reports_schema_errors_with_file_name(fake_repo: Path) -> None:
    _write_variant(fake_repo, "ch09_p02_bad.toml", 'id = "ch09_p02"\n')
    with pytest.raises(CatalogError, match=r"ch09_p02_bad\.toml: invalid catalog entry"):
        Registry.load(fake_repo)


def test_load_entry_unreadable(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="cannot read"):
        load_entry(tmp_path / "missing.toml")


# ---------------------------------------------------------------- path whitelist


def test_resolve_path_for_every_kind(fake_repo: Path) -> None:
    registry = Registry.load(fake_repo)
    root = fake_repo.resolve()
    entry = registry.get("ch09_p02")
    assert registry.resolve_path(entry, "scan") == root / "docs" / "sample.pdf"
    assert registry.resolve_path("ch09_p02", "legacy") == root / "legacy_code" / "sample.f90"
    assert registry.resolve_path(entry, "fortran_module") == root / "fortran/src/sample_mod.f90"
    assert registry.resolve_path(entry, "fortran_app") == root / "fortran/app/ch09_p02_sample.f90"
    assert registry.resolve_path(entry, "study") == root / "content" / "ch09_p02.md"
    assert registry.resolve_path(entry, "catalog") == root / "catalog" / "ch09_p02_sample.toml"
    assert registry.resolve_path(entry, "python") == root / "python/src/gerald_na/cli.py"


def test_python_kind_prefers_package_init(fake_repo: Path) -> None:
    package = fake_repo / "python" / "src" / "math"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    registry = Registry.load(fake_repo)
    assert registry.catalog_path("lagrange_like", "python") == "python/src/math/__init__.py"


def test_resolve_path_without_scan(fake_repo: Path) -> None:
    registry = Registry.load(fake_repo)
    with pytest.raises(CatalogPathError, match="no scan"):
        registry.resolve_path("lagrange_like", "scan")


def test_resolve_path_rejects_unknown_requests(fake_repo: Path) -> None:
    registry = Registry.load(fake_repo)
    with pytest.raises(CatalogPathError, match="not catalogued"):
        registry.resolve_path("../../etc/passwd", "legacy")
    with pytest.raises(CatalogPathError, match="unknown file kind"):
        registry.resolve_path("ch09_p02", "secrets")  # type: ignore[arg-type]
    with pytest.raises(CatalogPathError, match="no legacy file"):
        registry.resolve_path("ch09_p02", "legacy", index=1)
    foreign = load_entry(SAMPLE).model_copy(update={"title": "Other"})
    with pytest.raises(CatalogPathError, match="does not belong"):
        registry.resolve_path(foreign, "study")


def test_resolve_path_rejects_traversal_that_bypassed_validation(tmp_path: Path) -> None:
    entry = load_entry(SAMPLE)
    tampered_files = entry.files.model_copy(update={"study_page": "../outside.md"})
    tampered = entry.model_copy(update={"files": tampered_files})
    registry = Registry(tmp_path, [(tmp_path / "catalog" / "ch09_p02_sample.toml", tampered)])
    with pytest.raises(CatalogPathError, match="escapes the repository root"):
        registry.resolve_path(tampered, "study")
    problems = registry.check_integrity()
    assert any(p.check == "path" and "escapes" in p.message for p in problems)


def test_resolve_path_rejects_symlink_escape(fake_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sample.pdf").write_text("x", encoding="utf-8")
    shutil.rmtree(fake_repo / "docs")
    (fake_repo / "docs").symlink_to(outside, target_is_directory=True)
    registry = Registry.load(fake_repo)
    with pytest.raises(CatalogPathError, match="escapes the repository root"):
        registry.resolve_path("ch09_p02", "scan")


# ---------------------------------------------------------------- integrity


def test_integrity_clean_repo(fake_repo: Path) -> None:
    assert Registry.load(fake_repo).check_integrity() == []


def test_integrity_ignores_uncatalogued_files(fake_repo: Path) -> None:
    for relative in (
        "legacy_code/fortran/chapter_4/derivatives.pdf",
        "legacy_code/fortran/chapter_5/integration_methods.pdf",
        "docs/chapter_06_program_01_listing.pdf",
    ):
        path = fake_repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4\n")
    assert Registry.load(fake_repo).check_integrity() == []


@pytest.mark.parametrize(
    ("relative", "kind"),
    [
        ("legacy_code/sample.f90", "legacy"),
        ("docs/sample.pdf", "scan"),
        ("fortran/src/sample_mod.f90", "fortran_module"),
        ("fortran/app/ch09_p02_sample.f90", "fortran_app"),
        ("content/ch09_p02.md", "study"),
    ],
)
def test_integrity_reports_missing_files(fake_repo: Path, relative: str, kind: str) -> None:
    (fake_repo / relative).unlink()
    problems = Registry.load(fake_repo).check_integrity()
    assert len(problems) == 1
    problem = problems[0]
    assert problem.program_id == "ch09_p02"
    assert problem.check == "missing_file"
    assert problem.message == f"{kind} file {relative} not found"
    assert str(problem) == f"ch09_p02: [missing_file] {kind} file {relative} not found"


def test_integrity_treats_directory_as_missing(fake_repo: Path) -> None:
    (fake_repo / "content" / "lagrange_like.md").unlink()
    (fake_repo / "content" / "lagrange_like.md").mkdir()
    problems = Registry.load(fake_repo).check_integrity()
    assert [p.check for p in problems] == ["missing_file"]


@pytest.mark.parametrize(
    ("target", "fragment"),
    [
        ("gerald_na.no_such_module:run", "cannot import gerald_na.no_such_module"),
        ("gerald_na.cli:no_such_function", "does not exist"),
        ("gerald_na:__version__", "is not callable"),
    ],
)
def test_integrity_reports_bad_python_callable(fake_repo: Path, target: str, fragment: str) -> None:
    text = SAMPLE.read_text(encoding="utf-8").replace('"gerald_na.cli:main"', f'"{target}"')
    _write_variant(fake_repo, SAMPLE.name, text)
    problems = Registry.load(fake_repo).check_integrity()
    assert [p.check for p in problems] == ["python_callable"]
    assert fragment in problems[0].message


def test_integrity_reports_duplicate_ids_and_bad_names(fake_repo: Path) -> None:
    text = SAMPLE.read_text(encoding="utf-8")
    _write_variant(fake_repo, "ch09_p02_copy.toml", text)
    _write_variant(fake_repo, "wrong_name.toml", _chapter3_variant())
    problems = Registry.load(fake_repo).check_integrity()
    checks = sorted(p.check for p in problems)
    assert checks == ["file_name", "missing_file", "missing_file", "unique_id"]
    duplicate = next(p for p in problems if p.check == "unique_id")
    assert "ch09_p02_sample.toml" in duplicate.message
    misnamed = next(p for p in problems if p.check == "file_name")
    assert misnamed.program_id == "ch03_p01"


def test_integrity_reports_shared_executable(fake_repo: Path) -> None:
    confirmed = _chapter3_variant().replace('"ch03_p01_sample"', '"ch03_p01_x"')
    _write_variant(fake_repo, "ch03_p01_sample.toml", confirmed)
    unconfirmed = LAGRANGE_LIKE.read_text(encoding="utf-8").replace(
        '"lagrange_like"', '"ch03_p01_x"'
    )
    _write_variant(fake_repo, "ch03_p01_x.toml", unconfirmed)
    problems = Registry.load(fake_repo).check_integrity()
    shared = [p for p in problems if p.check == "unique_executable"]
    assert len(shared) == 1
    assert "ch03_p01_x is also used by" in shared[0].message


def test_integrity_reports_presets_that_do_not_compile(fake_repo: Path) -> None:
    text = SAMPLE.read_text(encoding="utf-8").replace('"x - 0.5"', '"__import__(1)"')
    _write_variant(fake_repo, SAMPLE.name, text)
    problems = Registry.load(fake_repo).check_integrity()
    assert [p.check for p in problems] == ["preset"]
    assert problems[0].message.startswith("preset 1 does not compile")


def test_integrity_rechecks_values_of_unvalidated_entries(tmp_path: Path) -> None:
    entry = load_entry(SAMPLE)
    bad_input = entry.inputs[0].model_copy(update={"default": 99.0})
    bad_preset = entry.function.presets[0].model_copy(update={"expr": " "})
    bad_function = entry.function.model_copy(update={"presets": (bad_preset,)})
    bad_question = entry.practice[0].model_copy(update={"inputs": {"x2": 50.0}})
    tampered = entry.model_copy(
        update={
            "inputs": (bad_input, *entry.inputs[1:]),
            "function": bad_function,
            "practice": (bad_question,),
        }
    )
    registry = Registry(tmp_path, [(tmp_path / "catalog" / "ch09_p02.toml", tampered)])
    checks = {p.check for p in registry.check_integrity()}
    assert {"default", "preset", "practice", "missing_file"} <= checks


# ---------------------------------------------------------------- cached accessor and CLI


def test_get_registry_uses_settings_repo_root(
    fake_repo: Path, clean_env: pytest.MonkeyPatch
) -> None:
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(fake_repo))
    get_registry.cache_clear()
    try:
        registry = get_registry()
        assert get_registry() is registry
        assert registry.repo_root == fake_repo.resolve()
        assert [entry.id for entry in registry.programs] == ["ch09_p02", "lagrange_like"]
    finally:
        get_registry.cache_clear()


def test_cli_catalog_list(
    fake_repo: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(fake_repo))
    assert cli.main(["catalog", "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[:6] == ["ch09_p02", "ch", "9", "prog", "2", "p.300"]
    assert lines[1].split()[:4] == ["lagrange_like", "unconfirmed", "no", "scan"]
    assert lines[-1] == "2 program(s)"


def test_cli_catalog_check_ok(
    fake_repo: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(fake_repo))
    assert cli.main(["catalog", "check"]) == 0
    assert "catalog OK: 2 program(s)" in capsys.readouterr().out


def test_cli_catalog_check_lists_problems(
    fake_repo: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(fake_repo))
    (fake_repo / "content" / "ch09_p02.md").unlink()
    assert cli.main(["catalog", "check"]) == 1
    err = capsys.readouterr().err
    assert "1 catalog problem(s):" in err
    assert "ch09_p02: [missing_file] study file content/ch09_p02.md not found" in err


@pytest.mark.parametrize("action", ["list", "check"])
def test_cli_catalog_reports_load_errors(
    fake_repo: Path,
    clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    action: str,
) -> None:
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(fake_repo))
    _write_variant(fake_repo, "broken.toml", "id = [\n")
    assert cli.main(["catalog", action]) == 1
    assert "invalid TOML" in capsys.readouterr().err


def test_cli_catalog_without_action_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["catalog"]) == 0
    assert "usage: gerald-na catalog" in capsys.readouterr().out
