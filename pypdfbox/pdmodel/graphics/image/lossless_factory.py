from __future__ import annotations

import io
import zlib
from typing import TYPE_CHECKING

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.filter import CCITTFaxDecode

from .pd_image_x_object import PDImageXObject

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

# Spec keys used as image-XObject metadata. Defined locally rather than
# imported from ``pd_image_x_object`` because that module keeps them
# private; defining them here mirrors upstream's ``COSName.*`` literals.
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
_SMASK: COSName = COSName.get_pdf_name("SMask")
_DECODE_PARMS: COSName = COSName.get_pdf_name("DecodeParms")
_FLATE_DECODE: COSName = COSName.FLATE_DECODE  # type: ignore[attr-defined]
_CCITT_FAX_DECODE: COSName = COSName.get_pdf_name("CCITTFaxDecode")
_K: COSName = COSName.get_pdf_name("K")
_COLUMNS: COSName = COSName.get_pdf_name("Columns")
_ROWS: COSName = COSName.get_pdf_name("Rows")
_DEVICE_GRAY: COSName = COSName.get_pdf_name("DeviceGray")
_DEVICE_RGB: COSName = COSName.get_pdf_name("DeviceRGB")
_INDEXED: COSName = COSName.get_pdf_name("Indexed")

# Heuristic threshold: bitmaps with at least this many pixels go through
# CCITT G4 (typically halves stream size on real fax-style content).
# Below the threshold the per-stream overhead of /Filter switching plus
# the CCITT decode-params dict outweighs the modest compression win, so
# we stay on flate for tiny bitmaps. 64x64 = 4096 pixels = 512 bytes raw
# is the rough break-even on a sparse pattern.
_CCITT_PIXEL_THRESHOLD: int = 64 * 64


class LosslessFactory:
    """
    Factory for creating a :class:`PDImageXObject` containing a lossless
    compressed image. Mirrors upstream
    ``org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory``.

    Upstream is keyed on ``java.awt.image.BufferedImage`` and dispatches
    on Java image types (``TYPE_BYTE_GRAY``, ``TYPE_INT_ARGB`` …); the
    Python port is keyed on :class:`PIL.Image.Image` and dispatches on
    the PIL ``mode`` field (``"1"``, ``"L"``, ``"I;16"``, ``"RGB"``,
    ``"RGBA"``, ``"P"``, ``"PA"``).

    Behaviour parity with upstream:

    - 1-bit images (``mode == "1"``) → ``/DeviceGray`` with 1 BPC.
      Large bitmaps (≥ ``_CCITT_PIXEL_THRESHOLD`` pixels) use
      ``/CCITTFaxDecode`` Group 4 — the natural choice for fax-style
      monochrome content and what upstream's ``CCITTFactory`` produces.
      Smaller bitmaps stay on ``/FlateDecode`` of the packed bitstream
      (avoids the per-stream overhead of CCITT params for trivial
      images).
    - 8-bit grayscale (``mode == "L"``) → ``/DeviceGray`` 8 BPC.
    - 16-bit grayscale (``mode in ("I;16", "I;16L", "I;16B")``) →
      ``/DeviceGray`` 16 BPC.
    - RGB → ``/DeviceRGB`` 8 BPC.
    - RGBA → split alpha into a separate 8-bit ``/DeviceGray`` SMask
      :class:`PDImageXObject`, attach via ``/SMask``.
    - LA (grayscale + alpha) → 8-bit ``/DeviceGray`` with /SMask.
    - Indexed/palette (``mode == "P"``, ``"PA"``) →
      ``/Indexed [/DeviceRGB N <hex>]``. Palette transparency in
      ``info["transparency"]`` is folded into a 1-bit ``/SMask`` so the
      indexed channel itself stays opaque.

    Use :meth:`create_from_image`. The class is a static factory:
    upstream marks it ``final`` with a private constructor; we follow
    that shape — instantiation has no useful semantics.
    """

    def __init__(self) -> None:  # pragma: no cover - matches upstream private ctor
        raise TypeError("LosslessFactory is a static factory; do not instantiate")

    # ---------- public entry point ----------

    @staticmethod
    def create_from_image(
        document: PDDocument,
        image: Image.Image,
    ) -> PDImageXObject:
        """Create a new lossless-encoded image XObject from ``image``.

        Mirrors upstream
        ``LosslessFactory.createFromImage(PDDocument, BufferedImage)``.

        :param document: the document the image is being created in;
            its ``COSDocument.scratch_file`` is used for stream backing
            (matches upstream's per-document scratch-file lifecycle).
        :param image: the PIL image to embed. Any ``mode`` listed in
            this class's docstring is supported; other modes are
            converted via :meth:`PIL.Image.Image.convert` to a supported
            equivalent (typically ``"RGB"`` or ``"RGBA"``).
        :return: a fresh :class:`PDImageXObject` with ``/Filter
            /FlateDecode`` and the appropriate color space and SMask.
        :raises OSError: on flate-encoding failure (re-raised from
            :mod:`zlib`).
        """
        if not isinstance(image, Image.Image):
            raise TypeError(
                f"image must be a PIL.Image.Image, got {type(image).__name__}"
            )

        mode = image.mode

        # 1-bit fast path → DeviceGray 1 BPC.
        # Upstream ``isGrayImage`` only returns true when the source has
        # no transparency, but Pillow's "1" mode never carries an alpha
        # channel itself (palette transparency for "1" is exotic and
        # callers can convert to "LA" first).
        if mode == "1":
            return _create_from_one_bit(document, image)

        # 8-bit grayscale → DeviceGray 8 BPC.
        if mode == "L":
            return _create_from_gray(document, image, bpc=8)

        # 16-bit grayscale → DeviceGray 16 BPC.
        # Upstream handles this through PredictorEncoder when source is
        # ``DataBuffer.TYPE_USHORT``; we keep behaviour ("preserve
        # bit-depth") and use a plain flate raster.
        if mode in ("I;16", "I;16L", "I;16B"):
            return _create_from_gray16(document, image)

        # Grayscale + alpha → DeviceGray 8 BPC + 8-bit SMask.
        if mode == "LA":
            return _create_from_gray_alpha(document, image)

        # Indexed / paletted.
        if mode in ("P", "PA"):
            return _create_from_indexed(document, image)

        # RGBA → RGB raster + 8-bit SMask alpha.
        if mode == "RGBA":
            return _create_from_rgba(document, image)

        # Anything else (RGB, but also CMYK / YCbCr / LAB / RGBa /
        # I / F …): convert to RGB and emit an opaque DeviceRGB raster.
        # Upstream's "fallback to 8-bit sRGB and might lose color
        # information" path.
        if mode != "RGB":
            image = image.convert("RGB")
        return _create_from_rgb(document, image)


