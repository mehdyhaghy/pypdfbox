"""Render destination for optional content visibility.

Mirrors ``org.apache.pdfbox.rendering.RenderDestination``. Optional
content groups are visible depending on the render purpose: graphics
export, on-screen viewing, or printing.
"""

from __future__ import annotations

from enum import Enum


class RenderDestination(Enum):
    """Optional content groups are visible depending on the render purpose."""

    # Graphics export.
    EXPORT = "Export"
    # Viewing.
    VIEW = "View"
    # Printing.
    PRINT = "Print"


__all__ = ["RenderDestination"]
