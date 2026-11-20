"""Milestone 1.3 functional tests: README "Getting started" / "Running the programs" /
"Using the web interface" sections and the RUN_COMMANDS generated block of
``gerald-na catalog index``.

Every expectation below is taken from README.md (the documented commands and outputs) or from the
milestone spec. Generator stale/missing-marker behaviour is exercised on a throw-away copy of the
repository (``GERALD_NA_REPO_ROOT``) so the real README is never modified.
"""

import html
import os
import re
import shutil
import socket
import subprocess
import time

import pytest
import requests

from conftest import BASE_URL, REPO_ROOT, SINGLE_BIN_DIR, run_cli, run_driver, trace_records

README = REPO_ROOT / "README.md"
RUN_START = "<!-- RUN_COMMANDS_START -->"
RUN_END = "<!-- RUN_COMMANDS_END -->"
IDX_START = "<!-- PROGRAM_INDEX_START -->"
IDX_END = "<!-- PROGRAM_INDEX_END -->"
DRIVERS = (
    "ch01_p01_bisection",
    "ch01_p02_bairstow",
    "ch03_p01_simpson",
    "ch03_p02_romberg",
    "ch04_p01_central_difference",
    "lagrange_interpolation",
)


def block(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def readme_text():
    return README.read_text(encoding="utf-8")


def sh(cmd, cwd=REPO_ROOT, timeout=60):
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True,
                          cwd=str(cwd), timeout=timeout, check=False)


