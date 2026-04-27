"""Upstream-named alias for :class:`PDPropertyList`.

Apache PDFBox places ``PDPropertyList`` under
``org.apache.pdfbox.pdmodel.documentinterchange.markedcontent``. The pypdfbox
implementation lives under ``pypdfbox.pdmodel.graphics`` for historical
reasons; this module re-exports the same class at the upstream-equivalent
import path so PDFBox developers can find it where they expect.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList

__all__ = ["PDPropertyList"]
