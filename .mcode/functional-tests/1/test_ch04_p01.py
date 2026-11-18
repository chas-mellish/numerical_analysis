"""Functional tests of Chapter 4 Program 1 (derivatives by central differences), ch04_p01.

Covers the Fortran drivers (real64 build/bin and real32 build/single/bin), the ``gerald-na`` CLI
(python / fortran / compare engines) and the live web app (JSON API, practice checks, file
routes, study page). Expected values come from catalog/ch04_p01_central_difference.toml and the
program header (book p. 90): book card ``0.0 0.1``, F(X) = X**2*EXP(X), ten rows, H = 0.1*H.
"""

import pytest
import requests

from conftest import BASE_URL, SINGLE_BIN_DIR, api_run, run_cli, run_driver, trace_records

DRIVER = "ch04_p01_central_difference"
CARD = "0.0       0.1\n"
HEADING = "DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS"
# Real64 book text (carriage-control column dropped, as returned by the engines' book_text).
BOOK_TEXT_REAL64 = (
    "DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS\n"
    "AT X =  0.00\n"
    "\n"
    "   H             DX                 DDX\n"
    "\n"
    " 1.0E-01      1.0016675E-02      2.0100083E+00\n"
    " 1.0E-02      1.0000166E-04      2.0001000E+00\n"
    " 1.0E-03      1.0000001E-06      2.0000010E+00\n"
    " 1.0E-04      1.0000000E-08      2.0000000E+00\n"
    " 1.0E-05      1.0000000E-10      2.0000000E+00\n"
    " 1.0E-06      9.9999999E-13      2.0000000E+00\n"
    " 1.0E-07      9.9999999E-15      2.0000000E+00\n"
    " 1.0E-08      9.9999999E-17      2.0000000E+00\n"
    " 1.0E-09      1.0000000E-18      2.0000000E+00\n"
    " 1.0E-10      1.0000000E-20      2.0000000E+00\n"
)
FIRST_ROW = " 1.0E-01      1.0016675E-02      2.0100083E+00"
# Book golden values (tolerances from the catalog [[expected]] steps, real64).
BOOK_ROWS = [
    (1.0e-1, 1.0016675e-2, 2.0100083), (1.0e-2, 1.0000150e-4, 2.0000999),
    (1.0e-3, 9.9995000e-7, 2.0000009), (1.0e-4, 1.0000000e-8, 2.0000000),
    (1.0e-5, 9.9500000e-11, 1.9999999), (1.0e-6, 9.5000000e-13, 1.9999999),
    (1.0e-7, 5.0000000e-15, 1.9999999), (1.0e-8, 0.0, 2.0000000),
    (1.0e-9, 0.0, 2.0000000), (1.0e-10, 0.0, 2.0000000),
]
TOL64 = {"h": 1.0e-12, "dx": 2.0e-9, "ddx": 2.0e-7}
TOL32 = {"h": 1.0e-8, "dx": 1.0e-8, "ddx": 1.0e-6}
RUN_EP = "/api/programs/ch04_p01/run"


def _strip_cc(text):
    """Drop the carriage-control column of the driver's raw stdout."""
    return "".join(line[1:] + "\n" if line else "\n" for line in text.split("\n")[:-1])


def _check_rows(rows, tol):
    assert len(rows) == 10
    for k, ((h, dx, ddx), row) in enumerate(zip(BOOK_ROWS, rows, strict=True), start=1):
        assert int(row["k"]) == k
        assert abs(float(row["h"]) - h) <= tol["h"], (k, row)
        assert abs(float(row["dx"]) - dx) <= tol["dx"], (k, row)
        assert abs(float(row["ddx"]) - ddx) <= tol["ddx"], (k, row)


