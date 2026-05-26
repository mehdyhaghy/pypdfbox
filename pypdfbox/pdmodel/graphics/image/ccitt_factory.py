"""Factory for ``/CCITTFaxDecode`` Image XObjects.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.CCITTFactory``: a
final class with a private constructor and three public static
factories. Upstream supports two production paths:

1. ``createFromImage(PDDocument, BufferedImage)`` -- encode a 1-bit
   ``BufferedImage`` raster as CCITT Group 4. We port this path here,
   substituting Pillow's ``"1"`` mode for the AWT
   ``TYPE_BYTE_BINARY``/pixel-size-1 dispatch.

2. ``createFromFile`` / ``createFromByteArray`` -- extract an existing
   single-strip CCITT T.4/T.6 TIFF payload and re-wrap it without
   recompression. Multi-page TIFFs are addressed by a zero-based
   ``number`` argument (returns ``None`` past end-of-IFD chain).

The TIFF parser follows upstream's byte-by-byte IFD walk in
``CCITTFactory.extractFromTiff`` so we honour:

* both endiannesses ("II" little-endian and "MM" big-endian);
* byte/short tag values padded with garbage in the remaining bytes;
* ``FillOrder=2`` (LSB-first) bit reversal via the upstream
  ``fliptable``;
* multi-page navigation through the next-IFD-offset chain.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.filter import CCITTFaxDecode
from pypdfbox.pdmodel.graphics.color import PDColorSpace, PDDeviceGray
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


# Bit-reversal table for FillOrder=2 (LSB-first) TIFFs. Identical to
# upstream's ``CCITTFactory.fliptable``.
_FLIP_TABLE: bytes = bytes(int(f"{b:08b}"[::-1], 2) for b in range(256))


def read_short(endianness: str, reader: BinaryIO) -> int:
    """Read an unsigned 16-bit value honouring TIFF endianness.

    Mirrors upstream ``CCITTFactory.readshort(char, RandomAccessRead)``
    (line 470). ``endianness`` is ``"I"`` (little) or ``"M"`` (big).
    """
    b0 = reader.read(1)
    b1 = reader.read(1)
    if not b0 or not b1:
        raise OSError("Not a valid tiff file")
    lo = b0[0]
    hi = b1[0]
    if endianness == "I":
        return lo | (hi << 8)
    return (lo << 8) | hi


def read_long(endianness: str, reader: BinaryIO) -> int:
    """Read an unsigned 32-bit value honouring TIFF endianness.

    Mirrors upstream ``CCITTFactory.readlong(char, RandomAccessRead)``
    (line 479).
    """
    chunk = reader.read(4)
    if len(chunk) != 4:
        raise OSError("Not a valid tiff file")
    b0, b1, b2, b3 = chunk[0], chunk[1], chunk[2], chunk[3]
    if endianness == "I":
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
    return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3


def extract_from_tiff(
    reader: BinaryIO,
    out_stream: BinaryIO,
    params: COSDictionary,
    number: int,
) -> None:
    """Extract the CCITT-fax strip for image ``number`` into ``out_stream``.

    Mirrors upstream ``CCITTFactory.extractFromTiff`` (line 235). Walks
    the TIFF header, advances ``number`` IFDs through the next-IFD-offset
    chain, harvests the few CCITT-relevant tags (256/257/259/262/266/
    273/274/279/292/324/325) into ``params``, then copies the strip into
    ``out_stream``. ``out_stream`` is left empty when the requested IFD
    is past the end of the chain (caller checks size).

    :raises OSError: on malformed TIFF data or unsupported tag values
        (matches upstream's ``IOException``).
    """
    reader.seek(0)
    head = reader.read(2)
    if len(head) != 2:
        raise OSError("Not a valid tiff file")
    endianness = chr(head[0])
    if chr(head[1]) != endianness:
        raise OSError("Not a valid tiff file")
    if endianness not in ("M", "I"):
        raise OSError("Not a valid tiff file")

    magic_number = read_short(endianness, reader)
    if magic_number != 42:
        raise OSError("Not a valid tiff file")

    address = read_long(endianness, reader)
    reader.seek(address)

    # Skip ``number`` IFDs by following the next-IFD-offset chain.
    for _ in range(number):
        numtags = read_short(endianness, reader)
        if numtags > 50:
            raise OSError("Not a valid tiff file")
        reader.seek(address + 2 + numtags * 12)
        address = read_long(endianness, reader)
        if address == 0:
            return
        reader.seek(address)

    numtags = read_short(endianness, reader)
    # The number 50 is somewhat arbitrary; it just stops us loading up junk
    # from somewhere and tramping on. Mirrors upstream comment.
    if numtags > 50:
        raise OSError("Not a valid tiff file")

    # Default value to detect error.
    k = -1000
    dataoffset = 0
    datalength = 0
    fillorder = 1

    for _ in range(numtags):
        tag = read_short(endianness, reader)
        type_ = read_short(endianness, reader)
        count = read_long(endianness, reader)
        # Note that when the type is shorter than 4 bytes, the rest can
        # be garbage and must be ignored.
        if type_ == 1:  # byte value
            byte = reader.read(1)
            if not byte:
                raise OSError("Not a valid tiff file")
            val = byte[0]
            reader.read(3)  # discard padding
        elif type_ == 3:  # short value
            val = read_short(endianness, reader)
            reader.read(2)  # discard padding
        else:  # long and other types
            val = read_long(endianness, reader)

        if tag == 256:
            params.set_int("Columns", val)
        elif tag == 257:
            params.set_int("Rows", val)
        elif tag == 259:
            # T6/T4 Compression
            if val == 4:
                k = -1
            elif val == 3:
                k = 0
        elif tag == 262:
            if val == 1:
                params.set_boolean("BlackIs1", True)
        elif tag == 266:
            # http://www.awaresystems.be/imaging/tiff/tifftags/fillorder.html
            if val not in (1, 2):
                raise OSError(f"FillOrder {val} is not supported")
            fillorder = val
        elif tag == 273:
            if count == 1:
                dataoffset = val
        elif tag == 274:
            # http://www.awaresystems.be/imaging/tiff/tifftags/orientation.html
            if val != 1:
                raise OSError(f"Orientation {val} is not supported")
        elif tag == 279:
            if count == 1:
                datalength = val
        elif tag == 292:
            if (val & 1) != 0:
                # T4 2D - arbitrary positive K value
                k = 50
            # http://www.awaresystems.be/imaging/tiff/tifftags/t4options.html
            if (val & 4) != 0:
                raise OSError("CCITT Group 3 'uncompressed mode' is not supported")
            if (val & 2) != 0:
                raise OSError(
                    "CCITT Group 3 'fill bits before EOL' is not supported"
                )
        elif tag == 324:  # noqa: SIM102 - mirrors upstream switch/if structure
            if count == 1:
                dataoffset = val
        elif tag == 325:  # noqa: SIM102 - mirrors upstream switch/if structure
            if count == 1:
                datalength = val
        # else: do nothing (unknown tag)

    if k == -1000:
        raise OSError("First image in tiff is not CCITT T4 or T6 compressed")
    if dataoffset == 0:
        raise OSError("First image in tiff is not a single tile/strip")

    params.set_int("K", k)

    reader.seek(dataoffset)
    remaining = datalength
    while remaining > 0:
        chunk = reader.read(min(8192, remaining))
        if not chunk:
            break
        if fillorder == 2:
            chunk = chunk.translate(_FLIP_TABLE)
        out_stream.write(chunk)
        remaining -= len(chunk)


def prepare_image_x_object(
    document: PDDocument,
    byte_array: bytes,
    width: int,
    height: int,
    init_color_space: PDColorSpace,
) -> PDImageXObject:
    """Encode raw 1-bit packed bytes as CCITT Group 4 and wrap into an
    :class:`PDImageXObject`.

    Mirrors upstream ``CCITTFactory.prepareImageXObject`` (line 137):
    runs the raw bitstream through ``FilterFactory.getFilter(CCITTFaxDecode).encode``
    using a ``/DecodeParms`` carrying ``/Columns`` and ``/Rows``, then
    stamps ``/K -1`` (Group 4) on the wrapped XObject's ``/DecodeParms``.
    """
    decode_params = COSDictionary()
    decode_params.set_int("Columns", int(width))
    decode_params.set_int("Rows", int(height))

    stream_shell = COSDictionary()
    stream_shell.set_item(_DECODE_PARMS, decode_params)

    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(byte_array), enc_buf, stream_shell)
    encoded = enc_buf.getvalue()

    # Upstream stamps K=-1 on the dict *after* encode.
    decode_params.set_int("K", -1)

    return _build_image_xobject(
        document, encoded, int(width), int(height), decode_params, init_color_space
    )


def _build_image_xobject(
    document: PDDocument,
    encoded: bytes,
    columns: int,
    rows: int,
    decode_params: COSDictionary,
    color_space: PDColorSpace = PDDeviceGray.INSTANCE,
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
    x_image.set_color_space(color_space)
    return x_image


def create_from_random_access_impl(
    document: PDDocument,
    reader: BinaryIO,
    number: int,
) -> PDImageXObject | None:
    """Build an Image XObject by extracting image ``number`` from the
    TIFF data ``reader`` exposes.

    Mirrors upstream ``CCITTFactory.createFromRandomAccessImpl``
    (line 209). Returns ``None`` when the requested IFD is past the end
    of the TIFF's IFD chain.
    """
    decode_params = COSDictionary()
    bos = io.BytesIO()
    extract_from_tiff(reader, bos, decode_params, number)
    if bos.tell() == 0:
        return None
    encoded = bos.getvalue()
    columns = decode_params.get_int("Columns", 0)
    rows = decode_params.get_int("Rows", 0)
    return _build_image_xobject(
        document, encoded, columns, rows, decode_params, PDDeviceGray.INSTANCE
    )


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
        ``CCITTFactory.createFromImage(PDDocument, BufferedImage)``
        (line 60). Pillow's ``"1"`` mode already packs rows MSB-first to
        byte boundaries (the ISO 32000-1 §8.9.5.1 convention) so we hand
        the raster straight to :func:`prepare_image_x_object`.

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
        # via ``writeBits(~rgb & 1)`` so the Group 4 stream encodes black as
        # the foreground run. ``prepare_image_x_object`` carries no
        # /BlackIs1, so ``CCITTFaxDecode.encode`` takes its default
        # (BlackIs0) branch and performs the equivalent inversion before
        # handing the raster to libtiff -- the resulting stream is
        # byte-identical to upstream ``CCITTFactory`` and decodes back to
        # this raster. We therefore pass PIL's ``tobytes()`` unchanged.
        raw = image.tobytes()

        return prepare_image_x_object(
            document, raw, int(width), int(height), PDDeviceGray.INSTANCE
        )

    @staticmethod
    def create_from_byte_array(
        document: PDDocument,
        byte_array: bytes | bytearray | memoryview,
        number: int = 0,
    ) -> PDImageXObject | None:
        """Extract image ``number`` (0-based) from a TIFF in memory.

        Mirrors upstream ``CCITTFactory.createFromByteArray`` (lines 107
        and 128). Returns ``None`` if ``number`` is past the end of the
        TIFF's IFD chain.
        """
        if not isinstance(byte_array, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"byte_array must be bytes-like, got {type(byte_array).__name__}"
            )
        tiff_bytes = bytes(byte_array)
        return create_from_random_access_impl(
            document, io.BytesIO(tiff_bytes), int(number)
        )

    @staticmethod
    def create_from_file(
        document: PDDocument,
        path: str | Path,
        number: int = 0,
    ) -> PDImageXObject | None:
        """Read ``path`` and extract image ``number`` from the TIFF.

        Mirrors upstream ``CCITTFactory.createFromFile`` (lines 170 and
        190). The file is fully read into memory then released, so
        callers may delete the file immediately after the call returns
        (see upstream ``testCreateFromFileLock``).
        """
        return CCITTFactory.create_from_byte_array(
            document, Path(path).read_bytes(), int(number)
        )

    # ------------------------------------------------------------------
    # Private upstream helpers exposed as static methods for 1:1 parity
    # with ``CCITTFactory.java``. These mirror the Java private static
    # methods (which the parity scanner sees on the class surface);
    # they are not part of the public Python API but are kept available
    # so the class roster matches upstream method-for-method.
    # ------------------------------------------------------------------

    @staticmethod
    def prepare_image_x_object(
        document: PDDocument,
        byte_array: bytes,
        width: int,
        height: int,
        init_color_space: PDColorSpace,
    ) -> PDImageXObject:
        """Mirror of upstream ``CCITTFactory.prepareImageXObject`` (line 137).

        Delegates to the module-level :func:`prepare_image_x_object`.
        """
        return prepare_image_x_object(
            document, byte_array, width, height, init_color_space
        )

    @staticmethod
    def create_from_random_access_impl(
        document: PDDocument,
        reader: BinaryIO,
        number: int,
    ) -> PDImageXObject | None:
        """Mirror of upstream ``CCITTFactory.createFromRandomAccessImpl``
        (line 209). Delegates to the module-level
        :func:`create_from_random_access_impl`.
        """
        return create_from_random_access_impl(document, reader, number)

    @staticmethod
    def extract_from_tiff(
        reader: BinaryIO,
        out_stream: BinaryIO,
        params: COSDictionary,
        number: int,
    ) -> None:
        """Mirror of upstream ``CCITTFactory.extractFromTiff`` (line 235).

        Delegates to the module-level :func:`extract_from_tiff`.
        """
        extract_from_tiff(reader, out_stream, params, number)

    @staticmethod
    def readshort(endianness: str, reader: BinaryIO) -> int:
        """Mirror of upstream ``CCITTFactory.readshort`` (line 470).

        Upstream's Java name is the single token ``readshort`` (not
        ``readShort``), so the parity scanner's snake-case converter
        produces ``readshort`` -- we expose that exact spelling alongside
        the public :func:`read_short`.
        """
        return read_short(endianness, reader)

    @staticmethod
    def readlong(endianness: str, reader: BinaryIO) -> int:
        """Mirror of upstream ``CCITTFactory.readlong`` (line 479).

        Upstream's Java name is the single token ``readlong`` (not
        ``readLong``), matching :meth:`readshort` above.
        """
        return read_long(endianness, reader)


__all__ = [
    "CCITTFactory",
    "create_from_random_access_impl",
    "extract_from_tiff",
    "prepare_image_x_object",
    "read_long",
    "read_short",
]
