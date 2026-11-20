"""README program index and study pages: generated from the catalog and consistent with it.

* README.md's program index and run-commands block and every study page's errata table must
  equal what ``gerald-na catalog index --write`` (``make readme-index``) would write.
* Every study page has the same section structure, an errata table holding every catalog
  erratum id with its kind, ``[practice-id]`` markers matching the catalog ``[[practice]]`` ids,
  and precision notes quoting the book and modern values.
"""

import re
import shutil
import subprocess
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
    RUN_COMMANDS_END,
    RUN_COMMANDS_START,
    GeneratedBlockError,
    book_reference,
    escape_cell,
    format_expected_value,
    generated_files,
    printf_argument,
    printf_command,
    render_errata_table,
    render_program_index,
    render_run_commands,
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
    "ch04_p01": ("1.0000150E-04", "1.0000166E-04", "0.0000000E-99", "central_difference_rows"),
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


def _readme_block(repo_root: Path, start: str, end: str) -> str:
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    return readme.split(f"{start}\n")[1].split(end)[0]


def test_readme_generated_blocks_are_up_to_date(registry: Registry) -> None:
    readme = next(item for item in generated_files(registry) if item.relative == "README.md")
    assert not readme.stale, (
        "README.md generated blocks (program index, run commands) are out of date: "
        "run `make readme-index`"
    )


def test_study_page_errata_tables_are_up_to_date(registry: Registry) -> None:
    stale = [item.relative for item in generated_files(registry) if item.stale]
    assert stale == [], f"out of date, run `make readme-index`: {stale}"


def test_readme_index_lists_every_program(registry: Registry, repo_root: Path) -> None:
    block = _readme_block(repo_root, INDEX_START, INDEX_END)
    for entry in registry.programs:
        assert f"| `{entry.id}` | {book_reference(entry)} |" in block
        assert f"[`{entry.files.fortran_executable}`]({entry.files.fortran_app})" in block
        assert f"`{entry.files.python_callable}`" in block
        assert f"]({entry.files.study_page})" in block
    lagrange = next(line for line in block.splitlines() if "`lagrange_interpolation`" in line)
    assert "| unconfirmed |" in lagrange
    assert "| **no** |" in lagrange
    assert "Without a scan: `lagrange_interpolation`" in block


def test_readme_run_commands_list_every_program(registry: Registry, repo_root: Path) -> None:
    block = _readme_block(repo_root, RUN_COMMANDS_START, RUN_COMMANDS_END)
    fortran, python = re.findall(r"^```sh\n(.*?)^```$", block, re.MULTILINE | re.DOTALL)
    for entry in registry.programs:
        comment = f"# {entry.id}: {entry.title}\n"
        assert comment in fortran, entry.id
        assert (
            f"{comment}printf {printf_argument(entry.data_card.text)} "
            f"| build/bin/{entry.files.fortran_executable}\n"
        ) in fortran, entry.id
        assert f"{comment}uv run gerald-na run {entry.id}\n" in python, entry.id
        rows = re.findall(rf"^\| `{re.escape(entry.id)}` \| `([a-z0-9_]+)` \|", block, re.MULTILINE)
        assert rows == [expected.name for expected in entry.expected], entry.id
    commands = [line for line in fortran.splitlines() if not line.startswith("#")]
    assert len(commands) == len(registry)
    assert "printf '0.        1.        1.E-5\\n' | build/bin/ch01_p01_bisection" in fortran


def test_run_commands_expected_table_values(registry: Registry) -> None:
    block = render_run_commands(registry)
    assert "| `ch01_p01` | `root` | `0.4435729` | `0.443572998046875` |" in block
    # int without real64_value: the book value is repeated in the real64 column
    assert "| `ch01_p01` | `iterations` | `15` | `15` |" in block
    # rows / table: dashes and the escaped description only
    steps = registry.get("ch01_p01").expected[2]
    assert steps.kind == "rows"
    assert f"| `ch01_p01` | `steps` | - | - | {escape_cell(steps.description or '')} |" in block
    factors = next(item for item in registry.get("ch01_p02").expected if item.name == "factors")
    assert f"| `ch01_p02` | `factors` | - | - | {escape_cell(factors.description or '')} |" in block
    assert format_expected_value(1.0000000031710762e-20) == "`1.0000000031710762e-20`"
    assert format_expected_value(0.0) == "`0.0`"
    assert format_expected_value(10) == "`10`"
    assert format_expected_value("A|B") == r"A\|B"


