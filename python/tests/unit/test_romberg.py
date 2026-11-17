"""Chapter 3, Program 2 (Romberg integration): book data card, every original branch, properties."""

import math
from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.special import sici

from gerald_na.algorithms import RombergResult, RombergStep, Rounding, romberg
from gerald_na.algorithms.romberg import (
    BOOK_FIRST_PANELS,
    BOOK_MAX_HALVINGS,
    BOOK_SEED,
    sinc,
)
from gerald_na.engines import PythonEngine, RunRequest
from gerald_na.engines.adapters import get_adapter
from gerald_na.engines.adapters.romberg import RombergAdapter, book_seed_for
from gerald_na.engines.trace import parse_trace
from gerald_na.errors import ExpressionError, FortranRunError, InputError
from gerald_na.expr import compile_expr
from gerald_na.registry import CatalogEntry, get_registry

BOOK_CARD = (15.0, 2.0e-7)  # "15.0  2.E-7"

# The printed table of the scan (docs/chapter_03_program_02_listing.pdf): line L = TRAP(1..L, L).
SCAN_TABLE = (
    (1.6077255,),
    (1.6156591, 1.6183036),
    (1.6175654, 1.6182008, 1.6181940),
    (1.6180369, 1.6181940, 1.6181936, 1.6181936),
)

# The scan's output, line by line with the carriage-control column consumed. The two blank
# lines before the heading come from the // of format 200.
SCAN_OUTPUT = """\


VALUE OF SINE INTEGRAL BETWEEN 0 AND  15.00 BY ROMBERG INTEGRATION

1.6077255
1.6156591 1.6183036
1.6175654 1.6182008 1.6181940
1.6180369 1.6181940 1.6181936 1.6181936

VALUE IS  1.6181936,
  80 SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF  2.0000000E-07
"""

SI_15 = float(sici(15.0)[0])


@pytest.fixture(scope="module")
def book_result() -> RombergResult:
    return romberg(sinc, *BOOK_CARD)


@pytest.fixture(scope="module")
def entry() -> CatalogEntry:
    return get_registry().get("ch03_p02")


# ---------------------------------------------------------------- the book's data card


def test_book_card_converges_after_80_subintervals(book_result: RombergResult) -> None:
    assert book_result.converged
    assert book_result.iterations == 3
    assert book_result.subintervals == 80
    assert [len(line) for line in book_result.table] == [1, 2, 3, 4]
    assert len(book_result.steps) == 3
    assert book_result.value == book_result.table[-1][-1]
    assert (book_result.b, book_result.tol) == BOOK_CARD


def test_book_card_value(book_result: RombergResult) -> None:
    assert book_result.value == pytest.approx(1.6181936, abs=1e-6)  # the book
    assert book_result.value == pytest.approx(SI_15, abs=1e-9)  # Si(15) in real64
    assert book_result.value == 1.6181944440409433  # bit for bit (catalog real64_value)


def test_book_card_table_matches_the_scan(book_result: RombergResult) -> None:
    for got_line, want_line in zip(book_result.table, SCAN_TABLE, strict=True):
        for got, want in zip(got_line, want_line, strict=True):
            assert got == pytest.approx(want, abs=1e-6)


def test_book_card_tolerance_test(book_result: RombergResult) -> None:
    """IF (ABSF(TRAP(I+1,I+1) - TRAP(I,I+1)) - TOL) 50,50,20: line 3 fails, line 4 passes."""
    diffs = [step.diff for step in book_result.steps]
    assert diffs[0] > 2e-7
    assert diffs[1] == pytest.approx(abs(SCAN_TABLE[2][2] - SCAN_TABLE[2][1]), rel=0.05)
    assert diffs[1] > 2e-7
    assert diffs[2] <= 2e-7
    # the book's own line 4 meets the test as well
    assert abs(SCAN_TABLE[3][3] - SCAN_TABLE[3][2]) <= 2e-7


def test_step_records(book_result: RombergResult) -> None:
    for i, step in enumerate(book_result.steps, start=1):
        assert step == RombergStep(
            k=i,
            panels=BOOK_FIRST_PANELS * 2**i,
            h=1.5 / 2**i,
            trap=book_result.trap(1, i + 1),
            best=book_result.trap(i + 1, i + 1),
            diff=abs(book_result.trap(i + 1, i + 1) - book_result.trap(i, i + 1)),
        )


