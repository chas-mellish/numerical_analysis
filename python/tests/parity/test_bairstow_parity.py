"""ch01_p02 parity beyond the generic suite: ``--verbose`` text and outcome coverage.

The generic ``test_parity.py`` compares results, steps, errors and the book text. Here the
driver's ``--verbose`` extras (true factors X**2 - R X - S and their roots) must equal
:meth:`BairstowResult.verbose_text` character for character, and the generated input sets must
reach every outcome (success, NON_CONVERGENT, DEGREE) and the zero-denominator nudge.
"""

import pytest

from gerald_na.engines import FortranRunner, PythonEngine, RunRequest
from gerald_na.registry import get_registry
from gerald_na.settings import Settings
from tests.parity.test_parity import input_sets

pytestmark = pytest.mark.fortran

ENTRY = get_registry().get("ch01_p02")
SINGULAR = {"a": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -16.0], "n": 4}
"""x**4 - 16 from R = S = 0: DENOM is exactly zero, one nudge."""


@pytest.fixture(scope="module")
def fortran() -> FortranRunner:
    runner = FortranRunner(Settings())
    if not runner.is_available(ENTRY):
        pytest.skip("ch01_p02_bairstow not built: run `make build-fortran`")
    return runner


CASES = [("singular", SINGULAR), *input_sets(ENTRY)]


@pytest.mark.parametrize(("label", "inputs"), CASES, ids=[label for label, _ in CASES])
def test_verbose_text_agrees(fortran: FortranRunner, label: str, inputs: dict[str, object]) -> None:
    request = RunRequest.for_entry(ENTRY, inputs, verbose=True)
    py = PythonEngine().run(ENTRY, request)
    ft = fortran.run(ENTRY, request)
    assert py.status == ft.status, (py.error, ft.error)
    assert py.book_text == ft.book_text
    if py.ok:
        assert py.verbose_text
        assert py.verbose_text == ft.verbose_text


def test_singular_card_nudges_on_both_engines(fortran: FortranRunner) -> None:
    request = RunRequest.for_entry(ENTRY, SINGULAR)
    for engine in (PythonEngine(), fortran):
        outcome = engine.run(ENTRY, request)
        assert outcome.ok, outcome.error
        assert outcome.result.nudges == 1


def test_generated_inputs_cover_every_outcome() -> None:
    statuses = {
        PythonEngine().run(ENTRY, RunRequest.for_entry(ENTRY, inputs)).status
        for _, inputs in input_sets(ENTRY)
    }
    assert {"OK", "NON_CONVERGENT", "DEGREE"} <= statuses, statuses
