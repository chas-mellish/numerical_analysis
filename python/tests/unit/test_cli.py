"""``gerald-na`` command-line interface."""

import json
from pathlib import Path
from typing import Any

import pytest

from gerald_na import __version__, cli
from gerald_na.errors import InputError


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"gerald-na {__version__}"


def test_help_lists_serve(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "usage: gerald-na" in out
    assert "serve" in out


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 0
    assert "usage: gerald-na" in capsys.readouterr().out


def test_unknown_command_is_an_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["frobnicate"])
    assert exit_info.value.code == 2


def _capture_uvicorn(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    import uvicorn

    calls: dict[str, Any] = {}

    def fake_run(app: str, **kwargs: Any) -> None:
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    return calls


def test_serve_uses_settings_defaults(clean_env: pytest.MonkeyPatch) -> None:
    calls = _capture_uvicorn(clean_env)
    assert cli.main(["serve"]) == 0
    assert calls == {
        "app": "gerald_na.web.app:create_app",
        "factory": True,
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
    }


def test_serve_options_override_settings(clean_env: pytest.MonkeyPatch) -> None:
    calls = _capture_uvicorn(clean_env)
    clean_env.setenv("GERALD_NA_PORT", "9300")
    assert cli.main(["serve", "--host", "0.0.0.0", "--reload"]) == 0  # noqa: S104
    assert calls["host"] == "0.0.0.0"  # noqa: S104
    assert calls["port"] == 9300
    assert calls["reload"] is True
    assert cli.main(["serve", "--port", "9400"]) == 0
    assert calls["port"] == 9400


# ---------------------------------------------------------------- gerald-na run


def test_run_prints_the_book_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "ch01_p01"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "AT X =   .5000000 F(X) =   -.100576"
    assert out.endswith("THE VALUE, X =   .4435729 IS A ROOT.  15 ITERATIONS WERE REQUIRED.\n")


def test_run_with_inputs_preset_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "run",
        "ch01_p01",
        "--preset",
        "2",
        "--input",
        "x1=1.",
        "--input",
        "x2=2",
        "--trace-json",
    ]
    assert cli.main(argv) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["engine"] == "python"
    assert data["preset"] == 2
    assert data["inputs"] == {"x1": 1.0, "x2": 2.0, "tol": 1e-5}
    assert data["result"]["iterations"] == 18
    assert len(data["steps"]) == 18


def test_run_custom_expression(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "ch01_p01", "--expr", "x - 0.25"]) == 0
    assert "IS A ROOT.   2 ITERATIONS" in capsys.readouterr().out


def test_run_error_path_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "ch01_p01", "--input", "x1=2", "--input", "x2=3"]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("FUNCTION VALUES WITH INITIAL X VALUES")
    assert "BRACKET" in captured.err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["run", "ch99_p99"], "unknown program"),
        (["run", "ch01_p01", "--input", "x9=1"], "unknown input"),
        (["run", "ch01_p01", "--input", "x1"], "NAME=VALUE"),
        (["run", "ch01_p01", "--input", "x1=nan"], "not a Fortran real"),
        (["run", "ch01_p01", "--input", "x1=1,2"], "takes one number"),
        (["run", "ch01_p01", "--input", "tol=5"], "above the maximum"),
        (["run", "ch01_p01", "--preset", "7"], "unknown preset"),
        (["run", "ch01_p01", "--preset", "1", "--expr", "x"], "either a preset"),
        (["run", "ch01_p01", "--expr", "import os"], "error:"),
        (["run", "ch01_p01", "--engine", "fortran", "--expr", "x"], "only on the Python engine"),
    ],
)
def test_run_invalid_requests_exit_2(
    capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    assert cli.main(argv) == 2
    assert message in capsys.readouterr().err


def test_run_fortran_without_binaries_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert cli.main(["run", "ch01_p01", "--engine", "fortran", "--bin-dir", str(tmp_path)]) == 2
    assert "not built" in capsys.readouterr().err
    assert cli.main(["run", "ch01_p01", "--engine", "compare", "--bin-dir", str(tmp_path)]) == 2


def test_parse_input_text_lists_and_points() -> None:
    from gerald_na.registry import load_entry

    fixture = Path(__file__).parent / "fixtures" / "registry" / "lagrange_like.toml"
    entry = load_entry(fixture)
    points = next(i for i in entry.inputs if i.type == "point_list")
    integer = next(i for i in entry.inputs if i.type == "int")
    assert cli.parse_input_text(points, "1,2 3.,4.E0") == [[1.0, 2.0], [3.0, 4.0]]
    assert cli.parse_input_text(integer, "7") == 7
    with pytest.raises(InputError, match="x,y pairs"):
        cli.parse_input_text(points, "1,2,3")
    with pytest.raises(InputError, match="not an integer"):
        cli.parse_input_text(integer, "7.5")


@pytest.mark.fortran
def test_run_fortran_and_compare(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "ch01_p01", "--engine", "fortran"]) == 0
    assert capsys.readouterr().out.endswith("15 ITERATIONS WERE REQUIRED.\n")
    assert cli.main(["run", "ch01_p01", "--engine", "compare"]) == 0
    out = capsys.readouterr().out
    assert "=== python: OK" in out
    assert "=== fortran: OK" in out
    assert "same outcome: True  same iterations: True" in out
    assert cli.main(["run", "ch01_p01", "--engine", "compare", "--trace-json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["matches"] is True
    assert report["engines"] == ["python", "fortran"]