# ---------- per-mode builders ----------


def _create_from_one_bit(document: PDDocument, image: Image.Image) -> PDImageXObject:
    """1-bit DeviceGray. PIL's ``"1"`` mode emits ``tobytes()`` already
    in the ISO 32000-1 §8.9.5.1 layout: rows packed MSB-first with each
    row starting on a fresh byte boundary, ``1`` meaning the larger
    value (white). No repacking needed.

    Large bitmaps are routed through CCITT Group 4 — the spec-preferred
    encoding for fax-style monochrome content and the format upstream
    PDFBox emits via ``CCITTFactory.createFromImage``. Small bitmaps
    stay on flate (the CCITT framing overhead doesn't pay off below the
    threshold and exact-output round-trips on tiny test images are
    easier to reason about with flate's raw bit layout).
    """
    width, height = image.size
    raw = image.tobytes()
    if width * height >= _CCITT_PIXEL_THRESHOLD:
        try:
            return _prepare_ccitt_image_x_object(document, raw, width, height)
        except Exception:
            # Defensive: any libtiff hiccup falls back to the flate path
            # so we never lose an image to encoding failure. Upstream
            # CCITTFactory makes the same fallback decision.
            pass
    return _prepare_image_x_object(
        document,
        raw,
        width,
        height,
        bits_per_component=1,
        color_space=_DEVICE_GRAY,
    )


def _create_from_gray(
    document: PDDocument, image: Image.Image, *, bpc: int
) -> PDImageXObject:
    width, height = image.size
    return _prepare_image_x_object(
        document,
        image.tobytes(),
        width,
        height,
        bits_per_component=bpc,
        color_space=_DEVICE_GRAY,
    )


def _create_from_gray16(document: PDDocument, image: Image.Image) -> PDImageXObject:
    """16-bit grayscale → DeviceGray 16 BPC.

    PDF spec §8.9.5.1 mandates big-endian sample order. Pillow's
    ``"I;16"`` and ``"I;16L"`` modes store little-endian shorts, while
    ``"I;16B"`` already stores bytes in PDF order.
    """
    width, height = image.size
    raw = image.tobytes()
    if image.mode == "I;16B":
        return _prepare_image_x_object(
            document,
            raw,
            width,
            height,
            bits_per_component=16,
            color_space=_DEVICE_GRAY,
        )

    # Swap each pair of bytes to MSB-first.
    out = bytearray(len(raw))
    out[0::2] = raw[1::2]
    out[1::2] = raw[0::2]
    return _prepare_image_x_object(
        document,
        bytes(out),
        width,
        height,
        bits_per_component=16,
        color_space=_DEVICE_GRAY,
    )


