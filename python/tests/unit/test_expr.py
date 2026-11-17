"""The ``ast``-whitelisted expression compiler: valid input, aliases, unsafe input, limits."""

import math
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gerald_na.errors import TRACE_ERROR_CODES, ExpressionError, GeraldNAError, InputError
from gerald_na.expr import (
    FUNCTION_ALIASES,
    FUNCTIONS,
    MAX_CONSTANT_EXPONENT,
    MAX_NODES,
    MAX_SOURCE_LENGTH,
    CompiledExpr,
    compile_expr,
    powi,
)

BOOK_F = "EXPF(-X) - SINF(3.1415926*X/2.)"


def test_book_function() -> None:
    f = compile_expr(BOOK_F)
    assert isinstance(f, CompiledExpr)
    assert f.source == BOOK_F
    assert f.normalized == "exp(-x) - sin(3.1415926 * x / 2.0)"
    for x in (0.0, 0.25, 0.5, 1.0):
        assert f(x) == math.exp(-x) - math.sin(3.1415926 * x / 2.0)
    assert f(1) == f(1.0)  # integers are accepted as x


@pytest.mark.parametrize(
    ("source", "x", "expected"),
    [
        ("x", 2.0, 2.0),
        ("X", 2.0, 2.0),
        ("2.*X", 1.5, 3.0),
        ("1.E-5", 0.0, 1.0e-5),
        ("1.e-5 + 0*x", 0.0, 1.0e-5),
        (".5*x", 4.0, 2.0),
        ("3.1415926", 0.0, 3.1415926),
        ("x**3 - x - 1", 2.0, 5.0),
        ("-x**2", 3.0, -9.0),  # ** binds tighter than unary minus, as in Fortran
        ("(-x)**2", 3.0, 9.0),
        ("2**3**2", 0.0, 512.0),  # right-associative
        ("+x - -x", 1.0, 2.0),
        ("x/4", 2.0, 0.5),
        ("cos(x) - x", 0.0, 1.0),
        ("sin(x)/x", 1.0, math.sin(1.0)),
        ("exp(-x**2)", 1.0, math.exp(-1.0)),
        ("1/(1+x**2)", 1.0, 0.5),
        ("tan(x)", 0.5, math.tan(0.5)),
        ("asin(x) + acos(x)", 0.5, math.asin(0.5) + math.acos(0.5)),
        ("atan(x)", 1.0, math.pi / 4),
        ("atan2(x, 1)", 1.0, math.pi / 4),
        ("sinh(x) + cosh(x) + tanh(x)", 0.5, math.sinh(0.5) + math.cosh(0.5) + math.tanh(0.5)),
        ("log(x) + log10(x)", 100.0, math.log(100.0) + 2.0),
        ("sqrt(x)", 9.0, 3.0),
        ("abs(x)", -2.0, 2.0),
        ("floor(x) + ceil(x)", 1.5, 3.0),
        ("pi", 0.0, math.pi),
        ("E", 0.0, math.e),
        ("PI*x", 1.0, math.pi),
        ("x**0.5", 4.0, 2.0),
        ("x**x", 2.0, 4.0),
        ("(-2)**2", 0.0, 4.0),
        ("  x + 1  ", 1.0, 2.0),
        ("x\t+ 1", 1.0, 2.0),
    ],
)
def test_valid_expressions(source: str, x: float, expected: float) -> None:
    assert compile_expr(source)(x) == pytest.approx(expected, rel=1e-15)


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("EXPF", "exp"),
        ("SINF", "sin"),
        ("COSF", "cos"),
        ("ABSF", "abs"),
        ("SQRTF", "sqrt"),
        ("LOGF", "log"),
        ("ATANF", "atan"),
        ("TANHF", "tanh"),
        ("ALOG", "log"),
        ("ALOG10", "log10"),
        ("DSQRT", "sqrt"),
        ("Exp", "exp"),
        ("ln", "log"),
        ("ArcTan", "atan"),
    ],
)
def test_aliases_are_case_insensitive(alias: str, canonical: str) -> None:
    f = compile_expr(f"{alias}(x)")
    g = compile_expr(f"{canonical}(x)")
    assert f.normalized == g.normalized == f"{canonical}(x)"
    assert f(0.7) == g(0.7)


