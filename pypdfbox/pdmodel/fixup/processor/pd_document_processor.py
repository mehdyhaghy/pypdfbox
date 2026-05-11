"""Processor protocol — port of
``org.apache.pdfbox.pdmodel.fixup.processor.PDDocumentProcessor``.

Java path:
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/processor/PDDocumentProcessor.java``
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class PDDocumentProcessor(ABC):
    """Mirror of the upstream ``PDDocumentProcessor`` interface — a
    single ``void process()`` declaration. Concrete processors are
    driven by an :class:`AcroFormDefaultFixup` or applied directly."""

    @abstractmethod
    def process(self) -> None:
        """Mirrors ``process`` (Java line 21)."""


__all__ = ["PDDocumentProcessor"]
