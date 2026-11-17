"""Program catalog: loads ``catalog/*.toml`` into validated models.

The catalog schema is documented in ``docs/architecture.md`` ("Catalog schema").
"""

from gerald_na.registry.loader import (
    CATALOG_DIR,
    PYTHON_SOURCE_DIR,
    CatalogError,
    CatalogPathError,
    FileKind,
    IntegrityProblem,
    Registry,
    get_registry,
    load_entry,
)
from gerald_na.registry.models import (
    ANSWER_FIELDS,
    BookRef,
    CatalogEntry,
    CatalogInput,
    Chart,
    DataCard,
    Erratum,
    Expected,
    FilesRef,
    FunctionSpec,
    PracticeQuestion,
    Preset,
    ResultExtra,
    StepColumn,
    TraceRecord,
    TraceSpec,
)

__all__ = [
    "ANSWER_FIELDS",
    "CATALOG_DIR",
    "PYTHON_SOURCE_DIR",
    "BookRef",
    "CatalogEntry",
    "CatalogError",
    "CatalogInput",
    "CatalogPathError",
    "Chart",
    "DataCard",
    "Erratum",
    "Expected",
    "FileKind",
    "FilesRef",
    "FunctionSpec",
    "IntegrityProblem",
    "PracticeQuestion",
    "Preset",
    "Registry",
    "ResultExtra",
    "StepColumn",
    "TraceRecord",
    "TraceSpec",
    "get_registry",
    "load_entry",
]
