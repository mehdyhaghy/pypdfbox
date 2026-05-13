from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from .loader import Loader
from .pdmodel import (
    PDDocument,
    PDDocumentCatalog,
    PDPage,
    PDPageTree,
    PDRectangle,
    PDResources,
)

try:
    __version__ = _pkg_version("pypdfbox")
except PackageNotFoundError:  # pragma: no cover - source tree without install metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "Loader",
    "PDDocument",
    "PDDocumentCatalog",
    "PDPage",
    "PDPageTree",
    "PDRectangle",
    "PDResources",
    "__version__",
]