# ----------------------------------------------------------------------------- Fortran driver
class TestCh04Driver:
    def test_ch04_driver_book_card(self, evidence):
        res = run_driver(DRIVER, CARD)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=CARD)
        assert res.returncode == 0
        assert _strip_cc(res.stdout) == BOOK_TEXT_REAL64

    def test_ch04_driver_trace(self, evidence):
        res = run_driver(DRIVER, CARD, "--trace")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=CARD, args="--trace")
        assert res.returncode == 0
        steps = trace_records(res.stdout, "STEP")
        _check_rows(steps, TOL64)
        (result,) = trace_records(res.stdout, "RESULT")
        assert result["converged"] == "T" and result["iterations"] == "10"
        assert float(result["fo"]) == 0.0
        assert abs(float(result["first_dx"]) - 1.0016675e-2) < 1e-9
        assert abs(float(result["first_ddx"]) - 2.0100083) < 1e-7
        assert abs(float(result["last_ddx"]) - 2.0) < 1e-12
        assert abs(float(result["value"]) - 1.0000000031710762e-20) < 1e-30
        assert float(result["value"]) == float(steps[-1]["dx"])

    def test_ch04_driver_preset_sin(self, evidence):
        card = "1.0 0.1\n"
        res = run_driver(DRIVER, card, "--trace", "--preset", "2")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card,
                 args="--trace --preset 2")
        assert res.returncode == 0
        (result,) = trace_records(res.stdout, "RESULT")
        assert abs(float(result["first_ddx"]) - (-0.8407699926874178)) < 5e-8
        assert abs(float(result["first_dx"]) - 0.5394022521697) < 1e-9  # sin(.1)/.1*cos(1)

    def test_ch04_driver_preset_log10(self, evidence):
        card = "0.19 0.02\n"
        res = run_driver(DRIVER, card, "--trace", "--preset", "3")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card,
                 args="--trace --preset 3")
        assert res.returncode == 0
        (result,) = trace_records(res.stdout, "RESULT")
        assert abs(float(result["first_dx"]) - 2.2942593338911355) < 5e-7
        assert abs(float(result["value"]) - 2.2857604697890097) < 5e-9

    def test_ch04_driver_verbose(self, evidence):
        book = run_driver(DRIVER, CARD)
        res = run_driver(DRIVER, CARD, "--verbose")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=CARD, args="--verbose")
        assert res.returncode == 0
        assert res.stdout.startswith(book.stdout)
        assert "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)" in res.stdout
        assert "FO = F(X)" in res.stdout and "ROW 10:" in res.stdout

    def test_ch04_driver_help(self, evidence):
        res = run_driver(DRIVER, "", "--help")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args="--help")
        assert res.returncode == 0
        assert "usage: ch04_p01_central_difference" in res.stdout and "--preset" in res.stdout

    @pytest.mark.parametrize("card", ["0 0\n", "0 -1\n"], ids=["h_zero", "h_negative"])
    def test_ch04_driver_h_not_positive(self, card, evidence):
        res = run_driver(DRIVER, card)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card)
        assert res.returncode == 1
        assert HEADING not in res.stdout  # rejected before the heading
        assert "H must be a positive finite number" in res.stderr

    def test_ch04_driver_h_not_positive_trace(self, evidence):
        card = "0 -1\n"
        res = run_driver(DRIVER, card, "--trace")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card, args="--trace")
        assert res.returncode == 2
        assert res.stdout.startswith("ERROR,code=INPUT,message=")

    def test_ch04_driver_non_finite_x(self, evidence):
        card = "nan 0.1\n"
        res = run_driver(DRIVER, card)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card)
        assert res.returncode == 1
        assert HEADING not in res.stdout
        assert "finite" in res.stderr

    def test_ch04_driver_malformed_card(self, evidence):
        card = "abc\n"
        res = run_driver(DRIVER, card)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card)
        assert res.returncode == 1
        assert "could not read the data card" in res.stderr

    def test_ch04_driver_unknown_preset(self, evidence):
        res = run_driver(DRIVER, CARD, "--preset", "9")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=CARD, args="--preset 9")
        assert res.returncode == 1
        assert "unknown preset 9" in res.stderr

    def test_ch04_driver_non_finite_f_first_row(self, evidence):
        card = "0.01 0.1\n"  # LOG10(X - H) with X - H < 0
        res = run_driver(DRIVER, card, "--trace", "--preset", "3")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card,
                 args="--trace --preset 3")
        assert res.returncode == 2
        assert trace_records(res.stdout, "STEP") == []
        assert "ERROR,code=INPUT,message=F(X-H) is not a finite number" in res.stdout

    def test_ch04_driver_non_finite_mid_run(self, evidence):
        card = "695 0.1\n"  # DDX overflows at row 9 (round-off / H**2)
        res = run_driver(DRIVER, card, "--trace")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=card, args="--trace")
        assert res.returncode == 2
        assert len(trace_records(res.stdout, "STEP")) == 8
        assert "ERROR,code=INPUT" in res.stdout and "(row 9)" in res.stdout
        book = run_driver(DRIVER, card)
        assert book.returncode == 1
        assert HEADING in book.stdout and "(row 9)" in book.stderr
        assert len([ln for ln in book.stdout.splitlines() if ln.startswith("  1.0E-")]) == 8

    def test_ch04_single_precision_driver(self, evidence):
        res = run_driver(DRIVER, CARD, "--trace", bin_dir=SINGLE_BIN_DIR)
        book = run_driver(DRIVER, CARD, bin_dir=SINGLE_BIN_DIR)
        evidence(stdout=book.stdout + res.stdout, stderr=res.stderr, exit_code=res.returncode, stdin=CARD,
                 args="build/single/bin --trace")
        assert res.returncode == 0 and book.returncode == 0
        _check_rows(trace_records(res.stdout, "STEP"), TOL32)
        # real32 reproduces the book's zero DX for the last three rows.
        assert book.stdout.count("0.0000000E-99") == 3
        assert "1.0016676E-02      2.0100085E+00" in book.stdout


