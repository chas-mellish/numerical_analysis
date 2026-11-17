"""Function evaluation shared by the algorithm ports."""

import math
from collections.abc import Callable

from gerald_na.errors import InputError

__all__ = ["evaluate_finite"]


def evaluate_finite(f: Callable[[float], float], x: float) -> float:
    """``f(x)`` as a float; a NaN or infinite value is an :class:`InputError`."""
    value = float(f(x))
    if not math.isfinite(value):
        raise InputError(f"F(X) is not a finite number at X = {x!r}")
    return value
