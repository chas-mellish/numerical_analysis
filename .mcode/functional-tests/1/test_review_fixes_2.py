"""Functional regression tests for the second round of milestone-1 code-review fixes.

* ``evaluate_finite`` gained a ``name`` label and central_difference reuses it: non-finite
  function values must still be INPUT errors (Fortran: ``F(X-H) is not a finite number``) with the
  partial book output, and custom-expression overflow still surfaces as EXPRESSION for
  central difference, bisection and Romberg.
* charts.py: ``_abs_residual_figure`` / ``_delta_figure`` use ``_log_axis``; the chart JSON
  (log y-axis, power exponent format) of bisection, Bairstow, Romberg and ch04 must be unchanged.
"""

import json
import re
from html.parser import HTMLParser

import pytest
import requests

from conftest import BASE_URL, api_run, run_cli

HEADING = "DERIVATIVES COMPUTED BY CENTRAL DIFFERENCE FORMULAS\n"
CHART_DATA = re.compile(r'data-testid="result-chart-data">(.*?)</script>', re.S)


@pytest.fixture(autouse=True)
def _up(server):
    return server


class _FormDefaults(HTMLParser):
    """Collect the default ``in_*`` values and the selected preset of a program's run form."""

    def __init__(self):
        super().__init__()
        self.pairs = []
        self.function = None
        self._in_select = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and (a.get("name") or "").startswith("in_"):
            self.pairs.append((a["name"], a.get("value") or ""))
        elif tag == "select" and a.get("name") == "function":
            self._in_select = True
        elif tag == "option" and self._in_select:
            if self.function is None or "selected" in a:
                self.function = a.get("value")

    def handle_endtag(self, tag):
        if tag == "select":
            self._in_select = False


def _run_defaults(program_id):
    page = requests.get(f"{BASE_URL}/programs/{program_id}", timeout=15)
    assert page.status_code == 200
    parser = _FormDefaults()
    parser.feed(page.text)
    form = parser.pairs + [("engine", "python")]
    if parser.function is not None:
        form.append(("function", parser.function))
    resp = requests.post(f"{BASE_URL}/programs/{program_id}/run", data=form, timeout=30)
    match = CHART_DATA.search(resp.text)
    figures = json.loads(match.group(1)) if match else None
    return resp, form, figures


def _axes(fig):
    return {k: (v.get("type"), v.get("exponentformat")) for k, v in fig["layout"].items() if k.endswith("axis")}


def _summary(figures):
    return [{"id": f["id"], "title": f["title"], "axes": _axes(f)} for f in figures]


