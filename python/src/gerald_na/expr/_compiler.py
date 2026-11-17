"""Compile learner-supplied expressions of one variable into safe Python callables.

The source is parsed with :func:`ast.parse` (``mode="eval"``) and every node is checked against a
small whitelist. The validated tree is then turned into nested closures, one per node, so the
input is never handed to ``eval``/``exec`` and cannot reach attributes, builtins or imports.

Accepted syntax (names are case-insensitive)::

    numbers        2   2.   .5   1.E-5   3.1415926
    the variable   x   X
    operators      +  -  *  /  **  unary + and -  parentheses
    constants      pi  e
    functions      sin cos tan asin acos atan atan2(y, x) sinh cosh tanh exp log log10 sqrt
                   abs floor ceil, plus FORTRAN aliases (SINF, EXPF, ALOG, DSQRT, ...)

Limits guard against denial of service: the source length, the number of AST nodes, and the
magnitude of constant exponents (``9**9**9`` is rejected before anything is computed). At run
time every operation goes through ``math``; domain errors, overflow, division by zero and
non-finite results raise :class:`~gerald_na.errors.ExpressionError`.
"""

import ast
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from gerald_na.errors import ExpressionError

__all__ = [
    "CONSTANTS",
    "FUNCTIONS",
    "FUNCTION_ALIASES",
    "MAX_CONSTANT_EXPONENT",
    "MAX_NODES",
    "MAX_SOURCE_LENGTH",
    "VARIABLE",
    "CompiledExpr",
    "compile_expr",
]

MAX_SOURCE_LENGTH: Final = 500
"""Longest accepted expression, in characters."""

MAX_NODES: Final = 200
"""Largest accepted syntax tree, in :mod:`ast` nodes."""

MAX_CONSTANT_EXPONENT: Final = 1000.0
"""Largest accepted magnitude of an exponent that does not depend on ``x``."""

VARIABLE: Final = "x"
"""The only variable; ``X`` is accepted too."""

type _Fn = Callable[[float], float]


def _floor(value: float) -> float:
    return float(math.floor(value))


def _ceil(value: float) -> float:
    return float(math.ceil(value))


FUNCTIONS: Mapping[str, tuple[int, Callable[..., float]]] = MappingProxyType(
    {
        "sin": (1, math.sin),
        "cos": (1, math.cos),
        "tan": (1, math.tan),
        "asin": (1, math.asin),
        "acos": (1, math.acos),
        "atan": (1, math.atan),
        "atan2": (2, math.atan2),
        "sinh": (1, math.sinh),
        "cosh": (1, math.cosh),
        "tanh": (1, math.tanh),
        "exp": (1, math.exp),
        "log": (1, math.log),
        "log10": (1, math.log10),
        "sqrt": (1, math.sqrt),
        "abs": (1, math.fabs),
        "floor": (1, _floor),
        "ceil": (1, _ceil),
    }
)
"""Canonical function names mapped to ``(number of arguments, implementation)``."""

FUNCTION_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        # FORTRAN II library names, as written in the book's listings.
        "sinf": "sin",
        "cosf": "cos",
        "atanf": "atan",
        "tanhf": "tanh",
        "expf": "exp",
        "logf": "log",
        "sqrtf": "sqrt",
        "absf": "abs",
        # FORTRAN IV / 77 specific names.
        "alog": "log",
        "alog10": "log10",
        "dsin": "sin",
        "dcos": "cos",
        "dtan": "tan",
        "dasin": "asin",
        "dacos": "acos",
        "datan": "atan",
        "datan2": "atan2",
        "dsinh": "sinh",
        "dcosh": "cosh",
        "dtanh": "tanh",
        "dexp": "exp",
        "dlog": "log",
        "dlog10": "log10",
        "dsqrt": "sqrt",
        "dabs": "abs",
        # Common spellings.
        "ln": "log",
        "arcsin": "asin",
        "arccos": "acos",
        "arctan": "atan",
    }
)
"""Lower-case alternative names mapped to the canonical function name."""

