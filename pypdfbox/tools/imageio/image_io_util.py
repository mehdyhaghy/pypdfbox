"""``ImageIOUtil`` class port — writes images to disk via Pillow.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/imageio/ImageIOUtil.java
    (lines 53-411)

Library-first: Pillow's ``Image.save`` covers PNG / JPEG / TIFF / GIF /
BMP / WBMP. We expose the same 3-arg / 4-arg / 5-arg overloads as
upstream so callers can drop in ``ImageIOUtil.write_image(...)``
unchanged.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from PIL import Image

from .jpeg_util import JPEGUtil
from .meta_util import MetaUtil
from .tiff_util import TIFFUtil

LOG = logging.getLogger(__name__)


def _to_pil(image: Any) -> Image.Image:
    """Coerce a ``BufferedImage``-shaped argument to a Pillow ``Image``.

    pypdfbox's renderer hands back Pillow images directly; if a caller
    passes a path-like or bytes, we open it the obvious way.
    """
    if isinstance(image, Image.Image):
        return image
    if isinstance(image, (bytes, bytearray, memoryview)):
        return Image.open(io.BytesIO(bytes(image)))
    if isinstance(image, (str, Path)):
        return Image.open(image)
    raise TypeError(f"Cannot coerce {type(image)} to a PIL.Image")


_PIL_FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "jpg2": "JPEG2000",
    "jp2": "JPEG2000",
    "jpeg2000": "JPEG2000",
    "png": "PNG",
    "gif": "GIF",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
    "wbmp": "WBMP",
}


def _pil_format(format_name: str) -> str:
    return _PIL_FORMAT_MAP.get(format_name.lower(), format_name.upper())


class ImageIOUtil:
    """Static-only utility — mirrors upstream ``ImageIOUtil``."""

    def __new__(cls) -> ImageIOUtil:  # pragma: no cover — mirrors private ctor
        raise TypeError("ImageIOUtil is a static-only utility")

    # --- overload 1: (image, filename, dpi) -> bool --------------------
    @staticmethod
    def write_image(
        image: Any,
        target: Any,
        dpi_or_format: Any = None,
        compression_quality: float | None = None,
        compression_type: str | None = None,
    ) -> bool:
        """Mirror of upstream overload family ``writeImage(...)``.

        Java upstream has 5 overloads (2/3/4/5/6-arg). We unify them on a
        single Python signature; positional args follow the longest
        upstream form ``(image, formatName_or_filename, output_or_dpi,
        dpi, compressionQuality, compressionType)`` with the third arg
        polymorphic to ride the same shape.
        """
        try:
            pil = _to_pil(image)
        except (TypeError, OSError) as exc:
            LOG.error("write_image: %s", exc)
            return False

        # Resolve (filename | output stream | format), and the dpi number.
        filename: str | None = None
        output_stream = None
        format_name: str | None = None
        dpi: int = 72
        if isinstance(target, (str, Path)):
            filename = str(target)
            format_name = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
            if isinstance(dpi_or_format, int):
                dpi = dpi_or_format
        elif hasattr(target, "write"):
            output_stream = target
            # third positional must be the format name in this shape
            format_name = str(dpi_or_format or "png").lower()
            if isinstance(compression_quality, int):
                dpi = compression_quality
                compression_quality = None
        else:
            LOG.error("write_image: unsupported target type %s", type(target))
            return False

        if compression_quality is None:
            compression_quality = 0.0 if format_name == "png" else 1.0

        save_kwargs: dict[str, Any] = {"format": _pil_format(format_name), "dpi": (dpi, dpi)}
        if format_name in {"jpg", "jpeg"}:
            save_kwargs["quality"] = int(max(0.0, min(1.0, compression_quality)) * 100)
            JPEGUtil.update_metadata(pil, dpi)
        elif format_name.startswith("tif"):
            param: dict[str, Any] = {}
            if compression_type:
                param["compressionType"] = compression_type
            else:
                TIFFUtil.set_compression_type(param, pil)
            comp = param.get("compressionType")
            if comp == "CCITT T.6":
                save_kwargs["compression"] = "group4"
            elif comp == "LZW":
                save_kwargs["compression"] = "tiff_lzw"
            TIFFUtil.update_metadata({}, pil, dpi)

        try:
            if output_stream is not None:
                pil.save(output_stream, **save_kwargs)
            else:
                if filename is None:  # defensive — should be unreachable
                    raise OSError("no filename or output stream")
                pil.save(filename, **save_kwargs)
        except (OSError, ValueError, KeyError) as exc:
            LOG.error("write_image: %s", exc)
            return False
        # debug log the format/standard metadata, mirrors upstream side-effect.
        MetaUtil.debug_log_metadata(pil, MetaUtil.STANDARD_METADATA_FORMAT)
        return True

    @staticmethod
    def get_writer_format_names() -> list[str]:
        """Convenience helper — Java has ``ImageIO.getWriterFormatNames()``."""
        return sorted(_PIL_FORMAT_MAP.keys())

    @staticmethod
    def has_icc_profile(image: Any) -> bool:
        """Mirror of upstream private ``hasICCProfile``."""
        try:
            pil = _to_pil(image)
        except (TypeError, OSError):
            return False
        return bool(pil.info.get("icc_profile"))

    @staticmethod
    def get_as_deflated_bytes(profile: bytes) -> bytes:
        """Mirror of upstream private ``getAsDeflatedBytes``."""
        import zlib
        return zlib.compress(profile)

    @staticmethod
    def get_or_create_child_node(parent: Any, name: str) -> Any:
        """Mirror of upstream private ``getOrCreateChildNode``.

        ``parent`` is a dict-like; we just ensure ``parent[name]`` exists.
        """
        if isinstance(parent, dict):
            return parent.setdefault(name, {})
        raise TypeError("get_or_create_child_node expects a dict-like parent")

    @staticmethod
    def set_dpi(metadata: Any, dpi: int, format_name: str) -> None:
        """Mirror of upstream private ``setDPI``."""
        if isinstance(metadata, dict):
            res = (dpi / 25.4) if format_name.upper() == "PNG" else (25.4 / dpi)
            metadata.setdefault("Dimension", {})
            metadata["Dimension"]["HorizontalPixelSize"] = str(res)
            metadata["Dimension"]["VerticalPixelSize"] = str(res)
