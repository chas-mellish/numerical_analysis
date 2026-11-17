"""Emulate the book's chopped arithmetic on the book's data cards.

This is the evidence behind ``docs/architecture.md``, "The book's computer". The book's Simpson
(``ch03_p01``) and Romberg (``ch03_p02``) printouts are a few units of 1e-7 *below* the true
Si(B), and neither IEEE real32 nor real64 reproduces them. The two candidate machine families of
the time chopped (truncated toward zero) every floating-point result:

* binary with a 27-bit mantissa (IBM 704/709/7090/7094 single precision);
* decimal with 8 digits (IBM 1620 FORTRAN II-D default; 9 digits shown for comparison).

:class:`ChoppedMachine` models such a machine exactly: every operation is computed on exact
:class:`fractions.Fraction` values and the result is chopped to the mantissa. The functions
below replay the listings operation by operation, in the same order as the modules in
``gerald_na.algorithms`` (which mirror the scans):

* :func:`simpson_si` and :func:`romberg_si`: the Chapter 3 cards, F(X) = SIN(X)/X with the
  book's literal ``1.`` for F(0) (these discriminate between the models);
* :func:`bisection_rows`: the Ch. 1 Prog. 1 card, whose printed digits every model reproduces
  (not discriminating);
* :func:`coefficient_echo`: the Ch. 1 Prog. 2 coefficient echo, which only a decimal machine
  prints exactly;
* :func:`central_difference_rows`: the Ch. 4 Prog. 1 card ``0.0 0.1`` with F(X) = X**2*EXPF(X),
  whose small-H DX digits none of the models reproduces (they depend on the machine's EXPF).

Printed values are chopped as well (:func:`printed`): the book's printer truncated the last
digit and dropped the leading zero.

Limitation: the machine's own SIN and EXP routines are unknown. The emulation takes a correctly
rounded real64 value of the (exactly representable) argument and chops it to the mantissa, so
the results are indications, not proof.

Run ``python -m gerald_na.tools.book_machine`` (from ``python/``: ``uv run python -m
gerald_na.tools.book_machine``) to print the table quoted in the docs. Standard library only.
"""

import argparse
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

__all__ = [
    "BAIRSTOW_COEFFICIENTS",
    "BOOK_BISECTION",
    "BOOK_ROMBERG",
    "BOOK_SIMPSON",
    "MODELS",
    "ChoppedMachine",
    "RombergRun",
    "bisection_rows",
    "central_difference_rows",
    "coefficient_echo",
    "main",
    "printed",
    "report",
    "romberg_si",
    "simpson_si",
]

BOOK_SIMPSON = Fraction("1.5499307")
"""Si(5) as printed by the book (ch03_p01, data card ``5.0 100``)."""

BOOK_ROMBERG = Fraction("1.6181936")
"""Si(15) as printed by the book (ch03_p02, data card ``15.0 2.E-7``)."""

BOOK_BISECTION: tuple[tuple[int, Fraction, Fraction], ...] = tuple(
    (k, Fraction(x), Fraction(fx))
    for k, x, fx in (
        (1, ".5000000", "-.100576"),
        (2, ".2500000", ".396117"),
        (3, ".3750000", ".131719"),
        (4, ".4375000", ".011255"),
        (5, ".4687500", "-.045774"),
        (6, ".4531250", "-.017534"),
        (7, ".4453125", "-.003207"),
        (8, ".4414062", ".004006"),
        (9, ".4433593", ".000395"),
        (10, ".4443359", "-.001407"),
        (11, ".4438476", "-.000506"),
        (12, ".4436035", "-.000055"),
        (13, ".4434814", ".000170"),
        (14, ".4435424", ".000057"),
        (15, ".4435729", ".000001"),
    )
)
"""The book's bisection table (k, X, F(X)) as printed on page 24 (``ch01_p01``)."""


