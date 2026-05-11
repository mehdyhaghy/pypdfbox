"""Functional interface for filtering ``PDAnnotation`` instances.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.AnnotationFilter``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/
annotation/AnnotationFilter.java``).

Upstream is a ``@FunctionalInterface`` taking ``PDAnnotation`` and returning
``boolean``. Python callers can pass any callable that matches that
signature; this class is retained for API parity so user code that types
``filter: AnnotationFilter`` still resolves.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation


class AnnotationFilter(ABC):
    """Single-method strategy used by ``PDPage.get_annotations(filter)``."""

    @abstractmethod
    def accept(self, annotation: PDAnnotation) -> bool:
        """Return True if ``annotation`` should be kept."""


__all__ = ["AnnotationFilter"]
