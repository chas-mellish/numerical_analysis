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

REPO_ROOT = Path(__file__).resolve().parents[3]
BIN_DIR = REPO_ROOT / "build" / "bin"
SINGLE_BIN_DIR = REPO_ROOT / "build" / "single" / "bin"
HOST = os.environ.get("GERALD_NA_HOST", "127.0.0.1")
PORT = os.environ.get("GERALD_NA_PORT", "8000")
BASE_URL = f"http://{HOST}:{PORT}"
EVIDENCE_FILE = Path(os.environ.get("FT_EVIDENCE_FILE", "/tmp/ft_evidence.json"))

# Book data cards shared by the real64 and real32 driver tests.
BISECTION_CARD = "0. 1. 1.E-5\n"
BAIRSTOW_CARD = "0. 1. -17.8 99.41 -261.218 352.611 -134.106\n0. 0. 1.E-5 20 5\n"
SIMPSON_CARD = "5.0 100\n"
ROMBERG_CARD = "15.0 2.E-7\n"
LAGRANGE_CARD = "05\n2.3756 1.6\n3.2682 1.9\n4.4571 2.2\n6.0502 2.5\n8.1919 2.8\n5.0\n"

_EVIDENCE: dict[str, dict[str, object]] = {}


def run_driver(name, card, *flags, timeout=20, bin_dir=BIN_DIR):
    """Run a compiled Fortran driver from ``bin_dir`` with ``card`` on stdin."""
    return subprocess.run(
        [str(bin_dir / name), *flags],
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
