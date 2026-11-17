"""Practice questions: run the engines with the question's inputs and check a learner answer.

The reference is always computed, never read from the catalog's ``answer`` field: the Python
engine runs the question's inputs (book card plus ``[[practice]] inputs``) and preset, and the
learner's answer is compared with the result attribute ``answer_field`` within ``tolerance``
(absolute; booleans and a zero tolerance compare exactly). When the Fortran driver is available
it runs too and its answer is shown beside Python's.
"""

import math
from dataclasses import dataclass, field

from gerald_na.engines import RunOutcome, RunRequest
from gerald_na.errors import GeraldNAError
from gerald_na.registry import CatalogEntry, PracticeQuestion
from gerald_na.web.forms import parse_number
from gerald_na.web.presenters import format_value
from gerald_na.web.services import WebState

__all__ = ["ComputedAnswer", "PracticeCheck", "answer_kind", "check_practice", "parse_answer"]

_TRUE = {"true", "t", "yes", "y", "1", ".true."}
_FALSE = {"false", "f", "no", "n", "0", ".false."}


@dataclass
class ComputedAnswer:
    """What one engine computed for the question."""

    engine: str
    value: object = None
    text: str = ""
    error: str | None = None


@dataclass
class PracticeCheck:
    """The feedback for one submitted answer."""

    question: PracticeQuestion
    answer_text: str
    correct: bool | None
    message: str
    computed: list[ComputedAnswer] = field(default_factory=list)
    readable: bool = True
    """False when the learner's answer could not be read (nothing was run)."""


def answer_kind(entry: CatalogEntry, question: PracticeQuestion) -> str:
    """``bool`` or ``number``: how the learner's answer is read."""
    if question.answer_field == "converged":
        return "bool"
    for extra in entry.trace.result_extras:
        if extra.key == question.answer_field and extra.type == "bool":
            return "bool"
    return "number"


def parse_answer(text: str, kind: str) -> bool | float:
    """The learner's answer as a value; raises :class:`ValueError` when unreadable."""
    value = text.strip()
    if kind == "bool":
        lowered = value.lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ValueError("answer yes or no (true/false)")
    return float(parse_number(value, integer=False))


def _computed(outcome: RunOutcome, answer_field: str) -> ComputedAnswer:
    if outcome.error is not None:
        return ComputedAnswer(
            outcome.engine, error=f"{outcome.error.code}: {outcome.error.message}"
        )
    value = getattr(outcome.result, answer_field, None)
    if value is None:
        return ComputedAnswer(outcome.engine, error=f"the result has no {answer_field!r}")
    return ComputedAnswer(outcome.engine, value=value, text=format_value(value))


def _matches(learner: bool | float, reference: object, tolerance: float) -> bool:
    if isinstance(learner, bool) or isinstance(reference, bool):
        return bool(learner) == bool(reference) and isinstance(learner, bool)
    if not isinstance(reference, int | float):
        return False
    difference = abs(float(learner) - float(reference))
    return math.isfinite(difference) and difference <= tolerance


def check_practice(
    state: WebState, entry: CatalogEntry, question: PracticeQuestion, answer_text: str
) -> PracticeCheck:
    """Check ``answer_text`` against the engines (see the module docstring)."""
    kind = answer_kind(entry, question)
    try:
        learner = parse_answer(answer_text, kind)
    except ValueError as exc:
        return PracticeCheck(question, answer_text, None, str(exc), readable=False)
    request = RunRequest.for_entry(entry, entry.practice_inputs(question), preset=question.preset)
    computed: list[ComputedAnswer] = []
    statuses = state.engine_statuses(entry)
    for name in ("python", "fortran"):
        if not statuses[name].available:
            continue
        try:
            engine = state.python_engine() if name == "python" else state.fortran_runner()
            computed.append(_computed(engine.run(entry, request), question.answer_field))
        except GeraldNAError as exc:
            computed.append(ComputedAnswer(name, error=f"{exc.code}: {exc.message}"))
    reference = next((item for item in computed if item.error is None), None)
    if reference is None:
        reason = computed[0].error if computed else "no engine is available for this program"
        return PracticeCheck(
            question, answer_text, None, f"the answer could not be computed ({reason})", computed
        )
    correct = _matches(learner, reference.value, question.tolerance)
    tolerance = "" if question.tolerance == 0 else f" (within {question.tolerance:g})"
    if correct:
        message = f"Your answer matches the computed {reference.text}{tolerance}."
    else:
        message = f"The engine computes {reference.text}{tolerance}."
    return PracticeCheck(question, answer_text, correct, message, computed)
