"""README program index and study pages: generated from the catalog and consistent with it.

* README.md's program index and every study page's errata table must equal what
  ``gerald-na catalog index --write`` (``make readme-index``) would write.
* Every study page has the same section structure, an errata table holding every catalog
  erratum id with its kind, ``[practice-id]`` markers matching the catalog ``[[practice]]`` ids,
  and precision notes quoting the book and modern values.
"""

import re
import shutil
from pathlib import Path

import pytest

from gerald_na.cli import main
from gerald_na.registry import Registry
from gerald_na.registry.generated import (
    ERRATA_END,
    ERRATA_START,
    INDEX_END,
    INDEX_START,
    KIND_LABELS,
    GeneratedBlockError,
    book_reference,
    escape_cell,
    generated_files,
    render_errata_table,
    render_program_index,
    replace_block,
)

SECTIONS = (
    "## The method",
    "## The book's data card",  # "data cards" for Bairstow
    "## Other outcomes the program handles",
    "## Errata",
    "## Precision",
    "## Practice questions",
)
"""Second-level sections every study page has, in this order (prefix match)."""

PRECISION_FIGURES = {
    "ch01_p01": ("0.4435729", ".4414062", "0.4414063", "truncated"),
    "ch01_p02": ("4.19999", "3.29999", "chopped"),
    "ch03_p01": ("1.5499312", "1.5499307", "gerald_na.tools.book_machine"),
    "ch03_p02": ("1.6181944", "1.6181936", "gerald_na.tools.book_machine"),
    "lagrange_interpolation": ("2.3119", "2.3119012901784366"),
}
"""Values each page's precision section must quote (book versus modern digits)."""

_ROW_ID = re.compile(r"^\| `([a-z0-9][a-z0-9_-]*)` \| ([^|]+) \|", re.MULTILINE)
_PRACTICE_MARKER = re.compile(r"\*\*\[([a-z0-9][a-z0-9_-]*)\]\*\*")


@pytest.fixture(scope="module")
def registry(repo_root: Path) -> Registry:
    return Registry.load(repo_root)


def _page(registry: Registry, program_id: str) -> str:
    return registry.resolve_path(program_id, "study").read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n{heading}")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


# ------------------------------------------------------------------ up to date


def test_readme_program_index_is_up_to_date(registry: Registry) -> None:
    readme = next(item for item in generated_files(registry) if item.relative == "README.md")
    assert not readme.stale, "README.md program index is out of date: run `make readme-index`"


def test_study_page_errata_tables_are_up_to_date(registry: Registry) -> None:
    stale = [item.relative for item in generated_files(registry) if item.stale]
    assert stale == [], f"out of date, run `make readme-index`: {stale}"


def test_readme_index_lists_every_program(registry: Registry, repo_root: Path) -> None:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    block = readme.split(INDEX_START)[1].split(INDEX_END)[0]
    for entry in registry.programs:
        assert f"| `{entry.id}` | {book_reference(entry)} |" in block
        assert f"[`{entry.files.fortran_executable}`]({entry.files.fortran_app})" in block
        assert f"`{entry.files.python_callable}`" in block
        assert f"]({entry.files.study_page})" in block
    lagrange = next(line for line in block.splitlines() if "`lagrange_interpolation`" in line)
    assert "| unconfirmed |" in lagrange
    assert "| **no** |" in lagrange
    assert "Without a scan: `lagrange_interpolation`" in block


# ------------------------------------------------------------------ study pages


def test_every_program_has_a_study_page_with_the_common_sections(registry: Registry) -> None:
    for entry in registry.programs:
        text = _page(registry, entry.id)
        assert text.startswith("# "), entry.id
        headings = [line for line in text.splitlines() if line.startswith("## ")]
        positions = []
        for section in SECTIONS:
            matches = [i for i, heading in enumerate(headings) if heading.startswith(section)]
            assert len(matches) == 1, f"{entry.id}: expected one {section!r} section"
            positions.append(matches[0])
        assert positions == sorted(positions), f"{entry.id}: sections out of order {headings}"
        assert f"`{entry.files.study_page}`" not in text  # pages do not link to themselves
        assert f"catalog/{entry.id}" in text, f"{entry.id}: page should name its catalog file"


def test_study_page_errata_table_contains_every_catalog_erratum(registry: Registry) -> None:
    for entry in registry.programs:
        errata = _section(_page(registry, entry.id), "## Errata")
        assert ERRATA_START in errata, entry.id
        assert ERRATA_END in errata, entry.id
        table = errata.split(ERRATA_START)[1].split(ERRATA_END)[0]
        rows = {match.group(1): match.group(2).strip() for match in _ROW_ID.finditer(table)}
        expected = {erratum.id: KIND_LABELS[erratum.kind] for erratum in entry.errata}
        missing = sorted(set(expected) - set(rows))
        assert missing == [], f"{entry.id}: errata table lacks {missing}"
        assert rows == expected, f"{entry.id}: errata ids or kinds differ from the catalog"
        for erratum in entry.errata:
            assert escape_cell(erratum.note) in table, f"{entry.id}: wording of {erratum.id}"


