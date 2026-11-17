"""Standard-library-only implementations of the book algorithms.

Each algorithm is a pure function returning a frozen result dataclass with ``value``,
``converged``, ``iterations``, ``steps`` and ``book_text()``; error paths that ended in
``CALL EXIT`` in the original listings raise the typed errors of :mod:`gerald_na.errors`.
"""

from gerald_na.algorithms._fortran_format import Rounding, format_e, format_es, format_f, format_i
from gerald_na.algorithms.bairstow import (
    BairstowFactor,
    BairstowResult,
    BairstowStep,
    bairstow,
    factor_roots,
)
from gerald_na.algorithms.bisection import BisectionResult, BisectionStep, bisection
from gerald_na.algorithms.simpson import SimpsonResult, SimpsonStep, simpson
from gerald_na.algorithms.romberg import RombergResult, RombergStep, romberg

__all__ = [
    "BairstowFactor",
    "BairstowResult",
    "BairstowStep",
    "BisectionResult",
    "BisectionStep",
    "RombergResult",
    "RombergStep",
    "Rounding",
    "bairstow",
    "SimpsonResult",
    "SimpsonStep",
    "bisection",
    "factor_roots",
    "format_e",
    "format_es",
    "format_f",
    "format_i",
    "simpson",
    "romberg",
]