def test_extrapolation_formula(book_result: RombergResult) -> None:
    """Label 40: TRAP(II+1,I+1) = TRAP(II,I+1) + 1./(4.**II-1.)*(TRAP(II,I+1) - TRAP(II,I))."""
    t = book_result.trap
    for col in range(2, len(book_result.table) + 1):
        for ii in range(1, col):
            expected = t(ii, col) + (1.0 / (4.0**ii - 1.0)) * (t(ii, col) - t(ii, col - 1))
            assert t(ii + 1, col) == expected


def test_first_column_is_the_trapezoidal_rule() -> None:
    result = romberg(lambda x: math.exp(-x * x), 2.0, -1.0)  # negative TOL: the full table
    for col, line in enumerate(result.table, start=1):
        n = BOOK_FIRST_PANELS * 2 ** (col - 1)
        h = 2.0 / n
        trapezoid = h * (
            (1.0 + math.exp(-4.0)) / 2.0 + math.fsum(math.exp(-((i * h) ** 2)) for i in range(1, n))
        )
        assert line[0] == pytest.approx(trapezoid, rel=1e-13)


def test_trap_accessor(book_result: RombergResult) -> None:
    assert book_result.trap(1, 1) == book_result.table[0][0]
    assert book_result.trap(4, 4) == book_result.value
    for bad in ((2, 1), (0, 1), (1, 5), (5, 5)):
        with pytest.raises(IndexError):
            book_result.trap(*bad)


# ---------------------------------------------------------------- book text


def _replay(table: tuple[tuple[float, ...], ...]) -> RombergResult:
    """A result holding the book's printed values, nudged up by half a unit of the 7th decimal
    so that the chopping output conversion prints exactly the scan's digits."""
    nudged = tuple(tuple(v + 5e-9 for v in line) for line in table)
    return RombergResult(
        value=nudged[-1][-1],
        converged=True,
        iterations=len(table) - 1,
        steps=(),
        table=nudged,
        subintervals=BOOK_FIRST_PANELS * 2 ** (len(table) - 1),
        b=BOOK_CARD[0],
        tol=BOOK_CARD[1],
    )


def test_book_text_with_book_values_reproduces_the_scan() -> None:
    """Character for character, except the documented table alignment (erratum
    table-row-alignment: FORMAT 203 puts one more blank before each table line than the scan
    shows) and the trailing blanks of the Hollerith fields (invisible on paper)."""
    text = _replay(SCAN_TABLE).book_text()
    lines = text.splitlines()
    table_lines = slice(4, 8)
    assert all(line.startswith(" 1.") for line in lines[table_lines])
    lines[table_lines] = [line[1:] for line in lines[table_lines]]
    assert [line.rstrip() for line in lines] == SCAN_OUTPUT.splitlines()
    # the Hollerith fields keep their trailing blanks: 24H ... INTEGRATION_ and 2H,_
    assert lines[2].endswith("INTEGRATION ")
    assert lines[9] == "VALUE IS  1.6181936, "


def test_book_text_of_the_book_card(book_result: RombergResult) -> None:
    assert book_result.book_text() == (
        "\n"
        "\n"
        "VALUE OF SINE INTEGRAL BETWEEN 0 AND  15.00 BY ROMBERG INTEGRATION \n"
        "\n"
        " 1.6077254\n"
        " 1.6156591 1.6183036\n"
        " 1.6175654 1.6182009 1.6181940\n"
        " 1.6180375 1.6181948 1.6181944 1.6181944\n"
        "\n"
        "VALUE IS  1.6181944, \n"
        "  80 SUBINTERVALS WERE REQUIRED TO MEET TOLERANCE OF  2.0000000E-07\n"
    )


