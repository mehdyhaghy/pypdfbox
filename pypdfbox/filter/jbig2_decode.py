from __future__ import annotations

from typing import BinaryIO, Final

from pypdfbox.cos import COSArray, COSDictionary, COSStream

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# ISO 32000-1 §7.4.7 JBIG2Decode parameter keys.
_JBIG2_GLOBALS: Final[str] = "JBIG2Globals"


def _resolve_decode_params(parameters: COSDictionary | None, index: int) -> COSDictionary:
    """Resolve effective ``/DecodeParms`` for the filter at ``index``.

    Mirrors the convention used by :mod:`ccitt_fax_decode` /
    :mod:`flate_decode`: the ``parameters`` argument is the *stream
    dictionary*, from which we pull ``/DecodeParms`` (single dict or
    array indexed by filter position). Missing entries return an empty
    dict so callers can use ``get_dictionary_object`` defaults
    uniformly. Falls back to ``parameters`` itself when the caller
    handed us the decode-params dict directly (this is how the
    hand-written tests invoke the filter).
    """
    if parameters is None:
        return COSDictionary()
    for key in ("DecodeParms", "DP"):
        params = parameters.get_dictionary_object(key)
        if isinstance(params, COSDictionary):
            return params
        if isinstance(params, COSArray):
            try:
                entry = params.get_object(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
            return COSDictionary()
    return parameters


def _read_globals_bytes(decode_params: COSDictionary) -> bytes:
    """Pull and decode the ``/JBIG2Globals`` stream, if present.

    The globals entry is itself a content stream (may carry its own
    ``/Filter`` chain — typically ``/FlateDecode``).
    ``COSStream.to_byte_array`` runs the chain so we get the raw
    global-segment bytes the JBIG2 codec expects (the shared symbol /
    page dictionaries that logically precede the per-image segments).
    """
    globals_obj = decode_params.get_dictionary_object(_JBIG2_GLOBALS)
    if globals_obj is None:
        return b""
    if not isinstance(globals_obj, COSStream):
        # Spec permits only a stream here; defend against malformed
        # input by treating anything else as no globals rather than
        # crashing the whole image decode.
        return b""
    return bytes(globals_obj.to_byte_array())


def _inverted_bitmap_bytes(bitmap: object) -> bytes:
    """Return the bitmap's packed bytes with JBIG2 polarity inverted.

    JBIG2 (ITU-T T.88) defines pixel value ``1`` = black, ``0`` = white.
    The PDF image pipeline (and Apache PDFBox's ``JBIG2Filter``) want the
    opposite packed polarity for a 1-bit ``DeviceGray`` raster: decoded
    sample ``0`` = black, ``1`` = white — the same polarity the
    ``/CCITTFaxDecode`` filter emits by default (``/BlackIs1`` false).

    Upstream ``Bitmaps.buildRaster`` (the unscaled path) does exactly
    this: ``dst[idx] = ~bitmap.getByte(idx)`` then masks the trailing
    pad bits of each row's last partial byte back to ``0``. The
    ``JBIG2Filter`` writes that inverted, pad-cleared buffer straight to
    the image decode stream. We reproduce it byte-for-byte so
    ``PDImageXObject.get_image()`` is bit-exact with PDFBox's
    ``getImage()``.
    """
    width = bitmap.get_width()  # type: ignore[attr-defined]
    height = bitmap.get_height()  # type: ignore[attr-defined]
    row_stride = bitmap.get_row_stride()  # type: ignore[attr-defined]
    src = bitmap.get_byte_array()  # type: ignore[attr-defined]

    # Mask for the trailing (pad) bits of a row's last byte; mirrors the
    # upstream ``(~0xff >> (width & 7)) & 0xff`` expression. ``width & 7``
    # == 0 means the row is byte-aligned and there is no partial byte to
    # mask, so the whole-byte loop covers every byte.
    rem = width & 7
    if rem == 0:
        full_bytes = row_stride
        pad_mask = 0
    else:
        full_bytes = row_stride - 1
        pad_mask = (~0xFF >> rem) & 0xFF

    dst = bytearray(height * row_stride)
    idx = 0
    for _ in range(height):
        for _ in range(full_bytes):
            dst[idx] = (~src[idx]) & 0xFF
            idx += 1
        if pad_mask != 0:
            dst[idx] = (~src[idx]) & pad_mask
            idx += 1
    return bytes(dst)


class JBIG2Decode(Filter):
    """``/JBIG2Decode`` filter (ISO 32000-1 §7.4.7).

    Decodes a JBIG2 (ITU-T T.88) bilevel image stream by delegating to
    the first-party pure-Python JBIG2 decoder in :mod:`pypdfbox.jbig2`
    (a port of the Apache-2.0 ``apache/pdfbox-jbig2`` plugin — no GPL
    code, no native extension). The decoder returns a bilevel
    :class:`~pypdfbox.jbig2.bitmap.Bitmap`; we invert its polarity to the
    1-bit ``DeviceGray`` raster the image pipeline expects (sample
    ``0`` = black, ``1`` = white) and write the packed scanline buffer.

    JBIG2 is bilevel by definition (one bit per pixel, packed MSB-first
    into bytes) so the surfaced parameters are fixed at
    ``/BitsPerComponent = 1`` and ``/ColorComponents = 1``. Geometry
    (``/Width``, ``/Height``) is intrinsic to the codestream and surfaced
    via ``DecodeResult.parameters`` so callers can patch the image
    XObject when those entries are absent.

    Per spec the only ``/DecodeParms`` entry is ``/JBIG2Globals``: a
    stream containing shared symbol / page dictionaries. When present,
    its decoded bytes are decoded into a ``JBIG2Globals`` and handed to
    the document so the per-image segments can resolve their referred-to
    global segments. Decoder-only — there is no PDF producer use case
    for JBIG2 in pypdfbox (matching upstream, which ships no encoder).

    Mirrors `org.apache.pdfbox.filter.JBIG2Filter`.
    """

    #: ``/JBIG2Globals`` parameter key per ISO 32000-1 §7.4.7. Exposed
    #: as a class attribute so callers reaching for the upstream
    #: ``COSName.JBIG2_GLOBALS`` reference site land on a stable name.
    JBIG2_GLOBALS: Final[str] = _JBIG2_GLOBALS

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        # Lazy import: the JBIG2 decoder package pulls in a fair amount
        # of segment/arithmetic-decoder machinery we don't want to drag
        # into every filter import until a JBIG2 stream is decoded.
        from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
        from pypdfbox.jbig2.jbig2_document import JBIG2Document

        decode_params = _resolve_decode_params(parameters, index)
        globals_bytes = _read_globals_bytes(decode_params)

        encoded_bytes = encoded.read()
        out_params = parameters if parameters is not None else COSDictionary()
        if not encoded_bytes and not globals_bytes:
            return DecodeResult(parameters=out_params, bytes_written=0)

        # Decode the /JBIG2Globals stream (shared dictionaries) into a
        # JBIG2Globals, if present, and pass it to the per-image
        # document so referred-to global segments resolve. Mirrors
        # upstream JBIG2Filter prepending the globals stream, but using
        # the proper two-arg document constructor rather than naive byte
        # concatenation (the upstream JBIG2 *plugin* path).
        try:
            global_segments = None
            if globals_bytes:
                globals_doc = JBIG2Document(ImageInputStream(globals_bytes))
                global_segments = globals_doc.get_global_segments()

            document = JBIG2Document(
                ImageInputStream(encoded_bytes), global_segments
            )
            page = document.get_page(1)
            if page is None:
                raise OSError("JBIG2Decode: no page 1 in JBIG2 stream")
            bitmap = page.get_bitmap()
        except OSError:
            raise
        except Exception as exc:
            raise OSError(f"JBIG2Decode: JBIG2 decode failed: {exc}") from exc

        samples = _inverted_bitmap_bytes(bitmap)
        width = bitmap.get_width()
        height = bitmap.get_height()

        bytes_written = decoded.write(samples)

        out_params.set_int("Width", width)
        out_params.set_int("Height", height)
        # JBIG2 is bilevel by ITU-T T.88 definition.
        out_params.set_int("BitsPerComponent", 1)
        out_params.set_int("ColorComponents", 1)
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        """``/JBIG2Decode`` is a decode-only filter — by upstream design.

        Mirrors ``JBIG2Filter`` in Apache PDFBox, which inherits the
        default ``encode`` that raises ``UnsupportedOperationException``.
        PDFBox does not ship a JBIG2 encoder (and no production PDF
        toolchain produces JBIG2 from scratch — the format is the
        province of dedicated tools such as ``jbig2enc`` invoked by
        upstream OCR / scan pipelines). This is upstream-faithful
        behaviour, not a pypdfbox deferral.
        """
        raise NotImplementedError(
            "JBIG2Decode.encode is not implemented (decode-only)"
        )


# PDF spec defines NO short-name abbreviation for /JBIG2Decode
# (ISO 32000-1 §7.4.2 Table 6) — register only the long name.
FilterFactory.register("JBIG2Decode", JBIG2Decode())
