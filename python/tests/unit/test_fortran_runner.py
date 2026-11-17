"""``FortranRunner`` error mapping and safety rules, driven by fake driver scripts.

The fake drivers are small ``/bin/sh`` scripts installed in ``tmp_path`` under the catalog's
executable name, so the whitelist logic is exercised exactly as with real binaries. No Fortran
compiler is needed.
"""

import stat
from pathlib import Path

import pytest

from gerald_na.algorithms.bisection import BisectionResult
from gerald_na.engines import FortranRunner, RunRequest
from gerald_na.engines.fortran import DriverRun
from gerald_na.errors import (
    BracketError,
    EngineUnavailableError,
    FortranRunError,
    InputError,
    NonConvergenceError,
    ZeroProductError,
)
from gerald_na.registry import CatalogEntry, get_registry
from gerald_na.settings import Settings

TRACE_OK = """\
STEP,k=1,x1=0.00000000000000000E+000,x2=1.00000000000000000E+000,x=5.00000000000000000E-001,fx=-1.00576112000487550E-001
STEP,k=2,x1=0.00000000000000000E+000,x2=5.00000000000000000E-001,x=2.50000000000000000E-001,fx=3.96117356895129225E-001
RESULT,value=2.50000000000000000E-001,converged=T,iterations=2,root_at_endpoint=F,fx1=1.00000000000000000E+000,fx2=-6.32120558828557333E-001
"""

BOOK_OK = """\
 AT X =   .5000000 F(X) =   -.100576
 AT X =   .2500000 F(X) =    .396117
 THE VALUE, X =   .2500000 IS A ROOT.   2 ITERATIONS WERE REQUIRED.
"""


@pytest.fixture(scope="module")
def entry() -> CatalogEntry:
    return get_registry().get("ch01_p01")


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    return directory


def install(directory: Path, name: str, body: str) -> Path:
    """Write an executable ``/bin/sh`` script."""
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def driver(trace: str, trace_status: int, book: str = "", book_status: int = 0) -> str:
    """A fake driver: ``trace`` with ``--trace``, otherwise ``book``; records argv and stdin."""
    return f"""\
here=$(dirname "$0")
printf '%s\\n' "$*" >> "$here/argv.log"
cat > "$here/stdin.log"
case " $* " in
  *" --trace "*) cat <<'EOF'
{trace}EOF
  exit {trace_status};;
esac
case " $* " in
  *" --verbose "*) cat <<'EOF'
{book}
 VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)
EOF
  exit {book_status};;
esac
cat <<'EOF'
{book}EOF
exit {book_status}
"""


def runner(bin_dir: Path, **kwargs: object) -> FortranRunner:
    return FortranRunner(Settings(), bin_dir=bin_dir, registry=get_registry(), **kwargs)  # type: ignore[arg-type]


def book_request(entry: CatalogEntry, **overrides: object) -> RunRequest:
    return RunRequest.for_entry(entry, overrides)


# ---------------------------------------------------------------- success path


def test_success_maps_trace_into_the_result_dataclass(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK))
    outcome = runner(bin_dir).run(entry, book_request(entry, tol=0.5))
    assert outcome.ok, outcome.error
    result = outcome.result
    assert isinstance(result, BisectionResult)
    assert result.iterations == 2
    assert result.value == 0.25
    assert result.converged
    assert result.fx2 == -6.32120558828557333e-001
    assert (result.x1, result.x2, result.tol, result.max_iter) == (0.0, 1.0, 0.5, 25)
    assert outcome.engine == "fortran"
    assert outcome.raw_stdout == BOOK_OK
    assert outcome.book_text == "".join(line[1:] + "\n" for line in BOOK_OK.splitlines())
    assert outcome.trace_text == TRACE_OK
    # stdin is the generated data card; flags are fixed, preset 1 by default
    assert (bin_dir / "stdin.log").read_text(encoding="utf-8") == "0.0 1.0 0.5\n"
    assert (bin_dir / "argv.log").read_text(encoding="utf-8").splitlines() == [
        "--trace --preset 1",
        "--preset 1",
    ]


def test_preset_and_verbose_flags(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK))
    request = RunRequest.for_entry(entry, {"x1": 1.0, "x2": 2.0}, preset=3, verbose=True)
    outcome = runner(bin_dir).run(entry, request)
    assert outcome.preset == 3
    assert (bin_dir / "argv.log").read_text(encoding="utf-8").splitlines() == [
        "--trace --preset 3",
        "--preset 3",
        "--verbose --preset 3",
    ]
    assert outcome.verbose_text == "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)\n"
    assert outcome.book_text.startswith("AT X =")