def test_book_text_carriage_control_and_rounding(book_result: RombergResult) -> None:
    plain = book_result.book_text().splitlines()
    with_cc = book_result.book_text(carriage_control=True).splitlines()
    assert [line[1:] for line in with_cc] == plain
    assert with_cc[4] == "  1.6077254"
    assert with_cc[-1].startswith("   80 SUBINTERVALS")
    # chopping (the book's printer) versus rounding: 1.60772548... prints 1.6077254 / 1.6077255
    nearest = book_result.book_text(rounding=Rounding.NEAREST).splitlines()
    assert nearest[4] == " 1.6077255"


def test_input_echoes_are_rounded_to_nearest() -> None:
    """B and TOL are card values: 2.3 must not print as 2.29, 2.E-7 not as 1.9999999E-07."""
    text = romberg(sinc, 2.3, 2.0e-7).book_text()
    assert "BETWEEN 0 AND   2.30 BY" in text
    assert text.endswith("TOLERANCE OF  2.0000000E-07\n")
    small = romberg(sinc, 0.5, 1.0e-3).book_text()
    assert "BETWEEN 0 AND    .50 BY" in small  # no leading zero, like the book's printer


# ---------------------------------------------------------------- not meeting TOL


def test_non_convergence_after_8_extrapolations() -> None:
    result = romberg(math.sqrt, 1.0, 1.0e-14)
    assert not result.converged
    assert result.iterations == BOOK_MAX_HALVINGS
    assert result.subintervals == 2560
    assert [len(line) for line in result.table] == list(range(1, 10))
    assert result.value == result.trap(9, 9)
    assert all(step.diff > 1.0e-14 for step in result.steps)
    assert result.value == pytest.approx(2.0 / 3.0, abs=1e-4)


def test_non_convergence_book_text() -> None:
    result = romberg(math.sqrt, 1.0, 1.0e-14)
    lines = result.book_text().splitlines()
    # 4 heading records, 9 table lines of which line 9 takes two records (8 + 1 values),
    # a blank line and format 201
    assert len(lines) == 4 + 10 + 2
    assert len(lines[12].split()) == 8
    assert len(lines[13].split()) == 1
    assert lines[-1].startswith("VALUE IS ")
    assert lines[-1].endswith(" BUT DID NOT MEET TOLERANCE OF  1.0000000E-14")
    assert "SUBINTERVALS" not in result.book_text()


def test_negative_tol_is_never_met() -> None:
    result = romberg(lambda x: 1.0, 3.0, -1.0)
    assert not result.converged
    assert result.iterations == BOOK_MAX_HALVINGS
    assert result.value == 3.0


def test_zero_difference_takes_the_zero_branch() -> None:
    """IF (...) 50,50,20: a difference equal to TOL (here 0 = 0) converges."""
    result = romberg(lambda x: 1.0, 4.0, 0.0)
    assert result.converged
    assert result.iterations == 1
    assert result.steps[0].diff == 0.0
    assert result.value == 4.0


def test_runge_preset_does_not_converge_in_real64() -> None:
    result = romberg(lambda x: 1.0 / (1.0 + x * x), 100.0, 1.0e-13)
    assert not result.converged
    assert result.value == pytest.approx(math.atan(100.0), abs=1e-6)


def test_zero_upper_limit() -> None:
    result = romberg(sinc, 0.0, 2.0e-7)
    assert result.converged
    assert result.iterations == 1
    assert result.value == 0.0


# ---------------------------------------------------------------- the seed F0 + F(B)


def test_sinc_has_the_book_limit() -> None:
    assert sinc(0.0) == BOOK_SEED == 1.0
    assert sinc(2.0) == math.sin(2.0) / 2.0


def test_f0_book_seed_equals_the_limit(book_result: RombergResult) -> None:
    seeded = romberg(lambda x: math.sin(x) / x, *BOOK_CARD, f0=BOOK_SEED)
    assert seeded == book_result


def test_f0_replaces_f_at_zero() -> None:
    calls: list[float] = []

    def f(x: float) -> float:
        calls.append(x)
        return 3.0 * x + 1.0

    result = romberg(f, 2.0, 1e-12, f0=1.0)
    assert 0.0 not in calls
    assert result.trap(1, 1) == pytest.approx(8.0, rel=1e-15)  # exact for a linear integrand
    default = romberg(lambda x: 3.0 * x + 1.0, 2.0, 1e-12)
    assert default.table == result.table