def test_printf_argument_escapes_percent_quote_and_backslash() -> None:
    assert printf_argument("50% it's\\x") == "'50%% it'\\''s\\\\x\\n'"


def test_printf_argument_joins_cards_and_strips_blank_lines() -> None:
    card = "\n\n  0.     1.\n0.   0.   20  5\n\n"
    assert printf_argument(card) == "'  0.     1.\\n0.   0.   20  5\\n'"


def test_printf_argument_multi_card_programs(registry: Registry) -> None:
    bairstow = printf_argument(registry.get("ch01_p02").data_card.text)
    assert bairstow.count("\\n") == 2
    assert bairstow.endswith("20  5\\n'")
    lagrange = printf_argument(registry.get("lagrange_interpolation").data_card.text)
    assert lagrange == (
        "'05\\n2.3756  1.6\\n3.2682  1.9\\n4.4571  2.2\\n6.0502  2.5\\n8.1919  2.8\\n5.0\\n'"
    )


def test_printf_command_no_dash_prefix_for_digit_cards() -> None:
    assert printf_command("0. 1. 1.E-5", "x") == "printf '0. 1. 1.E-5\\n' | build/bin/x"


def test_printf_command_adds_end_of_options_for_leading_dash_card() -> None:
    assert printf_command("-1.0   2.0\n", "x") == "printf -- '-1.0   2.0\\n' | build/bin/x"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
@pytest.mark.parametrize(
    "card",
    [
        "0.        1.        1.E-5",
        "50% it's \\n back\\slash\n  second card  \n",
        "%d %s ''",
        "-1.0   2.0",
    ],
    ids=["plain", "special", "format-like", "leading-dash"],
)
def test_printf_argument_round_trips_through_sh(card: str) -> None:
    # Prefix printf_argument with `-- ` for leading-dash cards, so sh's
    # printf does not treat the data card as options (what printf_command
    # does for the generator).
    arg = printf_argument(card)
    end_of_options = "-- " if arg.startswith("'-") else ""
    out = subprocess.run(  # noqa: S603 - fixed argv, no user input
        ["sh", "-c", f"printf {end_of_options}{arg}"],  # noqa: S607 - POSIX sh on PATH
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out == card.strip("\n") + "\n"


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


def test_cli_catalog_index_prints_the_index(
    capsys: pytest.CaptureFixture[str], registry: Registry
) -> None:
    assert main(["catalog", "index"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("| Program id | Book reference |")
    assert "`lagrange_interpolation` | unconfirmed" in out
    # Bare `catalog index` prints only the program index; RUN_COMMANDS is
    # produced by --write / --check, matching origin behaviour.
    assert out == render_program_index(registry)
    assert "build/bin/ch01_p01_bisection" not in out
    assert "uv run gerald-na run lagrange_interpolation" not in out


def test_cli_catalog_index_check_names_a_stale_run_commands_block(
    tmp_path: Path,
    repo_root: Path,
    clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _scratch_repo(tmp_path, repo_root)
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(root))
    readme = root / "README.md"
    original = readme.read_text(encoding="utf-8")
    readme.write_text(
        original.replace("uv run gerald-na run ch01_p01\n", "uv run gerald-na run stale\n"),
        encoding="utf-8",
    )
    assert main(["catalog", "index", "--check"]) == 1
    err = capsys.readouterr().err
    assert "README.md (RUN_COMMANDS)" in err
    assert "PROGRAM_INDEX" not in err
    assert main(["catalog", "index", "--write"]) == 0
    assert capsys.readouterr().out.splitlines() == ["updated README.md"]
    assert readme.read_text(encoding="utf-8") == original
    assert main(["catalog", "index", "--check"]) == 0


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


def test_cli_catalog_index_reports_missing_run_commands_markers(
    tmp_path: Path,
    repo_root: Path,
    clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _scratch_repo(tmp_path, repo_root)
    clean_env.setenv("GERALD_NA_REPO_ROOT", str(root))
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(text.replace(f"{RUN_COMMANDS_END}\n", ""), encoding="utf-8")
    assert main(["catalog", "index", "--check"]) == 1
    assert "README.md: needs exactly one <!-- RUN_COMMANDS_START -->" in capsys.readouterr().err
    assert main(["catalog", "index", "--write"]) == 1
    assert readme.read_text(encoding="utf-8") == text.replace(f"{RUN_COMMANDS_END}\n", "")