# --------------------------------------------------------------------------- repo copy for generator
@pytest.fixture
def repo_copy(tmp_path):
    """A copy of the repository files the registry reads (no venv, no build, no .git)."""
    dst = tmp_path / "ftrun_repo"
    ignore = shutil.ignore_patterns(".venv", "__pycache__", ".git", "build", "node_modules",
                                    ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov")
    shutil.copytree(REPO_ROOT, dst, ignore=ignore, symlinks=True)
    yield dst
    shutil.rmtree(dst, ignore_errors=True)


def index_in(root, *args):
    return run_cli("catalog", "index", *args, env_extra={"GERALD_NA_REPO_ROOT": str(root)})


# =========================================================================== catalog index CLI
class TestCatalogIndexCli:
    def test_m13_index_prints_both_blocks(self, evidence):
        r = run_cli("catalog", "index")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index")
        assert r.returncode == 0, r.stderr
        text = readme_text()
        idx = block(text, IDX_START, IDX_END).lstrip("\n")
        run = block(text, RUN_START, RUN_END).lstrip("\n")
        # The index, a blank line, then the run commands, identical to the README blocks.
        assert r.stdout == idx + "\n" + run
        assert "| Program id | Book reference |" in r.stdout
        assert "printf '0.        1.        1.E-5\\n' | build/bin/ch01_p01_bisection" in r.stdout
        assert "uv run gerald-na run lagrange_interpolation" in r.stdout
        assert "| Program id | Quantity | Book | real64 | What the book prints |" in r.stdout

    def test_m13_index_check_up_to_date(self, evidence):
        r = run_cli("catalog", "index", "--check")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --check")
        assert r.returncode == 0, r.stderr
        assert "generated Markdown up to date in 7 file(s)" in r.stdout

    def test_m13_index_check_stale_run_commands(self, repo_copy, evidence):
        readme = repo_copy / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text.replace("uv run gerald-na run ch03_p01\n", "uv run gerald-na run ch03_p0X\n", 1),
                          encoding="utf-8")
        r = index_in(repo_copy, "--check")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --check (RUN_COMMANDS edited)")
        assert r.returncode == 1
        assert "README.md (RUN_COMMANDS)" in r.stderr
        assert "PROGRAM_INDEX" not in r.stderr
        assert "make readme-index" in r.stderr

    def test_m13_index_check_stale_program_index_only(self, repo_copy, evidence):
        readme = repo_copy / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text.replace("6 programs. Without a scan", "7 programs. Without a scan", 1), encoding="utf-8")
        r = index_in(repo_copy, "--check")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --check (PROGRAM_INDEX edited)")
        assert r.returncode == 1
        assert "README.md (PROGRAM_INDEX)" in r.stderr
        assert "RUN_COMMANDS" not in r.stderr

    def test_m13_index_check_both_stale(self, repo_copy, evidence):
        readme = repo_copy / "README.md"
        text = readme.read_text(encoding="utf-8")
        text = text.replace("6 programs. Without a scan", "7 programs. Without a scan", 1)
        text = text.replace("uv run gerald-na run ch03_p01\n", "uv run gerald-na run ch03_p0X\n", 1)
        readme.write_text(text, encoding="utf-8")
        r = index_in(repo_copy, "--check")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --check (both edited)")
        assert r.returncode == 1
        assert "README.md (PROGRAM_INDEX, RUN_COMMANDS)" in r.stderr

    @pytest.mark.parametrize("marker", [RUN_START, RUN_END])
    def test_m13_index_check_missing_marker(self, repo_copy, marker, evidence):
        readme = repo_copy / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8").replace(marker + "\n", "", 1), encoding="utf-8")
        r = index_in(repo_copy, "--check")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=f"catalog index --check ({marker} removed)")
        assert r.returncode == 1
        assert "README.md" in r.stderr and "RUN_COMMANDS" in r.stderr
        assert "Traceback" not in r.stderr

    def test_m13_index_write_missing_marker_refused(self, repo_copy, evidence):
        readme = repo_copy / "README.md"
        broken = readme.read_text(encoding="utf-8").replace(RUN_END + "\n", "", 1)
        readme.write_text(broken, encoding="utf-8")
        r = index_in(repo_copy, "--write")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --write (marker removed)")
        assert r.returncode == 1
        assert "RUN_COMMANDS" in r.stderr
        assert readme.read_text(encoding="utf-8") == broken

    def test_m13_index_write_regenerates_run_commands(self, repo_copy, evidence):
        readme = repo_copy / "README.md"
        original = readme.read_text(encoding="utf-8")
        start = original.index(RUN_START) + len(RUN_START)
        end = original.index(RUN_END)
        readme.write_text(original[:start] + "\nstale\n" + original[end:], encoding="utf-8")
        w = index_in(repo_copy, "--write")
        c = index_in(repo_copy, "--check")
        evidence(exit_code=w.returncode, stdout=w.stdout + "\n--- check:\n" + c.stdout, stderr=w.stderr + c.stderr,
                 command="catalog index --write then --check")
        assert w.returncode == 0, w.stderr
        assert "updated README.md" in w.stdout
        assert readme.read_text(encoding="utf-8") == original
        assert c.returncode == 0

    def test_m13_index_write_regenerates_errata(self, repo_copy, evidence):
        page = repo_copy / "content" / "ch01_p01.md"
        original = page.read_text(encoding="utf-8")
        start = original.index("<!-- ERRATA_TABLE_START -->") + len("<!-- ERRATA_TABLE_START -->")
        end = original.index("<!-- ERRATA_TABLE_END -->")
        page.write_text(original[:start] + "\nstale\n" + original[end:], encoding="utf-8")
        c = index_in(repo_copy, "--check")
        w = index_in(repo_copy, "--write")
        evidence(exit_code=w.returncode, stdout=c.stderr + "\n--- write:\n" + w.stdout, stderr=w.stderr,
                 command="catalog index --check / --write (errata edited)")
        assert c.returncode == 1 and "content/ch01_p01.md (ERRATA_TABLE)" in c.stderr
        assert w.returncode == 0 and "updated content/ch01_p01.md" in w.stdout
        assert page.read_text(encoding="utf-8") == original

    def test_m13_index_write_already_up_to_date(self, repo_copy, evidence):
        r = index_in(repo_copy, "--write")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --write (clean)")
        assert r.returncode == 0
        assert "generated Markdown already up to date in 7 file(s)" in r.stdout

    def test_m13_index_check_and_write_exclusive(self, evidence):
        r = run_cli("catalog", "index", "--check", "--write")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="catalog index --check --write")
        assert r.returncode == 2
        assert "not allowed with argument" in r.stderr

    def test_m13_index_reflects_catalog_change(self, repo_copy, evidence):
        """A catalog [[expected]] edit makes RUN_COMMANDS stale and --write puts the new text in."""
        cat = next((repo_copy / "catalog").glob("ch03_p01*.toml"))
        text = cat.read_text(encoding="utf-8")
        assert 'description = "WITH 100 PANELS"' in text
        cat.write_text(text.replace('description = "WITH 100 PANELS"', 'description = "FTRUN EDITED PANELS"', 1),
                       encoding="utf-8")
        c = index_in(repo_copy, "--check")
        w = index_in(repo_copy, "--write")
        new = (repo_copy / "README.md").read_text(encoding="utf-8")
        evidence(exit_code=c.returncode, stdout=c.stdout + c.stderr + "\n--- write:\n" + w.stdout, stderr=w.stderr,
                 command="catalog index --check after catalog [[expected]] edit")
        assert c.returncode == 1 and "RUN_COMMANDS" in c.stderr
        assert "| `ch03_p01` | `panels` | `100` | `100` | FTRUN EDITED PANELS |" in block(new, RUN_START, RUN_END)


