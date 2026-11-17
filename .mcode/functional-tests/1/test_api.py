"""Functional tests of the JSON API of the live server (GET /api/programs, POST .../run)."""

import pytest
import requests

from conftest import BASE_URL, api_run

PROGRAMS = ["ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02", "lagrange_interpolation"]
BOOK_VALUE = {"ch01_p01": (0.4435729, 1e-6), "ch03_p01": (1.5499312, 1e-7),
              "ch03_p02": (1.6181944, 1e-7), "lagrange_interpolation": (2.3119, 1e-4)}


@pytest.fixture(autouse=True)
def _up(server):
    return server


class TestCatalogApi:
    def test_api_list_programs(self, evidence):
        resp = requests.get(f"{BASE_URL}/api/programs", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:3000], endpoint="/api/programs", method="GET")
        assert resp.status_code == 200
        body = resp.json()
        assert [p["id"] for p in body] == PROGRAMS
        bis = body[0]
        assert {"inputs", "engines"} <= set(bis)
        assert [i["name"] for i in bis["inputs"]] == ["x1", "x2", "tol"]

    def test_api_get_program_detail(self, evidence):
        resp = requests.get(f"{BASE_URL}/api/programs/ch03_p02", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:3000], endpoint="/api/programs/ch03_p02", method="GET")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "ch03_p02"
        assert body["data_card"]["values"] == {"b": 15.0, "tol": 2e-7}
        assert body["files"]["scan"] == "/files/ch03_p02/scan"
        errata = {e["id"] for e in body["errata"]}
        assert "non-finite-values" in errata

    def test_api_get_program_not_found(self, evidence):
        resp = requests.get(f"{BASE_URL}/api/programs/ch09_p09", timeout=10)
        evidence(status=resp.status_code, body=resp.text, endpoint="/api/programs/ch09_p09", method="GET")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