class TestChartPayloads:
    def test_chart_bisection_abs_residual_log_axis(self, evidence):
        resp, form, figs = _run_defaults("ch01_p01")
        evidence(status=resp.status_code, body=json.dumps(_summary(figs or [])), request=form,
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200 and figs
        assert [f["id"] for f in figs] == ["bracket", "abs_residual"]
        fig = figs[1]
        assert fig["title"] == "|F(X)| per iteration (log scale)"
        assert _axes(fig) == {"xaxis": (None, None), "yaxis": ("log", "power")}
        ys = [y for y in fig["data"][0]["y"] if y is not None]
        assert ys and all(y > 0 for y in ys)

    def test_chart_bairstow_factors_delta_log_axis(self, evidence):
        resp, form, figs = _run_defaults("ch01_p02")
        evidence(status=resp.status_code, body=json.dumps(_summary(figs or [])), request=form,
                 endpoint="/programs/ch01_p02/run", method="POST")
        assert resp.status_code == 200 and figs
        ids = [f["id"] for f in figs]
        assert ids == ["factors_r", "factors_s", "factors_delta", "factors_roots", "factors_polynomial"]
        delta = figs[2]
        assert delta["title"] == "|DELR| + |DELS| per iteration, by factor (log scale)"
        assert _axes(delta) == {"xaxis": (None, None), "yaxis": ("log", "power")}
        assert len(delta["data"]) >= 1
        for other in (figs[0], figs[1]):
            assert _axes(other)["yaxis"] == (None, None)

    def test_chart_romberg_heatmap(self, evidence):
        resp, form, figs = _run_defaults("ch03_p02")
        evidence(status=resp.status_code, body=json.dumps(_summary(figs or [])), request=form,
                 endpoint="/programs/ch03_p02/run", method="POST")
        assert resp.status_code == 200 and figs
        assert [f["id"] for f in figs] == ["romberg_heatmap"]
        assert figs[0]["data"][0]["type"] == "heatmap"
        assert all(t == (None, None) for t in _axes(figs[0]).values())

    def test_chart_ch04_convergence_log_axes(self, evidence):
        resp, form, figs = _run_defaults("ch04_p01")
        evidence(status=resp.status_code, body=json.dumps(_summary(figs or [])), request=form,
                 endpoint="/programs/ch04_p01/run", method="POST")
        assert resp.status_code == 200 and figs
        summary = {f["id"]: _axes(f) for f in figs}
        assert summary == {
            "convergence_dx": {"xaxis": ("log", "power"), "yaxis": ("log", "power")},
            "convergence_ddx": {"xaxis": ("log", "power"), "yaxis": (None, None)},
            "convergence_changes": {"xaxis": ("log", "power"), "yaxis": ("log", "power")},
        }


class TestNonFiniteErrors:
    def test_api_ch04_non_finite_f_compare(self, evidence):
        body = {"engine": "compare", "preset": 3, "inputs": {"x": 0.05, "h": 0.1}}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text[:3000], request=body,
                 endpoint="/api/programs/ch04_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False and data["status"] == ["INPUT", "INPUT"]
        py, ft = data["outcomes"]
        assert py["error"]["message"] == "log10(-0.05) is outside the function's domain (at x = -0.05)"
        assert ft["error"]["message"].startswith("F(X-H) is not a finite number at X = -5.0")
        for outcome in (py, ft):
            assert outcome["steps"] == []
            assert outcome["book_text"] == f"{HEADING}AT X =  0.05\n\n   H             DX                 DDX\n\n"

    def test_api_ch04_expression_overflow_python(self, evidence):
        body = {"engine": "python", "expression": "x*1e308", "inputs": {"x": 1.9, "h": 0.1}}
        resp = api_run("ch04_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch04_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False and data["status"] == "EXPRESSION"
        assert data["error"] == {"code": "EXPRESSION", "message": "x * 1e+308 is not a finite number at x = 1.9"}
        assert data["steps"] == [] and data["book_text"].startswith(HEADING + "AT X =  1.90\n")

    def test_api_bisection_expression_non_finite(self, evidence):
        body = {"engine": "python", "expression": "x*1e308*2-1"}
        resp = api_run("ch01_p01", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == {"code": "EXPRESSION",
                                 "message": "x * 1e+308 * 2.0 - 1.0 is not a finite number at x = 1.0"}

    def test_api_romberg_expression_non_finite(self, evidence):
        body = {"engine": "python", "expression": "x*1e308*2"}
        resp = api_run("ch03_p02", body)
        evidence(status=resp.status_code, body=resp.text, request=body,
                 endpoint="/api/programs/ch03_p02/run", method="POST")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == {"code": "EXPRESSION",
                                 "message": "x * 1e+308 * 2.0 is not a finite number at x = 15.0"}

    def test_cli_ch04_non_finite_f_fortran(self, evidence):
        args = ["run", "ch04_p01", "--engine", "fortran", "--preset", "3", "--input", "x=0.01", "--input", "h=0.1"]
        res = run_cli(*args)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args=" ".join(args))
        assert res.returncode == 1
        out = res.stdout + res.stderr
        assert "fortran: INPUT: F(X-H) is not a finite number at X = -9.0" in out
        assert HEADING + "AT X =  0.01\n" in res.stdout

    def test_cli_ch04_expression_overflow_python(self, evidence):
        args = ["run", "ch04_p01", "--engine", "python", "--expr", "x*1e308", "--input", "x=1.9", "--input", "h=0.1"]
        res = run_cli(*args)
        evidence(stdout=res.stdout, stderr=res.stderr, exit_code=res.returncode, args=" ".join(args))
        assert res.returncode == 1
        assert "python: EXPRESSION: x * 1e+308 is not a finite number at x = 1.9" in res.stdout + res.stderr
        assert HEADING + "AT X =  1.90\n" in res.stdout