# =========================================================================== RUN_COMMANDS block executes
def _fortran_commands():
    run = block(readme_text(), RUN_START, RUN_END)
    return re.findall(r"^(printf .* \| build/bin/(\S+))$", run, flags=re.M)


EXPECT_FORTRAN = {
    "ch01_p01_bisection": ["THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED."],
    "ch01_p02_bairstow": ["X**2 +    4.19999 X +   -2.09999", "X**2 +    3.30000 X +   -6.20000",
                          "1.00000X +  -10.30000"],
    "ch03_p01_simpson": ["IS 1.5499312 WITH 100 PANELS"],
    "ch03_p02_romberg": ["VALUE IS  1.6181944,", "80 SUBINTERVALS WERE REQUIRED"],
    "ch04_p01_central_difference": ["1.0016675E-02", "2.0100083E+00", "1.0000000E-20"],
    "lagrange_interpolation": ["2.3119"],
}


class TestRunCommandsBlock:
    def test_m13_run_commands_cover_all_programs(self, evidence):
        cmds = _fortran_commands()
        evidence(exit_code=0, stdout="\n".join(c for c, _ in cmds), command="parse RUN_COMMANDS")
        assert sorted(exe for _, exe in cmds) == sorted(DRIVERS)

    @pytest.mark.parametrize("exe", DRIVERS)
    def test_m13_run_commands_fortran_executes(self, exe, evidence):
        cmd = dict((e, c) for c, e in _fortran_commands())[exe]
        r = sh(cmd)
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=cmd)
        assert r.returncode == 0, r.stderr
        for needle in EXPECT_FORTRAN[exe]:
            assert needle in r.stdout

    @pytest.mark.parametrize("exe", DRIVERS)
    def test_m13_run_commands_single_bin_dir(self, exe, evidence):
        """The block says: use build/single/bin/ for the single-precision build."""
        cmd = dict((e, c) for c, e in _fortran_commands())[exe].replace("build/bin/", "build/single/bin/")
        r = sh(cmd)
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=cmd)
        assert r.returncode == 0, r.stderr

    @pytest.mark.parametrize("pid,needle", [
        ("ch01_p01", "15 ITERATIONS WERE REQUIRED"),
        ("ch01_p02", "4.19999"),
        ("ch03_p01", "1.5499312"),
        ("ch03_p02", "1.6181944"),
        ("ch04_p01", "2.0100083E+00"),
        ("lagrange_interpolation", "2.3119"),
    ])
    def test_m13_run_commands_python_executes(self, pid, needle, evidence):
        run = block(readme_text(), RUN_START, RUN_END)
        assert f"uv run gerald-na run {pid}\n" in run
        r = run_cli("run", pid)
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=f"(cd python) uv run gerald-na run {pid}")
        assert r.returncode == 0, r.stderr
        assert needle in r.stdout

    def test_m13_expected_table_real64_matches_drivers(self, evidence):
        """Every real64 scalar in the expected-results table is what the default build prints."""
        run = block(readme_text(), RUN_START, RUN_END)
        rows = re.findall(r"^\| `(\w+)` \| `(\w+)` \| `([^`]*)` \| `([^`]*)` \|", run, flags=re.M)
        checks = {
            ("ch01_p01", "root"): "0.443572998046875",
            ("ch01_p01", "iterations"): "15",
            ("ch03_p01", "value"): "1.5499312397703537",
            ("ch03_p02", "value"): "1.6181944440409433",
            ("ch03_p02", "subintervals"): "80",
            ("ch04_p01", "first_dx"): "0.010016675001984412",
            ("lagrange_interpolation", "value"): "2.3119012901784366",
        }
        table = {(p, q): r64 for p, q, _book, r64 in rows}
        bis = run_driver("ch01_p01_bisection", "0. 1. 1.E-5\n", "--trace")
        lag = run_driver("lagrange_interpolation", "05\n2.3756 1.6\n3.2682 1.9\n4.4571 2.2\n6.0502 2.5\n8.1919 2.8\n5.0\n", "--trace")
        evidence(exit_code=0, stdout=str(table) + "\n" + bis.stdout[-400:] + lag.stdout[-400:], command="expected table vs --trace")
        for key, val in checks.items():
            assert table.get(key) == val, (key, table.get(key))
        res = trace_records(bis.stdout, "RESULT")[0]
        assert abs(float(res["value"]) - 0.443572998046875) == 0.0
        assert res["iterations"] == "15"
        lres = trace_records(lag.stdout, "RESULT")[0]
        assert abs(float(lres["value"]) - 2.3119012901784366) < 1e-14


