"""Fortran edit-descriptor rendering (``Iw.m``, ``Fw.d``, ``Ew.d[Ee]``, ``ESw.d[Ee]``).

The book programs print their results through ``FORMAT`` statements. To reproduce that
line-printer text exactly, the Python engine renders numbers with the same rules a Fortran
processor follows:

* the value is rounded from its *exact* binary value, using one of the Fortran rounding modes
  (``RN``, ``RC``, ``RZ``, ``RU``, ``RD``; see :class:`Rounding`);
* the optional leading zero of a value below one (``0.5`` versus ``.5``) is printed only when
  ``leading_zero`` is set *and* the field has room for it;
* a negative value keeps its minus sign even when it rounds to zero (``-0.000``), and so does a
  negative zero, as gfortran does;
* a field too narrow for the value is filled with ``w`` asterisks;
* infinities print as ``Infinity`` / ``Inf`` and NaN as ``NaN`` when they fit (gfortran style).

The defaults reproduce gfortran's list of choices for every processor-dependent point except
the leading zero, which defaults to the book's style (``.5000000``). The scans in ``docs/`` were
printed by a processor that *truncates* (``Rounding.ZERO``): for example the exact dyadic
midpoint 0.443572998046875 appears as ``.4435729`` in the bisection listing.
"""

import math
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Context,
    Decimal,
)
from enum import StrEnum

__all__ = ["Rounding", "format_e", "format_es", "format_f", "format_i"]


class Rounding(StrEnum):
    """Fortran rounding modes (the ``RN``/``RC``/``RZ``/``RU``/``RD`` edit descriptors)."""

    NEAREST = "RN"
    """Round to nearest, ties to even (gfortran's default when no mode is given)."""
    COMPATIBLE = "RC"
    """Round to nearest, ties away from zero."""
    ZERO = "RZ"
    """Truncate toward zero; what the book's line printer output shows."""
    UP = "RU"
    """Round toward +infinity."""
    DOWN = "RD"
    """Round toward -infinity."""


_DECIMAL_ROUNDING = {
    Rounding.NEAREST: ROUND_HALF_EVEN,
    Rounding.COMPATIBLE: ROUND_HALF_UP,
    Rounding.ZERO: ROUND_DOWN,
    Rounding.UP: ROUND_CEILING,
    Rounding.DOWN: ROUND_FLOOR,
}

# Enough precision for any exact double (at most 767 significant decimal digits).
_CONTEXT = Context(prec=1100, Emin=-2000, Emax=2000)


def _stars(width: int) -> str:
    return "*" * width


def _fit(text: str, width: int) -> str:
    """Right-justify ``text`` in ``width`` columns, or asterisks if it does not fit."""
    if width == 0:
        return text
    if len(text) > width:
        return _stars(width)
    return text.rjust(width)


def _sign(negative: bool, sign_plus: bool) -> str:
    if negative:
        return "-"
    return "+" if sign_plus else ""


def _check_width(w: int, d: int, *, allow_zero_width: bool) -> None:
    if w < 0 or (w == 0 and not allow_zero_width):
        raise ValueError(f"invalid field width {w}")
    if d < 0:
        raise ValueError(f"invalid number of digits {d}")


def _non_finite(value: float, w: int, sign_plus: bool) -> str:
    """gfortran's rendering of infinities and NaN in a numeric field."""
    if math.isnan(value):
        return _fit("NaN", w) if w == 0 or w >= 3 else _stars(w)
    sign = _sign(value < 0, sign_plus)
    long_form = sign + "Infinity"
    if w == 0 or len(long_form) <= w:
        return _fit(long_form, w)
    short_form = sign + "Inf"
    return _fit(short_form, w) if len(short_form) <= w else _stars(w)


def _rounded(value: Decimal, places: int, rounding: Rounding) -> Decimal:
    """``value`` (non-negative) rounded to ``places`` digits after the decimal point."""
    return value.quantize(
        Decimal(1).scaleb(-places), rounding=_DECIMAL_ROUNDING[rounding], context=_CONTEXT
    )


def _magnitude_mode(rounding: Rounding, negative: bool) -> Rounding:
    """Rounding mode to apply to ``abs(value)`` so that the signed value rounds as requested.

    On a non-negative magnitude, Decimal's ``ROUND_CEILING`` (``Rounding.UP``) means "away from
    zero" and ``ROUND_DOWN`` (``Rounding.ZERO``) means "toward zero".
    """
    if rounding is Rounding.UP:
        return Rounding.ZERO if negative else Rounding.UP
    if rounding is Rounding.DOWN:
        return Rounding.UP if negative else Rounding.ZERO
    return rounding


def format_i(value: int, w: int, m: int | None = None, *, sign_plus: bool = False) -> str:
    """Render ``value`` with ``Iw`` or ``Iw.m`` (``w = 0`` gives the minimal width, like ``I0``).

    ``m`` is the minimum number of digits (zero-padded). ``Iw.0`` prints a zero value as blanks.
    """
    if w < 0:
        raise ValueError(f"invalid field width {w}")
    if m is not None and (m < 0 or (w and m > w)):
        raise ValueError(f"invalid minimum digits {m} for width {w}")
    if m == 0 and value == 0:
        return " " * w
    digits = str(abs(value))
    if m is not None:
        digits = digits.rjust(m, "0")
    return _fit(_sign(value < 0, sign_plus) + digits, w)


