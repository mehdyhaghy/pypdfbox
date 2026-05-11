"""Common base for AcroForm processors.

Mirrors ``org.apache.pdfbox.pdmodel.fixup.processor.AbstractProcessor``
(Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/AbstractProcessor.java``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_document_processor import PDDocumentProcessor

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class AbstractProcessor(PDDocumentProcessor):
    """Base class — holds the document the processor operates on.

    Mirrors the upstream ``AbstractProcessor`` (Java line 21).
    """

    def __init__(self, document: PDDocument) -> None:
        self.document = document

    def process(self) -> None:
        raise NotImplementedError


__all__ = ["AbstractProcessor"]