# =========================================================================== Getting started
class TestGettingStarted:
    def test_m13_quickstart_version(self, evidence):
        r = sh("uv --directory python run gerald-na --version")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="uv --directory python run gerald-na --version")
        assert r.returncode == 0
        assert r.stdout.strip() == "gerald-na 0.1.0"

    def test_m13_quickstart_build_bin_listing(self, evidence):
        r = sh("ls build/bin")
        evidence(exit_code=r.returncode, stdout=r.stdout, command="ls build/bin")
        assert r.returncode == 0
        assert sorted(r.stdout.split()) == sorted(DRIVERS)

    def test_m13_quickstart_healthz(self, server, evidence):
        resp = requests.get(f"{BASE_URL}/healthz", timeout=10)
        evidence(status=resp.status_code, body=resp.text, endpoint="/healthz", method="GET")
        assert resp.status_code == 200
        assert resp.text == '{"status":"ok","version":"0.1.0","engines":{"python":true,"fortran":true}}'

    def test_m13_quickstart_home_title(self, server, evidence):
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:3000], endpoint="/", method="GET")
        assert resp.status_code == 200
        assert re.search(r"<h1[^>]*>\s*Programs\s*</h1>", resp.text)

    def test_m13_no_fortran_cli_engine_message(self, tmp_path, evidence):
        empty = tmp_path / "ftrun_empty_bin"
        empty.mkdir()
        r = run_cli("run", "ch01_p01", "--engine", "fortran", env_extra={"GERALD_NA_FORTRAN_BIN_DIR": str(empty)})
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr,
                 command="GERALD_NA_FORTRAN_BIN_DIR=<empty> gerald-na run ch01_p01 --engine fortran")
        assert r.returncode == 2
        assert "Fortran driver ch01_p01_bisection is not built in" in (r.stdout + r.stderr)
        assert "(run `make build-fortran`)" in (r.stdout + r.stderr)