@dataclass(frozen=True, slots=True)
class ChoppedMachine:
    """Floating point with ``digits`` base-``base`` mantissa digits; results chopped to zero.

    ``base = 2, digits = 27`` is IBM 7090 single precision; ``base = 10, digits = 8`` is the
    IBM 1620 default. Values are exact :class:`~fractions.Fraction` objects that are always
    representable on the machine. The exponent range is unlimited (no overflow or underflow
    happens on the book's cards).
    """

    base: int
    digits: int

    def __post_init__(self) -> None:
        if self.base not in (2, 10):
            raise ValueError(f"base must be 2 or 10, got {self.base}")
        if self.digits < 1:
            raise ValueError(f"digits must be positive, got {self.digits}")

    @property
    def label(self) -> str:
        """Short description, for example ``27-bit binary``."""
        kind = "bit binary" if self.base == 2 else "digit decimal"
        return f"{self.digits}-{kind}"

    def chop(self, value: Fraction) -> Fraction:
        """``value`` truncated toward zero to :attr:`digits` significant digits in :attr:`base`."""
        if value == 0:
            return Fraction(0)
        sign = -1 if value < 0 else 1
        magnitude = abs(value)
        low = Fraction(self.base) ** (self.digits - 1)
        high = low * self.base
        exponent = 0
        scaled = magnitude
        # Normalize: low <= scaled < high, with scaled = magnitude * base**exponent.
        while scaled >= high:
            scaled /= self.base
            exponent -= 1
        while scaled < low:
            scaled *= self.base
            exponent += 1
        mantissa = math.floor(scaled)
        return sign * Fraction(mantissa) / Fraction(self.base) ** exponent

    def const(self, text: str) -> Fraction:
        """A source-program constant such as ``"2.E-7"``, converted (and chopped) on input."""
        return self.chop(Fraction(text.replace("E", "e")))

    def add(self, a: Fraction, b: Fraction) -> Fraction:
        """Chopped ``a + b``."""
        return self.chop(a + b)

    def sub(self, a: Fraction, b: Fraction) -> Fraction:
        """Chopped ``a - b``."""
        return self.chop(a - b)

    def mul(self, a: Fraction, b: Fraction) -> Fraction:
        """Chopped ``a * b``."""
        return self.chop(a * b)

    def div(self, a: Fraction, b: Fraction) -> Fraction:
        """Chopped ``a / b``."""
        return self.chop(a / b)

    def sin(self, x: Fraction) -> Fraction:
        """SINF(X): a correctly rounded real64 sine of ``x``, chopped (the real SINF is unknown)."""
        return self.chop(Fraction(math.sin(float(x))))

    def exp(self, x: Fraction) -> Fraction:
        """EXPF(X): a correctly rounded real64 exponential of ``x``, chopped."""
        return self.chop(Fraction(math.exp(float(x))))

    def sinc(self, x: Fraction) -> Fraction:
        """The book's statement function ``F(X) = SINF(X)/X``."""
        return self.div(self.sin(x), x)


def printed(value: Fraction, places: int) -> Fraction:
    """``value`` as the book's printer showed it with ``places`` decimals: chopped, not rounded."""
    scale = 10**places
    magnitude = Fraction(math.floor(abs(value) * scale), scale)
    return -magnitude if value < 0 else magnitude


MODELS: tuple[ChoppedMachine, ...] = (
    ChoppedMachine(2, 27),
    ChoppedMachine(10, 8),
    ChoppedMachine(10, 9),
)
"""The models compared in ``docs/architecture.md``."""