CONSTANTS: Mapping[str, float] = MappingProxyType({"pi": math.pi, "e": math.e})
"""Named constants."""

_BINARY_OPERATORS: Final[Mapping[type[ast.operator], str]] = MappingProxyType(
    {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "**"}
)

_OPERATOR_HINTS: Final[Mapping[type[ast.operator], str]] = MappingProxyType(
    {
        ast.BitXor: "'^' is not a power operator here; write x**2 for x squared",
        ast.FloorDiv: "'//' is not supported; use '/'",
        ast.Mod: "'%' is not supported",
        ast.MatMult: "'@' is not supported",
    }
)


def _describe(node: ast.AST) -> str:
    """A short, learner-friendly name for a rejected syntax element."""
    descriptions: dict[type[ast.AST], str] = {
        ast.Attribute: "attribute access ('.name')",
        ast.Subscript: "indexing ('[...]')",
        ast.Lambda: "lambda expressions",
        ast.ListComp: "comprehensions",
        ast.SetComp: "comprehensions",
        ast.DictComp: "comprehensions",
        ast.GeneratorExp: "comprehensions",
        ast.Compare: "comparisons",
        ast.BoolOp: "'and'/'or'",
        ast.IfExp: "conditional expressions",
        ast.NamedExpr: "assignment expressions",
        ast.JoinedStr: "strings",
        ast.List: "lists",
        ast.Tuple: "tuples (check for a stray comma)",
        ast.Set: "sets",
        ast.Dict: "dictionaries",
        ast.Starred: "'*' unpacking",
        ast.Await: "'await'",
        ast.Yield: "'yield'",
        ast.YieldFrom: "'yield'",
        ast.Slice: "slices",
    }
    return descriptions.get(type(node), f"'{type(node).__name__}' syntax")


@dataclass(frozen=True, slots=True)
class CompiledExpr:
    """A validated expression of ``x``; call it like a function: ``f(0.5)``.

    ``source`` is the text as entered; ``normalized`` is the canonical rendering (lower-case
    canonical names, explicit operators), suitable for display and caching.
    """

    source: str
    normalized: str
    _fn: _Fn = field(repr=False, compare=False)

    def __call__(self, x: float) -> float:
        value = float(x)
        result = self._fn(value)
        if not math.isfinite(result):
            raise ExpressionError(
                f"{self.normalized} is not a finite number at x = {value!r}",
                source=self.source,
            )
        return result


def _error(message: str, source: str, node: ast.AST | None = None) -> ExpressionError:
    position = None
    if node is not None:
        offset = getattr(node, "col_offset", None)
        if isinstance(offset, int):
            position = offset + 1
    where = f" (at column {position})" if position is not None else ""
    return ExpressionError(message + where, source=source, position=position)


def _eval_error(message: str) -> ExpressionError:
    return ExpressionError(message)


