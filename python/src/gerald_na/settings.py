"""Runtime settings: ``config/settings.toml`` overridden by ``GERALD_NA_*`` environment variables.

Precedence (highest first): keyword arguments, environment variables, ``config/settings.toml``,
field defaults. The repository root is auto-detected (see :func:`find_repo_root`) unless given
explicitly through ``GERALD_NA_REPO_ROOT`` or the ``repo_root`` keyword argument. Relative paths
such as ``fortran_bin_dir`` are resolved against it.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

__all__ = [
    "CONFIG_FILE",
    "ENV_PREFIX",
    "EngineName",
    "Settings",
    "find_repo_root",
    "get_settings",
    "list_executables",
]

ENV_PREFIX = "GERALD_NA_"
CONFIG_FILE = Path("config") / "settings.toml"
"""Location of the settings file, relative to the repository root."""

type EngineName = Literal["python", "fortran"]


def _is_repo_root(path: Path) -> bool:
    return (path / CONFIG_FILE).is_file() or (path / "catalog").is_dir()


def find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root: the nearest ancestor holding ``config/settings.toml`` or
    ``catalog/``.

    The search starts at ``start`` (default: this package's directory) and falls back to the
    current working directory and its ancestors. If neither search succeeds, the current working
    directory is returned.
    """
    starts = [start] if start is not None else [Path(__file__).resolve().parent, Path.cwd()]
    for origin in starts:
        resolved = origin.resolve()
        for candidate in (resolved, *resolved.parents):
            if _is_repo_root(candidate):
                return candidate
    return Path.cwd().resolve()


def list_executables(directory: Path) -> list[str]:
    """Names of the executable regular files in ``directory`` (empty if it does not exist)."""
    if not directory.is_dir():
        return []
    return sorted(
        entry.name for entry in directory.iterdir() if entry.is_file() and os.access(entry, os.X_OK)
    )


class Settings(BaseSettings):
    """Application settings (see ``config/settings.toml`` for the documented defaults)."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        extra="ignore",
        frozen=True,
    )

    repo_root: Path = Field(
        default_factory=find_repo_root,
        description="Repository root; relative paths are resolved against it.",
    )
    fortran_bin_dir: Path = Field(
        default=Path("build/bin"),
        description="Directory of the compiled Fortran drivers (relative to repo_root).",
    )
    run_timeout_s: float = Field(
        default=5.0, gt=0, description="Timeout in seconds for one Fortran driver run."
    )
    engines_enabled: tuple[EngineName, ...] = Field(
        default=("python", "fortran"), description="Engines offered by the UI and API."
    )
    host: str = Field(default="127.0.0.1", description="Bind address for `gerald-na serve`.")
    port: int = Field(default=8000, ge=1, le=65535, description="Port for `gerald-na serve`.")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use keyword arguments, then environment, then the repository's settings TOML."""
        root = _explicit_repo_root(init_settings) or find_repo_root()
        toml_source = TomlConfigSettingsSource(settings_cls, toml_file=root / CONFIG_FILE)
        return (init_settings, env_settings, toml_source)

    def resolve_path(self, path: Path) -> Path:
        """Resolve ``path`` against :attr:`repo_root` unless it is already absolute."""
        return path if path.is_absolute() else self.repo_root / path

    @property
    def config_file(self) -> Path:
        """The settings TOML file belonging to :attr:`repo_root`."""
        return self.repo_root / CONFIG_FILE

    @property
    def fortran_bin_path(self) -> Path:
        """Absolute directory of the compiled Fortran drivers."""
        return self.resolve_path(self.fortran_bin_dir)

    def fortran_executables(self) -> list[str]:
        """Names of the Fortran drivers currently present in :attr:`fortran_bin_path`."""
        return list_executables(self.fortran_bin_path)


def _explicit_repo_root(init_settings: PydanticBaseSettingsSource) -> Path | None:
    """The repository root given as a keyword argument or ``GERALD_NA_REPO_ROOT``, if any."""
    from_init = init_settings().get("repo_root")
    if from_init is not None:
        return Path(from_init)
    from_env = os.environ.get(f"{ENV_PREFIX}REPO_ROOT")
    if from_env:
        return Path(from_env)
    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, loaded once. Call ``get_settings.cache_clear()`` to reload."""
    return Settings()
