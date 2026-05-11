"""``JPEGUtil`` class port — sets DPI on a JPEG metadata tree.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/imageio/JPEGUtil.java
    (lines 28-96)

In Pillow the DPI is set by passing ``dpi=(x, y)`` to ``Image.save``; we
expose a small adapter that builds the matching ``info`` dict so callers
that need to inspect / round-trip metadata still see the right values.
"""
from __future__ import annotations

from typing import Any

from .meta_util import MetaUtil


class JPEGUtil:
    """Static-only utility — final class with private ctor in upstream."""

    def __new__(cls) -> JPEGUtil:  # pragma: no cover — mirrors private ctor
        raise TypeError("JPEGUtil is a static-only utility")

    @staticmethod
    def update_metadata(metadata: Any, dpi: int) -> None:
        """Mirror of upstream package-private ``updateMetadata(IIOMetadata, int)``.

        Sets JFIF density attributes on the metadata tree. ``metadata`` can be:
          - a Pillow ``Image`` (we patch ``.info['dpi']``)
          - a generic dict (we set ``"Xdensity"`` / ``"Ydensity"``)
        """
        MetaUtil.debug_log_metadata(metadata, MetaUtil.JPEG_NATIVE_FORMAT)
        if hasattr(metadata, "info") and isinstance(metadata.info, dict):
            metadata.info["dpi"] = (dpi, dpi)
            return
        if isinstance(metadata, dict):
            metadata.setdefault("majorVersion", "1")
            metadata.setdefault("minorVersion", "2")
            metadata["resUnits"] = "1"
            metadata["Xdensity"] = str(dpi)
            metadata["Ydensity"] = str(dpi)
            metadata.setdefault("thumbWidth", "0")
            metadata.setdefault("thumbHeight", "0")
