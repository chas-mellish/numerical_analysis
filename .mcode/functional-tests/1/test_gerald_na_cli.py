"""Functional tests of the ``gerald-na`` console script (run / catalog / --version / --help)."""

import json

import pytest

from conftest import run_cli

BOOK = {
    "ch01_p01": 0.4435729,
    "ch03_p01": 1.5499312,
    "ch03_p02": 1.6181944,
    "lagrange_interpolation": 2.3119,
}


class TestTopLevel:
    def test_cli_version(self, evidence):
        res = run_cli("--version")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args="--version")
        assert res.returncode == 0
        assert res.stdout.strip() == "gerald-na 0.1.0"

    def test_cli_help(self, evidence):
        res = run_cli("--help")
        evidence(stdout=res.stdout, exit_code=res.returncode, args="--help")
        assert res.returncode == 0
        for word in ("serve", "run", "catalog"):
            assert word in res.stdout


class TestCatalog:
    def test_cli_catalog_list(self, evidence):
        res = run_cli("catalog", "list")
        evidence(stdout=res.stdout, exit_code=res.returncode, args="catalog list")
        assert res.returncode == 0
        for pid in ("ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02", "lagrange_interpolation"):
            assert pid in res.stdout
        assert "5 program(s)" in res.stdout

    def test_cli_catalog_check(self, evidence):
        res = run_cli("catalog", "check")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args="catalog check")
        assert res.returncode == 0
        assert "catalog OK: 5 program(s)" in res.stdout

    def test_cli_catalog_index_check(self, evidence):
        res = run_cli("catalog", "index", "--check")
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode,
                 args="catalog index --check")
        assert res.returncode == 0
        assert "up to date" in res.stdout


class TestRunBook:
    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_cli_run_bisection_book(self, engine, evidence):
        res = run_cli("run", "ch01_p01", "--engine", engine)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode,
                 args=f"run ch01_p01 --engine {engine}")
        assert res.returncode == 0
        assert "15 ITERATIONS WERE REQUIRED" in res.stdout
        assert ".4435729" in res.stdout

    @pytest.mark.parametrize("engine", ["python", "fortran"])
    def test_cli_run_bairstow_book(self, engine, evidence):
        res = run_cli("run", "ch01_p02", "--engine", engine, "--trace-json")
        evidence(stdout=res.stdout[:3000], exit_code=res.returncode,
                 args=f"run ch01_p02 --engine {engine} --trace-json")
        assert res.returncode == 0
        factors = json.loads(res.stdout)["result"]["factors"]
        coeffs = [f["coefficients"] for f in factors]
        assert [f["kind"] for f in factors] == ["quadratic", "quadratic", "linear"]
        expected = [[4.2, -2.1], [3.3, -6.2], [1.0, -10.3]]
        for got, want in zip(coeffs, expected, strict=True):
            assert abs(got[0] - want[0]) < 1e-4 and abs(got[1] - want[1]) < 1e-4

    @pytest.mark.parametrize("engine", ["python", "fortran"])
    @pytest.mark.parametrize("program", ["ch03_p01", "ch03_p02", "lagrange_interpolation"])
    def test_cli_run_book_value(self, program, engine, evidence):
        res = run_cli("run", program, "--engine", engine, "--trace-json")
        evidence(stdout=res.stdout[:3000], exit_code=res.returncode,
                 args=f"run {program} --engine {engine} --trace-json")
        assert res.returncode == 0
        body = json.loads(res.stdout)
        assert body["status"] == "OK"
        assert abs(body["result"]["value"] - BOOK[program]) < 1e-4 if program == "lagrange_interpolation" \
            else abs(body["result"]["value"] - BOOK[program]) < 1e-7
        if program == "ch03_p02":
            assert body["result"]["subintervals"] == 80
            assert len(body["result"]["table"]) == 4

    @pytest.mark.parametrize("program", ["ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02",
                                         "lagrange_interpolation"])
    def test_cli_run_compare_agrees(self, program, evidence):
        res = run_cli("run", program, "--engine", "compare", "--trace-json")
        evidence(stdout=res.stdout[:2500], exit_code=res.returncode,
                 args=f"run {program} --engine compare --trace-json")
        assert res.returncode == 0
        body = json.loads(res.stdout)
        assert body["same_status"] is True
        assert body["same_iterations"] is True
        assert body["matches"] is True
        assert body["status"] == ["OK", "OK"]


class TestRunErrors:
    def test_cli_run_unknown_program(self, evidence):
        res = run_cli("run", "nope")
        evidence(stdout=res.stdout + res.stderr, exit_code=res.returncode, args="run nope")
        assert res.returncode == 2
        assert "unknown program 'nope'" in res.stderr

    def test_cli_run_expr_on_fortran_rejected(self, evidence):
        res = run_cli("run", "ch01_p01", "--engine", "fortran", "--expr", "x-1")
        evidence(stdout=res.stdout + res.stderr, exit_code=res.returncode,
                 args="run ch01_p01 --engine fortran --expr x-1")
        assert res.returncode == 2
        assert "Python engine" in res.stderr

    def test_cli_run_custom_expression_python(self, evidence):
        res = run_cli("run", "ch01_p01", "--expr", "x**2-2", "--input", "x1=1", "--input", "x2=2",
                      "--input", "tol=1e-6")
        evidence(stdout=res.stdout[-300:], exit_code=res.returncode,
                 args="run ch01_p01 --expr x**2-2 --input x1=1 --input x2=2 --input tol=1e-6")
        assert res.returncode == 0
        assert "1.4142136 IS A ROOT" in res.stdout

    def test_cli_run_odd_panels_both_engines(self, evidence):
        res = run_cli("run", "ch03_p01", "--engine", "compare", "--input", "n=99", "--trace-json")
        evidence(stdout=res.stdout[:2000], stderr=res.stderr, exit_code=res.returncode,
                 args="run ch03_p01 --engine compare --input n=99 --trace-json")
        assert res.returncode == 1
        body = json.loads(res.stdout)
        assert body["status"] == ["ODD_PANELS", "ODD_PANELS"]
        assert body["same_status"] is True

    def test_cli_run_bad_input_value(self, evidence):
        res = run_cli("run", "ch01_p01", "--input", "tol=abc")
        evidence(stdout=res.stdout + res.stderr, exit_code=res.returncode, args="run ch01_p01 --input tol=abc")
        assert res.returncode == 2
        assert "tol" in res.stderr

    def test_cli_run_invalid_engine_option(self, evidence):
        res = run_cli("run", "ch01_p01", "--engine", "cobol")
        evidence(stdout=res.stdout + res.stderr, exit_code=res.returncode, args="run ch01_p01 --engine cobol")
        assert res.returncode == 2
        assert "invalid choice" in res.stderr