# ----------------------------------------------------------------------------- gerald-na CLI
class TestCh04Cli:
    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_ch04_cli_run_book(self, engine, evidence):
        res = run_cli("run", "ch04_p01", "--engine", engine)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args=f"run ch04_p01 --engine {engine}")
        assert res.returncode == 0
        assert res.stdout == BOOK_TEXT_REAL64

    def test_ch04_cli_run_compare(self, evidence):
        res = run_cli("run", "ch04_p01", "--engine", "compare")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args="run ch04_p01 --engine compare")
        assert res.returncode == 0
        assert "same outcome: True  same iterations: True" in res.stdout
        assert res.stdout.count(FIRST_ROW) == 2

    def test_ch04_cli_verbose_python_matches_fortran(self, evidence):
        py = run_cli("run", "ch04_p01", "--engine", "python", "--verbose")
        ft = run_cli("run", "ch04_p01", "--engine", "fortran", "--verbose")
        evidence(stdout=py.stdout, stderr=py.stderr, exit_code=py.returncode,
                 args="run ch04_p01 --engine python --verbose")
        assert py.returncode == ft.returncode == 0
        assert "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)" in py.stdout
        assert py.stdout == ft.stdout

    @pytest.mark.parametrize("preset,inputs", [("2", ["x=1.0"]), ("3", ["x=0.19", "h=0.02"])],
                             ids=["sin", "log10"])
    def test_ch04_cli_compare_presets(self, preset, inputs, evidence):
        args = ["run", "ch04_p01", "--engine", "compare", "--preset", preset]
        for item in inputs:
            args += ["--input", item]
        res = run_cli(*args)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args=" ".join(args))
        assert res.returncode == 0
        assert "same outcome: True  same iterations: True" in res.stdout

    def test_ch04_cli_h_zero_rejected(self, evidence):
        res = run_cli("run", "ch04_p01", "--engine", "python", "--input", "h=0")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode,
                 args="run ch04_p01 --engine python --input h=0")
        assert res.returncode == 2
        assert "h" in res.stderr and "minimum" in res.stderr

    def test_ch04_cli_domain_error(self, evidence):
        args = ["run", "ch04_p01", "--engine", "compare", "--preset", "3", "--input", "x=0.05", "--input", "h=0.1"]
        res = run_cli(*args)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args=" ".join(args))
        assert res.returncode == 1
        assert "INPUT" in res.stdout + res.stderr

    def test_ch04_cli_expr_python_and_fortran(self, evidence):
        py = run_cli("run", "ch04_p01", "--engine", "python", "--expr", "x**3")
        ft = run_cli("run", "ch04_p01", "--engine", "fortran", "--expr", "x**3")
        evidence(stdout=py.stdout + ft.stdout, stderr=ft.stderr, exit_code=ft.returncode,
                 args="run ch04_p01 --engine python|fortran --expr x**3")
        assert py.returncode == 0
        assert " 1.0E-01      1.0000000E-02      0.0000000E-99" in py.stdout  # (3H^2 X + H^3... at 0: H^2)
        assert ft.returncode == 2
        assert "Python engine" in ft.stderr


# ----------------------------------------------------------------------------- JSON API
@pytest.fixture
def _up(server):
    return server


