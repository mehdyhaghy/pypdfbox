"""Common base for document fixups.

Mirrors ``org.apache.pdfbox.pdmodel.fixup.AbstractFixup`` (Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/AbstractFixup.java``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_document_fixup import PDDocumentFixup

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class AbstractFixup(PDDocumentFixup):
    """Base class — holds the document the fixup will operate on.

    Mirrors the upstream ``AbstractFixup`` (Java line 21). The Python
    port keeps the protected-final ``document`` field exposed under the
    same name; subclasses access it directly.
    """

    def __init__(self, document: PDDocument) -> None:
        self.document = document

    def apply(self) -> None:
        """Abstract — concrete fixups override this."""
        raise NotImplementedError


__all__ = ["AbstractFixup"]
