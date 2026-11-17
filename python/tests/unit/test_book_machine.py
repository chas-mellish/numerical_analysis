"""The chopped-arithmetic emulation reproduces the numbers quoted in docs/architecture.md.

``docs/architecture.md``, "The book's computer", cites these values as evidence; if the tool or
the docs change, this test keeps them in step.
"""

from fractions import Fraction

import pytest

from gerald_na.tools import book_machine
from gerald_na.tools.book_machine import (
    BOOK_BISECTION,
    ChoppedMachine,
    bisection_rows,
    coefficient_echo,
    printed,
    romberg_si,
    simpson_si,
)

BINARY27 = ChoppedMachine(2, 27)
DECIMAL8 = ChoppedMachine(10, 8)
DECIMAL9 = ChoppedMachine(10, 9)


def _round(value: Fraction, places: int) -> float:
    return round(float(value), places)


def test_chop_binary_truncates_toward_zero() -> None:
    machine = ChoppedMachine(2, 3)
    assert machine.chop(Fraction(15, 2)) == 7  # 111.1b -> 111b
    assert machine.chop(Fraction(-15, 2)) == -7
    assert machine.chop(Fraction(1, 3)) == Fraction(5, 16)  # 0.0101010...b -> 0.0101b
    assert machine.chop(Fraction(0)) == 0


def test_chop_decimal_truncates_toward_zero() -> None:
    machine = ChoppedMachine(10, 4)
    assert machine.chop(Fraction("3.14159")) == Fraction("3.141")
    assert machine.chop(Fraction("-0.000123456")) == Fraction("-0.0001234")
    assert machine.chop(Fraction(123456)) == 123400
    assert machine.const("2.E-7") == Fraction(2, 10_000_000)


def test_invalid_machines_are_rejected() -> None:
    with pytest.raises(ValueError, match="base"):
        ChoppedMachine(16, 6)
    with pytest.raises(ValueError, match="digits"):
        ChoppedMachine(2, 0)
    with pytest.raises(ValueError, match="even"):
        simpson_si(BINARY27, n=7)


def test_printed_chops_like_the_book_printer() -> None:
    assert printed(Fraction("0.44140625"), 7) == Fraction("0.4414062")
    assert printed(Fraction("-0.0005069"), 6) == Fraction("-0.000506")


def test_simpson_models_match_the_docs() -> None:
    binary = simpson_si(BINARY27)
    assert _round(binary, 9) == 1.549930662  # docs: 1.54993066
    assert _round(binary, 7) == 1.5499307  # the book's value, rounded ...
    assert printed(binary, 7) == Fraction("1.5499306")  # ... and 1.5499306 when chopped
    assert _round(simpson_si(DECIMAL8), 7) == 1.5499262
    assert _round(simpson_si(DECIMAL9), 7) == 1.5499308


def test_romberg_models_match_the_docs() -> None:
    binary = romberg_si(BINARY27)
    assert binary.converged
    assert len(binary.lines) == 4
    assert binary.subintervals == 80
    assert _round(binary.value, 7) == 1.6181938
    book_last_line = (1.6180369, 1.6181940, 1.6181936, 1.6181936)
    assert all(
        abs(float(v) - b) < 3e-7 for v, b in zip(binary.lines[-1], book_last_line, strict=True)
    )
    decimal8 = romberg_si(DECIMAL8)
    assert (len(decimal8.lines), _round(decimal8.value, 7)) == (4, 1.6181909)
    decimal9 = romberg_si(DECIMAL9)
    assert (len(decimal9.lines), _round(decimal9.value, 7)) == (4, 1.6181941)


def test_romberg_without_convergence_returns_the_full_table() -> None:
    run = romberg_si(BINARY27, tol="-1.")
    assert not run.converged
    assert len(run.lines) == 9
    assert run.subintervals == 2560


@pytest.mark.parametrize("machine", [BINARY27, DECIMAL8], ids=["binary27", "decimal8"])
def test_bisection_digits_do_not_discriminate(machine: ChoppedMachine) -> None:
    rows = bisection_rows(machine)
    assert len(rows) == 15
    for (k, x, fx), (book_k, book_x, book_fx) in zip(rows, BOOK_BISECTION, strict=True):
        assert k == book_k
        assert printed(x, 7) == book_x
        assert printed(fx, 6) == book_fx


def test_coefficient_echo_needs_a_decimal_machine() -> None:
    assert [float(v) for v in coefficient_echo(DECIMAL8)][:4] == [1.0, -17.8, 99.41, -261.218]
    binary = [float(v) for v in coefficient_echo(BINARY27)]
    assert binary[1:4] == [-17.79999, 99.40999, -261.21799]


def test_main_prints_the_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert book_machine.main([]) == 0
    out = capsys.readouterr().out
    assert "27-bit binary" in out
    assert "1.549930662" in out
    assert "bisection 15/15" in out
    assert book_machine.main(["--bits", "24", "--digits", "7"]) == 0
    out = capsys.readouterr().out
    assert "24-bit binary" in out
    assert "7-digit decimal" in out


def test_romberg_binary_table_is_within_3e7_of_the_book() -> None:
    book = (
        (1.6077255,),
        (1.6156591, 1.6183036),
        (1.6175654, 1.6182008, 1.6181940),
        (1.6180369, 1.6181940, 1.6181936, 1.6181936),
    )
    lines = romberg_si(BINARY27).lines
    assert [len(line) for line in lines] == [len(line) for line in book]
    for line, book_line in zip(lines, book, strict=True):
        for value, book_value in zip(line, book_line, strict=True):
            assert abs(float(printed(value, 7)) - book_value) <= 3e-7 + 1e-12