class _Compiler:
    """Validate an :mod:`ast` tree and build the closure that evaluates it."""

    def __init__(self, source: str) -> None:
        self.source = source

    def compile(self, node: ast.expr) -> tuple[_Fn, ast.expr]:
        """Return the evaluating closure and a canonical copy of the tree (for ``normalized``)."""
        match node:
            case ast.Constant(value=bool()):
                raise _error("True/False are not allowed; use numbers", self.source, node)
            case ast.Constant(value=int() | float() as number):
                return self._number(number, node)
            case ast.Constant(value=complex()):
                raise _error("complex numbers are not allowed", self.source, node)
            case ast.Constant(value=str() | bytes()):
                raise _error("strings are not allowed", self.source, node)
            case ast.Constant(value=constant):
                raise _error(f"{constant!r} is not allowed", self.source, node)
            case ast.Name(id=name):
                return self._name(name, node)
            case ast.UnaryOp(op=ast.USub() | ast.UAdd() as op, operand=operand):
                return self._unary(op, operand)
            case ast.BinOp(left=left, op=op, right=right):
                return self._binary(left, op, right, node)
            case ast.Call():
                return self._call(node)
            case _:
                raise _error(f"{_describe(node)} not allowed", self.source, node)

    def _number(self, number: float, node: ast.expr) -> tuple[_Fn, ast.expr]:
        try:
            value = float(number)
        except OverflowError:
            raise _error("number too large", self.source, node) from None
        if not math.isfinite(value):
            raise _error("number too large", self.source, node)

        def constant(_x: float) -> float:
            return value

        return constant, ast.Constant(value=value)

    def _name(self, name: str, node: ast.expr) -> tuple[_Fn, ast.expr]:
        key = name.lower()
        if key == VARIABLE:

            def variable(x: float) -> float:
                return x

            return variable, ast.Name(id=VARIABLE)
        if key in CONSTANTS:
            value = CONSTANTS[key]

            def constant(_x: float) -> float:
                return value

            return constant, ast.Name(id=key)
        if key in FUNCTIONS or key in FUNCTION_ALIASES:
            raise _error(f"{name} is a function; call it like {name}(x)", self.source, node)
        raise _error(
            f"unknown name {name!r}; use the variable x, the constants pi and e, "
            "or a supported function",
            self.source,
            node,
        )

    def _unary(self, op: ast.unaryop, operand: ast.expr) -> tuple[_Fn, ast.expr]:
        inner, canonical = self.compile(operand)
        if isinstance(op, ast.UAdd):
            return inner, ast.UnaryOp(op=ast.UAdd(), operand=canonical)

        def negate(x: float) -> float:
            return -inner(x)

        return negate, ast.UnaryOp(op=ast.USub(), operand=canonical)

    def _binary(
        self, left: ast.expr, op: ast.operator, right: ast.expr, node: ast.expr
    ) -> tuple[_Fn, ast.expr]:
        symbol = _BINARY_OPERATORS.get(type(op))
        if symbol is None:
            hint = _OPERATOR_HINTS.get(type(op), f"operator '{type(op).__name__}' not allowed")
            raise _error(hint, self.source, node)
        lhs, left_canonical = self.compile(left)
        rhs, right_canonical = self.compile(right)
        canonical = ast.BinOp(left=left_canonical, op=type(op)(), right=right_canonical)
        match symbol:
            case "+":

                def add(x: float) -> float:
                    return lhs(x) + rhs(x)

                return add, canonical
            case "-":

                def subtract(x: float) -> float:
                    return lhs(x) - rhs(x)

                return subtract, canonical
            case "*":

                def multiply(x: float) -> float:
                    return lhs(x) * rhs(x)

                return multiply, canonical
            case "/":

                def divide(x: float) -> float:
                    denominator = rhs(x)
                    if denominator == 0.0:
                        raise _eval_error(f"division by zero at x = {x!r}")
                    return lhs(x) / denominator

                return divide, canonical
            case _:
                self._check_constant_exponent(right, rhs)

                def power(x: float) -> float:
                    base, exponent = lhs(x), rhs(x)
                    try:
                        return math.pow(base, exponent)
                    except OverflowError:
                        raise _eval_error(
                            f"overflow in ({base!r})**({exponent!r}) at x = {x!r}"
                        ) from None
                    except ValueError:
                        raise _eval_error(
                            f"({base!r})**({exponent!r}) is undefined (at x = {x!r})"
                        ) from None

                return power, canonical

    def _check_constant_exponent(self, exponent: ast.expr, fn: _Fn) -> None:
        """Reject a constant exponent of excessive magnitude before anything else runs."""
        if any(
            isinstance(sub, ast.Name) and sub.id.lower() == VARIABLE for sub in ast.walk(exponent)
        ):
            return
        try:
            value = fn(0.0)
        except ExpressionError as exc:
            raise _error(f"invalid exponent: {exc.message}", self.source, exponent) from None
        if not math.isfinite(value) or abs(value) > MAX_CONSTANT_EXPONENT:
            raise _error(
                f"exponent too large (the limit is {MAX_CONSTANT_EXPONENT:g})",
                self.source,
                exponent,
            )

    def _call(self, node: ast.Call) -> tuple[_Fn, ast.expr]:
        if not isinstance(node.func, ast.Name):
            raise _error(f"{_describe(node.func)} not allowed", self.source, node.func)
        name = node.func.id
        key = name.lower()
        canonical_name = FUNCTION_ALIASES.get(key, key)
        if canonical_name not in FUNCTIONS:
            if key in CONSTANTS or key == VARIABLE:
                raise _error(f"{name} is not a function", self.source, node.func)
            raise _error(f"unknown function {name!r}", self.source, node.func)
        if node.keywords:
            raise _error("keyword arguments are not allowed", self.source, node.keywords[0])
        arity, implementation = FUNCTIONS[canonical_name]
        if len(node.args) != arity:
            plural = "argument" if arity == 1 else "arguments"
            raise _error(f"{name} takes {arity} {plural}, got {len(node.args)}", self.source, node)
        compiled = [self.compile(argument) for argument in node.args]
        canonical = ast.Call(
            func=ast.Name(id=canonical_name), args=[c for _, c in compiled], keywords=[]
        )
        arguments = [fn for fn, _ in compiled]

        def call(x: float) -> float:
            values = [argument(x) for argument in arguments]
            try:
                return float(implementation(*values))
            except ValueError:
                shown = ", ".join(repr(v) for v in values)
                raise _eval_error(
                    f"{canonical_name}({shown}) is outside the function's domain (at x = {x!r})"
                ) from None
            except OverflowError:
                shown = ", ".join(repr(v) for v in values)
                raise _eval_error(f"overflow in {canonical_name}({shown}) at x = {x!r}") from None

        return call, canonical


