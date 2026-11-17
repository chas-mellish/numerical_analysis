"""Functional tests of the HTML routes, practice checks and the whitelisted file route."""

import pytest
import requests

from conftest import BASE_URL


@pytest.fixture(autouse=True)
def _up(server):
    return server


class TestHtmlPages:
    def test_html_home_lists_programs(self, evidence):
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:2500], endpoint="/", method="GET")
        assert resp.status_code == 200
        for pid in ("ch01_p01", "ch01_p02", "ch03_p01", "ch03_p02", "lagrange_interpolation"):
            assert f"/programs/{pid}" in resp.text

    def test_html_program_page(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/ch01_p01", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:2500], endpoint="/programs/ch01_p01", method="GET")
        assert resp.status_code == 200
        for testid in ("engine-python", "engine-fortran", "engine-compare", "data-card"):
            assert f'data-testid="{testid}"' in resp.text

    def test_html_program_page_not_found(self, evidence):
        resp = requests.get(f"{BASE_URL}/programs/ch09_p09", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:1000], endpoint="/programs/ch09_p09", method="GET")
        assert resp.status_code == 404

    def test_html_run_form_compare_simpson(self, evidence):
        form = {"engine": "compare", "in_b": "5.0", "in_n": "100", "function": "1"}
        resp = requests.post(f"{BASE_URL}/programs/ch03_p01/run", data=form, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:3000], request=form,
                 endpoint="/programs/ch03_p01/run", method="POST")
        assert resp.status_code == 200
        assert 'data-testid="compare-view"' in resp.text
        assert 'data-testid="book-text-fortran"' in resp.text
        assert "1.5499312" in resp.text

    def test_html_run_form_fortran_bisection(self, evidence):
        form = {"engine": "fortran", "in_x1": "0.", "in_x2": "1.", "in_tol": "1.E-5", "function": "1"}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:3000], request=form,
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 200
        assert "15 ITERATIONS WERE REQUIRED" in resp.text

    def test_html_run_form_invalid_value(self, evidence):
        form = {"engine": "python", "in_x1": "abc", "in_x2": "1.", "in_tol": "1.E-5", "function": "1"}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:2000], request=form,
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422

    def test_html_run_form_custom_on_fortran(self, evidence):
        form = {"engine": "fortran", "in_x1": "1", "in_x2": "2", "in_tol": "1.E-5",
                "function": "custom", "expression": "x - 1.5"}
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/run", data=form, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:2000], request=form,
                 endpoint="/programs/ch01_p01/run", method="POST")
        assert resp.status_code == 422


class TestPractice:
    def test_practice_correct_answer(self, evidence):
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/practice/book-iterations",
                             data={"answer": "15"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text, request={"answer": "15"},
                 endpoint="/programs/ch01_p01/practice/book-iterations", method="POST")
        assert resp.status_code == 200
        assert 'data-testid="practice-verdict" data-correct="true"' in resp.text

    def test_practice_wrong_answer(self, evidence):
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/practice/book-iterations",
                             data={"answer": "14"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text, request={"answer": "14"},
                 endpoint="/programs/ch01_p01/practice/book-iterations", method="POST")
        assert resp.status_code == 200
        assert 'data-correct="false"' in resp.text

    def test_practice_unreadable_answer(self, evidence):
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/practice/book-iterations",
                             data={"answer": "abc"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text, request={"answer": "abc"},
                 endpoint="/programs/ch01_p01/practice/book-iterations", method="POST")
        assert resp.status_code == 422

    def test_practice_unknown_question(self, evidence):
        resp = requests.post(f"{BASE_URL}/programs/ch01_p01/practice/nope",
                             data={"answer": "1"}, timeout=30)
        evidence(status=resp.status_code, body=resp.text[:800], request={"answer": "1"},
                 endpoint="/programs/ch01_p01/practice/nope", method="POST")
        assert resp.status_code == 404


class TestFileRoute:
    @pytest.mark.parametrize(
        ("path", "ctype", "needle"),
        [
            ("ch01_p01/scan", "application/pdf", b"%PDF"),
            ("ch01_p01/legacy", "text/plain", b"PROGRAM"),
            ("ch01_p01/fortran_module", "text/plain", b"module"),
            ("ch01_p01/python", "text/plain", b"def bisection"),
            ("ch01_p01/study", "text/plain", b"#"),
        ],
        ids=["scan", "legacy", "fortran_module", "python", "study"],
    )
    def test_files_whitelisted(self, path, ctype, needle, evidence):
        resp = requests.get(f"{BASE_URL}/files/{path}", timeout=10)
        evidence(status=resp.status_code, body=f"{resp.headers.get('content-type')} {resp.content[:120]!r}",
                 endpoint=f"/files/{path}", method="GET")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(ctype)
        assert needle.lower() in resp.content[:20000].lower()

    @pytest.mark.parametrize(
        "path",
        ["ch01_p01/..%2F..%2Fetc%2Fpasswd", "..%2F..%2Fetc/passwd", "ch01_p01/%2e%2e",
         "ch01_p01/legacy?index=9", "ch01_p01/legacy?index=-1", "ch01_p01/legacy?index=..%2F..",
         "lagrange_interpolation/scan", "ch01_p01/secrets", "nope/scan"],
        ids=["encoded_traversal_kind", "encoded_traversal_id", "dotdot_kind", "index_oob",
             "index_negative", "index_traversal", "missing_scan", "unknown_kind", "unknown_program"],
    )
    def test_files_rejects_outside_whitelist(self, path, evidence):
        resp = requests.get(f"{BASE_URL}/files/{path}", timeout=10)
        evidence(status=resp.status_code, body=resp.text[:300], endpoint=f"/files/{path}", method="GET")
        assert resp.status_code == 404
        assert b"root:" not in resp.content
