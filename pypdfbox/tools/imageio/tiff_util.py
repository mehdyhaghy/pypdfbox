"""``TIFFUtil`` class port — TIFF compression + metadata helpers.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/imageio/TIFFUtil.java
    (lines 34-179)

The Java helpers configure javax.imageio's TIFF writer; Pillow exposes
the equivalent through ``Image.save(..., compression='group4'|'tiff_lzw',
dpi=(x,y))``. We provide adapter functions that produce the right kwargs
for both flows.
"""
from __future__ import annotations

import logging
from typing import Any

from .meta_util import MetaUtil

LOG = logging.getLogger(__name__)


class TIFFUtil:
    """Static-only utility — final class with private ctor in upstream."""

    def __new__(cls) -> TIFFUtil:  # pragma: no cover — mirrors private ctor
        raise TypeError("TIFFUtil is a static-only utility")

    @staticmethod
    def set_compression_type(param: dict[str, Any], image: Any) -> None:
        """Mirror of upstream ``setCompressionType(ImageWriteParam, BufferedImage)``.

        ``param`` is a mutable dict (acts as the ImageWriteParam stand-in).
        ``image`` is a Pillow ``Image`` (or anything with ``.mode`` /
        ``.size``). We pick CCITT G4 for bitonal images, LZW otherwise.
        """
        is_bitonal = False
        try:
            if getattr(image, "mode", None) == "1":
                is_bitonal = True
        except AttributeError:
            pass
        if is_bitonal:
            param["compressionType"] = "CCITT T.6"
        else:
            param["compressionType"] = "LZW"

    @staticmethod
    def update_metadata(metadata: Any, image: Any, dpi: int) -> None:
        """Mirror of upstream package-private ``updateMetadata``."""
        meta_format = getattr(metadata, "native_metadata_format_name", None)
        if isinstance(metadata, dict):
            meta_format = MetaUtil.SUN_TIFF_FORMAT
        if meta_format is None:
            LOG.debug("TIFF image writer doesn't support any data format")
            return
        MetaUtil.debug_log_metadata(metadata, meta_format)
        # Build a minimal TIFFIFD-like dict for downstream consumers.
        if isinstance(metadata, dict):
            metadata.setdefault("TIFFIFD", {})
            ifd = metadata["TIFFIFD"]
            ifd[282] = TIFFUtil.create_rational_field(282, "XResolution", dpi, 1)
            ifd[283] = TIFFUtil.create_rational_field(283, "YResolution", dpi, 1)
            ifd[296] = TIFFUtil.create_short_field(296, "ResolutionUnit", 2)
            height = getattr(image, "height", None) or (
                image.size[1] if hasattr(image, "size") else 1
            )
            ifd[278] = TIFFUtil.create_long_field(278, "RowsPerStrip", height)
            ifd[305] = TIFFUtil.create_ascii_field(305, "Software", "PDFBOX")
            if getattr(image, "mode", None) == "1":
                ifd[262] = TIFFUtil.create_short_field(262, "PhotometricInterpretation", 0)
        elif hasattr(metadata, "info") and isinstance(metadata.info, dict):
            metadata.info["dpi"] = (dpi, dpi)
        MetaUtil.debug_log_metadata(metadata, meta_format)

    # --- field-builder helpers (mirror upstream private statics, promoted) ---
    @staticmethod
    def create_short_field(number: int, name: str, val: int) -> dict[str, Any]:
        return {"number": number, "name": name, "type": "short", "value": val}

    @staticmethod
    def create_ascii_field(number: int, name: str, val: str) -> dict[str, Any]:
        return {"number": number, "name": name, "type": "ascii", "value": val}

    @staticmethod
    def create_long_field(number: int, name: str, val: int) -> dict[str, Any]:
        return {"number": number, "name": name, "type": "long", "value": val}

    @staticmethod
    def create_rational_field(
        number: int, name: str, numerator: int, denominator: int,
    ) -> dict[str, Any]:
        return {
            "number": number,
            "name": name,
            "type": "rational",
            "value": f"{numerator}/{denominator}",
        }