def _create_from_gray_alpha(
    document: PDDocument, image: Image.Image
) -> PDImageXObject:
    width, height = image.size
    # Split into ("L",) and ("L",) for alpha.
    l_band, a_band = image.split()
    img = _prepare_image_x_object(
        document,
        l_band.tobytes(),
        width,
        height,
        bits_per_component=8,
        color_space=_DEVICE_GRAY,
    )
    smask = _prepare_image_x_object(
        document,
        a_band.tobytes(),
        width,
        height,
        bits_per_component=8,
        color_space=_DEVICE_GRAY,
    )
    img.get_cos_object().set_item(_SMASK, smask.get_cos_object())
    return img


def _create_from_rgb(document: PDDocument, image: Image.Image) -> PDImageXObject:
    width, height = image.size
    return _prepare_image_x_object(
        document,
        image.tobytes(),
        width,
        height,
        bits_per_component=8,
        color_space=_DEVICE_RGB,
    )


def _create_from_rgba(document: PDDocument, image: Image.Image) -> PDImageXObject:
    width, height = image.size
    # Split into R,G,B,A — interleave RGB without alpha for the body,
    # use the A band raw for the SMask. Upstream does the same split via
    # ``image.getRGB`` + alpha extraction.
    r, g, b, a = image.split()
    rgb = Image.merge("RGB", (r, g, b))
    img = _prepare_image_x_object(
        document,
        rgb.tobytes(),
        width,
        height,
        bits_per_component=8,
        color_space=_DEVICE_RGB,
    )
    smask = _prepare_image_x_object(
        document,
        a.tobytes(),
        width,
        height,
        bits_per_component=8,
        color_space=_DEVICE_GRAY,
    )
    img.get_cos_object().set_item(_SMASK, smask.get_cos_object())
    return img


def _create_from_indexed(
    document: PDDocument, image: Image.Image
) -> PDImageXObject:
    """Indexed/palette → ``/ColorSpace [/Indexed /DeviceRGB hival lookup]``.

    Pillow's ``"P"`` mode carries the palette in ``getpalette()`` (a
    flat list of RGB or RGBA samples — Pillow normalises both). The
    palette is right-truncated to ``(hival + 1) * 3`` bytes per spec.
    Palette transparency, if present in ``image.info["transparency"]``,
    is folded into a 1-bit ``/SMask``.
    """
    if image.mode == "PA":
        # Drop the redundant alpha channel of "PA" (same alpha is
        # encoded via palette indices) and treat as plain "P".
        image = image.convert("P")

    width, height = image.size
    palette = image.getpalette()
    if palette is None:
        # Defensive: a "P" image without a palette is malformed; fall
        # back to RGB conversion.
        return _create_from_rgb(document, image.convert("RGB"))
    # Pillow may pad the palette to 256*3 even for fewer entries.
    # Index data tells us the actual hival.
    raw_indices = image.tobytes()
    hival = max(raw_indices) if raw_indices else 0
    # Palette is RGB triplets. Some Pillow versions return RGBA
    # quadruplets for palette modes that include alpha; normalise.
    raw_mode = image.palette.mode if image.palette is not None else "RGB"
    if raw_mode == "RGBA":
        triplets = bytearray()
        for i in range(0, len(palette), 4):
            triplets.extend(palette[i : i + 3])
        palette_bytes = bytes(triplets)
    else:
        palette_bytes = bytes(palette)
    # Truncate to hival+1 entries (3 bytes each).
    palette_bytes = palette_bytes[: (hival + 1) * 3]
    # Right-pad in case Pillow returned a short palette.
    expected = (hival + 1) * 3
    if len(palette_bytes) < expected:
        palette_bytes = palette_bytes + b"\x00" * (expected - len(palette_bytes))

    img = _prepare_image_x_object(
        document,
        raw_indices,
        width,
        height,
        bits_per_component=8,
        color_space=_build_indexed_colorspace(hival, palette_bytes),
    )

    # Palette transparency → 1-bit /SMask (opaque vs fully transparent).
    transparency = image.info.get("transparency")
    if isinstance(transparency, (bytes, bytearray)):
        # Per-index alpha table.
        alpha_table = bytes(transparency)
        # 8-bit alpha SMask: lookup palette[index] for each sample.
        smask_bytes = bytearray(len(raw_indices))
        for i, idx in enumerate(raw_indices):
            smask_bytes[i] = alpha_table[idx] if idx < len(alpha_table) else 0xFF
        smask = _prepare_image_x_object(
            document,
            bytes(smask_bytes),
            width,
            height,
            bits_per_component=8,
            color_space=_DEVICE_GRAY,
        )
        img.get_cos_object().set_item(_SMASK, smask.get_cos_object())
    elif isinstance(transparency, int):
        # Single transparent index → 1-bit binary mask.
        row_bytes = (width + 7) // 8
        packed = bytearray(row_bytes * height)
        for y in range(height):
            for x in range(width):
                idx = raw_indices[y * width + x]
                if idx != transparency:
                    packed[y * row_bytes + (x >> 3)] |= 0x80 >> (x & 7)
        smask = _prepare_image_x_object(
            document,
            bytes(packed),
            width,
            height,
            bits_per_component=1,
            color_space=_DEVICE_GRAY,
        )
        img.get_cos_object().set_item(_SMASK, smask.get_cos_object())

    return img


