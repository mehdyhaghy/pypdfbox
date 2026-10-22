"""Document-level fixup helpers — port of ``org.apache.pdfbox.pdmodel.fixup``."""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .abstract_fixup import AbstractFixup
    from .acro_form_default_fixup import AcroFormDefaultFixup
    from .pd_document_fixup import PDDocumentFixup

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AbstractFixup": ".abstract_fixup",
        "AcroFormDefaultFixup": ".acro_form_default_fixup",
        "PDDocumentFixup": ".pd_document_fixup",
    },
)

__all__ = [
    "AbstractFixup",
    "AcroFormDefaultFixup",
    "PDDocumentFixup",
]
