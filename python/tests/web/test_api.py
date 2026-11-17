"""JSON API: program list and detail, runs on every engine, and the error scheme."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from gerald_na.registry import get_registry
from tests.web.conftest import BISECTION


def run(client: TestClient, body: dict[str, Any], program: str = BISECTION) -> Any:
    return client.post(f"/api/programs/{program}/run", json=body)


def test_list_programs_schema(client: TestClient) -> None:
    response = client.get("/api/programs")
    assert response.status_code == 200
    programs = response.json()
    assert isinstance(programs, list)
    assert [p["id"] for p in programs] == [e.id for e in get_registry().programs]
    bisection = next(p for p in programs if p["id"] == BISECTION)
    assert set(bisection) >= {
        "id",
        "title",
        "book_ref",
        "confirmed",
        "inputs",
        "presets",
        "engines",
        "scan_available",
        "url",
    }
    assert bisection["confirmed"] is True
    assert bisection["book_ref"]["page"] == 24
    assert [i["name"] for i in bisection["inputs"]] == ["x1", "x2", "tol"]
    tol = bisection["inputs"][2]
    assert tol["type"] == "real"
    assert tol["default"] == 1e-5
    assert tol["min"] == 1e-12
    assert [p["id"] for p in bisection["presets"]] == [1, 2, 3]
    assert "python" in bisection["engines"]
    assert bisection["scan_available"] is True


def test_list_programs_engines_without_fortran(python_only_client: TestClient) -> None:
    programs = python_only_client.get("/api/programs").json()
    assert next(p for p in programs if p["id"] == BISECTION)["engines"] == ["python"]


def test_program_detail(client: TestClient) -> None:
    response = client.get(f"/api/programs/{BISECTION}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == BISECTION
    assert data["trace"]["step_columns"][0]["key"] == "k"
    assert data["chart"]["kind"] == "bracket"
    assert len(data["practice"]) == len(get_registry().get(BISECTION).practice)
    files = data["files"]
    assert files["scan"] == f"/files/{BISECTION}/scan"
    assert files["legacy"] == [f"/files/{BISECTION}/legacy"]
    assert not any(
        str(v).startswith(("docs/", "fortran/", "/l", "content/")) for v in files.values()
    )
    assert data["engines"]["python"] == {"available": True, "reason": ""}


def test_program_detail_unknown(client: TestClient) -> None:
    response = client.get("/api/programs/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_unconfirmed_program_detail(lagrange_client: TestClient) -> None:
    data = lagrange_client.get("/api/programs/lagrange_interpolation").json()
    assert data["book_ref_confirmed"] is False
    assert data["files"]["scan"] is None
    assert data["scan_available"] is False
    listing = lagrange_client.get("/api/programs").json()
    assert listing[0]["confirmed"] is False
    assert listing[0]["engines"] == []


def test_run_python_book_card(client: TestClient) -> None:
    response = run(client, {"engine": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "OK"
    assert data["mode"] == "python"
    assert data["result"]["iterations"] == 15
    assert abs(data["result"]["value"] - 0.4435729) < 1e-7
    assert len(data["steps"]) == 15
    assert set(data["steps"][0]) == {"k", "x1", "x2", "x", "fx"}
    assert "15 ITERATIONS WERE REQUIRED." in data["book_text"]


def test_run_defaults_to_python_and_merges_inputs(client: TestClient) -> None:
    data = run(client, {"inputs": {"tol": 1e-3}}).json()
    assert data["engine"] == "python"
    assert data["result"]["iterations"] == 9
    assert data["inputs"] == {"x1": 0.0, "x2": 1.0, "tol": 1e-3}


def test_run_with_preset_and_expression(client: TestClient) -> None:
    data = run(client, {"preset": 2, "inputs": {"x1": 1, "x2": 2}}).json()
    assert data["preset"] == 2
    assert abs(data["result"]["value"] - 1.3247185) < 1e-6
    data = run(client, {"expression": "cos(x) - x"}).json()
    assert data["ok"]
    assert data["expression"] == "cos(x) - x"
    assert data["preset"] is None


@pytest.mark.fortran
def test_run_fortran(client: TestClient) -> None:
    data = run(client, {"engine": "fortran"}).json()
    assert data["ok"]
    assert data["engine"] == "fortran"
    assert data["result"]["iterations"] == 15
    assert "raw_stdout" in data


@pytest.mark.fortran
def test_run_compare(client: TestClient) -> None:
    response = run(client, {"engine": "compare"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "compare"
    assert data["ok"] is True
    assert data["engines"] == ["python", "fortran"]
    assert data["matches"] is True
    assert data["iterations"] == [15, 15]
    assert data["cells"] == []
    assert len(data["outcomes"]) == 2


def test_run_book_error_is_200(client: TestClient) -> None:
    response = run(client, {"inputs": {"x1": 2.0, "x2": 3.0}})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["status"] == "BRACKET"
    assert data["error"]["code"] == "BRACKET"
    assert "OPPOSITE SIGNS" in data["error"]["message"]
    assert "result" not in data


def test_run_errors(client: TestClient) -> None:
    cases: list[tuple[str, dict[str, Any], int, str]] = [
        ("nope", {}, 404, "NOT_FOUND"),
        (BISECTION, {"engine": "matlab"}, 422, "VALIDATION"),
        (BISECTION, {"unknown_key": 1}, 422, "VALIDATION"),
        (BISECTION, {"preset": 0}, 422, "VALIDATION"),
        (BISECTION, {"inputs": {"tol": 5}}, 422, "INPUT"),
        (BISECTION, {"inputs": {"tol": "1e-5"}}, 422, "INPUT"),
        (BISECTION, {"inputs": {"bogus": 1}}, 422, "INPUT"),
        (BISECTION, {"preset": 7}, 422, "INPUT"),
        (BISECTION, {"preset": 1, "expression": "x"}, 422, "INPUT"),
        (BISECTION, {"expression": "x +"}, 422, "EXPRESSION"),
        (BISECTION, {"expression": "open('f')"}, 422, "EXPRESSION"),
        (BISECTION, {"engine": "fortran", "expression": "x"}, 422, "CUSTOM_FUNCTION_ENGINE"),
        (BISECTION, {"engine": "compare", "expression": "x"}, 422, "CUSTOM_FUNCTION_ENGINE"),
    ]
    for program, body, status, code in cases:
        response = run(client, body, program)
        assert response.status_code == status, (body, response.text)
        assert response.json()["error"]["code"] == code, body
        assert response.json()["error"]["message"]


def test_field_errors_and_expression_position(client: TestClient) -> None:
    error = run(client, {"inputs": {"tol": 5, "x1": -5000}}).json()["error"]
    assert set(error["fields"]) == {"tol", "x1"}
    error = run(client, {"expression": "x + * 2"}).json()["error"]
    assert isinstance(error["position"], int)
    assert error["position"] >= 1


def test_run_engine_unavailable_is_503(no_binaries_client: TestClient) -> None:
    for engine in ("fortran", "compare"):
        response = run(no_binaries_client, {"engine": engine})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ENGINE_UNAVAILABLE"


def test_run_engine_disabled_is_503(python_only_client: TestClient) -> None:
    response = run(python_only_client, {"engine": "fortran"})
    assert response.status_code == 503
    assert "disabled" in response.json()["error"]["message"]


def test_run_without_adapter_is_503(lagrange_client: TestClient) -> None:
    response = run(lagrange_client, {}, "lagrange_interpolation")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ENGINE_UNAVAILABLE"


def test_run_point_list(lagrange_client: TestClient, lagrange_adapter: object) -> None:
    data = run(
        lagrange_client, {"inputs": {"points": [[0, 0], [1, 1], [2, 4]]}}, "lagrange_interpolation"
    ).json()
    assert data["ok"]
    assert data["result"]["value"] == pytest.approx(9.0)
    error = run(lagrange_client, {"expression": "x"}, "lagrange_interpolation").json()["error"]
    assert error["code"] == "INPUT"


def test_unknown_api_path_is_json_404(client: TestClient) -> None:
    response = client.get("/api/nothing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