def _build_indexed_colorspace(hival: int, palette_bytes: bytes) -> COSArray:
    array = COSArray()
    array.add(_INDEXED)
    array.add(_DEVICE_RGB)
    array.add(COSInteger.get(hival))
    # Hex form keeps the writer output predictable (palette bytes are
    # often non-printable). Upstream uses an in-line ``COSString``.
    palette_str = COSString(palette_bytes)
    palette_str.set_force_hex_form(True)
    array.add(palette_str)
    return array


# ---------- shared stream-building helper ----------


def _prepare_ccitt_image_x_object(
    document: PDDocument,
    raw_bytes: bytes,
    width: int,
    height: int,
) -> PDImageXObject:
    """Build a 1 BPC ``/DeviceGray`` image XObject with
    ``/CCITTFaxDecode`` Group 4 encoding.

    Mirrors upstream ``org.apache.pdfbox.pdmodel.graphics.image.
    CCITTFactory.createFromImage`` — both go through a libtiff Group 4
    round-trip to produce the encoded payload.

    The ``/DecodeParms`` carries the canonical G4 quartet:
    ``/K -1`` (Group 4), ``/Columns width``, ``/Rows height``, and
    ``/BlackIs1 false`` (default; PIL ``"1"`` already maps 1=white).
    """
    decode_params = COSDictionary()
    decode_params.set_int("K", -1)
    decode_params.set_int("Columns", int(width))
    decode_params.set_int("Rows", int(height))

    # Wrap the raw pixel data in a one-element stream dict so
    # CCITTFaxDecode.encode resolves /DecodeParms the same way the
    # decoder does. Mirrors the producer convention upstream uses for
    # all single-filter encodes.
    stream_shell = COSDictionary()
    stream_shell.set_item(_DECODE_PARMS, decode_params)

    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw_bytes), enc_buf, stream_shell)
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
    return PDImageXObject(stream)


def _prepare_image_x_object(
    document: PDDocument,
    raw_bytes: bytes,
    width: int,
    height: int,
    *,
    bits_per_component: int,
    color_space: COSName | COSArray,
) -> PDImageXObject:
    """Mirrors upstream
    ``LosslessFactory.prepareImageXObject``: flate-encodes ``raw_bytes``
    and stamps the standard image-XObject dictionary entries.

    Uses :func:`zlib.compress` directly (the same primitive
    :class:`pypdfbox.filter.FlateDecode` calls — bypassing the filter
    plumbing avoids running through the predictor / parameters branch
    for an empty parameters dictionary).
    """
    encoded = zlib.compress(raw_bytes)

    cos_doc = document.get_document()
    stream = COSStream(cos_doc.scratch_file)
    stream.set_item(_TYPE, _XOBJECT)
    stream.set_item(_SUBTYPE, _IMAGE)
    stream.set_int(_WIDTH, int(width))
    stream.set_int(_HEIGHT, int(height))
    stream.set_int(_BITS_PER_COMPONENT, int(bits_per_component))
    stream.set_item(_COLORSPACE, color_space)
    stream.set_item(_FILTER, _FLATE_DECODE)
    stream.set_int(_LENGTH, len(encoded))
    stream.set_raw_data(encoded)
    return PDImageXObject(stream)


__all__ = ["LosslessFactory"]