def simpson_si(machine: ChoppedMachine, b: str = "5.0", n: int = 100) -> Fraction:
    """Ch. 3 Prog. 1 (Simpson's 1/3 rule) on ``machine``: Si(``b``) with ``n`` panels.

    The listing::

        XN = N ;  DELX = B/XN
        SUM = 1.0 + 4.*F(DELX) + F(B)
        X = 2.*DELX
        DO 10 I = 2,NHALF
        SUM = SUM + 2.*F(X) + 4.*F(X+DELX)
     10 X = X + 2.*DELX
        SININT = DELX/3.*SUM
    """
    if n < 2 or n % 2:
        raise ValueError(f"n must be an even number >= 2, got {n}")
    m = machine
    two, three, four = m.const("2."), m.const("3."), m.const("4.")
    bb = m.const(b)
    delx = m.div(bb, m.const(str(n)))
    total = m.add(m.add(m.const("1.0"), m.mul(four, m.sinc(delx))), m.sinc(bb))
    x = m.mul(two, delx)
    for _ in range(2, n // 2 + 1):
        total = m.add(m.add(total, m.mul(two, m.sinc(x))), m.mul(four, m.sinc(m.add(x, delx))))
        x = m.add(x, m.mul(two, delx))
    return m.mul(m.div(delx, three), total)


@dataclass(frozen=True, slots=True)
class RombergRun:
    """The emulated Romberg table (printed lines ``TRAP(1..L, L)``) and where it stopped."""

    lines: tuple[tuple[Fraction, ...], ...]
    converged: bool

    @property
    def value(self) -> Fraction:
        """The last entry of the last line: the reported integral."""
        return self.lines[-1][-1]

    @property
    def subintervals(self) -> int:
        """Subintervals of the last trapezoidal sum (10 * 2**halvings)."""
        return 10 << (len(self.lines) - 1)


def romberg_si(machine: ChoppedMachine, b: str = "15.0", tol: str = "2.E-7") -> RombergRun:
    """Ch. 3 Prog. 2 (Romberg integration) on ``machine``: Si(``b``) to tolerance ``tol``.

    Same operation order as the scan (see ``gerald_na.algorithms.romberg``): ``H = B/10.``,
    ``SUM = 1. + FCN(B)``, ``SUM = SUM + FCN(X)*2.``, ``TRAP = H/2.*SUM``, ``X = X + H + H`` and
    ``TRAP(II+1,I+1) = TRAP(II,I+1) + 1./(4.**II-1.)*(TRAP(II,I+1) - TRAP(II,I))``.
    """
    m = machine
    one, two = m.const("1."), m.const("2.")
    bb, tolerance = m.const(b), m.const(tol)
    h = m.div(bb, m.const("10."))
    total = m.add(one, m.sinc(bb))
    x = Fraction(0)
    for _ in range(2, 11):
        x = m.add(x, h)
        total = m.add(total, m.mul(m.sinc(x), two))
    columns: list[list[Fraction]] = [[m.mul(m.div(h, two), total)]]
    for i in range(1, 9):
        h = m.div(h, two)
        x = h
        for _ in range(2, 10 * 2**i + 1, 2):
            total = m.add(total, m.mul(m.sinc(x), two))
            x = m.add(m.add(x, h), h)
        previous = columns[i - 1]
        column = [m.mul(m.div(h, two), total)]
        for ii in range(1, i + 1):
            factor = m.div(one, m.sub(m.chop(Fraction(4) ** ii), one))
            column.append(
                m.add(column[ii - 1], m.mul(factor, m.sub(column[ii - 1], previous[ii - 1])))
            )
        columns.append(column)
        if m.sub(abs(m.sub(column[i], column[i - 1])), tolerance) <= 0:
            return RombergRun(tuple(tuple(c) for c in columns), converged=True)
    return RombergRun(tuple(tuple(c) for c in columns), converged=False)


def bisection_rows(machine: ChoppedMachine) -> tuple[tuple[int, Fraction, Fraction], ...]:
    """Ch. 1 Prog. 1 (interval halving) on ``machine`` with the book card ``0. 1. 1.E-5``.

    ``F(X) = EXPF(-X) - SINF(3.1415926*X/2.)``; returns ``(k, X, F(X))`` per printed row, in the
    listing's order: ``X = (X1 + X2)/2.``, stop when ``ABSF(FX) - TOL <= 0``, otherwise keep the
    half with a sign change (``IF (FX*FX1) 10, 11, 12``).
    """
    m = machine
    pi, two = m.const("3.1415926"), m.const("2.")

    def f(x: Fraction) -> Fraction:
        return m.sub(m.exp(-x), m.sin(m.div(m.mul(pi, x), two)))

    x1, x2, tol = m.const("0."), m.const("1."), m.const("1.E-5")
    fx1 = f(x1)
    rows: list[tuple[int, Fraction, Fraction]] = []
    for k in range(1, 26):
        x = m.div(m.add(x1, x2), two)
        fx = f(x)
        rows.append((k, x, fx))
        if m.sub(abs(fx), tol) <= 0:
            break
        if m.mul(fx, fx1) < 0:
            x2 = x
        else:
            x1, fx1 = x, fx
    return tuple(rows)


def central_difference_rows(machine: ChoppedMachine) -> tuple[tuple[Fraction, Fraction], ...]:
    """Ch. 4 Prog. 1 (central differences) on ``machine`` with the book card ``0.0 0.1``.

    ``F(X) = X**2*EXPF(X)``; returns ``(DX, DDX)`` per printed row, in the listing's order:
    ``FO = F(X)`` once, then ``DX = (FR - FL)/(2.*H)``, ``DDX = (FR - 2.*FO + FL)/H**2`` and
    ``H = 0.1*H`` (accumulated) for ten rows.
    """
    m = machine
    two, tenth = m.const("2."), m.const("0.1")

    def f(x: Fraction) -> Fraction:
        return m.mul(m.mul(x, x), m.exp(x))

    x, h = m.const("0.0"), m.const("0.1")
    fo = f(x)
    rows: list[tuple[Fraction, Fraction]] = []
    for _ in range(10):
        fr, fl = f(m.add(x, h)), f(m.sub(x, h))
        dx = m.div(m.sub(fr, fl), m.mul(two, h))
        ddx = m.div(m.add(m.sub(fr, m.mul(two, fo)), fl), m.mul(h, h))
        rows.append((dx, ddx))
        h = m.mul(tenth, h)
    return tuple(rows)


BAIRSTOW_COEFFICIENTS: tuple[str, ...] = ("1.", "-17.8", "99.41", "-261.218", "352.611", "-134.106")
"""Ch. 1 Prog. 2 card 1 (X**5 down to X**0), echoed by the book as 1.00000, -17.80000, ..."""


def coefficient_echo(machine: ChoppedMachine) -> tuple[Fraction, ...]:
    """The Bairstow coefficients as ``machine`` echoes them with FORMAT 6 (F10.5).

    Both conversions are chopped: the card value on input and the printed digits on output.
    """
    return tuple(printed(machine.const(text), 5) for text in BAIRSTOW_COEFFICIENTS)


def _fmt(value: Fraction, places: int = 9) -> str:
    return f"{float(value):.{places}f}"


def report(models: Sequence[ChoppedMachine] = MODELS) -> str:
    """The comparison table printed by :func:`main`."""
    lines = [
        "Chopped-arithmetic emulation of the book's data cards (Ch. 3: F(X) = SIN(X)/X, F(0) = 1.)",
        "",
        f"{'model':<18} {'Simpson Si(5)':>14} {'Romberg Si(15)':>15} {'lines':>5} {'subint':>6}",
        f"{'book':<18} {_fmt(BOOK_SIMPSON, 7):>14} {_fmt(BOOK_ROMBERG, 7):>15} {4:>5} {80:>6}",
        f"{'IEEE real64':<18} {_fmt(_ieee_simpson()):>14} {_fmt(_ieee_romberg()):>15}",
    ]
    for model in models:
        simpson = simpson_si(model)
        romberg = romberg_si(model)
        lines.append(
            f"{model.label:<18} {_fmt(simpson):>14} {_fmt(romberg.value):>15} "
            f"{len(romberg.lines):>5} {romberg.subintervals:>6}"
        )
    lines.append("")
    lines.append(
        "Ch. 1 Prog. 1 (bisection) rows whose printed X (F10.7) and F(X) (F10.6), chopped,"
    )
    lines.append(
        "match the book (15 rows), and the Ch. 1 Prog. 2 coefficient echo (FORMAT 6, F10.5):"
    )
    for model in models:
        rows = bisection_rows(model)
        matches = sum(
            1
            for (_, x, fx), (_, book_x, book_fx) in zip(rows, BOOK_BISECTION, strict=False)
            if printed(x, 7) == book_x and printed(fx, 6) == book_fx
        )
        echo = " ".join(f"{float(v):.5f}" for v in coefficient_echo(model))
        lines.append(f"  {model.label:<16} bisection {matches:>2}/15  echo {echo}")
    lines.append("")
    for model in models:
        romberg = romberg_si(model)
        lines.append(f"Romberg table, {model.label}:")
        lines.extend("  " + " ".join(_fmt(v, 7) for v in line) for line in romberg.lines)
    return "\n".join(lines) + "\n"


def _ieee_simpson() -> Fraction:
    from gerald_na.algorithms.simpson import simpson

    return Fraction(simpson(lambda x: math.sin(x) / x, 5.0, 100, f0=1.0).value)


def _ieee_romberg() -> Fraction:
    from gerald_na.algorithms.romberg import romberg

    return Fraction(romberg(lambda x: math.sin(x) / x, 15.0, 2e-7, f0=1.0).value)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the emulation table (``--bits`` / ``--digits`` add custom models)."""
    parser = argparse.ArgumentParser(
        prog="python -m gerald_na.tools.book_machine",
        description="Replay the book's Simpson and Romberg cards in chopped arithmetic.",
    )
    parser.add_argument("--bits", type=int, action="append", default=[], help="binary mantissa")
    parser.add_argument("--digits", type=int, action="append", default=[], help="decimal digits")
    args = parser.parse_args(argv)
    extra = [ChoppedMachine(2, b) for b in args.bits] + [ChoppedMachine(10, d) for d in args.digits]
    sys.stdout.write(report(extra or MODELS))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