def format_f(
    value: float,
    w: int,
    d: int,
    *,
    rounding: Rounding = Rounding.NEAREST,
    leading_zero: bool = False,
    sign_plus: bool = False,
) -> str:
    """Render ``value`` with ``Fw.d`` (``w = 0`` gives the minimal width, like ``F0.d``).

    The optional zero before the decimal point of a value below one is printed only when
    ``leading_zero`` is true and there is room for it (never for ``F0.d``, as gfortran does).
    When ``d == 0`` and the value rounds to zero, the mandatory ``0.`` is printed.
    """
    _check_width(w, d, allow_zero_width=True)
    if not math.isfinite(value):
        return _non_finite(value, w, sign_plus)
    negative = math.copysign(1.0, value) < 0
    magnitude = _rounded(Decimal(abs(value)), d, _magnitude_mode(rounding, negative))
    text = f"{magnitude:.{d}f}"
    integer_part, _, fraction = text.partition(".")
    sign = _sign(negative, sign_plus)
    if integer_part != "0":
        return _fit(f"{sign}{integer_part}.{fraction}", w)
    if d == 0:
        return _fit(f"{sign}0.", w)
    short = f"{sign}.{fraction}"
    if leading_zero and w != 0 and len(short) < w:
        return _fit(f"{sign}0.{fraction}", w)
    return _fit(short, w)


def _exponent_text(exponent: int, e: int | None) -> str | None:
    """The exponent part of an ``E``/``ES`` field, or ``None`` if it does not fit."""
    sign = "-" if exponent < 0 else "+"
    digits = str(abs(exponent))
    if e is None:
        if len(digits) <= 2:
            return "E" + sign + digits.rjust(2, "0")
        if len(digits) == 3:
            return sign + digits
        return None
    if len(digits) > e:
        return None
    return "E" + sign + digits.rjust(e, "0")


def _scaled_digits(
    value: float, d: int, rounding: Rounding, shift: int
) -> tuple[bool, Decimal, int]:
    """Split ``|value|`` into a rounded significand and a decimal exponent.

    With ``shift = 0`` the significand lies in [0.1, 1) (``E`` editing); with ``shift = 1`` it
    lies in [1, 10) (``ES`` editing). Returns ``(negative, significand, exponent)``.
    """
    negative = math.copysign(1.0, value) < 0
    magnitude = Decimal(abs(value))
    mode = _magnitude_mode(rounding, negative)
    if magnitude == 0:
        return negative, _rounded(magnitude, d, mode), 0
    exponent = magnitude.adjusted() + 1 - shift
    significand = _rounded(magnitude.scaleb(-exponent, context=_CONTEXT), d, mode)
    if significand >= 10**shift:
        exponent += 1
        significand = _rounded(magnitude.scaleb(-exponent, context=_CONTEXT), d, mode)
    return negative, significand, exponent


def format_e(
    value: float,
    w: int,
    d: int,
    e: int | None = None,
    *,
    rounding: Rounding = Rounding.NEAREST,
    leading_zero: bool = False,
    sign_plus: bool = False,
) -> str:
    """Render ``value`` with ``Ew.d`` or ``Ew.dEe`` (scale factor ``0P``: ``0.dddE+xx``).

    Without ``e`` the exponent is ``E+xx`` for magnitudes up to 99 and ``+xxx`` (no letter) up to
    999, as the standard prescribes. The optional leading zero follows the ``Fw.d`` rule.
    """
    _check_width(w, d, allow_zero_width=False)
    if d == 0:
        raise ValueError("Ew.d needs d > 0")
    if e is not None and e <= 0:
        raise ValueError(f"invalid exponent digits {e}")
    if not math.isfinite(value):
        return _non_finite(value, w, sign_plus)
    negative, significand, exponent = _scaled_digits(value, d, rounding, shift=0)
    exponent_text = _exponent_text(exponent, e)
    if exponent_text is None:
        return _stars(w)
    fraction = f"{significand:.{d}f}".split(".")[1]
    sign = _sign(negative, sign_plus)
    short = f"{sign}.{fraction}{exponent_text}"
    if leading_zero and len(short) < w:
        return _fit(f"{sign}0.{fraction}{exponent_text}", w)
    return _fit(short, w)


def format_es(
    value: float,
    w: int,
    d: int,
    e: int | None = None,
    *,
    rounding: Rounding = Rounding.NEAREST,
    sign_plus: bool = False,
) -> str:
    """Render ``value`` with ``ESw.d`` or ``ESw.dEe`` (scientific: ``d.dddE+xx``).

    ``ES25.17E3`` is the trace protocol's real format (full real64 precision).
    """
    _check_width(w, d, allow_zero_width=False)
    if e is not None and e <= 0:
        raise ValueError(f"invalid exponent digits {e}")
    if not math.isfinite(value):
        return _non_finite(value, w, sign_plus)
    negative, significand, exponent = _scaled_digits(value, d, rounding, shift=1)
    exponent_text = _exponent_text(exponent, e)
    if exponent_text is None:
        return _stars(w)
    digits = f"{significand:.{d}f}" if d else f"{significand:.0f}."
    return _fit(f"{_sign(negative, sign_plus)}{digits}{exponent_text}", w)