def test_execute_returns_the_raw_run(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK))
    run = runner(bin_dir).execute(entry, "0. 1. 1.E-5\n", trace=True, preset=2)
    assert isinstance(run, DriverRun)
    assert run.returncode == 0
    assert run.stdout == TRACE_OK
    assert run.flags == ("--trace", "--preset", "2")
    assert run.describe() == f"{entry.files.fortran_executable} --trace --preset 2"
    assert (bin_dir / "stdin.log").read_text(encoding="utf-8") == "0. 1. 1.E-5\n"


# ---------------------------------------------------------------- typed errors (exit 2)


@pytest.mark.parametrize(
    ("record", "error_type", "steps"),
    [
        (
            "ERROR,code=BRACKET,message=FUNCTION VALUES WITH INITIAL X VALUES ARE NOT OF "
            "OPPOSITE SIGNS. CHANGE INPUTS.",
            BracketError,
            0,
        ),
        ("ERROR,code=ZERO_PRODUCT,message=ERROR.", ZeroProductError, 2),
        (
            "ERROR,code=NON_CONVERGENT,message=NON-CONVERGENT IN 25 ITERATIONS.",
            NonConvergenceError,
            2,
        ),
        ("ERROR,code=INPUT,message=F(X) is not a finite number at X = 1.0", InputError, 2),
    ],
)
def test_error_records_become_typed_errors(
    entry: CatalogEntry, bin_dir: Path, record: str, error_type: type, steps: int
) -> None:
    rows = "".join(TRACE_OK.splitlines(keepends=True)[:steps])
    book = " AT X =   .5000000 F(X) =   -.100576\n MESSAGE\n"
    install(bin_dir, entry.files.fortran_executable, driver(rows + record + "\n", 2, book, 1))
    outcome = runner(bin_dir).run(entry, book_request(entry))
    assert not outcome.ok
    assert type(outcome.error) is error_type
    assert outcome.error is not None
    assert outcome.error.message == record.partition("message=")[2]
    assert len(outcome.steps) == steps
    assert outcome.book_text == "AT X =   .5000000 F(X) =   -.100576\nMESSAGE\n"
    assert outcome.error.book_output == outcome.book_text


# ---------------------------------------------------------------- engine failures


@pytest.mark.parametrize(
    ("trace", "status", "match"),
    [
        ("hello, I am not a trace\n", 0, "malformed trace line 1"),
        ("", 0, "empty trace"),
        ("STEP,k=1,x1=0.0,x2=1.0,x=0.5,fx=1.0\n", 0, "no RESULT or ERROR"),
        ("ERROR,code=BRACKET,message=x\n", 0, "status 0 after an ERROR"),
        (TRACE_OK, 2, "status 2 without an ERROR"),
        ("ERROR,code=MELTDOWN,message=x\n", 2, "unknown trace error code 'MELTDOWN'"),
        (TRACE_OK, 3, "exited with status 3"),
        (TRACE_OK, 1, "exited with status 1"),
        ("STEP,k=1,x=0.5\nRESULT,value=0.5,converged=T,iterations=1\n", 0, "STEP keys"),
    ],
)
def test_protocol_violations_are_fortran_run_errors(
    entry: CatalogEntry, bin_dir: Path, trace: str, status: int, match: str
) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(trace, status, BOOK_OK))
    outcome = runner(bin_dir).run(entry, book_request(entry))
    assert isinstance(outcome.error, FortranRunError)
    assert outcome.status == "FORTRAN_RUN"
    assert match in outcome.error.message


def test_stderr_is_quoted_on_a_crash(entry: CatalogEntry, bin_dir: Path) -> None:
    install(
        bin_dir, entry.files.fortran_executable, "echo 'Fortran runtime error: boom' >&2\nexit 3\n"
    )
    outcome = runner(bin_dir).run(entry, book_request(entry))
    assert isinstance(outcome.error, FortranRunError)
    assert "Fortran runtime error: boom" in outcome.error.message


def test_killed_by_a_signal(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, "cat > /dev/null\nkill -SEGV $$\n")
    outcome = runner(bin_dir).run(entry, book_request(entry))
    assert isinstance(outcome.error, FortranRunError)
    assert "killed by signal" in outcome.error.message


def test_bad_book_mode_status(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK, 5))
    outcome = runner(bin_dir).run(entry, book_request(entry))
    assert isinstance(outcome.error, FortranRunError)
    assert "--preset 1 exited with status 5" in outcome.error.message


def test_timeout_stops_the_driver(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, "exec sleep 30\n")
    outcome = runner(bin_dir, timeout_s=0.3).run(entry, book_request(entry))
    assert isinstance(outcome.error, FortranRunError)
    assert "did not finish within 0.3 s" in outcome.error.message
    assert outcome.elapsed_ms < 10_000


