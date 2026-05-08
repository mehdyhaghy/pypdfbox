"""Factory for ``/DCTDecode`` Image XObjects.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory``: a
static-method utility class that wraps already-encoded JPEG bytes (or a
PIL image to be encoded) into a :class:`PDImageXObject` with
``/Filter /DCTDecode``, the raw bytes preserved verbatim, and ``/Width``
``/Height`` ``/BitsPerComponent`` ``/ColorSpace`` filled in from the
JPEG header.

Library-first: PIL/Pillow is already required by the rendering stack,
so we sniff JPEG metadata via ``PIL.Image.open`` rather than walking
SOF markers ourselves. ``Image.open`` is lazy — it parses the header
without decoding the pixel raster — so it stays competitive with
upstream's ``ImageReader.getWidth/getHeight`` path. The number of
components is read from PIL's ``mode`` (``L`` → 1, ``RGB`` → 3,
``CMYK`` → 4, ``YCbCr`` → 3) which mirrors what the upstream reader
extracts from the SOF ``numFrameComponents`` attribute.
"""
from __future__ import annotations

import io
from typing import TYPE_CHECKING, BinaryIO

from PIL import Image, UnidentifiedImageError

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.color import (
    PDColorSpace,
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_DCT_DECODE: COSName = COSName.get_pdf_name("DCTDecode")
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_XOBJECT: COSName = COSName.get_pdf_name("XObject")
_IMAGE: COSName = COSName.get_pdf_name("Image")


def _color_space_for_components(num_components: int) -> PDColorSpace:
    """Return the PDF color space for ``num_components`` JPEG channels.

    1 → ``/DeviceGray``, 3 → ``/DeviceRGB``, 4 → ``/DeviceCMYK``.
    Anything else raises ``ValueError`` to mirror upstream's
    ``UnsupportedOperationException`` ("number of data elements not
    supported"). ``ValueError`` is the closest Python analogue for
    "argument out of supported range".
    """
    if num_components == 1:
        return PDDeviceGray.INSTANCE
    if num_components == 3:
        return PDDeviceRGB.INSTANCE
    if num_components == 4:
        return PDDeviceCMYK.INSTANCE
    raise ValueError(
        f"number of data elements not supported: {num_components}"
    )


def _pil_mode_to_components(mode: str) -> int:
    """Map a PIL JPEG ``mode`` string to a JPEG channel count.

    PIL exposes ``L`` (1), ``RGB`` (3), ``YCbCr`` (3), ``CMYK`` (4),
    and ``LAB`` (3). ``YCbCr`` is treated as a 3-channel image because
    JPEG stores YCbCr as a 3-component frame even though PDF will
    expose it under ``/DeviceRGB``. Unknown modes return ``0`` so the
    caller can decide whether to error out.
    """
    if mode == "L":
        return 1
    if mode in ("RGB", "YCbCr", "LAB"):
        return 3
    if mode == "CMYK":
        return 4
    return 0


def _retrieve_dimensions(jpeg_bytes: bytes) -> tuple[int, int, int]:
    """Sniff ``(width, height, num_components)`` from JPEG header bytes.

    Mirrors upstream ``JPEGFactory.retrieveDimensions``. PIL's lazy
    ``Image.open`` reads only the JFIF/EXIF header markers and the SOF
    frame, so this stays O(header) regardless of pixel count.
    """
    try:
        probe = Image.open(io.BytesIO(jpeg_bytes))
    except UnidentifiedImageError as exc:
        raise ValueError("expected JPEG image, got unreadable image data") from exc

    with probe:
        # ``Image.open`` is lazy. Touch the format so PIL surfaces a bad
        # header up front rather than later in the pipeline.
        if probe.format != "JPEG":
            raise ValueError(
                f"expected JPEG image, got {probe.format!r}"
            )
        width, height = probe.size
        num_components = _pil_mode_to_components(probe.mode)
        if num_components == 0:
            # Fall back to the channel count PIL reports via ``getbands``.
            num_components = len(probe.getbands())
    return int(width), int(height), int(num_components)


def _build_image_xobject(
    jpeg_bytes: bytes,
    width: int,
    height: int,
    num_components: int,
) -> PDImageXObject:
    """Construct a ``PDImageXObject`` carrying ``jpeg_bytes`` verbatim."""
    color_space = _color_space_for_components(num_components)

    cos = COSStream()
    cos.set_raw_data(jpeg_bytes)
    # /Type and /Subtype mirror PDFBox's PDImageXObject(...) constructor
    # which wires both entries before returning. /Subtype is the entry
    # the parser dispatches on; /Type is informational but expected by
    # most validators.
    cos.set_item(_TYPE, _XOBJECT)
    cos.set_item(_SUBTYPE, _IMAGE)
    cos.set_item(_FILTER, _DCT_DECODE)

    image = PDImageXObject(cos)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(8)
    image.set_color_space(color_space)

    if isinstance(color_space, PDDeviceCMYK):
        # Upstream inverts the decode array for CMYK JPEGs because
        # JPEG-stored CMYK uses the Adobe inversion convention (255 =
        # ink-off) while PDF /DeviceCMYK assumes 0 = ink-off. The
        # ``[1 0 1 0 1 0 1 0]`` decode array mirrors upstream's
        # ``pdImage.setDecode(decode)`` line.
        image.set_decode([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

    return image


class JPEGFactory:
    """Factory for ``/DCTDecode`` Image XObjects.

    Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory``: a
    final class with a private constructor and three static factories.
    Python doesn't enforce "final" + "private constructor" the same
    way, so we expose the methods as ``@staticmethod`` and forbid
    instantiation by raising in ``__init__``.
    """

    def __init__(self) -> None:  # pragma: no cover - intentionally unreachable
        raise TypeError("JPEGFactory is a static-method utility class")

    @staticmethod
    def create_from_byte_array(
        document: PDDocument | None,
        byte_array: bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Wrap raw JPEG bytes into a ``PDImageXObject``.

        ``document`` is accepted for upstream signature parity but is
        unused here — pypdfbox stores image streams in their own
        ``COSStream`` and the document only takes ownership when the
        XObject is added to a page's resources, which the caller does
        separately. Mirrors upstream
        ``JPEGFactory.createFromByteArray(PDDocument, byte[])``.
        """
        del document  # kept for API parity; see docstring
        if not isinstance(byte_array, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"byte_array must be bytes-like, got {type(byte_array).__name__}"
            )
        jpeg_bytes = bytes(byte_array)
        width, height, num_components = _retrieve_dimensions(jpeg_bytes)
        return _build_image_xobject(jpeg_bytes, width, height, num_components)

    @staticmethod
    def create_from_stream(
        document: PDDocument | None,
        stream: BinaryIO | bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Wrap a JPEG stream into a ``PDImageXObject``.

        Reads ``stream`` to EOF and forwards to
        :meth:`create_from_byte_array`. Mirrors upstream
        ``JPEGFactory.createFromStream(PDDocument, InputStream)`` which
        reads the stream via ``IOUtils.toByteArray`` then delegates.
        """
        if isinstance(stream, (bytes, bytearray, memoryview)):
            data = bytes(stream)
        else:
            data = stream.read()
        return JPEGFactory.create_from_byte_array(document, data)

    @staticmethod
    def create_from_image(
        document: PDDocument | None,
        image: Image.Image,
        quality: float = 0.75,
        dpi: int = 72,
    ) -> PDImageXObject:
        """Encode ``image`` as a JPEG and wrap it as a ``PDImageXObject``.

        ``quality`` is in ``[0.0, 1.0]`` matching upstream's
        ``setCompressionQuality`` convention; PIL's ``quality`` argument
        runs ``[1, 95]`` so we rescale. ``dpi`` is recorded in the JFIF
        header for round-trip parity with upstream.

        The image is flattened to ``RGB`` when it carries an alpha
        channel — JPEG cannot represent alpha. Upstream extracts the
        alpha as a soft mask via a second JPEG XObject; we currently
        drop alpha (a TODO mirrored in CHANGES.md describes the
        soft-mask follow-up). Modes ``L``, ``RGB``, and ``CMYK`` are
        encoded directly.
        """
        del document  # kept for API parity; see create_from_byte_array
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )

        # Flatten alpha — JPEG cannot carry an alpha channel. Upstream
        # extracts /SMask separately; that path is deferred (see
        # CHANGES.md "JPEGFactory soft-mask").
        if image.mode in ("RGBA", "LA", "PA"):
            image = image.convert("RGB" if image.mode == "RGBA" else "L")
        elif image.mode == "P":
            image = image.convert("RGB")
        elif image.mode == "1":
            image = image.convert("L")
        elif image.mode in ("L", "RGB", "CMYK"):
            pass
        else:
            image = image.convert("RGB")

        # PIL's quality is 1..95; upstream's is 0.0..1.0. Map linearly
        # and clamp. Quality 0.0 still yields the lowest non-degenerate
        # PIL setting (1) — a true 0 would refuse to encode.
        q = max(0.0, min(1.0, float(quality)))
        pil_quality = max(1, min(95, int(round(q * 95.0))))

        buffer = io.BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=pil_quality,
            dpi=(int(dpi), int(dpi)),
        )
        jpeg_bytes = buffer.getvalue()

        # Re-sniff dimensions from the encoded bytes rather than the
        # source image — upstream's roundtrip equally relies on the
        # encoded SOF as the source of truth.
        width, height, num_components = _retrieve_dimensions(jpeg_bytes)
        return _build_image_xobject(jpeg_bytes, width, height, num_components)


__all__ = ["JPEGFactory"]
