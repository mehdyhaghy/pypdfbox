"""Functional-interface for custom image factories.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.CustomFactory``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .pd_image_x_object import PDImageXObject


class CustomFactory:
    """Adapter wrapping a user callback that creates a ``PDImageXObject``."""

    __slots__ = ("_fn",)

    def __init__(self, fn: Callable[[Any, bytes], Any]) -> None:
        self._fn = fn

    def create_from_byte_array(
        self,
        document: PDDocument,
        byte_array: bytes,
    ) -> PDImageXObject:
        """Create a ``PDImageXObject`` from raw bytes."""
        return self._fn(document, byte_array)

    def __call__(self, document: PDDocument, byte_array: bytes) -> PDImageXObject:
        return self._fn(document, byte_array)


__all__ = ["CustomFactory"]
