from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .k_cloner import KCloner
    from .layer_utility import LayerUtility
    from .overlay import (
        Overlay,
        Position,
    )
    from .page_extractor import PageExtractor
    from .pdf_clone_utility import PDFCloneUtility
    from .pdf_merger_utility import (
        AcroFormMergeMode,
        DocumentMergeMode,
        PDFMergerUtility,
    )
    from .splitter import Splitter

__getattr__, __dir__ = _attach(
    __name__,
    {
        "KCloner": ".k_cloner",
        "LayerUtility": ".layer_utility",
        "Overlay": ".overlay",
        "Position": ".overlay",
        "PageExtractor": ".page_extractor",
        "PDFCloneUtility": ".pdf_clone_utility",
        "AcroFormMergeMode": ".pdf_merger_utility",
        "DocumentMergeMode": ".pdf_merger_utility",
        "PDFMergerUtility": ".pdf_merger_utility",
        "Splitter": ".splitter",
    },
)

__all__ = [
    "AcroFormMergeMode",
    "DocumentMergeMode",
    "KCloner",
    "LayerUtility",
    "Overlay",
    "PDFCloneUtility",
    "PDFMergerUtility",
    "PageExtractor",
    "Position",
    "Splitter",
]
