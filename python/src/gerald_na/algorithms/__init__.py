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
from gerald_na.algorithms.central_difference import (
    CentralDifferenceResult,
    CentralDifferenceStep,
    central_difference,
)
from gerald_na.algorithms.lagrange import LagrangeResult, LagrangeStep, lagrange
from gerald_na.algorithms.romberg import RombergResult, RombergStep, romberg
from gerald_na.algorithms.simpson import SimpsonResult, SimpsonStep, simpson

__all__ = [
    "BairstowFactor",
    "BairstowResult",
    "BairstowStep",
    "BisectionResult",
    "BisectionStep",
    "CentralDifferenceResult",
    "CentralDifferenceStep",
    "LagrangeResult",
    "LagrangeStep",
    "RombergResult",
    "RombergStep",
    "Rounding",
    "SimpsonResult",
    "SimpsonStep",
    "bairstow",
    "bisection",
    "central_difference",
    "factor_roots",
    "format_e",
    "format_es",
    "format_f",
    "format_i",
    "lagrange",
    "romberg",
    "simpson",
]