class TestRunBook:
    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_api_run_bisection_book(self, engine, evidence):
        body = {"engine": engine}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3000], request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["status"] == "OK"
        assert len(data["steps"]) == 15
        assert abs(data["result"]["value"] - 0.4435729) < 1e-6
        assert "15 ITERATIONS WERE REQUIRED" in data["book_text"]

    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_api_run_bairstow_book(self, engine, evidence):
        body = {"engine": engine}
        resp = api_run("ch01_p02", body)
        evidence(status=resp.status_code, body=resp.text[:3000], request=body,
                 endpoint="/api/programs/ch01_p02/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        coeffs = [f["coefficients"] for f in data["result"]["factors"]]
        for got, want in zip(coeffs, [[4.2, -2.1], [3.3, -6.2], [1.0, -10.3]], strict=True):
            assert abs(got[0] - want[0]) < 1e-4 and abs(got[1] - want[1]) < 1e-4

    @pytest.mark.parametrize("engine", ["python", "fortran"])
    @pytest.mark.parametrize("program", ["ch03_p01", "ch03_p02", "lagrange_interpolation"])
    def test_api_run_book_value(self, program, engine, evidence):
        body = {"engine": engine}
        resp = api_run(program, body)
        evidence(status=resp.status_code, body=resp.text[:2500], request=body,
                 endpoint=f"/api/programs/{program}/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        value, tol = BOOK_VALUE[program]
        assert abs(data["result"]["value"] - value) < tol
        if program == "ch03_p02":
            assert data["result"]["subintervals"] == 80
            assert len(data["result"]["table"]) == 4

    @pytest.mark.parametrize("program", PROGRAMS)
    def test_api_run_compare_agrees(self, program, evidence):
        body = {"engine": "compare"}
        resp = api_run(program, body)
        evidence(status=resp.status_code, body=resp.text[:2000], request=body,
                 endpoint=f"/api/programs/{program}/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "compare"
        assert data["ok"] is True
        assert data["status"] == ["OK", "OK"]
        assert data["matches"] is True and data["same_iterations"] is True

    def test_api_run_input_override(self, evidence):
        body = {"engine": "compare", "inputs": {"tol": 1e-3}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text[:2000], request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["matches"] is True
        assert data["iterations"][0] == data["iterations"][1] < 15

    def test_api_run_preset(self, evidence):
        body = {"engine": "compare", "preset": 3, "inputs": {"x1": 0, "x2": 1}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text[:2500], request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True and data["matches"] is True
        value = data["outcomes"][1]["result"]["value"]
        assert abs(value - 0.7390851) < 1e-4  # Dottie number: cos(x) = x


class TestErrorPaths:
    """Algorithm error paths: 200 with ok=false and the same code on both engines."""

    @pytest.mark.parametrize(
        ("program", "inputs", "code"),
        [
            ("ch01_p01", {"x2": 0.3}, "BRACKET"),
            ("ch01_p01", {"tol": 1e-12}, "NON_CONVERGENT"),
            ("ch03_p01", {"n": 99}, "ODD_PANELS"),
            ("ch01_p02", {"lim": 2}, "NON_CONVERGENT"),
            ("ch01_p02", {"n": 7}, "DEGREE"),
            ("lagrange_interpolation", {"n": 3, "points": [[1, 1], [1, 2], [3, 3]], "xin": 2}, "INPUT"),
        ],
        ids=["bisection_bracket", "bisection_nonconv", "simpson_odd", "bairstow_nonconv",
             "bairstow_degree", "lagrange_dup_x"],
    )
    def test_api_error_path_compare(self, program, inputs, code, evidence):
        body = {"engine": "compare", "inputs": inputs}
        resp = api_run(program, body)
        evidence(status=resp.status_code, body=resp.text[:1500], request=body,
                 endpoint=f"/api/programs/{program}/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["status"] == [code, code]
        assert data["same_status"] is True

    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_api_error_path_single_engine(self, engine, evidence):
        body = {"engine": engine, "inputs": {"n": 99}}
        resp = api_run("ch03_p01", body)
        evidence(status=resp.status_code, body=resp.text[:1500], request=body,
                 endpoint="/api/programs/ch03_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "ODD_PANELS"

    def test_api_romberg_not_converged(self, evidence):
        # Preset 3 (1/(1+X**2)) on [0, 100] with TOL = 1E-13 does not converge in 8 extrapolations.
        body = {"engine": "compare", "preset": 3, "inputs": {"b": 100, "tol": 1e-13}}
        resp = api_run("ch03_p02", body)
        evidence(status=resp.status_code, body=resp.text[:2500], request=body,
                 endpoint="/api/programs/ch03_p02/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["matches"] is True
        assert data["status"] == ["OK", "OK"]
        left, right = (o["result"] for o in data["outcomes"])
        assert left["converged"] is False and right["converged"] is False
        assert left["iterations"] == right["iterations"] == 8
        assert left["subintervals"] == 2560

    def test_api_lagrange_count_mismatch(self, evidence):
        body = {"engine": "fortran", "inputs": {"n": 4}}
        resp = api_run("lagrange_interpolation", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/lagrange_interpolation/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INPUT"
        assert "n" in resp.json()["error"]["fields"]


class TestExpressions:
    def test_api_custom_expression_python(self, evidence):
        body = {"engine": "python", "expression": "x**2 - 2", "inputs": {"x1": 1, "x2": 2, "tol": 1e-6}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text[:2000], request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert abs(data["result"]["value"] - 2**0.5) < 1e-6

    def test_api_custom_expression_fortran_aliases(self, evidence):
        body = {"engine": "python", "expression": "EXPF(-X) - SINF(3.1415926*X/2.)"}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text[:1500], request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["iterations"] == 15
        assert abs(data["result"]["value"] - 0.4435729) < 1e-6

    def test_api_root_at_endpoint(self, evidence):
        body = {"engine": "python", "expression": "x - 1", "inputs": {"x1": 1, "x2": 2}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text[:1500], request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["root_at_endpoint"] is True
        assert data["result"]["iterations"] == 0
        assert data["result"]["value"] == 1.0

    @pytest.mark.parametrize("engine", ["fortran", "compare"])
    def test_api_custom_expression_rejected_non_python(self, engine, evidence):
        body = {"engine": engine, "expression": "x - 1"}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CUSTOM_FUNCTION_ENGINE"

    @pytest.mark.parametrize(
        "expr",
        ['__import__("os").system("id")', "x.__class__", "(lambda: 1)()", "x**999999",
         "open('/etc/passwd')", "[x for x in (1,2)]"],
        ids=["import", "attribute", "lambda", "huge_exponent", "open_call", "comprehension"],
    )
    def test_api_expression_safety_rejected(self, expr, evidence):
        body = {"engine": "python", "expression": expr}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        err = resp.json()["error"]
        assert err["code"] == "EXPRESSION"
        assert isinstance(err.get("position"), int)

    def test_api_expression_syntax_error(self, evidence):
        body = {"engine": "python", "expression": "x +* 2"}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "EXPRESSION"


class TestValidation:
    def test_api_unknown_program(self, evidence):
        body = {"engine": "python"}
        resp = api_run("nope", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/nope/run", method="POST")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_api_invalid_engine(self, evidence):
        body = {"engine": "jython"}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION"

    def test_api_unknown_body_key(self, evidence):
        body = {"engine": "python", "bogus": 1}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION"

    def test_api_invalid_input_type(self, evidence):
        body = {"engine": "python", "inputs": {"tol": "abc"}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        err = resp.json()["error"]
        assert err["code"] == "INPUT" and "tol" in err["fields"]

    def test_api_input_out_of_range(self, evidence):
        body = {"engine": "fortran", "inputs": {"tol": 1e-30}}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert "tol" in resp.json()["error"]["fields"]

    def test_api_unknown_preset(self, evidence):
        body = {"engine": "python", "preset": 9}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INPUT"

    def test_api_preset_with_expression(self, evidence):
        body = {"engine": "python", "preset": 2, "expression": "x"}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INPUT"

    def test_api_malformed_json(self, evidence):
        resp = requests.post(f"{BASE_URL}/api/programs/ch01_p01/run", data="{not json",
                             headers={"Content-Type": "application/json"}, timeout=10)
        evidence(status=resp.status_code, body=resp.text, request="{not json",
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION"