def test_every_alias_targets_a_function() -> None:
    assert set(FUNCTION_ALIASES.values()) <= set(FUNCTIONS)


def test_normalized_is_canonical_and_recompiles() -> None:
    f = compile_expr("ALOG10(X)+2*PI")
    assert f.normalized == "log10(x) + 2.0 * pi"
    assert compile_expr(f.normalized)(10.0) == f(10.0)


def test_compiled_expr_equality_and_repr() -> None:
    a = compile_expr("x+1")
    b = compile_expr("x+1")
    assert a == b
    assert "_fn" not in repr(a)
    assert "x+1" in repr(a)


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("__import__('os')", "unknown function"),
        ("__import__('os').system('ls')", "attribute access"),
        ("x.real", "attribute access"),
        ("().__class__", "attribute access"),
        ("x[0]", "indexing"),
        ("(lambda: 1)()", "lambda"),
        ("lambda x: x", "lambda"),
        ("[x for x in (1, 2)]", "comprehensions"),
        ("sum(i for i in (1, 2))", "unknown function"),
        ("{x: 1}", "dictionaries"),
        ("[x]", "lists"),
        ("{x}", "sets"),
        ("x, 1", "tuples"),
        ("x if x else 1", "conditional"),
        ("x > 1", "comparisons"),
        ("x and 1", "'and'/'or'"),
        ("(y := 2)", "assignment"),
        ("f'{x}'", "strings"),
        ("'abc'", "strings"),
        ("b'abc'", "strings"),
        ("1j", "complex"),
        ("True", "True/False"),
        ("None", "None"),
        ("...", "Ellipsis"),
        ("foo(x)", "unknown function 'foo'"),
        ("y + 1", "unknown name 'y'"),
        ("eval('1')", "unknown function"),
        ("exec", "unknown name"),
        ("sin", "sin is a function"),
        ("SINF + 1", "SINF is a function"),
        ("pi(2)", "pi is not a function"),
        ("x(2)", "x is not a function"),
        ("sin(x=1)", "keyword arguments"),
        ("sin(*x)", "unpacking"),
        ("sin(x, x)", "sin takes 1 argument, got 2"),
        ("atan2(x)", "atan2 takes 2 arguments, got 1"),
        ("log(x, 2)", "log takes 1 argument"),
        ("sin(x)(1)", "'Call' syntax"),
        ("x ^ 2", "write x**2"),
        ("x // 2", "'//'"),
        ("x % 2", "'%'"),
        ("x @ x", "'@'"),
        ("x << 1", "operator 'LShift'"),
        ("~x", "'UnaryOp' syntax"),
        ("not x", "'UnaryOp' syntax"),
        ("await x", "'await'"),
        ("x[1:2]", "indexing"),
    ],
)
def test_rejects_unsafe_or_unsupported_input(source: str, fragment: str) -> None:
    with pytest.raises(ExpressionError, match=re.escape(fragment)) as info:
        compile_expr(source)
    assert info.value.source == source
    assert info.value.position is not None
    assert 1 <= info.value.position <= len(source)


@pytest.mark.parametrize(
    "source",
    ["9**9**9", "2**10000", "x**1001", "x**(-2000)", "10**(10**3.5)", "x**(1e308*10)"],
)
def test_rejects_huge_constant_exponents(source: str) -> None:
    with pytest.raises(ExpressionError, match="exponent"):
        compile_expr(source)


def test_exponent_limit_is_inclusive() -> None:
    f = compile_expr(f"x**{MAX_CONSTANT_EXPONENT:g}")
    assert f(1.0) == 1.0


