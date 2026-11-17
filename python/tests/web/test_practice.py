"""Practice questions: answers checked against the engines."""

import pytest
from fastapi.testclient import TestClient

from gerald_na.registry import PracticeQuestion, get_registry
from gerald_na.web.practice import answer_kind, parse_answer
from tests.web.conftest import BISECTION, HX


def check(
    client: TestClient, question: str, answer: str, program: str = BISECTION
) -> tuple[int, str]:
    response = client.post(
        f"/programs/{program}/practice/{question}", data={"answer": answer}, headers=HX
    )
    return response.status_code, response.text


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("book-iterations", "15"),
        ("loose-tol-iterations", "9"),
        ("loose-tol-root", "0.443359"),
        ("cubic-root", "1.324718"),
        ("dottie-iterations", "16"),
    ],
)
def test_correct_answers(python_only_client: TestClient, question: str, answer: str) -> None:
    status, html = check(python_only_client, question, answer)
    assert status == 200
    assert 'data-correct="true"' in html
    assert 'data-testid="practice-computed-python"' in html
    assert 'data-testid="practice-explanation"' in html


def test_incorrect_answer_shows_computed_value(python_only_client: TestClient) -> None:
    status, html = check(python_only_client, "book-iterations", "14")
    assert status == 200
    assert 'data-correct="false"' in html
    assert "Incorrect" in html
    assert "The engine computes 15" in html
    status, html = check(python_only_client, "loose-tol-root", "0.4435")  # outside 5e-6
    assert 'data-correct="false"' in html


def test_unreadable_answer_is_422(python_only_client: TestClient) -> None:
    status, html = check(python_only_client, "book-iterations", "fifteen")
    assert status == 422
    assert 'data-testid="practice-invalid"' in html


def test_unknown_question_is_404(python_only_client: TestClient) -> None:
    assert check(python_only_client, "no-such-question", "1")[0] == 404


@pytest.mark.fortran
def test_fortran_answer_shown_when_available(client: TestClient) -> None:
    status, html = check(client, "cubic-root", "1.3247185")
    assert status == 200
    assert 'data-correct="true"' in html
    assert 'data-testid="practice-computed-fortran"' in html


def test_practice_without_engine(lagrange_client: TestClient) -> None:
    status, html = check(lagrange_client, "value-at-3", "9", "lagrange_interpolation")
    assert status == 200
    assert 'data-correct="unknown"' in html
    assert "could not be computed" in html


def test_practice_with_point_list(lagrange_client: TestClient, lagrange_adapter: object) -> None:
    status, html = check(lagrange_client, "value-at-3", "9.0000001", "lagrange_interpolation")
    assert status == 200
    assert 'data-correct="true"' in html


def test_parse_answer_kinds() -> None:
    entry = get_registry().get(BISECTION)
    converged = PracticeQuestion(
        id="c", prompt="p", answer_field="converged", explanation="e", tolerance=0.0
    )
    assert answer_kind(entry, converged) == "bool"
    assert answer_kind(entry, entry.practice[0]) == "number"
    root_q = PracticeQuestion(id="r", prompt="p", answer_field="root_at_endpoint", explanation="e")
    assert answer_kind(entry, root_q) == "bool"
    assert parse_answer(" Yes ", "bool") is True
    assert parse_answer(".FALSE.", "bool") is False
    assert parse_answer("1.E-3", "number") == pytest.approx(1e-3)
    with pytest.raises(ValueError, match="yes or no"):
        parse_answer("maybe", "bool")
    with pytest.raises(ValueError, match="not a number"):
        parse_answer("inf", "number")
