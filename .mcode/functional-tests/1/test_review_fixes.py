"""Functional tests for the behaviors changed by the milestone-1 code-review fixes.

Covers: JSON 413 body-size limit (declared and streamed), JSON 405 on GET .../run, HTML/API
shared validation order (CUSTOM_FUNCTION_ENGINE wins over field errors), shared per-input checks
(list cap, non-finite message), form number syntax, Python-engine verbose_text parity with the
Fortran drivers (API and CLI), Simpson with b = 0, and the updated catalog expected/errata.
"""

import re

import pytest
import requests

from conftest import BASE_URL, api_run, run_cli, run_driver

LIMIT = 64 * 1024
RUN_URL = f"{BASE_URL}/api/programs/ch01_p01/run"
FIELD_ERROR = re.compile(r'data-testid="field-error-([^"]+)"><strong>[^<]*</strong>: ([^<]*)<')
VALIDATION_CODE = re.compile(r'data-testid="validation-error" data-code="([^"]*)"')


@pytest.fixture(autouse=True)
def _up(server):
    return server


def _form_run(program_id, form):
    resp = requests.post(f"{BASE_URL}/programs/{program_id}/run", data=form, timeout=30)
    codes = VALIDATION_CODE.findall(resp.text)
    fields = dict(FIELD_ERROR.findall(resp.text))
    return resp, (codes[0] if codes else None), fields