def test_compiled_book_expression_needs_the_seed() -> None:
    """SIN(X)/X compiled by gerald_na.expr divides by zero at X = 0 without the book's seed."""
    f = compile_expr("SIN(X)/X")
    with pytest.raises(ExpressionError) as info:
        romberg(f, *BOOK_CARD)
    assert info.value.steps == ()
    assert romberg(f, *BOOK_CARD, f0=BOOK_SEED).value == 1.6181944440409433


@pytest.mark.parametrize(
    ("b", "tol", "f0"),
    [(math.nan, 1e-6, None), (math.inf, 1e-6, None), (1.0, math.nan, None), (1.0, 1e-6, math.inf)],
)
def test_non_finite_inputs_are_input_errors(b: float, tol: float, f0: float | None) -> None:
    with pytest.raises(InputError):
        romberg(sinc, b, tol, f0=f0)


def test_nan_function_value_is_an_input_error() -> None:
    def f(x: float) -> float:
        return math.nan if 0.24 < x < 0.26 else math.cos(x)

    with pytest.raises(InputError) as info:
        romberg(f, 10.0, 1e-30)
    assert "X = 0.25" in info.value.message
    steps = info.value.steps
    assert all(isinstance(step, RombergStep) for step in steps)
    assert [step.k for step in steps if isinstance(step, RombergStep)] == [1]  # met at halving 2
    assert type(info.value) is InputError


def test_nan_at_zero_is_an_input_error() -> None:
    with pytest.raises(InputError) as info:
        romberg(lambda x: math.nan if x == 0.0 else 1.0, 1.0, 1e-6)
    assert info.value.steps == ()


# ---------------------------------------------------------------- the book's arithmetic


def _chop27(x: float) -> float:
    """Chop ``x`` to a 27-bit binary mantissa (the book's single precision, IBM 7090 class)."""
    if x == 0.0:
        return 0.0
    mantissa, exponent = math.frexp(x)
    return math.ldexp(math.trunc(mantissa * 2**27) / 2**27, exponent)


def _romberg_chopped(b: float, tol: float) -> tuple[list[list[float]], int]:
    """The listing evaluated with every result chopped to 27 bits (test-only model)."""
    c = _chop27

    def fcn(x: float) -> float:
        return c(c(math.sin(x)) / x)

    h = c(b / 10.0)
    total = c(1.0 + fcn(b))
    x = 0.0
    for _ in range(2, 11):
        x = c(x + h)
        total = c(total + c(fcn(x) * 2.0))
    columns = [[c(c(h / 2.0) * total)]]
    k = 10
    for i in range(1, 9):
        h = c(h / 2.0)
        x = h
        k = 10 * 2**i
        for _ in range(2, k + 1, 2):
            total = c(total + c(fcn(x) * 2.0))
            x = c(c(x + h) + h)
        column = [c(c(h / 2.0) * total)]
        for ii in range(1, i + 1):
            q = c(1.0 / (4.0**ii - 1.0))
            column.append(c(column[ii - 1] + c(q * c(column[ii - 1] - columns[i - 1][ii - 1]))))
        columns.append(column)
        if c(abs(c(column[i] - column[i - 1])) - tol) <= 0.0:
            break
    return columns, k


def test_book_arithmetic_model_explains_the_scan() -> None:
    """27-bit chopped arithmetic stops at the same line with K = 80 and lands within 3e-7 of
    every printed entry (IEEE real64 is up to 8.6e-7 away); the machine's own SINF is unknown,
    so the digits are not reproduced exactly (precision notes of the catalog)."""
    columns, k = _romberg_chopped(*BOOK_CARD)
    assert k == 80
    assert [len(column) for column in columns] == [1, 2, 3, 4]
    worst = max(
        abs(got - want)
        for column, line in zip(columns, SCAN_TABLE, strict=True)
        for got, want in zip(column, line, strict=True)
    )
    assert worst < 3e-7
    real64 = romberg(sinc, *BOOK_CARD)
    worst_real64 = max(
        abs(got - want)
        for column, line in zip(real64.table, SCAN_TABLE, strict=True)
        for got, want in zip(column, line, strict=True)
    )
    assert worst_real64 > 8e-7


