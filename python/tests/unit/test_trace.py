"""Generic ``--trace`` parser (DD2): typing of values, record access, protocol violations."""

import math

import pytest

from gerald_na.engines.trace import (
    MAX_LINE_LENGTH,
    Record,
    Trace,
    parse_trace,
    parse_value,
)
from gerald_na.errors import FortranRunError

BOOK_TRACE = """\
STEP,k=1,x1=0.00000000000000000E+000,x2=1.00000000000000000E+000,x=5.00000000000000000E-001,fx=-1.00576112000487550E-001
STEP,k=2,x1=0.00000000000000000E+000,x2=5.00000000000000000E-001,x=2.50000000000000000E-001,fx=3.96117356895129225E-001
RESULT,value=2.50000000000000000E-001,converged=T,iterations=2,root_at_endpoint=F
"""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("T", True),
        ("F", False),
        ("15", 15),
        ("-3", -3),
        ("4.43572998046875000E-001", 0.443572998046875),
        ("-1.00000000000000000E+003", -1000.0),
        ("1.5", 1.5),
        ("quadratic", "quadratic"),
        ("BRACKET", "BRACKET"),
    ],
)
def test_values_are_typed(text: str, expected: object) -> None:
    value = parse_value(text)
    assert value == expected
    assert type(value) is type(expected)


@pytest.mark.parametrize(("text", "check"), [("NaN", math.isnan), ("-Infinity", math.isinf)])
def test_ieee_specials_are_reals(text: str, check: object) -> None:
    value = parse_value(text)
    assert isinstance(value, float)
    assert check(value)  # type: ignore[operator]


def test_parses_steps_and_result() -> None:
    trace = parse_trace(BOOK_TRACE)
    assert isinstance(trace, Trace)
    assert len(trace) == 3
    assert [record.integer("k") for record in trace.steps] == [1, 2]
    assert trace.steps[0].real("fx") == -1.00576112000487550e-001
    result = trace.result
    assert result is not None
    assert trace.error is None
    assert trace.terminal is result
    assert result.real("value") == 0.25
    assert result.logical("converged") is True
    assert result.logical("root_at_endpoint") is False
    assert result.integer("iterations") == 2
    assert result.line == 3
    assert "value" in result
    assert result["iterations"] == 2
    assert [r.type for r in trace] == ["STEP", "STEP", "RESULT"]


def test_any_record_type_is_grouped() -> None:
    text = (
        "TABLE,row=1,col=1,value=1.60772551000000000E+000\n"
        "FACTOR,kind=quadratic,r=4.2E+000,s=-2.1E+000\n"
        "TABLE,row=2,col=1,value=1.61565910000000000E+000\n"
        "RESULT,value=2.0,converged=T,iterations=7,subintervals=80\n"
    )
    trace = parse_trace(text)
    assert [r.integer("row") for r in trace.of_type("TABLE")] == [1, 2]
    factor = trace.of_type("FACTOR")[0]
    assert factor.text("kind") == "quadratic"
    assert factor.real("s") == -2.1
    assert trace.of_type("NOPE") == ()
    assert trace.result is not None
    assert trace.result.integer("subintervals") == 80


def test_error_record_keeps_the_message_verbatim() -> None:
    text = (
        "STEP,k=1,x1=0.0,x2=1.0,x=0.5,fx=1.0\n"
        "ERROR,code=ZERO_PRODUCT,message=ERROR. FX1 AND FX2 NOT ZERO, = THOUGH\n"
    )
    trace = parse_trace(text)
    assert trace.result is None
    error = trace.error
    assert error is not None
    assert error.text("code") == "ZERO_PRODUCT"
    assert error.text("message") == "ERROR. FX1 AND FX2 NOT ZERO, = THOUGH"
    assert len(trace.steps) == 1


def test_blank_lines_and_fortran_padding_are_ignored() -> None:
    trace = parse_trace("\n" + BOOK_TRACE.replace("\n", "   \n") + "\n\n")
    assert len(trace) == 3


def test_text_accessor_spells_logicals_and_numbers() -> None:
    record = Record("RESULT", {"converged": True, "n": 3, "flag": False})
    assert record.text("converged") == "T"
    assert record.text("flag") == "F"
    assert record.text("n") == "3"


def test_integers_widen_to_reals() -> None:
    assert Record("STEP", {"k": 3}).real("k") == 3.0


@pytest.mark.parametrize(
    ("record", "call"),
    [
        (Record("STEP", {"k": 1.5}), lambda r: r.integer("k")),
        (Record("STEP", {"k": True}), lambda r: r.integer("k")),
        (Record("STEP", {"x": "abc"}), lambda r: r.real("x")),
        (Record("STEP", {"x": True}), lambda r: r.real("x")),
        (Record("RESULT", {"converged": 1}), lambda r: r.logical("converged")),
        (Record("STEP", {}), lambda r: r.real("x")),
    ],
)
def test_wrong_field_types_are_protocol_errors(record: Record, call: object) -> None:
    with pytest.raises(FortranRunError):
        call(record)  # type: ignore[operator]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("", "empty trace"),
        ("\n  \n", "empty trace"),
        ("STEP,k=1,x=0.5\n", "no RESULT or ERROR"),
        ("Hello from a crashed driver\n", "record type"),
        ("step,k=1\nRESULT,value=1.0,converged=T,iterations=1\n", "record type"),
        ("STEP,k\nRESULT,value=1.0,converged=T,iterations=1\n", "key=value"),
        ("STEP,K=1\nRESULT,value=1.0,converged=T,iterations=1\n", "key=value"),
        ("STEP,k=1,k=2\nRESULT,value=1.0,converged=T,iterations=1\n", "duplicate"),
        ("STEP,k=\nRESULT,value=1.0,converged=T,iterations=1\n", "empty or padded"),
        ("STEP,k= 1\nRESULT,value=1.0,converged=T,iterations=1\n", "empty or padded"),
        ("RESULT,value=1.0,converged=T,iterations=1\nSTEP,k=1\n", "must be the last"),
        (
            "RESULT,value=1.0,converged=T,iterations=1\nRESULT,value=1.0,converged=T,iterations=1\n",
            "exactly one",
        ),
        (
            "RESULT,value=1.0,converged=T,iterations=1\nERROR,code=INPUT,message=x\n",
            "exactly one",
        ),
        ("RESULT,value=1.0,converged=T\n", "iterations"),
        ("RESULT,value=abc,converged=T,iterations=1\n", "not a real"),
        ("RESULT,value=1.0,converged=yes,iterations=1\n", "not T or F"),
        ("RESULT,value=1.0,converged=T,iterations=1.5\n", "not an integer"),
        ("ERROR,code=BRACKET\n", "message"),
        ("ERROR,message=no code\n", "code"),
        ("STEP," + "x" * MAX_LINE_LENGTH + "\n", "longer than"),
    ],
)
def test_malformed_output_raises_fortran_run_error(text: str, match: str) -> None:
    with pytest.raises(FortranRunError, match=match):
        parse_trace(text)


def test_error_messages_quote_a_short_snippet() -> None:
    with pytest.raises(FortranRunError) as info:
        parse_trace("garbage " * 100 + "\n")
    assert "line 1" in info.value.message
    assert "..." in info.value.message
    assert len(info.value.message) < 200