# =========================================================================== Running the programs
class TestRunningPrograms:
    def test_m13_doc_bisection_printf(self, evidence):
        r = sh("printf '0. 1. 1.E-5\\n' | build/bin/ch01_p01_bisection")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="printf '0. 1. 1.E-5\\n' | build/bin/ch01_p01_bisection")
        lines = r.stdout.splitlines()
        assert r.returncode == 0
        assert lines[0] == " AT X =   .5000000 F(X) =   -.100576"
        assert lines[1] == " AT X =   .2500000 F(X) =    .396117"
        assert lines[-2] == " AT X =   .4435729 F(X) =    .000000"
        assert lines[-1] == " THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED."

    def test_m13_doc_bairstow_sample_input(self, evidence):
        r = sh("build/bin/ch01_p02_bairstow < sample_input.txt")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="build/bin/ch01_p02_bairstow < sample_input.txt")
        assert r.returncode == 0
        tail = "\n".join(r.stdout.rstrip("\n").splitlines()[-5:])
        assert tail == (" THE QUADRATIC FACTORS ARE-\n\n X**2 +    4.19999 X +   -2.09999\n"
                        " X**2 +    3.30000 X +   -6.20000\n    1.00000X +  -10.30000")

    def test_m13_doc_trace_bisection(self, evidence):
        r = sh("printf '0. 1. 1.E-5\\n' | build/bin/ch01_p01_bisection --trace")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="... | ch01_p01_bisection --trace")
        lines = r.stdout.splitlines()
        assert r.returncode == 0
        assert lines[0] == ("STEP,k=1,x1=0.00000000000000000E+000,x2=1.00000000000000000E+000,"
                            "x=5.00000000000000000E-001,fx=-1.00576112000487550E-001")
        assert lines[-1] == ("RESULT,value=4.43572998046875000E-001,converged=T,iterations=15,root_at_endpoint=F,"
                             "fx1=1.00000000000000000E+000,fx2=-6.32120558828557333E-001")
        assert all(l.startswith(("STEP,", "RESULT,")) for l in lines)

    def test_m13_doc_trace_no_sign_change(self, evidence):
        r = sh("printf '0.5 1. 1.E-5\\n' | build/bin/ch01_p01_bisection --trace")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="printf '0.5 1. 1.E-5\\n' | ch01_p01_bisection --trace")
        assert r.returncode == 2
        assert r.stdout.strip() == ("ERROR,code=BRACKET,message=FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF "
                                    "OPPOSITE SIGNS. CHANGE INPUTS.")

    def test_m13_doc_book_error_exit_1(self, evidence):
        r = sh("printf '0.5 1. 1.E-5\\n' | build/bin/ch01_p01_bisection")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="printf '0.5 1. 1.E-5\\n' | ch01_p01_bisection")
        assert r.returncode == 1
        assert "FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS." in r.stdout

    def test_m13_doc_preset2_bisection(self, evidence):
        r = sh("printf '1. 2. 1.E-5\\n' | build/bin/ch01_p01_bisection --preset 2")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="printf '1. 2. 1.E-5\\n' | ch01_p01_bisection --preset 2")
        assert r.returncode == 0
        assert r.stdout.splitlines()[-1] == " THE VALUE, X =  1.3247184 IS A ROOT.  18 ITERATIONS WERE REQUIRED."

    def test_m13_doc_preset3_simpson(self, evidence):
        r = sh("printf '1.0 10\\n' | build/bin/ch03_p01_simpson --preset 3")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="printf '1.0 10\\n' | ch03_p01_simpson --preset 3")
        assert r.returncode == 0
        assert " VALUE OF SINE INTEGRAL FROM X = 0 TO X =  1.00 IS  .7853981 WITH  10 PANELS" in r.stdout.splitlines()

    @pytest.mark.parametrize("exe", DRIVERS)
    def test_m13_doc_driver_verbose_heading(self, exe, evidence):
        cmd = dict((e, c) for c, e in _fortran_commands())[exe] + " --verbose"
        r = sh(cmd)
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=cmd)
        assert r.returncode == 0
        assert "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)" in r.stdout

    @pytest.mark.parametrize("exe", DRIVERS)
    def test_m13_doc_driver_help(self, exe, evidence):
        r = run_driver(exe, "", "--help")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=f"build/bin/{exe} --help")
        assert r.returncode == 0
        out = r.stdout.lower()
        for flag in ("--trace", "--verbose", "--help"):
            assert flag in out
        has_preset = exe not in ("ch01_p02_bairstow", "lagrange_interpolation")
        assert ("--preset" in out) == has_preset

    @pytest.mark.parametrize("exe", ("ch01_p02_bairstow", "lagrange_interpolation"))
    def test_m13_doc_preset_rejected_on_data_drivers(self, exe, evidence):
        cmd = dict((e, c) for c, e in _fortran_commands())[exe] + " --preset 2"
        r = sh(cmd)
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command=cmd)
        assert r.returncode != 0

    def test_m13_doc_single_central_difference(self, evidence):
        r = sh("printf '0.0 0.1\\n' | build/single/bin/ch04_p01_central_difference")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="printf '0.0 0.1\\n' | build/single/bin/ch04_p01_central_difference")
        assert r.returncode == 0
        tail = [l for l in r.stdout.splitlines() if l.strip()][-4:]
        assert tail == ["  1.0E-07      8.4703277E-15      2.0000000E+00",
                        "  1.0E-08      0.0000000E-99      2.0000000E+00",
                        "  1.0E-09      0.0000000E-99      2.0000000E+00",
                        "  1.0E-10      0.0000000E-99      2.0000000E+00"]

    def test_m13_doc_single_precision_digits(self, evidence):
        bis = run_driver("ch01_p01_bisection", "0. 1. 1.E-5\n", bin_dir=SINGLE_BIN_DIR)
        sim = run_driver("ch03_p01_simpson", "5.0 100\n", bin_dir=SINGLE_BIN_DIR)
        rom = run_driver("ch03_p02_romberg", "15.0 2.E-7\n", bin_dir=SINGLE_BIN_DIR)
        out = bis.stdout + sim.stdout + rom.stdout
        evidence(exit_code=max(bis.returncode, sim.returncode, rom.returncode), stdout=out, command="build/single/bin bisection/simpson/romberg")
        assert " AT X =   .4435729 F(X) =    .000001" in bis.stdout
        assert "IS 1.5499314 WITH 100 PANELS" in sim.stdout
        assert "VALUE IS  1.6181944," in rom.stdout

    def test_m13_doc_python_compare_simpson(self, evidence):
        r = run_cli("run", "ch03_p01", "--engine", "compare")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="uv run gerald-na run ch03_p01 --engine compare")
        assert r.returncode == 0
        lines = r.stdout.splitlines()
        assert re.fullmatch(r"=== python: OK \([\d.]+ ms\)", lines[0])
        assert lines[1] == "VALUE OF SINE INTEGRAL FROM X = 0 TO X =  5.00 IS 1.5499312 WITH 100 PANELS"
        assert re.fullmatch(r"=== fortran: OK \([\d.]+ ms\)", lines[2])
        assert lines[3] == lines[1]
        assert lines[4] == "=== differences"
        assert lines[5] == "same outcome: True  same iterations: True"
        assert re.match(r"\s+K: max abs 0\.000e\+00  max rel 0\.000e\+00  first differing row -", lines[6])

    def test_m13_doc_python_expr(self, evidence):
        r = run_cli("run", "ch01_p01", "--expr", "x**3 - 2", "--input", "x1=1", "--input", "x2=2")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="uv run gerald-na run ch01_p01 --expr 'x**3 - 2' --input x1=1 --input x2=2")
        assert r.returncode == 0
        assert r.stdout.splitlines()[-1] == "THE VALUE, X =  1.2599220 IS A ROOT.  18 ITERATIONS WERE REQUIRED."

    def test_m13_doc_python_expr_fortran_refused(self, evidence):
        r = run_cli("run", "ch01_p01", "--expr", "x**3 - 2", "--engine", "fortran")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="gerald-na run ch01_p01 --expr ... --engine fortran")
        assert r.returncode == 2

    def test_m13_doc_python_expr_fortran_names(self, evidence):
        r = run_cli("run", "ch01_p01", "--expr", "EXPF(-X) - SINF(3.1415926*X/2.)")
        evidence(exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr, command="gerald-na run ch01_p01 --expr 'EXPF(-X) - SINF(3.1415926*X/2.)'")
        assert r.returncode == 0
        assert "15 ITERATIONS WERE REQUIRED" in r.stdout