def test_study_page_practice_markers_match_the_catalog(registry: Registry) -> None:
    for entry in registry.programs:
        practice = _section(_page(registry, entry.id), "## Practice questions")
        markers = _PRACTICE_MARKER.findall(practice)
        assert markers == [question.id for question in entry.practice], (
            f"{entry.id}: practice markers {markers} must list the catalog ids in order"
        )


def test_study_page_precision_notes_quote_book_and_modern_values(registry: Registry) -> None:
    assert set(PRECISION_FIGURES) == {entry.id for entry in registry.programs}
    for entry in registry.programs:
        precision = _section(_page(registry, entry.id), "## Precision")
        for figure in PRECISION_FIGURES[entry.id]:
            assert figure in precision, f"{entry.id}: precision notes should mention {figure}"


def test_unconfirmed_program_page_says_so(registry: Registry) -> None:
    entry = registry.get("lagrange_interpolation")
    assert not entry.book_ref_confirmed
    assert entry.files.scan_pdf is None
    head = _page(registry, entry.id).split("\n## ")[0]
    assert "unconfirmed" in head
    assert "no scan" in head


# ------------------------------------------------------------------ renderer units


def test_escape_cell_escapes_markdown_and_collapses_whitespace() -> None:
    assert escape_cell("  X**2 +\n  R_1 | <b> ~ `c` [x] & #  ") == (
        r"X\*\*2 + R\_1 \| \<b\> \~ \`c\` \[x\] \& \#"
    )


def test_replace_block_replaces_only_between_markers() -> None:
    text = "intro\n<!-- A -->\nold\n<!-- B -->\noutro\n"
    assert replace_block(text, "<!-- A -->", "<!-- B -->", "new\n", where="t") == (
        "intro\n<!-- A -->\nnew\n<!-- B -->\noutro\n"
    )


@pytest.mark.parametrize(
    "text",
    ["no markers", "<!-- A -->\n<!-- A -->\n<!-- B -->", "<!-- B -->\n<!-- A -->\n"],
    ids=["missing", "repeated", "reversed"],
)
def test_replace_block_rejects_bad_markers(text: str) -> None:
    with pytest.raises(GeneratedBlockError):
        replace_block(text, "<!-- A -->", "<!-- B -->", "x\n", where="t")


def test_render_errata_table_without_errata(registry: Registry) -> None:
    entry = registry.get("ch01_p01").model_copy(update={"errata": ()})
    assert render_errata_table(entry) == "No errata are recorded for this program.\n"


def test_render_program_index_rows_follow_book_order(registry: Registry) -> None:
    index = render_program_index(registry)
    ids = re.findall(r"^\| `([a-z0-9_]+)` \|", index, re.MULTILINE)
    assert ids == [entry.id for entry in registry.programs]
    assert "| `ch01_p01` | Ch. 1, Prog. 1, p. 24 |" in index


# ------------------------------------------------------------------ CLI


def _scratch_repo(tmp_path: Path, repo_root: Path) -> Path:
    root = tmp_path / "repo"
    for directory in ("catalog", "content", "config"):
        shutil.copytree(repo_root / directory, root / directory)
    shutil.copy(repo_root / "README.md", root / "README.md")
    return root


def test_cli_catalog_index_prints_the_index(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["catalog", "index"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("| Program id | Book reference |")
    assert "`lagrange_interpolation` | unconfirmed" in out


def test_cli_catalog_index_check_and_write(
    tmp_path: Path,
    repo_root: Path,
    clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _scratch_repo(tmp_path, repo_root)
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(root))
    assert main(["catalog", "index", "--check"]) == 0
    readme = root / "README.md"
    page = root / "content" / "ch03_p02.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("| `ch01_p01` | Ch. 1", "| `stale` | Ch. 1"),
        encoding="utf-8",
    )
    page.write_text(
        page.read_text(encoding="utf-8").replace("`fcn-call-slip`", "`gone`"), encoding="utf-8"
    )
    capsys.readouterr()
    assert main(["catalog", "index", "--check"]) == 1
    err = capsys.readouterr().err
    assert "README.md" in err
    assert "content/ch03_p02.md" in err
    assert main(["catalog", "index", "--write"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "updated README.md",
        "updated content/ch03_p02.md",
    ]
    assert main(["catalog", "index", "--check"]) == 0
    assert (root / "README.md").read_text(encoding="utf-8") == (repo_root / "README.md").read_text(
        encoding="utf-8"
    )
    assert main(["catalog", "index", "--write"]) == 0
    assert "already up to date" in capsys.readouterr().out


def test_cli_catalog_index_reports_missing_markers(
    tmp_path: Path,
    repo_root: Path,
    clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _scratch_repo(tmp_path, repo_root)
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(root))
    (root / "README.md").write_text("# no markers\n", encoding="utf-8")
    assert main(["catalog", "index", "--check"]) == 1
    assert "PROGRAM_INDEX_START" in capsys.readouterr().err