class TestBodySizeLimit:
    def test_api_body_too_large_declared(self, evidence):
        body = {"engine": "python", "expression": "x" + " " * (LIMIT + 10)}
        resp = requests.post(RUN_URL, json=body, timeout=30)
        evidence(status=resp.status_code, body=resp.text, request="<JSON body > 64 KiB, Content-Length set>",
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 413
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json()["error"]["code"] == "TOO_LARGE"

    def test_api_body_too_large_chunked(self, evidence):
        def chunks():
            yield b'{"engine":"python","expression":"x'
            for _ in range(10):
                yield b" " * 8000

        resp = requests.post(RUN_URL, data=chunks(), headers={"Content-Type": "application/json"},
                             timeout=30)
        evidence(status=resp.status_code, body=resp.text,
                 request="<chunked JSON body ~80 KB, no Content-Length>",
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 413
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json()["error"]["code"] == "TOO_LARGE"

    def test_api_body_just_under_limit_accepted(self, evidence):
        # Padding with JSON whitespace keeps the body valid; total stays under 64 KiB.
        text = '{"engine": "python"' + " " * (LIMIT - 200) + "}"
        resp = requests.post(RUN_URL, data=text, headers={"Content-Type": "application/json"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:600], request=f"<{len(text)}-byte JSON body>",
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_html_body_too_large(self, evidence):
        form = {"engine": "python", "function": "custom", "expression": "x" * (LIMIT + 10)}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, timeout=30)

        def chunks():
            yield b"engine=python&function=custom&expression="
            for _ in range(10):
                yield b"x" * 8000

        streamed = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=chunks(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        evidence(status=resp.status_code, body=f"declared: {resp.text[:200]} | streamed {streamed.status_code}: "
                 f"{streamed.text[:200]}", request="<form body > 64 KiB, declared and chunked>",
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 413
        assert streamed.status_code == 413

    def test_api_get_run_method_not_allowed(self, evidence):
        resp = requests.get(RUN_URL, timeout=10)
        evidence(status=resp.status_code, body=resp.text, endpoint="/api/programs/ch01_p01/run", method="GET")
        assert resp.status_code == 405
        assert resp.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


class TestSharedValidationOrder:
    @pytest.mark.parametrize("engine", ["fortran", "compare"])
    def test_html_custom_engine_wins_over_field_error(self, engine, evidence):
        form = {"engine": engine, "function": "custom", "expression": "x - 1",
                "in_x1": "abc", "in_x2": "1.", "in_tol": "1.E-5"}
        resp, code, fields = _form_run("ch01_p01", form)
        evidence(status=resp.status_code, body=f"code={code} fields={fields}", request=form,
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert code == "CUSTOM_FUNCTION_ENGINE"

    @pytest.mark.parametrize("engine", ["fortran", "compare"])
    def test_api_custom_engine_wins_over_field_error(self, engine, evidence):
        body = {"engine": engine, "expression": "x - 1", "inputs": {"x1": "abc", "x2": 1, "tol": 1e-5}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CUSTOM_FUNCTION_ENGINE"

    def test_html_field_errors_per_field(self, evidence):
        form = {"engine": "python", "function": "1", "in_x1": "abc", "in_x2": "1.", "in_tol": "1e999"}
        resp, code, fields = _form_run("ch01_p01", form)
        evidence(status=resp.status_code, body=f"code={code} fields={fields}", request=form,
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert code == "INPUT"
        assert set(fields) == {"x1", "tol"}
        assert fields["tol"] == "inf is not a finite number"


class TestSharedInputChecks:
    def test_api_non_finite_message(self, evidence):
        raw = '{"engine": "python", "inputs": {"tol": NaN}}'
        resp = requests.post(RUN_URL, data=raw, headers={"Content-Type": "application/json"}, timeout=10)
        evidence(status=resp.status_code, body=resp.text, request=raw,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        err = resp.json()["error"]
        assert err["code"] == "INPUT"
        assert err["fields"]["tol"] == "nan is not a finite number"

    def test_api_list_over_100_entries(self, evidence):
        body = {"engine": "python", "inputs": {"n": 5, "points": [[i, i] for i in range(101)], "xin": 5}}
        resp = api_run("lagrange_interpolation", body)
        evidence(status=resp.status_code, body=resp.text, request="{n:5, points:<101 pairs>, xin:5}",
                 endpoint="/api/programs/lagrange_interpolation/run", method="POST")
        assert resp.status_code == 422
        err = resp.json()["error"]
        assert err["code"] == "INPUT"
        assert err["fields"]["points"] == "at most 100 entries are accepted"

    @pytest.mark.parametrize(
        ("program", "form"),
        [
            ("ch01_p01", {"in_x1": ".5", "in_x2": "1.", "in_tol": "1.D-3"}),
            ("ch01_p01", {"in_x1": "0.", "in_x2": "1.", "in_tol": "1.E-5"}),
            ("ch03_p01", {"in_b": "5.0", "in_n": "100."}),
        ],
        ids=["dot_five_and_D_exponent", "book_card_syntax", "integral_real_for_int"],
    )
    def test_html_form_number_syntax(self, program, form, evidence):
        data = {"engine": "python", "function": "1", **form}
        resp, code, fields = _form_run(program, data)
        evidence(status=resp.status_code, body=f"code={code} fields={fields} {resp.text[:300]}", request=data,
                 endpoint=f"/programs/{program}/run", method="POST")
        assert resp.status_code == 200
        assert code is None and not fields

    def test_html_form_non_integral_int_rejected(self, evidence):
        data = {"engine": "python", "function": "1", "in_b": "5.0", "in_n": "100.5"}
        resp, code, fields = _form_run("ch03_p01", data)
        evidence(status=resp.status_code, body=f"code={code} fields={fields}", request=data,
                 endpoint="/programs/ch03_p01/run", method="POST")
        assert resp.status_code == 422
        assert "n" in fields


class TestVerbose:
    @pytest.mark.parametrize("program", ["ch01_p01", "ch03_p01", "ch03_p02", "lagrange_interpolation"])
    def test_api_python_verbose_matches_fortran(self, program, evidence):
        py = api_run(program, {"engine": "python", "verbose": True})
        ft = api_run(program, {"engine": "fortran", "verbose": True})
        evidence(status=py.status_code, body=f"python: {py.json().get('verbose_text')!r}\n"
                 f"fortran: {ft.json().get('verbose_text')!r}", request={"engine": "python", "verbose": True},
                 endpoint=f"/api/programs/{program}/run", method="POST")
        assert py.status_code == ft.status_code == 200
        text = py.json().get("verbose_text")
        assert text and "VERBOSE OUTPUT" in text
        assert text == ft.json().get("verbose_text")

    def test_api_verbose_absent_by_default(self, evidence):
        resp = api_run("ch01_p01", {"engine": "python"})
        evidence(status=resp.status_code, body=resp.text[:400], request={"engine": "python"},
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        assert not resp.json().get("verbose_text")

    @pytest.mark.parametrize("program", ["ch01_p01", "ch03_p01", "ch03_p02", "lagrange_interpolation"])
    def test_cli_python_verbose_matches_fortran(self, program, evidence):
        py = run_cli("run", program, "--engine", "python", "--verbose")
        ft = run_cli("run", program, "--engine", "fortran", "--verbose")
        evidence(stdout=py.stdout, stderr=py.stderr, exit_code=py.returncode,
                 args=f"run {program} --engine python --verbose")
        assert py.returncode == ft.returncode == 0
        assert "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)" in py.stdout
        assert py.stdout == ft.stdout

    @pytest.mark.parametrize(("driver", "card"), [("ch01_p01_bisection", "0. 1. 1.E-5\n"),
                                                  ("ch03_p01_simpson", "5.0 100\n"),
                                                  ("ch03_p02_romberg", "15.0 2.E-7\n")])
    def test_driver_verbose_extends_book_text(self, driver, card, evidence):
        book = run_driver(driver, card)
        verbose = run_driver(driver, card, "--verbose")
        evidence(stdout=verbose.stdout, stderr=verbose.stderr, exit_code=verbose.returncode, stdin=card)
        assert verbose.returncode == 0
        assert verbose.stdout.startswith(book.stdout)
        assert "VERBOSE OUTPUT (NOT PART OF THE BOOK TEXT)" in verbose.stdout


class TestSimpsonZeroUpperLimit:
    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_api_simpson_b_zero(self, engine, evidence):
        body = {"engine": engine, "inputs": {"b": 0}}
        resp = api_run("ch03_p01", body)
        evidence(status=resp.status_code, body=resp.text[-600:], request=body,
                 endpoint="/api/programs/ch03_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["status"] == "OK"
        assert data["result"]["value"] == 0.0

    def test_api_simpson_b_zero_compare(self, evidence):
        body = {"engine": "compare", "inputs": {"b": 0}}
        resp = api_run("ch03_p01", body)
        evidence(status=resp.status_code, body=resp.text[:800], request=body,
                 endpoint="/api/programs/ch03_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == ["OK", "OK"] and data["matches"] is True
        assert [o["result"]["value"] for o in data["outcomes"]] == [0.0, 0.0]

    def test_cli_simpson_b_zero(self, evidence):
        res = run_cli("run", "ch03_p01", "--engine", "python", "--input", "b=0")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode,
                 args="run ch03_p01 --engine python --input b=0")
        assert res.returncode == 0
        assert "IS  .0000000 WITH 100 PANELS" in res.stdout


class TestCatalogUpdates:
    def test_api_catalog_errata_and_expected(self, evidence):
        details = {pid: requests.get(f"{BASE_URL}/api/programs/{pid}", timeout=10).json()
                   for pid in ("ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02")}
        summary = {pid: {"expected": [e.get("name") for e in d["expected"]],
                         "errata": [e["id"] for e in d["errata"]]} for pid, d in details.items()}
        evidence(status=200, body=str(summary), endpoint="/api/programs/{id}", method="GET")
        ch01_errata = set(summary["ch01_p01"]["errata"])
        assert {"label-5-fall-through", "non-finite-values", "precision-last-digit"} <= ch01_errata
        assert "non-finite-values" in summary["ch03_p01"]["errata"]
        assert "non-finite-values" in summary["ch03_p02"]["errata"]
        assert not {"iterations", "nudges"} & set(summary["ch01_p02"]["expected"])
        assert "ordinates" not in summary["ch03_p01"]["expected"]