# =========================================================================== Web interface walkthrough
@pytest.mark.usefixtures("server")
class TestWebWalkthrough:
    def test_m13_web_home_grouping(self, evidence):
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:4000], endpoint="/", method="GET")
        assert resp.status_code == 200
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        positions = [t.find(s) for s in ("Chapter 1: Solution of Nonlinear Equations", "Chapter 3: Numerical Integration",
                                         "Chapter 4: Numerical Differentiation", "Book reference unconfirmed")]
        assert all(p >= 0 for p in positions) and positions == sorted(positions)
        assert t.find("Lagrangian interpolation") > positions[-1]
        assert "Scan available" in t and "No scan" in t and "Engines: python, fortran, compare" in t

    def test_m13_web_program_page_labels(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/ch01_p01", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:4000], endpoint="/programs/ch01_p01", method="GET")
        assert resp.status_code == 200
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        for label in ("All programs", "Book data card", "Fortran (compiled book driver)", "Compare Python and Fortran",
                      "Custom expression (Python engine only)", "Practice questions", "Your answer",
                      "Original scan", "Legacy OCR text", "Modern Fortran", "Study page",
                      "1: Book: exp(-x) - sin(pi x / 2)", "2: x^3 - x - 1", "3: cos(x) - x",
                      "A custom expression runs on the Python engine only: the Fortran drivers evaluate the catalog "
                      "presets (--preset N), so Fortran and compare are disabled."):
            assert label in t, label

    def test_m13_web_form_fragment(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/ch01_p01/form", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:3000], endpoint="/programs/ch01_p01/form", method="GET")
        assert resp.status_code == 200
        assert 'data-testid="run-form"' in resp.text
        assert re.search(r'name="in_x1"[^>]*\s+value="0\.0"', resp.text, flags=re.S) or 'value="0.0"' in resp.text
        assert 'value="1e-05"' in resp.text

    def test_m13_web_form_fragment_not_found(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/ch09_p09/form", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:1000], endpoint="/programs/ch09_p09/form", method="GET")
        assert resp.status_code == 404

    def test_m13_web_lagrange_add_point(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/lagrange_interpolation", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:3000], endpoint="/programs/lagrange_interpolation", method="GET")
        t = html.unescape(re.sub(r"<[^>]+>", " ", resp.text))
        assert resp.status_code == 200
        assert "Add point" in t and "Remove" in t
        assert "Updated automatically when you add or remove a row of Data pairs X(I), Y(I)." in re.sub(r"\s+", " ", t)
        assert "No scan available for this program" in re.sub(r"\s+", " ", t)

    def test_m13_web_expression_error(self, evidence):
        form = {"engine": "python", "in_x1": "0.", "in_x2": "1.", "in_tol": "1.E-5", "function": "custom", "expression": "x**"}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, headers={"HX-Request": "true"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:3000], request=form, endpoint="/programs/ch01_p01/run", method="POST")
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        assert "EXPRESSION" in t
        assert "syntax error: invalid syntax (at column 3)" in t
        assert re.search(r"Problem at column 3 ?:", t)
        assert "x**\n  ^" in html.unescape(resp.text)

    @pytest.mark.parametrize("expr,msg", [
        ("sin(x", "syntax error: '(' was never closed (at column 4)"),
        ("foo(x)", "unknown function 'foo' (at column 1)"),
        ("x + y", "unknown name 'y'; use the variable x, the constants pi and e, or a supported function (at column 5)"),
    ])
    def test_m13_api_expression_error_messages(self, expr, msg, evidence):
        body = {"engine": "python", "expression": expr}
        resp = requests.post(f"{BASE_URL}/api/programs/ch01_p01/run", json=body, timeout=30)
        evidence(status=resp.status_code, body=resp.text, request=body, endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "EXPRESSION"
        assert msg in resp.json()["error"]["message"]

    def test_m13_api_expression_domain_error(self, evidence):
        body = {"engine": "python", "expression": "log(x - 2)"}
        resp = requests.post(f"{BASE_URL}/api/programs/ch01_p01/run", json=body, timeout=30)
        evidence(status=resp.status_code, body=resp.text, request=body, endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        err = resp.json()["error"]
        assert err["code"] == "EXPRESSION"
        assert "log(-2.0) is outside the function's domain (at x = 0.0)" in err["message"]

    def test_m13_web_compare_agrees(self, evidence):
        form = {"engine": "compare", "in_x1": "0.", "in_x2": "1.", "in_tol": "1.E-5", "function": "1"}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, headers={"HX-Request": "true"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:3000], request=form, endpoint="/programs/ch01_p01/run", method="POST")
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        assert resp.status_code == 200
        assert "The engines agree bit for bit" in t
        assert "Iterations: python 15, fortran 15" in t
        assert "Outcome: python OK, fortran OK" in t

    @pytest.mark.parametrize("form,code,msg", [
        ({"in_x1": "0.5", "in_x2": "1.", "in_tol": "1.E-5", "function": "1"}, "BRACKET",
         "FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF OPPOSITE SIGNS. CHANGE INPUTS."),
    ])
    def test_m13_web_error_result(self, form, code, msg, evidence):
        form = {"engine": "python", **form}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, headers={"HX-Request": "true"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:3000], request=form, endpoint="/programs/ch01_p01/run", method="POST")
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        assert resp.status_code == 200
        assert code in t and msg in t and "No iteration rows." in t

    def test_m13_web_bairstow_non_convergent(self, evidence):
        form = [("engine", "python")] + [("in_a", v) for v in ("0.", "1.", "-17.8", "99.41", "-261.218", "352.611", "-134.106")]
        form += [("in_r1", "0."), ("in_s1", "0."), ("in_test", "1.E-5"), ("in_lim", "4"), ("in_n", "5")]
        resp = requests.post(f"{BASE_URL}/programs/ch01_p02/run", data=form, headers={"HX-Request": "true"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:3000], request=dict(form), endpoint="/programs/ch01_p02/run", method="POST")
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        assert resp.status_code == 200
        assert "NON_CONVERGENT DOES NOT CONVERGE AFTER 4 ITERATIONS" in t
        assert "python engine; the 4 iteration rows computed before the error are shown below." in t
        assert "DOES NOT CONVERGE AFTER    4 ITERATIONS" in html.unescape(resp.text)

    @pytest.mark.parametrize("answer,verdict,needle", [
        ("15", "true", "Your answer matches the computed 15."),
        ("abc", None, "'abc' is not a number (examples: 0.5, 1.E-5)"),
    ])
    def test_m13_web_practice(self, answer, verdict, needle, evidence):
        ep = "/programs/ch01_p01/practice/book-iterations"
        resp = requests.post(f"{BASE_URL}{ep}", data={"answer": answer}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:2000], request={"answer": answer}, endpoint=ep, method="POST")
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resp.text)))
        assert needle in t
        if verdict:
            assert resp.status_code == 200
            assert "Python engine: 15" in t and "Fortran engine: 15" in t

    def test_m13_api_examples(self, evidence):
        lst = requests.get(f"{BASE_URL}/api/programs", timeout=10)
        run = requests.post(f"{BASE_URL}/api/programs/ch01_p01/run", json={"engine": "python", "inputs": {"tol": 0.001}}, timeout=30)
        evidence(status=run.status_code, body=lst.text[:800] + "\n---\n" + run.text[:1500],
                 request={"engine": "python", "inputs": {"tol": 0.001}}, endpoint="/api/programs/ch01_p01/run", method="POST")
        assert lst.status_code == 200
        assert [p["id"] for p in lst.json()] == ["ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02", "ch04_p01", "lagrange_interpolation"]
        assert run.status_code == 200 and run.json()["ok"] is True


