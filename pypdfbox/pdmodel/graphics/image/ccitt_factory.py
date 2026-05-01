"""Factory for ``/CCITTFaxDecode`` Image XObjects.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.CCITTFactory``: a
final class with a private constructor and three public static
factories. Upstream supports two production paths:

1. ``createFromImage(PDDocument, BufferedImage)`` — encode a 1-bit
   ``BufferedImage`` raster as CCITT Group 4. We port this path here,
   substituting Pillow's ``"1"`` mode for the AWT
   ``TYPE_BYTE_BINARY``/pixel-size-1 dispatch.

2. ``createFromFile`` / ``createFromByteArray`` — extract an existing
   CCITT-encoded TIFF strip and re-wrap it. This path is **not yet
   ported**: it requires a TIFF tag walker that's only useful for input
   files already encoded as single-strip T4/T6 TIFFs. Callers needing
   that case should decode the TIFF themselves and feed the resulting
   ``"1"`` PIL image into :meth:`CCITTFactory.create_from_image`. See
   ``CHANGES.md`` for the deviation note.
"""
from __future__ import annotations

import io
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

        decode_params = COSDictionary()
        decode_params.set_int("K", -1)
        decode_params.set_int("Columns", int(width))
        decode_params.set_int("Rows", int(height))

        # Wrap in a one-element stream dict so CCITTFaxDecode.encode
        # resolves /DecodeParms the same way the decoder does.
        stream_shell = COSDictionary()
        stream_shell.set_item(_DECODE_PARMS, decode_params)

        enc_buf = io.BytesIO()
        CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, stream_shell)
        encoded = enc_buf.getvalue()

        cos_doc = document.get_document()
        stream = COSStream(cos_doc.scratch_file)
        stream.set_item(_TYPE, _XOBJECT)
        stream.set_item(_SUBTYPE, _IMAGE)
        stream.set_int(_WIDTH, int(width))
        stream.set_int(_HEIGHT, int(height))
        stream.set_int(_BITS_PER_COMPONENT, 1)
        stream.set_item(_COLORSPACE, _DEVICE_GRAY)
        stream.set_item(_FILTER, _CCITT_FAX_DECODE)
        stream.set_item(_DECODE_PARMS, decode_params)
        stream.set_int(_LENGTH, len(encoded))
        stream.set_raw_data(encoded)

        x_image = PDImageXObject(stream)
        x_image.set_color_space(PDDeviceGray.INSTANCE)
        return x_image


__all__ = ["CCITTFactory"]
