"""``gerald-na`` command-line interface."""

from typing import Any

import pytest

from gerald_na import __version__, cli


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
