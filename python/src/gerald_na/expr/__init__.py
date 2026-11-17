"""Safe compiler for learner-supplied function expressions (``ast`` whitelist, no ``eval``).

>>> f = compile_expr("EXPF(-X) - SINF(3.1415926*X/2.)")
>>> f.normalized
'exp(-x) - sin(3.1415926 * x / 2.0)'
>>> round(f(0.0), 6)
1.0
"""

from gerald_na.errors import ExpressionError
from gerald_na.expr._compiler import (
    CONSTANTS,
    FUNCTION_ALIASES,
    FUNCTIONS,
    MAX_CONSTANT_EXPONENT,
    MAX_NODES,
    MAX_SOURCE_LENGTH,
    VARIABLE,
    CompiledExpr,
    compile_expr,
)

__all__ = [
    "CONSTANTS",
    "FUNCTIONS",
    "FUNCTION_ALIASES",
    "MAX_CONSTANT_EXPONENT",
    "MAX_NODES",
    "MAX_SOURCE_LENGTH",
    "VARIABLE",
    "CompiledExpr",
    "ExpressionError",
    "compile_expr",
]