# =========================================================================== Troubleshooting env vars
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def alt_server():
    """Start ``gerald-na serve`` with extra env vars on a free port; yields the base URL."""
    procs = []

    def start(env_extra, use_env_port=True):
        port = _free_port()
        env = dict(os.environ)
        env.update(env_extra)
        args = ["uv", "--directory", str(REPO_ROOT / "python"), "run", "--frozen", "gerald-na", "serve"]
        if use_env_port:
            env["GERALD_NA_PORT"] = str(port)
        else:
            env.pop("GERALD_NA_PORT", None)
            args += ["--port", str(port)]
        env["GERALD_NA_HOST"] = "127.0.0.1"
        proc = subprocess.Popen(args, cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        procs.append(proc)
        url = f"http://127.0.0.1:{port}"
        for _ in range(120):
            try:
                if requests.get(f"{url}/healthz", timeout=1).status_code == 200:
                    return url
            except requests.RequestException:
                pass
            if proc.poll() is not None:
                break
            time.sleep(0.25)
        raise RuntimeError(f"alt server on {port} did not start")

    yield start
    for p in procs:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


class TestTroubleshooting:
    def test_m13_trouble_port_env(self, alt_server, evidence):
        url = alt_server({})
        resp = requests.get(f"{url}/healthz", timeout=5)
        evidence(status=resp.status_code, body=resp.text, endpoint=f"{url}/healthz (GERALD_NA_PORT)", method="GET")
        assert resp.status_code == 200 and resp.json()["status"] == "ok"

    def test_m13_trouble_port_option(self, alt_server, evidence):
        url = alt_server({}, use_env_port=False)
        resp = requests.get(f"{url}/healthz", timeout=5)
        evidence(status=resp.status_code, body=resp.text, endpoint=f"{url}/healthz (serve --port)", method="GET")
        assert resp.status_code == 200

    def test_m13_trouble_fortran_unavailable(self, alt_server, tmp_path, evidence):
        empty = tmp_path / "ftrun_empty_bin"
        empty.mkdir()
        url = alt_server({"GERALD_NA_FORTRAN_BIN_DIR": str(empty)})
        hz = requests.get(f"{url}/healthz", timeout=5)
        page = requests.get(f"{url}/programs/ch01_p01", timeout=10)
        home = requests.get(f"{url}/", timeout=10)
        body = {"engine": "fortran"}
        run = requests.post(f"{url}/api/programs/ch01_p01/run", json=body, timeout=30)
        py = requests.post(f"{url}/api/programs/ch01_p01/run", json={"engine": "python"}, timeout=30)
        evidence(status=run.status_code, body=hz.text + "\n---\n" + run.text, request=body,
                 endpoint="/api/programs/ch01_p01/run (GERALD_NA_FORTRAN_BIN_DIR=<empty>)", method="POST")
        assert hz.json()["engines"] == {"python": True, "fortran": False}
        pt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page.text)))
        assert "Unavailable: Fortran driver ch01_p01_bisection is not built in" in pt
        assert "(run `make build-fortran`)" in pt
        ht = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", home.text)))
        assert "Engines: python" in ht and "Engines: python, fortran" not in ht
        assert run.status_code == 503
        assert run.json()["error"]["code"] == "ENGINE_UNAVAILABLE"
        assert run.json()["error"]["message"].startswith("fortran engine unavailable: ")
        assert py.status_code == 200 and py.json()["ok"] is True

    def test_m13_trouble_single_bin_dir_compare(self, alt_server, evidence):
        url = alt_server({"GERALD_NA_FORTRAN_BIN_DIR": "build/single/bin"})
        body = {"engine": "compare"}
        resp = requests.post(f"{url}/api/programs/ch01_p01/run", json=body, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:2500], request=body,
                 endpoint="/api/programs/ch01_p01/run (GERALD_NA_FORTRAN_BIN_DIR=build/single/bin)", method="POST")
        assert resp.status_code == 200
        d = resp.json()
        assert d["matches"] is False
        assert d["same_iterations"] is True and d["iterations"] == [15, 15]
        assert len(d["cells"]) == 15
        assert f"{d['max_abs_diff']:.3e}" == "6.778e-08"

    def test_m13_trouble_run_timeout(self, alt_server, evidence):
        url = alt_server({"GERALD_NA_RUN_TIMEOUT_S": "0.0001"})
        body = {"engine": "fortran"}
        resp = requests.post(f"{url}/api/programs/ch01_p01/run", json=body, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:2000], request=body,
                 endpoint="/api/programs/ch01_p01/run (GERALD_NA_RUN_TIMEOUT_S=0.0001)", method="POST")
        d = resp.json()
        err = d.get("error") or {}
        assert err.get("code") == "FORTRAN_RUN"
        assert "Fortran driver ch01_p01_bisection did not finish within 0.0001 s and was stopped" in err.get("message", "")

    def test_m13_trouble_run_timeout_raised(self, alt_server, evidence):
        url = alt_server({"GERALD_NA_RUN_TIMEOUT_S": "20"})
        body = {"engine": "fortran"}
        resp = requests.post(f"{url}/api/programs/ch01_p01/run", json=body, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:1500], request=body,
                 endpoint="/api/programs/ch01_p01/run (GERALD_NA_RUN_TIMEOUT_S=20)", method="POST")
        assert resp.status_code == 200 and resp.json()["ok"] is True
