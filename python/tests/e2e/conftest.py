"""Playwright e2e fixtures: a live ``gerald-na serve`` for the session, or an external server.

By default the session starts the real application in a subprocess (``gerald-na serve`` on a
free local port, from the repository root), waits for ``GET /healthz`` and stops it at the end.
Set ``GERALD_NA_E2E_BASE_URL`` (for example ``http://127.0.0.1:8000``) to run the tests against a
server that is already running instead; nothing is started or stopped then.

pytest-playwright's ``base_url`` fixture is overridden with the live server's URL, so tests use
relative paths (``page.goto("/programs/ch01_p01")``). Tests marked ``fortran`` are skipped with
an explicit reason when the server reports the Fortran engine unavailable (no drivers in
``build/bin``; the repository-wide ``tests/conftest.py`` also skips them when no driver is built
locally). Browser tests are opt-in: run them with ``make e2e`` or ``pytest -m e2e tests/e2e``.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import pytest

from gerald_na.settings import find_repo_root

BASE_URL_ENV = "GERALD_NA_E2E_BASE_URL"
STARTUP_TIMEOUT_S = 30.0
FORTRAN_UNAVAILABLE = (
    "Fortran engine unavailable on the e2e server: run `make build-fortran` (drivers in build/bin)"
)


@dataclass(frozen=True)
class LiveServer:
    """The server under test: its base URL and the engines its ``/healthz`` reports."""

    url: str
    engines: dict[str, bool]

    def get_json(self, path: str) -> Any:
        """``GET`` a JSON document from the server."""
        with urllib.request.urlopen(f"{self.url}{path}", timeout=10) as response:  # noqa: S310
            return json.load(response)

    def engine_reason(self, program_id: str, engine: str) -> str | None:
        """Why ``engine`` cannot run ``program_id`` on this server, or ``None`` if it can."""
        status = self.get_json(f"/api/programs/{program_id}")["engines"][engine]
        if status["available"]:
            return None
        return f"{engine} engine unavailable for {program_id}: {status['reason']}"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def _healthz(url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{url}/healthz", timeout=2) as response:  # noqa: S310
            data: dict[str, Any] = json.load(response)
            return data if response.status == 200 else None
    except urllib.error.URLError, ConnectionError, TimeoutError:
        return None


def _serve_command(port: int) -> list[str]:
    script = Path(sys.executable).with_name("gerald-na")
    args = ["serve", "--host", "127.0.0.1", "--port", str(port)]
    if script.exists():
        return [str(script), *args]
    return [sys.executable, "-m", "gerald_na.cli", *args]


def _wait_until_healthy(url: str, process: subprocess.Popen[bytes], log: Path) -> dict[str, Any]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"gerald-na serve exited with {process.returncode} before /healthz answered:\n"
                + log.read_text(errors="replace")
            )
        health = _healthz(url)
        if health is not None:
            return health
        time.sleep(0.2)
    raise RuntimeError(
        f"gerald-na serve did not answer {url}/healthz within {STARTUP_TIMEOUT_S:.0f} s:\n"
        + log.read_text(errors="replace")
    )


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@pytest.fixture(scope="session")
def live_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LiveServer]:
    """The application under test, started for the session unless ``GERALD_NA_E2E_BASE_URL``."""
    external = os.environ.get(BASE_URL_ENV, "").strip().rstrip("/")
    if external:
        health = _healthz(external)
        if health is None:
            pytest.fail(f"{BASE_URL_ENV}={external}: GET /healthz did not answer 200")
        yield LiveServer(external, dict(health.get("engines", {})))
        return

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    log = tmp_path_factory.mktemp("e2e-server") / "server.log"
    log_file: IO[bytes]
    with log.open("wb") as log_file:
        process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            _serve_command(port),
            cwd=find_repo_root(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            health = _wait_until_healthy(url, process, log)
            yield LiveServer(url, dict(health.get("engines", {})))
        finally:
            _stop(process)


@pytest.fixture(scope="session")
def base_url(live_server: LiveServer) -> str:
    """pytest-playwright's base URL: the live server, so ``page.goto`` takes relative paths."""
    return live_server.url


@pytest.fixture(autouse=True)
def _skip_fortran_without_engine(request: pytest.FixtureRequest, live_server: LiveServer) -> None:
    """Skip ``fortran``-marked tests when the server under test cannot run the drivers."""
    if request.node.get_closest_marker("fortran") is not None and not live_server.engines.get(
        "fortran", False
    ):
        pytest.skip(FORTRAN_UNAVAILABLE)