@pytest.mark.usefixtures("_up")
class TestCh04Api:
    def test_ch04_api_catalog_entry(self, evidence):
        resp = requests.get(f"{BASE_URL}/api/programs/ch04_p01", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:3000], endpoint="/api/programs/ch04_p01", method="GET")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "ch04_p01" and body["book_ref"]["page"] == 90
        assert [i["name"] for i in body["inputs"]] == ["x", "h"]
        assert body["data_card"]["values"] == {"x": 0.0, "h": 0.1}
        assert [p["expr"] for p in body["function"]["presets"]] == ["X**2*EXP(X)", "SIN(X)", "1 + LOG10(X)"]
        assert body["files"]["legacy"] == ["/files/ch04_p01/legacy", "/files/ch04_p01/legacy?index=1"]
        assert body["files"]["scan"] == "/files/ch04_p01/scan"
        assert len(body["errata"]) == 10

    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_ch04_api_run_book(self, engine, evidence):
        body = {"engine": engine}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3500], request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["status"] == "OK"
        assert data["book_text"] == BOOK_TEXT_REAL64
        _check_rows(data["steps"], TOL64)
        res = data["result"]
        assert res["iterations"] == 10 and res["converged"] is True
        assert res["first_dx"] == 0.010016675001984412 and res["first_ddx"] == 2.010008336111607
        assert res["last_ddx"] == 2.0 and res["fo"] == 0.0

    def test_ch04_api_compare_book(self, evidence):
        body = {"engine": "compare"}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3500], request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["matches"] is True
        assert data["status"] == ["OK", "OK"] and data["iterations"] == [10, 10]
        assert data["max_abs_diff"] == 0.0
        py, ft = data["outcomes"]
        assert py["book_text"] == ft["book_text"] == BOOK_TEXT_REAL64
        assert py["steps"] == ft["steps"]
        assert py["result"]["value"] == ft["result"]["value"]

    @pytest.mark.parametrize("preset,inputs,field,expected,tol", [
        (2, {"x": 1.0}, "first_ddx", -0.8407699926874178, 5e-8),
        (3, {"x": 0.19, "h": 0.02}, "first_dx", 2.2942593338911355, 5e-7),
    ], ids=["sin", "log10"])
    def test_ch04_api_compare_presets(self, preset, inputs, field, expected, tol, evidence):
        body = {"engine": "compare", "preset": preset, "inputs": inputs}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3000], request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["matches"] is True
        py, ft = data["outcomes"]
        assert py["book_text"] == ft["book_text"]
        assert abs(ft["result"][field] - expected) < tol

    def test_ch04_api_custom_expression_python(self, evidence):
        body = {"engine": "python", "expression": "EXPF(X)*X**2"}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3000], request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["expression"] == "EXPF(X)*X**2"
        assert data["book_text"] == BOOK_TEXT_REAL64

    @pytest.mark.parametrize("engine", ["fortran", "compare"])
    def test_ch04_api_custom_expression_rejected(self, engine, evidence):
        body = {"engine": engine, "expression": "x**3"}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CUSTOM_FUNCTION_ENGINE"

    @pytest.mark.parametrize("expr", ["x**", "__import__('os')"], ids=["syntax", "unsafe"])
    def test_ch04_api_bad_expression(self, expr, evidence):
        body = {"engine": "python", "expression": expr}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "EXPRESSION"

    @pytest.mark.parametrize("engine,inputs,field", [
        ("python", {"h": 0}, "h"), ("fortran", {"h": -1}, "h"), ("compare", {"h": 1e-7}, "h"),
        ("python", {"x": 150}, "x"), ("python", {"x": "abc"}, "x"), ("fortran", {"h": 11}, "h"),
    ], ids=["h_zero", "h_negative", "h_below_min", "x_above_max", "x_not_number", "h_above_max"])
    def test_ch04_api_invalid_inputs(self, engine, inputs, field, evidence):
        body = {"engine": engine, "inputs": inputs}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 422
        err = resp.json()["error"]
        assert err["code"] == "INPUT"
        assert field in err["fields"]

    def test_ch04_api_boundary_inputs(self, evidence):
        body = {"engine": "compare", "inputs": {"x": -100, "h": 1e-6}}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:2500], request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["matches"] is True and data["iterations"] == [10, 10]

    def test_ch04_api_unknown_preset(self, evidence):
        body = {"engine": "python", "preset": 9}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INPUT"

    def test_ch04_api_domain_error_both_engines(self, evidence):
        body = {"engine": "compare", "preset": 3, "inputs": {"x": 0.05, "h": 0.1}}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3000], request=body, endpoint=RUN_EP, method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False and data["status"] == ["INPUT", "INPUT"]
        assert data["same_status"] is True
        for outcome in data["outcomes"]:
            assert outcome["steps"] == []
            assert outcome["book_text"].startswith(HEADING)
            assert outcome["error"]["code"] == "INPUT"


