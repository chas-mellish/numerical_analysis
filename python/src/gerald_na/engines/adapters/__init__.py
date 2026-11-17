"""Registry of the per-program adapters (:class:`~gerald_na.engines.programs.ProgramAdapter`).

Adding a program = one new module in this package with a ``ProgramAdapter`` subclass, plus one
entry in :data:`_BUILTIN` below (see ``docs/architecture.md``, "Adding a program to the
engines").
"""

from collections.abc import Mapping
from types import MappingProxyType

from gerald_na.engines.adapters.bairstow import BairstowAdapter
from gerald_na.engines.adapters.bisection import BisectionAdapter
from gerald_na.engines.programs import ProgramAdapter
from gerald_na.errors import EngineUnavailableError

__all__ = [
    "BairstowAdapter",
    "BisectionAdapter",
    "adapters",
    "get_adapter",
    "register_adapter",
]

_BUILTIN: tuple[ProgramAdapter, ...] = (BisectionAdapter(), BairstowAdapter())

_ADAPTERS: dict[str, ProgramAdapter] = {adapter.program_id: adapter for adapter in _BUILTIN}


def register_adapter(adapter: ProgramAdapter, *, replace: bool = False) -> None:
    """Register ``adapter`` for its ``program_id`` (``replace`` an existing one explicitly)."""
    if adapter.program_id in _ADAPTERS and not replace:
        raise ValueError(f"an adapter for {adapter.program_id!r} is already registered")
    _ADAPTERS[adapter.program_id] = adapter


def get_adapter(program_id: str) -> ProgramAdapter:
    """The adapter of ``program_id``; :class:`EngineUnavailableError` if none is registered."""
    try:
        return _ADAPTERS[program_id]
    except KeyError:
        raise EngineUnavailableError(
            f"program {program_id!r} has no engine adapter yet "
            "(add one in gerald_na.engines.adapters)"
        ) from None


def adapters() -> Mapping[str, ProgramAdapter]:
    """Read-only view of the registered adapters, keyed by program id."""
    return MappingProxyType(_ADAPTERS)