def test_timeout_comes_from_settings(clean_env: pytest.MonkeyPatch, bin_dir: Path) -> None:
    clean_env.setenv("GERALD_NA_RUN_TIMEOUT_S", "1.5")
    assert FortranRunner(Settings(), bin_dir=bin_dir).timeout_s == 1.5
    with pytest.raises(ValueError, match="timeout_s"):
        FortranRunner(Settings(), bin_dir=bin_dir, timeout_s=0)
    with pytest.raises(ValueError, match="max_output_bytes"):
        FortranRunner(Settings(), bin_dir=bin_dir, max_output_bytes=0)


def test_output_size_is_limited(entry: CatalogEntry, bin_dir: Path) -> None:
    install(
        bin_dir,
        entry.files.fortran_executable,
        "cat > /dev/null\ni=0\n"
        "while [ $i -lt 200 ]; do echo 'STEP,k=1,x1=0.0,x2=1.0,x=0.5,fx=1.0'; i=$((i+1)); done\n",
    )
    outcome = runner(bin_dir, max_output_bytes=1000).run(entry, book_request(entry))
    assert isinstance(outcome.error, FortranRunError)
    assert "more than the limit of 1000" in outcome.error.message


def test_driver_environment_is_reduced(
    entry: CatalogEntry, bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GFORTRAN_CONVERT_UNIT", "big_endian")
    install(
        bin_dir,
        entry.files.fortran_executable,
        'cat > /dev/null\nenv > "$(dirname "$0")/env.log"\nexit 3\n',
    )
    runner(bin_dir).execute(entry, "0 1 1e-5\n")
    env = (bin_dir / "env.log").read_text(encoding="utf-8")
    assert "GFORTRAN_CONVERT_UNIT" not in env
    assert "LC_ALL=C" in env


# ---------------------------------------------------------------- whitelist and availability


def test_missing_binary_is_engine_unavailable(entry: CatalogEntry, bin_dir: Path) -> None:
    fortran = runner(bin_dir)
    assert not fortran.is_available(entry)
    assert not fortran.any_available()
    with pytest.raises(EngineUnavailableError, match="not built"):
        fortran.run(entry, book_request(entry))


def test_non_executable_file_is_unavailable(entry: CatalogEntry, bin_dir: Path) -> None:
    (bin_dir / entry.files.fortran_executable).write_text("#!/bin/sh\n", encoding="utf-8")
    with pytest.raises(EngineUnavailableError, match="not built"):
        runner(bin_dir).executable_path(entry)


def test_whitelist_rejects_forged_entries(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, "evil", 'touch "$(dirname "$0")/pwned"\n')
    forged = entry.model_copy(
        update={"files": entry.files.model_copy(update={"fortran_executable": "evil"})}
    )
    fortran = runner(bin_dir)
    assert "evil" not in fortran.whitelist()
    assert entry.files.fortran_executable in fortran.whitelist()
    with pytest.raises(EngineUnavailableError, match="not a catalog entry"):
        fortran.run(forged, book_request(entry))
    stranger = forged.model_copy(update={"id": "ch99_p99"})
    with pytest.raises(EngineUnavailableError, match="not a catalog entry"):
        fortran.execute(stranger, "")
    assert not (bin_dir / "pwned").exists()


def test_available_when_the_driver_exists(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK))
    install(bin_dir, "not_in_catalog", "exit 0\n")
    fortran = runner(bin_dir, label="fortran (fake)")
    assert fortran.is_available(entry)
    assert fortran.any_available()
    assert fortran.label == "fortran (fake)"
    assert fortran.bin_dir == bin_dir


def test_relative_bin_dir_resolves_under_the_repo_root(repo_root: Path) -> None:
    fortran = FortranRunner(Settings(), bin_dir="build/single/bin")
    assert fortran.bin_dir == repo_root / "build" / "single" / "bin"
    assert FortranRunner(Settings()).bin_dir == Settings().fortran_bin_path


def test_custom_expressions_are_refused(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK))
    request = RunRequest.for_entry(entry, expression="x - 0.3")
    with pytest.raises(InputError, match="only on the Python engine"):
        runner(bin_dir).run(entry, request)
    assert not (bin_dir / "argv.log").exists()


def test_inputs_are_validated_before_the_driver_runs(entry: CatalogEntry, bin_dir: Path) -> None:
    install(bin_dir, entry.files.fortran_executable, driver(TRACE_OK, 0, BOOK_OK))
    with pytest.raises(InputError, match="not a finite number"):
        runner(bin_dir).run(entry, book_request(entry, x1=float("inf")))
    with pytest.raises(InputError, match="above the maximum"):
        runner(bin_dir).run(entry, book_request(entry, x2=1e9))
    assert not (bin_dir / "argv.log").exists()
