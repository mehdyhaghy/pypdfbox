"""Factory for ``/CCITTFaxDecode`` Image XObjects.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.CCITTFactory``: a
final class with a private constructor and three public static
factories. Upstream supports two production paths:

1. ``createFromImage(PDDocument, BufferedImage)`` — encode a 1-bit
   ``BufferedImage`` raster as CCITT Group 4. We port this path here,
   substituting Pillow's ``"1"`` mode for the AWT
   ``TYPE_BYTE_BINARY``/pixel-size-1 dispatch.

2. ``createFromFile`` / ``createFromByteArray`` — extract an existing
   single-strip CCITT T.4/T.6 TIFF payload and re-wrap it without
   recompression.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.filter import CCITTFaxDecode
from pypdfbox.pdmodel.graphics.color import PDDeviceGray
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_TYPE: COSName = COSName.get_pdf_name("Type")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_XOBJECT: COSName = COSName.get_pdf_name("XObject")
_IMAGE: COSName = COSName.get_pdf_name("Image")
_WIDTH: COSName = COSName.get_pdf_name("Width")
_HEIGHT: COSName = COSName.get_pdf_name("Height")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_COLORSPACE: COSName = COSName.get_pdf_name("ColorSpace")
_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_LENGTH: COSName = COSName.get_pdf_name("Length")
_DECODE_PARMS: COSName = COSName.get_pdf_name("DecodeParms")
_CCITT_FAX_DECODE: COSName = COSName.get_pdf_name("CCITTFaxDecode")
_DEVICE_GRAY: COSName = COSName.get_pdf_name("DeviceGray")

_TIFF_IMAGE_WIDTH = 256
_TIFF_IMAGE_LENGTH = 257
_TIFF_BITS_PER_SAMPLE = 258
_TIFF_COMPRESSION = 259
_TIFF_PHOTOMETRIC = 262
_TIFF_FILL_ORDER = 266
_TIFF_STRIP_OFFSETS = 273
_TIFF_STRIP_BYTE_COUNTS = 279
_TIFF_COMPRESSION_T4 = 3
_TIFF_COMPRESSION_T6 = 4
_TIFF_PHOTOMETRIC_WHITE_IS_ZERO = 0
_TIFF_FILL_LEFT_TO_RIGHT = 1


def _tag_scalar(value: object, tag: int) -> int:
    if isinstance(value, tuple):
        if len(value) != 1:
            raise ValueError(f"CCITTFactory: TIFF tag {tag} must be single-valued")
        value = value[0]
    return int(value)


def _single_strip_value(value: object, tag: int) -> int:
    if isinstance(value, tuple):
        if len(value) != 1:
            raise ValueError("CCITTFactory: only single-strip TIFF images are supported")
        value = value[0]
    return int(value)


def _decode_parms(columns: int, rows: int, k: int, black_is_1: bool) -> COSDictionary:
    decode_params = COSDictionary()
    decode_params.set_int("K", k)
    decode_params.set_int("Columns", int(columns))
    decode_params.set_int("Rows", int(rows))
    if black_is_1:
        decode_params.set_boolean("BlackIs1", True)
    return decode_params


def _build_image_xobject(
    document: PDDocument,
    encoded: bytes,
    columns: int,
    rows: int,
    decode_params: COSDictionary,
) -> PDImageXObject:
    cos_doc = document.get_document()
    stream = COSStream(cos_doc.scratch_file)
    stream.set_item(_TYPE, _XOBJECT)
    stream.set_item(_SUBTYPE, _IMAGE)
    stream.set_int(_WIDTH, int(columns))
    stream.set_int(_HEIGHT, int(rows))
    stream.set_int(_BITS_PER_COMPONENT, 1)
    stream.set_item(_COLORSPACE, _DEVICE_GRAY)
    stream.set_item(_FILTER, _CCITT_FAX_DECODE)
    stream.set_item(_DECODE_PARMS, decode_params)
    stream.set_int(_LENGTH, len(encoded))
    stream.set_raw_data(encoded)

    x_image = PDImageXObject(stream)
    x_image.set_color_space(PDDeviceGray.INSTANCE)
    return x_image


def _extract_single_strip_tiff(tiff_bytes: bytes) -> tuple[bytes, int, int, COSDictionary]:
    try:
        with Image.open(io.BytesIO(tiff_bytes)) as parsed:
            if parsed.format != "TIFF":
                raise ValueError(f"expected TIFF image, got {parsed.format!r}")
            tag_v2 = parsed.tag_v2
            columns = _tag_scalar(tag_v2[_TIFF_IMAGE_WIDTH], _TIFF_IMAGE_WIDTH)
            rows = _tag_scalar(tag_v2[_TIFF_IMAGE_LENGTH], _TIFF_IMAGE_LENGTH)
            bits_per_sample = _tag_scalar(
                tag_v2.get(_TIFF_BITS_PER_SAMPLE, 1), _TIFF_BITS_PER_SAMPLE
            )
            compression = _tag_scalar(tag_v2[_TIFF_COMPRESSION], _TIFF_COMPRESSION)
            fill_order = _tag_scalar(
                tag_v2.get(_TIFF_FILL_ORDER, _TIFF_FILL_LEFT_TO_RIGHT),
                _TIFF_FILL_ORDER,
            )
            photometric = _tag_scalar(
                tag_v2.get(_TIFF_PHOTOMETRIC, 1), _TIFF_PHOTOMETRIC
            )
            offset = _single_strip_value(
                tag_v2[_TIFF_STRIP_OFFSETS], _TIFF_STRIP_OFFSETS
            )
            count = _single_strip_value(
                tag_v2[_TIFF_STRIP_BYTE_COUNTS], _TIFF_STRIP_BYTE_COUNTS
            )
    except KeyError as exc:
        raise ValueError(f"CCITTFactory: missing required TIFF tag {exc}") from exc
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"CCITTFactory: unreadable TIFF data: {exc}") from exc

    if bits_per_sample != 1:
        raise ValueError(
            f"CCITTFactory: only 1-bit TIFF images are supported, got {bits_per_sample}"
        )
    if fill_order != _TIFF_FILL_LEFT_TO_RIGHT:
        raise ValueError(
            f"CCITTFactory: unsupported TIFF FillOrder {fill_order}"
        )
    if compression == _TIFF_COMPRESSION_T6:
        k = -1
    elif compression == _TIFF_COMPRESSION_T4:
        k = 0
    else:
        raise ValueError(
            f"CCITTFactory: unsupported TIFF compression {compression}"
        )
    if offset < 0 or count < 0 or offset + count > len(tiff_bytes):
        raise ValueError("CCITTFactory: invalid TIFF strip offset/count")

    strip = tiff_bytes[offset : offset + count]
    decode_params = _decode_parms(
        columns, rows, k, photometric == _TIFF_PHOTOMETRIC_WHITE_IS_ZERO
    )
    return strip, columns, rows, decode_params


class CCITTFactory:
    """Factory for ``/CCITTFaxDecode`` Image XObjects.

    Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.CCITTFactory``.
    Upstream is a final class with a private constructor and exposes
    only static factories; we follow the same shape and forbid
    instantiation by raising in ``__init__``.
    """

    def __init__(self) -> None:  # pragma: no cover - matches upstream private ctor
        raise TypeError(
            "CCITTFactory is a static-method utility class; do not instantiate"
        )

    @staticmethod
    def create_from_image(
        document: PDDocument,
        image: Image.Image,
    ) -> PDImageXObject:
        """Encode a 1-bit b/w PIL image as a CCITT Group 4 image XObject.

        Mirrors upstream
        ``CCITTFactory.createFromImage(PDDocument, BufferedImage)``.
        Pillow's ``"1"`` mode already packs rows MSB-first to byte
        boundaries (the ISO 32000-1 §8.9.5.1 convention) so we hand the
        raster straight to :class:`CCITTFaxDecode`.

        :raises ValueError: if ``image`` is not a 1-bit (``"1"`` mode)
            PIL image. Mirrors upstream's ``IllegalArgumentException``
            ("Only 1-bit b/w images supported"); ``ValueError`` is the
            Python analogue for an illegal argument.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )
        if image.mode != "1":
            raise ValueError("Only 1-bit b/w images supported")

        width, height = image.size
        # PIL "1": 1 = white (high value), 0 = black. Upstream flips bits
        # via ``writeBits(~rgb & 1)`` so the Group 4 stream encodes
        # without /BlackIs1. PIL's tobytes() already produces the same
        # 1=white packing — no flip needed at the CCITT layer for
        # parity with upstream's stream payload polarity.
        raw = image.tobytes()

        decode_params = _decode_parms(int(width), int(height), -1, False)

        # Wrap in a one-element stream dict so CCITTFaxDecode.encode
        # resolves /DecodeParms the same way the decoder does.
        stream_shell = COSDictionary()
        stream_shell.set_item(_DECODE_PARMS, decode_params)

        enc_buf = io.BytesIO()
        CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, stream_shell)
        encoded = enc_buf.getvalue()

        return _build_image_xobject(document, encoded, width, height, decode_params)

    @staticmethod
    def create_from_byte_array(
        document: PDDocument,
        byte_array: bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Extract a single-strip CCITT TIFF into an Image XObject."""
        if not isinstance(byte_array, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"byte_array must be bytes-like, got {type(byte_array).__name__}"
            )
        tiff_bytes = bytes(byte_array)
        encoded, columns, rows, decode_params = _extract_single_strip_tiff(tiff_bytes)
        return _build_image_xobject(document, encoded, columns, rows, decode_params)

    @staticmethod
    def createFromByteArray(  # noqa: N802 - upstream Java alias
        document: PDDocument,
        byte_array: bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Java-style alias for :meth:`create_from_byte_array`."""
        return CCITTFactory.create_from_byte_array(document, byte_array)

    @staticmethod
    def create_from_file(
        document: PDDocument,
        path: str | Path,
    ) -> PDImageXObject:
        """Read ``path`` and delegate to :meth:`create_from_byte_array`."""
        return CCITTFactory.create_from_byte_array(document, Path(path).read_bytes())

    @staticmethod
    def createFromFile(  # noqa: N802 - upstream Java alias
        document: PDDocument,
        path: str | Path,
    ) -> PDImageXObject:
        """Java-style alias for :meth:`create_from_file`."""
        return CCITTFactory.create_from_file(document, path)

    @staticmethod
    def createFromImage(  # noqa: N802 - upstream Java alias
        document: PDDocument,
        image: Image.Image,
    ) -> PDImageXObject:
        """Java-style alias for :meth:`create_from_image`."""
        return CCITTFactory.create_from_image(document, image)


__all__ = ["CCITTFactory"]