def _parse(source: str) -> ast.Expression:
    if not isinstance(source, str):
        raise ExpressionError("the expression must be text")
    if not source.strip():
        raise ExpressionError("the expression is empty", source=source)
    if len(source) > MAX_SOURCE_LENGTH:
        raise ExpressionError(
            f"the expression is too long ({len(source)} characters; the limit is "
            f"{MAX_SOURCE_LENGTH})",
            source=source,
        )
    for index, char in enumerate(source):
        if not (char.isascii() and (char.isprintable() or char in " \t")):
            raise ExpressionError(
                f"unexpected character {char!r} (at column {index + 1})",
                source=source,
                position=index + 1,
            )
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except SyntaxError as exc:
        leading = len(source) - len(source.lstrip())
        offset = exc.offset if exc.offset is not None and exc.offset >= 1 else len(source.strip())
        position = min(offset + leading, len(source))
        raise ExpressionError(
            f"syntax error: {exc.msg} (at column {position})", source=source, position=position
        ) from None
    except RecursionError, MemoryError, ValueError:
        raise ExpressionError("the expression is too deeply nested", source=source) from None
    nodes = sum(1 for _ in ast.walk(tree))
    if nodes > MAX_NODES:
        raise ExpressionError(
            f"the expression is too complex ({nodes} syntax elements; the limit is {MAX_NODES})",
            source=source,
        )
    if leading := len(source) - len(source.lstrip()):
        for sub in ast.walk(tree):
            if isinstance(sub, ast.expr | ast.keyword) and sub.col_offset is not None:
                sub.col_offset += leading
    return tree


def compile_expr(source: str) -> CompiledExpr:
    """Validate ``source`` and compile it into a :class:`CompiledExpr` of the variable ``x``.

    Raises :class:`~gerald_na.errors.ExpressionError` (with ``position`` set where possible) if
    the text is not a valid, whitelisted expression.
    """
    tree = _parse(source)
    fn, canonical = _Compiler(source).compile(tree.body)
    normalized = ast.unparse(ast.fix_missing_locations(ast.Expression(body=canonical)))
    return CompiledExpr(source=source, normalized=normalized, _fn=fn)
