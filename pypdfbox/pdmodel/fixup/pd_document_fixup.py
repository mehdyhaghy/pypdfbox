"""Fixup protocol — port of ``org.apache.pdfbox.pdmodel.fixup.PDDocumentFixup``.

Java path: ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fixup/PDDocumentFixup.java``
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class PDDocumentFixup(ABC):
    """Mirror of the upstream ``PDDocumentFixup`` interface (3 lines of
    Java — a single ``void apply()`` declaration). Concrete fixups
    implement :meth:`apply` to mutate the bound document in place."""

    @abstractmethod
    def apply(self) -> None:
        """Run the fixup. Mirrors ``PDDocumentFixup.apply`` (Java line 21)."""


__all__ = ["PDDocumentFixup"]
