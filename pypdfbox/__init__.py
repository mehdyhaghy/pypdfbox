from typing import TYPE_CHECKING

# Public re-exports resolve lazily (PEP 562) so ``import pypdfbox`` and the
# ``pypdfbox`` CLI stay cheap; the objects are the same ones the submodules
# define.
_LAZY_EXPORTS = {
    "Loader": "pypdfbox.loader",
    "PDDocument": "pypdfbox.pdmodel.pd_document",
    "PDDocumentCatalog": "pypdfbox.pdmodel.pd_document_catalog",
    "PDPage": "pypdfbox.pdmodel.pd_page",
    "PDPageTree": "pypdfbox.pdmodel.pd_page_tree",
    "PDRectangle": "pypdfbox.pdmodel.pd_rectangle",
    "PDResources": "pypdfbox.pdmodel.pd_resources",
}

if TYPE_CHECKING:
    from .loader import Loader
    from .pdmodel import (
        PDDocument,
        PDDocumentCatalog,
        PDPage,
        PDPageTree,
        PDRectangle,
        PDResources,
    )

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


def _package_version() -> str:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    try:
        return _pkg_version("pypdfbox")
    except PackageNotFoundError:  # pragma: no cover - source tree without install metadata
        return "0.0.0+unknown"


def __getattr__(name: str) -> object:
    if name == "__version__":
        value: object = _package_version()
    else:
        module_name = _LAZY_EXPORTS.get(name)
        if module_name is None:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        from importlib import import_module

        value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
