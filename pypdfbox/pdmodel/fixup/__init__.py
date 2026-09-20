"""Document-level fixup helpers — port of ``org.apache.pdfbox.pdmodel.fixup``."""

from .abstract_fixup import AbstractFixup
from .acro_form_default_fixup import AcroFormDefaultFixup
from .pd_document_fixup import PDDocumentFixup

__all__ = [
    "AbstractFixup",
    "AcroFormDefaultFixup",
    "PDDocumentFixup",
]