def test_invalid_constant_exponent_is_reported_at_compile_time() -> None:
    with pytest.raises(ExpressionError, match="invalid exponent: division by zero"):
        compile_expr("x**(1/0)")


def test_variable_exponent_is_checked_at_run_time() -> None:
    f = compile_expr("10**x")
    assert f(2.0) == pytest.approx(100.0)
    with pytest.raises(ExpressionError, match="overflow"):
        f(400.0)


def test_rejects_long_input() -> None:
    source = "x+" * (MAX_SOURCE_LENGTH // 2) + "x"
    with pytest.raises(ExpressionError, match="too long") as info:
        compile_expr(source)
    assert info.value.position is None


def test_rejects_too_many_nodes() -> None:
    source = "+".join(["x"] * (MAX_NODES // 2))
    assert len(source) <= MAX_SOURCE_LENGTH
    with pytest.raises(ExpressionError, match="too complex"):
        compile_expr(source)


def test_rejects_deep_nesting() -> None:
    depth = MAX_SOURCE_LENGTH // 2 - 1
    with pytest.raises(ExpressionError):
        compile_expr("(" * depth + "x" + ")" * depth)


def test_rejects_huge_literal() -> None:
    with pytest.raises(ExpressionError, match="number too large"):
        compile_expr("1" * 400)
    with pytest.raises(ExpressionError, match="number too large"):
        compile_expr("1e999")


@pytest.mark.parametrize("source", ["", "   ", "\t"])
def test_rejects_empty_input(source: str) -> None:
    with pytest.raises(ExpressionError, match="empty"):
        compile_expr(source)


@pytest.mark.parametrize(
    ("source", "position"),
    [("x\n+1", 2), ("x + \uff58", 5), ("sin(x)\x00", 7), ("x²", 2)],
)
def test_rejects_non_ascii_and_control_characters(source: str, position: int) -> None:
    with pytest.raises(ExpressionError, match="unexpected character") as info:
        compile_expr(source)
    assert info.value.position == position


def test_rejects_non_text() -> None:
    with pytest.raises(ExpressionError, match="must be text"):
        compile_expr(42)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("source", "position"),
    [("sin(", 4), ("  sin(", 6), ("x +", 3), ("2 x", 3), ("x)", 2)],
)
def test_syntax_errors_report_position(source: str, position: int) -> None:
    with pytest.raises(ExpressionError, match="syntax error") as info:
        compile_expr(source)
    assert info.value.position == position
    assert f"column {position}" in info.value.message


def test_validation_errors_report_column_with_leading_spaces() -> None:
    with pytest.raises(ExpressionError) as info:
        compile_expr("   x + y")
    assert info.value.position == 8


@pytest.mark.parametrize(
    ("source", "x", "fragment"),
    [
        ("sqrt(x)", -1.0, "sqrt(-1.0) is outside the function's domain"),
        ("log(x)", 0.0, "log(0.0) is outside"),
        ("ALOG(X)", -1.0, "log(-1.0) is outside"),
        ("asin(x)", 2.0, "asin(2.0) is outside"),
        ("1/x", 0.0, "division by zero at x = 0.0"),
        ("1/(x-0.5)", 0.5, "division by zero"),
        ("exp(x)", 1000.0, "overflow in exp(1000.0)"),
        ("cosh(x)", 1000.0, "overflow in cosh"),
        ("x**2", 1e200, "overflow in (1e+200)**(2.0)"),
        ("x**(1/3)", -8.0, "(-8.0)**(0.3333333333333333) is undefined"),
        ("x**-1", 0.0, "(0.0)**(-1.0) is undefined"),
        ("x*1e308*10", 1.0, "is not a finite number at x = 1.0"),
        ("x", math.inf, "is not a finite number"),
        ("x", math.nan, "is not a finite number"),
    ],
)
def test_evaluation_errors(source: str, x: float, fragment: str) -> None:
    f = compile_expr(source)
    with pytest.raises(ExpressionError) as info:
        f(x)
    assert fragment in info.value.message
    assert info.value.position is None


def test_expression_error_type() -> None:
    assert ExpressionError.code == "EXPRESSION"
    assert issubclass(ExpressionError, InputError)
    assert issubclass(ExpressionError, GeraldNAError)
    assert "EXPRESSION" not in TRACE_ERROR_CODES  # never produced by a Fortran driver
    error = ExpressionError("bad", source="x+", position=3)
    assert (error.message, error.source, error.position) == ("bad", "x+", 3)


def test_errors_carry_optional_context() -> None:
    error = GeraldNAError("boom", steps=[1, 2], book_output="BOOM\n")
    assert error.steps == (1, 2)
    assert error.book_output == "BOOM\n"
    plain = GeraldNAError("plain")
    assert plain.steps == ()
    assert plain.book_output is None


coefficient = st.floats(min_value=-10, max_value=10, allow_nan=False)


@given(a=coefficient, b=coefficient, c=coefficient, x=st.floats(min_value=-5, max_value=5))
def test_polynomials_match_python_arithmetic(a: float, b: float, c: float, x: float) -> None:
    f = compile_expr(f"{a!r}*x**2 + {b!r}*x + {c!r}")
    assert f(x) == pytest.approx(a * x**2 + b * x + c, rel=1e-12, abs=1e-12)


@given(st.text(max_size=60))
def test_arbitrary_text_never_escapes(source: str) -> None:
    # Anything either compiles into a CompiledExpr or raises ExpressionError: no other exception
    # type leaks out of the compiler.
    try:
        f = compile_expr(source)
    except ExpressionError:
        return
    assert isinstance(f, CompiledExpr)


# ---------------------------------------------------------------- Fortran integer powers


@pytest.mark.parametrize("x", [1.3247179572447458, 1.1, -0.7, 3.0000001, 1e-3])
def test_integer_literal_exponents_multiply_like_fortran(x: float) -> None:
    assert compile_expr("x**2")(x) == x * x
    assert compile_expr("x**3")(x) == (x * x) * x
    assert compile_expr("x**4")(x) == (x * x) * (x * x)
    assert compile_expr("x**-2")(x) == 1.0 / (x * x)
    assert compile_expr("x**+3")(x) == (x * x) * x
    # a real exponent is a real power, exactly like X**3. in Fortran
    assert compile_expr("x**3.")(x) == math.pow(x, 3.0)


def test_integer_power_differs_from_pow_somewhere() -> None:
    """Why the distinction matters: x**3 by multiplication is not always pow(x, 3)."""
    xs = [1.0 + i * 1e-3 for i in range(1, 2000)]
    assert any((x * x) * x != math.pow(x, 3.0) for x in xs)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5, 7, 8, 13, 64, -1, -3, 1000])
def test_powi_matches_square_and_multiply(n: int) -> None:
    x = 1.0001
    assert powi(x, n) == pytest.approx(x**n, rel=1e-12)
    assert powi(2.0, n) == 2.0**n
    assert powi(0.0, 0) == 1.0


def test_integer_exponents_stay_integers_when_normalized() -> None:
    f = compile_expr("X**3 - X - 1")
    assert f.normalized == "x ** 3 - x - 1.0"
    assert compile_expr("x**(-2)").normalized == "x ** (-2)"
    assert compile_expr("x**2.").normalized == "x ** 2.0"
    assert compile_expr(f.normalized)(1.1) == f(1.1)


def test_integer_power_errors() -> None:
    with pytest.raises(ExpressionError, match=r"overflow in \(1e\+200\)\*\*\(3\.0\)"):
        compile_expr("x**3")(1e200)
    with pytest.raises(ExpressionError, match=r"\(0\.0\)\*\*\(-2\.0\) is undefined"):
        compile_expr("x**-2")(0.0)
