"""Typed errors and their mapping to trace ERROR codes."""

import pytest

from gerald_na.errors import (
    TRACE_ERROR_CODES,
    BracketError,
    DegreeError,
    EngineError,
    EngineUnavailableError,
    FortranRunError,
    GeraldNAError,
    InputError,
    NonConvergenceError,
    OddPanelsError,
    ZeroProductError,
    error_from_trace,
)


@pytest.mark.parametrize(
    ("cls", "code"),
    [
        (InputError, "INPUT"),
        (BracketError, "BRACKET"),
        (ZeroProductError, "ZERO_PRODUCT"),
        (OddPanelsError, "ODD_PANELS"),
        (NonConvergenceError, "NON_CONVERGENT"),
        (DegreeError, "DEGREE"),
        (EngineError, "ENGINE"),
        (EngineUnavailableError, "ENGINE_UNAVAILABLE"),
        (FortranRunError, "FORTRAN_RUN"),
    ],
)
def test_error_codes_are_stable(cls: type[GeraldNAError], code: str) -> None:
    assert cls.code == code
    error = cls("details")
    assert isinstance(error, GeraldNAError)
    assert error.message == "details"
    assert str(error) == "details"


def test_hierarchy() -> None:
    assert issubclass(ZeroProductError, BracketError)
    assert issubclass(EngineUnavailableError, EngineError)
    assert issubclass(FortranRunError, EngineError)


def test_trace_codes_cover_algorithm_errors_only() -> None:
    assert set(TRACE_ERROR_CODES) == {
        "INPUT",
        "BRACKET",
        "ZERO_PRODUCT",
        "ODD_PANELS",
        "NON_CONVERGENT",
        "DEGREE",
    }
    for code, cls in TRACE_ERROR_CODES.items():
        assert cls.code == code


def test_error_from_trace_builds_typed_error() -> None:
    error = error_from_trace("ZERO_PRODUCT", "ERROR.")
    assert type(error) is ZeroProductError
    assert error.message == "ERROR."


def test_error_from_trace_rejects_unknown_codes() -> None:
    error = error_from_trace("BOGUS", "something")
    assert type(error) is FortranRunError
    assert "BOGUS" in error.message
