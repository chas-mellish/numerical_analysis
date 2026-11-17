"""Shared helpers for the functional tests of gerald_na (target app, milestone 1).

The tests run against:
* the compiled Fortran drivers in ``build/bin`` (stdin data cards, exit codes),
* the ``gerald-na`` console script (``uv --directory python run gerald-na``),
* the live server started by the lifecycle ``run`` script (GERALD_NA_HOST/PORT).

Every test stores its evidence (actual output, status / exit code) in
``FT_EVIDENCE_FILE`` (default /tmp/ft_evidence.json) so results can be recorded verbatim.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(os.environ.get("WORKSPACE_DIR", "/l2l/workspace")) / "numerical_analysis"
BIN_DIR = REPO_ROOT / "build" / "bin"
HOST = os.environ.get("GERALD_NA_HOST", "127.0.0.1")
PORT = os.environ.get("GERALD_NA_PORT", "8000")
BASE_URL = f"http://{HOST}:{PORT}"
EVIDENCE_FILE = Path(os.environ.get("FT_EVIDENCE_FILE", "/tmp/ft_evidence.json"))

_EVIDENCE: dict[str, dict[str, object]] = {}


def run_driver(name, card, *flags, timeout=20):
    """Run a compiled Fortran driver with ``card`` on stdin."""
    return subprocess.run(
        [str(BIN_DIR / name), *flags],
        input=card,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_cli(*args, timeout=120):
    """Run the ``gerald-na`` console script from the repository's uv project."""
    return subprocess.run(
        ["uv", "--directory", str(REPO_ROOT / "python"), "run", "--frozen", "gerald-na", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        cwd=str(REPO_ROOT),
    )


def api_run(program_id, body, timeout=30):
    return requests.post(f"{BASE_URL}/api/programs/{program_id}/run", json=body, timeout=timeout)


def trace_records(text, kind):
    """Parse ``KIND,key=value,...`` trace lines into dicts."""
    out = []
    for line in text.splitlines():
        if not line.startswith(kind + ","):
            continue
        fields = {}
        for part in line.split(",")[1:]:
            key, _, value = part.partition("=")
            fields[key] = value
        out.append(fields)
    return out


@pytest.fixture
def evidence(request):
    """Collect evidence for the current test: call ``evidence(key=value, ...)``."""
    record = _EVIDENCE.setdefault(request.node.name, {})

    def add(**kwargs):
        record.update(kwargs)

    return add


@pytest.fixture(scope="session")
def server():
    """Confirm the live server is up (the lifecycle run script must be running)."""
    resp = requests.get(f"{BASE_URL}/healthz", timeout=5)
    assert resp.status_code == 200, resp.text
    return BASE_URL


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        name = report.nodeid.split("::")[-1]
        rec = _EVIDENCE.setdefault(name, {})
        rec["outcome"] = report.outcome
        rec["duration_ms"] = round(report.duration * 1000, 1)
        if report.outcome == "failed":
            rec["failure"] = str(report.longrepr)[-1500:]


def pytest_sessionfinish(session, exitstatus):
    EVIDENCE_FILE.write_text(json.dumps(_EVIDENCE, indent=1, default=str), encoding="utf-8")
