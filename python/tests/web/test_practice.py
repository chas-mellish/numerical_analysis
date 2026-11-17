"""Practice questions: answers checked against the engines."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from gerald_na.engines import RunOutcome, RunRequest
from gerald_na.errors import BracketError, FortranRunError, GeraldNAError
from gerald_na.registry import CatalogEntry, PracticeQuestion, get_registry
from gerald_na.web.practice import answer_kind, check_practice, parse_answer
from gerald_na.web.services import EngineStatus, WebState
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


def test_practice_without_engine(synthetic_client: TestClient) -> None:
    status, html = check(synthetic_client, "value-at-3", "9", "synthetic_points")
    assert status == 200
    assert 'data-correct="unknown"' in html
    assert "could not be computed" in html


def test_practice_with_point_list(synthetic_client: TestClient, synthetic_adapter: object) -> None:
    status, html = check(synthetic_client, "value-at-3", "9.0000001", "synthetic_points")
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


# ---------------------------------------------------------------- engine errors (stub engines)


class _StubEngine:
    """An engine whose ``run`` returns a fixed outcome or raises a fixed error."""

    def __init__(self, behaviour: RunOutcome | GeraldNAError) -> None:
        self.behaviour = behaviour

    def run(self, entry: CatalogEntry, request: RunRequest) -> RunOutcome:
        if isinstance(self.behaviour, GeraldNAError):
            raise self.behaviour
        return self.behaviour


def _stub_state(python: _StubEngine | None = None, fortran: _StubEngine | None = None) -> WebState:
    def statuses(entry: CatalogEntry) -> dict[str, EngineStatus]:
        return {
            "python": EngineStatus("python", python is not None),
            "fortran": EngineStatus("fortran", fortran is not None),
        }

    state = SimpleNamespace(
        engine_statuses=statuses, python_engine=lambda: python, fortran_runner=lambda: fortran
    )
    return cast(WebState, state)


def _outcome(engine: str, **kwargs: Any) -> RunOutcome:
    return RunOutcome(
        engine=engine, program_id=BISECTION, inputs={}, preset=None, expression=None, **kwargs
    )


def _book_iterations() -> tuple[CatalogEntry, PracticeQuestion]:
    entry = get_registry().get(BISECTION)
    question = next(q for q in entry.practice if q.id == "book-iterations")
    assert question.answer_field == "iterations"
    return entry, question


def test_outcome_error_is_reported() -> None:
    entry, question = _book_iterations()
    state = _stub_state(python=_StubEngine(_outcome("python", error=BracketError("boom"))))
    result = check_practice(state, entry, question, "15")
    assert result.correct is None
    assert "could not be computed" in result.message
    assert "BRACKET: boom" in result.message
    assert result.computed[0].error == "BRACKET: boom"


def test_engine_exception_is_recorded() -> None:
    entry, question = _book_iterations()
    state = _stub_state(python=_StubEngine(FortranRunError("driver crashed")))
    result = check_practice(state, entry, question, "15")
    assert result.correct is None
    assert result.computed[0].engine == "python"
    assert "FORTRAN_RUN: driver crashed" in result.message


def test_falls_back_to_the_other_engine() -> None:
    entry, question = _book_iterations()
    state = _stub_state(
        python=_StubEngine(_outcome("python", error=BracketError("boom"))),
        fortran=_StubEngine(_outcome("fortran", result=SimpleNamespace(iterations=15))),
    )
    result = check_practice(state, entry, question, "15")
    assert result.correct is True
    assert [item.engine for item in result.computed] == ["python", "fortran"]
    assert result.computed[0].error is not None
    assert result.computed[1].error is None


def test_result_without_the_answer_field() -> None:
    entry, question = _book_iterations()
    state = _stub_state(python=_StubEngine(_outcome("python", result=SimpleNamespace())))
    result = check_practice(state, entry, question, "15")
    assert result.correct is None
    assert "the result has no 'iterations'" in result.message


def test_non_numeric_reference_never_matches() -> None:
    entry, question = _book_iterations()
    state = _stub_state(
        python=_StubEngine(_outcome("python", result=SimpleNamespace(iterations="x")))
    )
    assert check_practice(state, entry, question, "15").correct is False