# ---------------------------------------------------------------- engine adapter


def test_adapter_registered() -> None:
    assert isinstance(get_adapter("ch03_p02"), RombergAdapter)


def test_book_seed_only_for_the_book_integrand(entry: CatalogEntry) -> None:
    assert book_seed_for(entry, compile_expr("SIN(X)/X")) == BOOK_SEED
    assert book_seed_for(entry, compile_expr("sinf(x) / x")) == BOOK_SEED
    assert book_seed_for(entry, compile_expr("EXP(-X**2)")) is None
    assert book_seed_for(entry, compile_expr("sin(x)/x + 0")) is None
    assert book_seed_for(entry, sinc) is None


def test_python_engine_runs_the_book_card(entry: CatalogEntry, book_result: RombergResult) -> None:
    outcome = PythonEngine().run(entry, RunRequest.for_entry(entry, {}))
    assert outcome.ok
    assert outcome.result == book_result
    assert outcome.book_text == book_result.book_text()


def test_python_engine_learner_book_function_gets_the_seed(entry: CatalogEntry) -> None:
    request = RunRequest(inputs=dict(entry.data_card.values), expression="SINF(X)/X")
    outcome = PythonEngine().run(entry, request)
    assert outcome.ok
    assert outcome.result.value == 1.6181944440409433


def test_python_engine_learner_function_undefined_at_zero(entry: CatalogEntry) -> None:
    request = RunRequest(inputs=dict(entry.data_card.values), expression="1/X")
    outcome = PythonEngine().run(entry, request)
    assert outcome.status == "EXPRESSION"
    assert outcome.book_text == ""


@pytest.mark.parametrize(
    ("preset", "expected"), [(2, math.sqrt(math.pi) / 2 * math.erf(3.0)), (3, math.atan(3.0))]
)
def test_python_engine_presets(entry: CatalogEntry, preset: int, expected: float) -> None:
    request = RunRequest.for_entry(entry, {"b": 3.0, "tol": 1e-10}, preset=preset)
    outcome = PythonEngine().run(entry, request)
    assert outcome.ok
    assert outcome.result.value == pytest.approx(expected, abs=1e-10)


def _trace_text(result: RombergResult) -> list[str]:
    lines = [
        f"STEP,k={s.k},panels={s.panels},h={s.h!r},trap={s.trap!r},best={s.best!r},diff={s.diff!r}"
        for s in result.steps
    ]
    for col, line in enumerate(result.table, start=1):
        lines.extend(f"TABLE,row={row},col={col},value={v!r}" for row, v in enumerate(line, 1))
    lines.append(
        f"RESULT,value={result.value!r},converged={'T' if result.converged else 'F'},"
        f"iterations={result.iterations},subintervals={result.subintervals}"
    )
    return lines


def test_adapter_rebuilds_the_result_from_a_trace(
    entry: CatalogEntry, book_result: RombergResult
) -> None:
    inputs = {"b": 15.0, "tol": 2e-7}
    trace = parse_trace("\n".join(_trace_text(book_result)))
    assert RombergAdapter().result_from_trace(entry, inputs, trace) == book_result


@pytest.mark.parametrize(
    "mutate",
    [
        lambda lines: [line for line in lines if not line.startswith("TABLE,row=2,col=4")],
        lambda lines: [*lines[:3], "TABLE,row=5,col=4,value=1.0", *lines[3:]],
        lambda lines: [*lines[:3], lines[3], *lines[3:]],
        lambda lines: lines[1:],
        lambda lines: [line.replace("subintervals=80", "subintervals=81") for line in lines],
        lambda lines: (
            [line for line in lines if not line.startswith("RESULT")]
            + ["ERROR,code=INPUT,message=x"]
        ),
    ],
)
def test_adapter_rejects_inconsistent_traces(
    entry: CatalogEntry,
    book_result: RombergResult,
    mutate: Callable[[list[str]], list[str]],
) -> None:
    trace = parse_trace("\n".join(mutate(_trace_text(book_result))))
    with pytest.raises(FortranRunError):
        RombergAdapter().result_from_trace(entry, {"b": 15.0, "tol": 2e-7}, trace)


