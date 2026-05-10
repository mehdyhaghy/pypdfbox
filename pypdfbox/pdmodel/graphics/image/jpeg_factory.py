"""Factory for ``/DCTDecode`` Image XObjects.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory``: a
static-method utility class that wraps already-encoded JPEG bytes (or a
PIL image to be encoded) into a :class:`PDImageXObject` with
``/Filter /DCTDecode``, the raw bytes preserved verbatim, and ``/Width``
``/Height`` ``/BitsPerComponent`` ``/ColorSpace`` filled in from the
JPEG header.

Library-first: PIL/Pillow is already required by the rendering stack,
so we sniff JPEG metadata via ``PIL.Image.open`` rather than walking
SOF markers ourselves. ``Image.open`` is lazy -- it parses the header
without decoding the pixel raster -- so it stays competitive with
upstream's ``ImageReader.getWidth/getHeight`` path. The number of
components is read from PIL's ``mode`` (``L`` -> 1, ``RGB`` -> 3,
``CMYK`` -> 4, ``YCbCr`` -> 3) which mirrors what the upstream reader
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

    1 -> ``/DeviceGray``, 3 -> ``/DeviceRGB``, 4 -> ``/DeviceCMYK``.
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


def _split_alpha_for_smask(image: Image.Image) -> tuple[Image.Image, Image.Image | None]:
    """Return ``(color_image, alpha_mask)`` for JPEG soft-mask encoding."""
    if image.mode == "RGBA":
        return image.convert("RGB"), image.getchannel("A")
    if image.mode == "LA":
        return image.getchannel("L"), image.getchannel("A")
    if image.mode == "PA":
        rgba = image.convert("RGBA")
        return rgba.convert("RGB"), rgba.getchannel("A")
    if image.mode == "P" and "transparency" in image.info:
        rgba = image.convert("RGBA")
        return rgba.convert("RGB"), rgba.getchannel("A")
    return image, None


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
    final class with a private constructor and three public static
    factories (``create_from_stream``, ``create_from_byte_array``,
    ``create_from_image``) plus eight package-private helpers that
    upstream keeps as ``static`` methods on the class. Python doesn't
    enforce "final" + "private constructor" the same way, so we expose
    the methods as ``@staticmethod`` and forbid instantiation by
    raising in ``__init__``.
    """

    def __init__(self) -> None:  # pragma: no cover - intentionally unreachable
        raise TypeError("JPEGFactory is a static-method utility class")

    # ---------------------------------------------------------------
    # Public factories (upstream lines 81-279)
    # ---------------------------------------------------------------

    @staticmethod
    def create_from_stream(
        document: PDDocument | None,
        stream: BinaryIO | bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Wrap a JPEG stream into a ``PDImageXObject``.

        Reads ``stream`` to EOF and forwards to
        :meth:`create_from_byte_array`. Mirrors upstream
        ``JPEGFactory.createFromStream(PDDocument, InputStream)``
        (JPEGFactory.java:81-85) which reads the stream via
        ``IOUtils.toByteArray`` then delegates.
        """
        if isinstance(stream, (bytes, bytearray, memoryview)):
            data = bytes(stream)
        else:
            data = stream.read()
        return JPEGFactory.create_from_byte_array(document, data)

    @staticmethod
    def create_from_byte_array(
        document: PDDocument | None,
        byte_array: bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Wrap raw JPEG bytes into a ``PDImageXObject``.

        Mirrors upstream
        ``JPEGFactory.createFromByteArray(PDDocument, byte[])``
        (JPEGFactory.java:96-140). ``document`` is accepted for
        upstream signature parity but is unused here -- pypdfbox stores
        image streams in their own ``COSStream`` and the document only
        takes ownership when the XObject is added to a page's
        resources, which the caller does separately.
        """
        del document  # kept for API parity; see docstring
        if not isinstance(byte_array, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"byte_array must be bytes-like, got {type(byte_array).__name__}"
            )
        jpeg_bytes = bytes(byte_array)
        width, height, num_components = JPEGFactory.retrieve_dimensions(jpeg_bytes)
        return _build_image_xobject(jpeg_bytes, width, height, num_components)

    @staticmethod
    def create_from_image(
        document: PDDocument | None,
        image: Image.Image,
        quality: float = 0.75,
        dpi: int = 72,
    ) -> PDImageXObject:
        """Encode ``image`` as a JPEG and wrap it as a ``PDImageXObject``.

        Mirrors the three upstream overloads
        ``createFromImage(PDDocument, BufferedImage)``,
        ``createFromImage(PDDocument, BufferedImage, float)``, and
        ``createFromImage(PDDocument, BufferedImage, float, int)``
        (JPEGFactory.java:230-279). Upstream chains the overloads;
        Python's default arguments collapse them into a single method.

        The image is split into a color JPEG plus a grayscale JPEG
        ``/SMask`` when it carries an alpha channel. Modes ``L``,
        ``RGB``, and ``CMYK`` are encoded directly.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )
        return JPEGFactory.create_jpeg(document, image, quality, dpi)

    # ---------------------------------------------------------------
    # Helpers ported from upstream package-private statics.
    # ---------------------------------------------------------------

    @staticmethod
    def retrieve_dimensions(
        stream: bytes | bytearray | memoryview | BinaryIO,
    ) -> tuple[int, int, int]:
        """Sniff ``(width, height, num_components)`` from JPEG header bytes.

        Mirrors upstream ``retrieveDimensions(ByteArrayInputStream)``
        (JPEGFactory.java:149-186). Upstream first asks the JAI
        ``ImageReader`` for ``getWidth(0)``/``getHeight(0)``, then
        prefers the SOF metadata path (``getNumComponentsFromImageMetadata``)
        and falls back to decoding the raster when the metadata tree
        is missing. PIL's lazy ``Image.open`` performs the equivalent
        header sniff without decoding, so the metadata + raster
        fallback collapse into one fast path.
        """
        if isinstance(stream, (bytes, bytearray, memoryview)):
            jpeg_bytes = bytes(stream)
        else:
            jpeg_bytes = stream.read()
        try:
            probe = Image.open(io.BytesIO(jpeg_bytes))
        except UnidentifiedImageError as exc:
            raise ValueError("expected JPEG image, got unreadable image data") from exc

        with probe:
            if probe.format != "JPEG":
                raise ValueError(
                    f"expected JPEG image, got {probe.format!r}"
                )
            width, height = probe.size
            # Prefer the metadata path (SOF numFrameComponents), mirroring
            # upstream PDFBOX-4691.
            num_components = JPEGFactory.get_num_components_from_image_metadata(probe)
            if num_components == 0:
                num_components = _pil_mode_to_components(probe.mode)
            if num_components == 0:
                # Final fallback -- count PIL's reported bands. Upstream's
                # equivalent is ``raster.getNumDataElements()``.
                num_components = len(probe.getbands())
        return int(width), int(height), int(num_components)

    @staticmethod
    def get_num_components_from_image_metadata(reader: Image.Image) -> int:
        """Read ``numFrameComponents`` from JPEG SOF metadata.

        Mirrors upstream
        ``getNumComponentsFromImageMetadata(ImageReader)``
        (JPEGFactory.java:188-216). Upstream walks the
        ``javax_imageio_jpeg_image_1.0`` metadata tree with XPath;
        Pillow exposes the same value indirectly through
        :attr:`Image.mode`, which is what its JPEG decoder sets after
        reading the SOF marker. Returns ``0`` when no answer is
        available so the caller can fall back, matching upstream's
        contract.
        """
        try:
            return _pil_mode_to_components(reader.mode)
        except (AttributeError, ValueError):
            return 0

    @staticmethod
    def get_alpha_image(image: Image.Image) -> Image.Image | None:
        """Return the alpha channel of ``image`` or ``None`` if opaque.

        Mirrors upstream ``getAlphaImage(BufferedImage)``
        (JPEGFactory.java:282-303). Upstream raises
        ``UnsupportedOperationException`` for ``BITMASK`` transparency
        because a 1-bit alpha shouldn't be JPEG-compressed; PIL's
        equivalent is ``mode == "1"`` paired with the ``transparency``
        info entry, which we reject the same way.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )
        if image.mode == "1" and "transparency" in image.info:
            raise NotImplementedError(
                "BITMASK Transparency JPEG compression is not useful, "
                "use LosslessFactory instead"
            )
        if image.mode == "RGBA":
            return image.getchannel("A")
        if image.mode == "LA":
            return image.getchannel("A")
        if image.mode == "PA":
            return image.convert("RGBA").getchannel("A")
        if image.mode == "P" and "transparency" in image.info:
            return image.convert("RGBA").getchannel("A")
        return None

    @staticmethod
    def get_color_image(image: Image.Image) -> Image.Image:
        """Return the color channels of ``image`` (alpha stripped).

        Mirrors upstream ``getColorImage(BufferedImage)``
        (JPEGFactory.java:421-443). Upstream short-circuits when there
        is no alpha and converts RGBA to ``TYPE_3BYTE_BGR`` via
        ``ColorConvertOp``. PIL's ``Image.convert("RGB")`` is the
        direct analogue.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )
        if image.mode in ("L", "RGB", "CMYK", "YCbCr"):
            return image
        if image.mode == "RGBA":
            return image.convert("RGB")
        if image.mode == "LA":
            return image.getchannel("L")
        if image.mode == "PA":
            return image.convert("RGBA").convert("RGB")
        if image.mode == "P":
            if "transparency" in image.info:
                return image.convert("RGBA").convert("RGB")
            return image.convert("RGB")
        if image.mode == "1":
            return image.convert("L")
        # Upstream raises ``UnsupportedOperationException`` when the
        # source colour space isn't RGB; the closest Python contract is
        # ``NotImplementedError`` for "I haven't ported this branch".
        # Anything else gets a best-effort conversion to RGB.
        return image.convert("RGB")

    @staticmethod
    def get_color_space_from_awt(image: Image.Image) -> PDColorSpace:
        """Map a PIL image's mode/color space to a ``PDColorSpace``.

        Mirrors upstream ``getColorSpaceFromAWT(BufferedImage)``
        (JPEGFactory.java:392-418). The Pillow equivalent of
        ``ColorSpace.getType()`` is :attr:`Image.mode`, so we dispatch
        on that: ``L`` -> ``PDDeviceGray``, ``RGB``/``YCbCr`` ->
        ``PDDeviceRGB``, ``CMYK`` -> ``PDDeviceCMYK``. Anything else
        raises ``NotImplementedError`` matching upstream's
        ``UnsupportedOperationException("color space not implemented")``.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )
        mode = image.mode
        if mode == "L":
            return PDDeviceGray.INSTANCE
        if mode in ("RGB", "YCbCr"):
            return PDDeviceRGB.INSTANCE
        if mode == "CMYK":
            return PDDeviceCMYK.INSTANCE
        raise NotImplementedError(f"color space not implemented: {mode!r}")

    @staticmethod
    def get_jpeg_image_writer() -> object:
        """Return a JPEG encoder handle (always non-null).

        Mirrors upstream ``getJPEGImageWriter()``
        (JPEGFactory.java:332-350). Upstream walks
        ``ImageIO.getImageWritersBySuffix("jpeg")`` skipping the
        CLibJPEGImageWriter regression (PDFBOX-3566). pypdfbox uses
        Pillow's bundled JPEG encoder, which is a single global, so
        we return the ``PIL.Image`` module itself as a stable handle.
        Callers should treat the return value as opaque -- the
        contract is "non-null encoder", not a specific type.
        """
        return Image

    @staticmethod
    def encode_image_to_jpeg_stream(
        image: Image.Image,
        quality: float,
        dpi: int,
    ) -> bytes:
        """Encode ``image`` to a JPEG byte stream.

        Mirrors upstream ``encodeImageToJPEGStream(BufferedImage,
        float, int)`` (JPEGFactory.java:352-389). Upstream programs
        ``ImageWriteParam`` (mode + quality) and pokes the JFIF
        ``Xdensity``/``Ydensity``/``resUnits`` attributes via the
        metadata tree. Pillow exposes the same JFIF density via the
        ``dpi=(x, y)`` save kwarg. PIL's quality scale is ``[1, 95]``
        while upstream's is ``[0.0, 1.0]``, so we rescale.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )
        # Make sure the encoder handle is reachable; upstream raises
        # IOException("No ImageWriter found") if it isn't.
        JPEGFactory.get_jpeg_image_writer()

        q = max(0.0, min(1.0, float(quality)))
        pil_quality = max(1, min(95, int(round(q * 95.0))))

        buffer = io.BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=pil_quality,
            dpi=(int(dpi), int(dpi)),
        )
        return buffer.getvalue()

    @staticmethod
    def create_jpeg(
        document: PDDocument | None,
        image: Image.Image,
        quality: float,
        dpi: int,
    ) -> PDImageXObject:
        """Create a JPEG-encoded ``PDImageXObject`` from a PIL image.

        Mirrors upstream ``createJPEG(PDDocument, BufferedImage, float,
        int)`` (JPEGFactory.java:306-329) -- the private workhorse
        called by every ``createFromImage`` overload. Splits ``image``
        into colour + alpha, encodes the colour band via
        :meth:`encode_image_to_jpeg_stream`, builds the
        ``PDImageXObject``, and recursively encodes any alpha band as
        the soft mask.
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )

        # Match upstream's split: alpha goes to /SMask, colour goes to
        # the /DCTDecode body.
        awt_color_image = JPEGFactory.get_color_image(image)
        awt_alpha_image = JPEGFactory.get_alpha_image(image)

        encoded = JPEGFactory.encode_image_to_jpeg_stream(
            awt_color_image, quality, dpi
        )
        # Re-sniff dimensions from the encoded bytes -- upstream's
        # round-trip equally trusts the encoded SOF as the source of
        # truth.
        width, height, num_components = JPEGFactory.retrieve_dimensions(encoded)
        # Upstream's PDImageXObject constructor takes the colour space
        # explicitly; in pypdfbox we set it on the wrapper after build.
        ximage = _build_image_xobject(encoded, width, height, num_components)
        # Honour upstream's getColorSpaceFromAWT mapping when the
        # original image carries an explicit mode (e.g. ``CMYK``) that
        # would otherwise be deduced from band count alone.
        ximage.set_color_space(JPEGFactory.get_color_space_from_awt(awt_color_image))

        if awt_alpha_image is not None:
            ximage.set_soft_mask(
                JPEGFactory.create_from_image(
                    document, awt_alpha_image, quality, dpi
                )
            )
        return ximage

    # ---------------------------------------------------------------
    # Upstream Java-style aliases. Kept exclusively so the wave-350
    # alias regression test continues to pass; new code must call the
    # snake_case methods above.
    # ---------------------------------------------------------------

    @staticmethod
    def createFromByteArray(  # noqa: N802 - upstream Java alias
        document: PDDocument | None,
        byte_array: bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Java-style alias for :meth:`create_from_byte_array`."""
        return JPEGFactory.create_from_byte_array(document, byte_array)

    @staticmethod
    def createFromStream(  # noqa: N802 - upstream Java alias
        document: PDDocument | None,
        stream: BinaryIO | bytes | bytearray | memoryview,
    ) -> PDImageXObject:
        """Java-style alias for :meth:`create_from_stream`."""
        return JPEGFactory.create_from_stream(document, stream)

    @staticmethod
    def createFromImage(  # noqa: N802 - upstream Java alias
        document: PDDocument | None,
        image: Image.Image,
        quality: float = 0.75,
        dpi: int = 72,
    ) -> PDImageXObject:
        """Java-style alias for :meth:`create_from_image`."""
        return JPEGFactory.create_from_image(document, image, quality, dpi)


# Module-level back-compat alias for prior-wave tests that imported the
# pre-class-method form of the dimensions sniffer.
_retrieve_dimensions = JPEGFactory.retrieve_dimensions


__all__ = ["JPEGFactory"]