# ----------------------------------------------------------------------------- web pages / practice / files
@pytest.mark.usefixtures("_up")
class TestCh04Web:
    def test_ch04_html_program_page(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/ch04_p01", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:2500], endpoint="/programs/ch04_p01", method="GET")
        assert resp.status_code == 200
        assert "central differences" in resp.text.lower()
        for testid in ("engine-python", "engine-fortran", "engine-compare", "data-card"):
            assert f'data-testid="{testid}"' in resp.text

    def test_ch04_html_run_form_compare(self, evidence):
        form = {"engine": "compare", "in_x": "0.0", "in_h": "0.1", "function": "1"}
        resp = requests.post(f"{BASE_URL}/programs/ch04_p01/run", data=form, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:2500], request=form,
                 endpoint="/programs/ch04_p01/run", method="POST")
        assert resp.status_code == 200
        assert "1.0016675E-02" in resp.text and "2.0100083E+00" in resp.text

    @pytest.mark.parametrize("qid,answer,correct", [
        ("book-first-dx", "0.0100166750", "true"),
        ("book-first-dx", "0.0100167", "false"),
        ("rows", "10", "true"),
        ("sin-second-derivative", "-0.8407700", "true"),
        ("log-table-derivative", "2.294259", "true"),
    ], ids=["first_dx_correct", "first_dx_wrong", "rows", "sin_preset", "log_preset"])
    def test_ch04_practice(self, qid, answer, correct, evidence):
        ep = f"/programs/ch04_p01/practice/{qid}"
        resp = requests.post(f"{BASE_URL}{ep}", data={"answer": answer}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:1500], request={"answer": answer}, endpoint=ep, method="POST")
        assert resp.status_code == 200
        assert f'data-testid="practice-verdict" data-correct="{correct}"' in resp.text

    def test_ch04_practice_unreadable(self, evidence):
        ep = "/programs/ch04_p01/practice/book-first-dx"
        resp = requests.post(f"{BASE_URL}{ep}", data={"answer": "abc"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:800], request={"answer": "abc"}, endpoint=ep, method="POST")
        assert resp.status_code == 422

    @pytest.mark.parametrize(("path", "ctype", "needle"), [
        ("scan", "application/pdf", b"%PDF"),
        ("legacy", "application/pdf", b"%PDF"),
        ("legacy?index=1", "application/pdf", b"%PDF"),
        ("fortran_module", "text/plain", b"derivative"),
        ("fortran_app", "text/plain", b"program ch04_p01_central_difference"),
        ("python", "text/plain", b"def central_difference"),
        ("study", "text/plain", b"# Chapter 4, Program 1"),
    ], ids=["scan", "legacy0", "legacy1", "fortran_module", "fortran_app", "python", "study"])
    def test_ch04_files(self, path, ctype, needle, evidence):
        resp = requests.get(f"{BASE_URL}/files/ch04_p01/{path}", timeout=10)
        evidence(status=resp.status_code, body=f"{resp.headers.get('content-type')} {resp.content[:120]!r}",
                 endpoint=f"/files/ch04_p01/{path}", method="GET")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(ctype)
        assert needle.lower() in resp.content[:200000].lower()

    def test_ch04_files_legacy_scans_distinct(self, evidence):
        a = requests.get(f"{BASE_URL}/files/ch04_p01/legacy", timeout=10)
        b = requests.get(f"{BASE_URL}/files/ch04_p01/legacy?index=1", timeout=10)
        evidence(status=b.status_code, body=f"len0={len(a.content)} len1={len(b.content)}",
                 endpoint="/files/ch04_p01/legacy?index=1", method="GET")
        assert a.status_code == b.status_code == 200
        assert a.content != b.content

    @pytest.mark.parametrize("path", ["legacy?index=2", "legacy?index=-1", "..%2F..%2Fetc%2Fpasswd", "secrets"],
                             ids=["index_oob", "index_negative", "traversal", "unknown_kind"])
    def test_ch04_files_rejected(self, path, evidence):
        resp = requests.get(f"{BASE_URL}/files/ch04_p01/{path}", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:300], endpoint=f"/files/ch04_p01/{path}", method="GET")
        assert resp.status_code == 404
        assert b"root:" not in resp.content