# ---------------------------------------------------------------- properties (Hypothesis)


@settings(max_examples=60, deadline=None)
@given(b=st.floats(min_value=0.1, max_value=20.0))
def test_converges_to_the_sine_integral(b: float) -> None:
    """With a tight TOL the result is Si(b) (scipy.special.sici as the reference)."""
    result = romberg(sinc, b, 1e-10)
    assert result.converged
    assert result.value == pytest.approx(float(sici(b)[0]), abs=1e-8)


@settings(max_examples=60, deadline=None)
@given(
    coefficients=st.lists(st.floats(min_value=-10.0, max_value=10.0), min_size=1, max_size=8),
    b=st.floats(min_value=0.1, max_value=4.0),
)
def test_exact_for_polynomials_after_extrapolation(coefficients: list[float], b: float) -> None:
    """Row r of TRAP (r - 1 extrapolations) is exact for degree <= 2r - 1: the trapezoidal
    rule for degree 1, Simpson (r = 2) for cubics, Boole (r = 3) for quintics, r = 4 for
    degree 7."""

    def p(x: float) -> float:
        value = 0.0
        for c in reversed(coefficients):
            value = value * x + c
        return value

    degree = len(coefficients) - 1
    exact = math.fsum(c * b ** (k + 1) / (k + 1) for k, c in enumerate(coefficients))
    scale = math.fsum(abs(c) * b ** (k + 1) for k, c in enumerate(coefficients)) + 1e-300
    row = (degree + 2) // 2
    result = romberg(p, b, -1.0)  # never met: all 9 lines
    for col in range(row, len(result.table) + 1):
        assert abs(result.trap(row, col) - exact) <= 1e-12 * scale
    assert abs(result.value - exact) <= 1e-12 * scale


@settings(max_examples=80, deadline=None)
@given(
    b=st.floats(min_value=0.01, max_value=100.0),
    tol=st.floats(min_value=1e-14, max_value=1.0),
    preset=st.sampled_from([sinc, lambda x: math.exp(-x * x), lambda x: 1.0 / (1.0 + x * x)]),
)
def test_table_shape_and_stopping_rule(
    b: float, tol: float, preset: Callable[[float], float]
) -> None:
    result = romberg(preset, b, tol)
    rows = result.iterations + 1
    assert 1 <= result.iterations <= BOOK_MAX_HALVINGS
    assert [len(line) for line in result.table] == list(range(1, rows + 1))
    assert len(result.steps) == result.iterations
    assert result.subintervals == BOOK_FIRST_PANELS * 2**result.iterations
    assert result.value == result.table[-1][-1]
    assert [step.k for step in result.steps] == list(range(1, rows))
    # the scan's test: every halving before the last failed it; the last one passed it
    # unless all 8 were used
    assert all(step.diff - tol > 0.0 for step in result.steps[:-1])
    if result.converged:
        assert result.steps[-1].diff - tol <= 0.0
    else:
        assert result.iterations == BOOK_MAX_HALVINGS
        assert result.steps[-1].diff - tol > 0.0


# ---------------------------------------------------------------- catalog entry


def test_catalog_entry_matches_the_book(entry: CatalogEntry) -> None:
    assert entry.data_card.tokens() == ["15.0", "2.E-7"]
    assert entry.defaults() == {"b": 15.0, "tol": 2e-7}
    expected = {item.name: item for item in entry.expected}
    assert expected["value"].book_value == pytest.approx(1.6181936)
    assert expected["subintervals"].book_value == 80
    assert expected["table"].book_value == SCAN_TABLE
    assert entry.book_output.strip("\n").splitlines() == SCAN_OUTPUT.strip("\n").splitlines()
    assert entry.function.preset(1).expr == "SIN(X)/X"
    assert [column.key for column in entry.trace.step_columns] == [
        "k",
        "panels",
        "h",
        "trap",
        "best",
        "diff",
    ]
    assert [extra.key for extra in entry.trace.result_extras] == ["subintervals"]
    assert entry.chart.kind == "romberg_heatmap"
