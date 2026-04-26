from __future__ import annotations

import io
import struct
from typing import BinaryIO

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# ISO 32000-1 §7.4.9 CCITTFaxDecode parameter keys.
_K = "K"
_COLUMNS = "Columns"
_ROWS = "Rows"
_END_OF_LINE = "EndOfLine"
_END_OF_BLOCK = "EndOfBlock"
_BLACK_IS_1 = "BlackIs1"
_ENCODED_BYTE_ALIGN = "EncodedByteAlign"
_DAMAGED_ROWS_BEFORE_ERROR = "DamagedRowsBeforeError"

# TIFF tag IDs used in the synthetic wrapper.
_TIFF_IMAGE_WIDTH = 256
_TIFF_IMAGE_LENGTH = 257
_TIFF_BITS_PER_SAMPLE = 258
_TIFF_COMPRESSION = 259
_TIFF_PHOTOMETRIC = 262
_TIFF_FILL_ORDER = 266
_TIFF_STRIP_OFFSETS = 273
_TIFF_SAMPLES_PER_PIXEL = 277
_TIFF_ROWS_PER_STRIP = 278
_TIFF_STRIP_BYTE_COUNTS = 279
_TIFF_T4_OPTIONS = 292
_TIFF_T6_OPTIONS = 293

_TIFF_TYPE_SHORT = 3
_TIFF_TYPE_LONG = 4

# TIFF compression values per TIFF 6.0:
#   3 = CCITT T.4 (Group 3 fax, 1D or 2D depending on T4Options bit 0)
#   4 = CCITT T.6 (Group 4 fax)
_COMPRESSION_T4 = 3
_COMPRESSION_T6 = 4

# T4Options bits:
#   bit 0 = 2D coding (set for K>0 mixed G3, clear for K==0 1D-only G3)
#   bit 1 = uncompressed mode permitted
#   bit 2 = byte-aligned EOL codes  (PDF /EncodedByteAlign)
_T4_TWO_DIMENSIONAL = 0x1
_T4_ENCODED_BYTE_ALIGN = 0x4


def _resolve_decode_params(parameters: COSDictionary | None, index: int) -> COSDictionary:
    """Resolve effective ``/DecodeParms`` for the filter at ``index``.

    Mirrors the convention used by :mod:`lzw_decode` /
    :mod:`flate_decode`: the ``parameters`` argument is the *stream
    dictionary*, from which we pull ``/DecodeParms`` (single dict or
    array indexed by filter position). Missing entries return an empty
    dict so callers can use ``get_int`` / ``get_boolean`` defaults
    uniformly.
    """
    if parameters is None:
        return COSDictionary()
    for key in ("DecodeParms", "DP"):
        params = parameters.get_dictionary_object(key)
        if isinstance(params, COSDictionary):
            return params
        if isinstance(params, COSArray):
            try:
                entry = params.get(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
            return COSDictionary()
    # Fallback: caller passed the decode-params dict directly (this is
    # how the hand-written tests invoke the filter).
    return parameters


def _ifd_entry(tag: int, type_: int, count: int, value: int) -> bytes:
    """Pack a single 12-byte TIFF IFD entry. Both SHORT and LONG single
    values fit inside the 4-byte value field; we pad SHORTs with two
    trailing zero bytes."""
    if type_ == _TIFF_TYPE_SHORT:
        return struct.pack("<HHIHH", tag, type_, count, value, 0)
    if type_ == _TIFF_TYPE_LONG:
        return struct.pack("<HHII", tag, type_, count, value)
    raise ValueError(f"unsupported TIFF entry type {type_}")


def _build_tiff_wrapper(
    encoded: bytes,
    *,
    columns: int,
    rows: int,
    k: int,
    photometric: int,
    encoded_byte_align: bool,
) -> bytes:
    """Build a self-contained little-endian TIFF wrapping ``encoded`` as a
    single CCITT-compressed strip.

    The IFD always has the same fixed layout (10 entries) so the strip
    offset is a compile-time constant. This keeps the wrapper trivial to
    audit and avoids recomputing layout for each call.
    """
    if k < 0:
        compression = _COMPRESSION_T6
        # T6Options is reserved (bit 1 = uncompressed allowed). PDF never
        # sets uncompressed, so emit zero.
        options_tag = _TIFF_T6_OPTIONS
        options_value = 0
    else:
        compression = _COMPRESSION_T4
        options_tag = _TIFF_T4_OPTIONS
        options_value = 0
        if k > 0:
            options_value |= _T4_TWO_DIMENSIONAL
        if encoded_byte_align:
            options_value |= _T4_ENCODED_BYTE_ALIGN

    n_entries = 11
    ifd_size = 2 + n_entries * 12 + 4  # count + entries + next-IFD pointer
    strip_offset = 8 + ifd_size

    # Header: little-endian magic, version 42, IFD offset 8.
    header = struct.pack("<2sHI", b"II", 42, 8)

    # Tag order MUST be ascending per TIFF 6.0 spec; tags 256..279
    # come first, then T4Options/T6Options at 292/293.
    entries = b"".join(
        [
            _ifd_entry(_TIFF_IMAGE_WIDTH, _TIFF_TYPE_LONG, 1, columns),
            _ifd_entry(_TIFF_IMAGE_LENGTH, _TIFF_TYPE_LONG, 1, rows),
            _ifd_entry(_TIFF_BITS_PER_SAMPLE, _TIFF_TYPE_SHORT, 1, 1),
            _ifd_entry(_TIFF_COMPRESSION, _TIFF_TYPE_SHORT, 1, compression),
            _ifd_entry(_TIFF_PHOTOMETRIC, _TIFF_TYPE_SHORT, 1, photometric),
            # FillOrder=1: most-significant-bit-first within each byte.
            # PDF CCITT streams are MSB-first; matches TIFF default but
            # we emit it explicitly so the wrapper is unambiguous.
            _ifd_entry(_TIFF_FILL_ORDER, _TIFF_TYPE_SHORT, 1, 1),
            _ifd_entry(_TIFF_STRIP_OFFSETS, _TIFF_TYPE_LONG, 1, strip_offset),
            _ifd_entry(_TIFF_SAMPLES_PER_PIXEL, _TIFF_TYPE_SHORT, 1, 1),
            _ifd_entry(_TIFF_ROWS_PER_STRIP, _TIFF_TYPE_LONG, 1, rows),
            _ifd_entry(_TIFF_STRIP_BYTE_COUNTS, _TIFF_TYPE_LONG, 1, len(encoded)),
            _ifd_entry(options_tag, _TIFF_TYPE_LONG, 1, options_value),
        ]
    )

    assert len(entries) == n_entries * 12

    ifd = struct.pack("<H", n_entries) + entries + struct.pack("<I", 0)
    return header + ifd + encoded


class CCITTFaxDecode(Filter):
    """``/CCITTFaxDecode`` filter (ISO 32000-1 §7.4.9).

    Decodes Group 3 (T.4) and Group 4 (T.6) fax-encoded streams by
    wrapping the encoded bytes in a synthetic TIFF and delegating to
    Pillow's libtiff-backed decoder. The decoded output is a raw
    bit-packed scanline buffer (rows padded to whole bytes, MSB-first
    within each byte) — the same shape the PDF image XObject expects in
    its decoded body.

    Decoder-only: PDF rarely *encodes* CCITT (the upstream PDFBox
    encoder is a TIFF round-trip too, and we have no producer use case
    yet). ``encode()`` raises ``NotImplementedError``.

    Mirrors `org.apache.pdfbox.filter.CCITTFaxFilter`.
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        decode_params = _resolve_decode_params(parameters, index)

        k = decode_params.get_int(_K, 0)
        columns = decode_params.get_int(_COLUMNS, 1728)  # PDF default
        rows = decode_params.get_int(_ROWS, 0)
        black_is_1 = decode_params.get_boolean(_BLACK_IS_1, False)
        encoded_byte_align = decode_params.get_boolean(_ENCODED_BYTE_ALIGN, False)
        # /EndOfLine and /EndOfBlock affect the *encoded* G3 stream's
        # framing. libtiff handles end-of-block detection on its own; we
        # don't need to forward them through the wrapper, but we accept
        # them so callers can pass real PDF DecodeParms verbatim.
        _ = decode_params.get_boolean(_END_OF_LINE, False)
        _ = decode_params.get_boolean(_END_OF_BLOCK, True)
        _ = decode_params.get_int(_DAMAGED_ROWS_BEFORE_ERROR, 0)

        if columns <= 0:
            raise OSError(f"CCITTFaxDecode: invalid /Columns {columns}")

        encoded_bytes = encoded.read()
        if not encoded_bytes:
            # An empty body is harmless — emit no scanlines.
            out_params = parameters if parameters is not None else COSDictionary()
            return DecodeResult(parameters=out_params, bytes_written=0)

        # PDF spec §7.4.9: with /Rows omitted (≤ 0) the decoder must
        # discover the row count from the encoded stream. libtiff does
        # exactly that when ImageLength is "large enough", so we feed it
        # a generous upper bound and trim afterwards.
        wrapper_rows = rows if rows > 0 else _estimate_rows(encoded_bytes, columns)

        # PDF default polarity: 0 = black, 1 = white  → TIFF photometric
        # 1 (BlackIsZero). With /BlackIs1 = true the polarity flips.
        photometric = 1 if not black_is_1 else 0

        tiff_bytes = _build_tiff_wrapper(
            encoded_bytes,
            columns=columns,
            rows=wrapper_rows,
            k=k,
            photometric=photometric,
            encoded_byte_align=encoded_byte_align,
        )

        try:
            with Image.open(io.BytesIO(tiff_bytes)) as image:
                if image.mode != "1":
                    image = image.convert("1")
                image.load()
                scanlines = image.tobytes()
                actual_height = image.size[1]
                actual_width = image.size[0]
        except Exception as exc:
            raise OSError(f"CCITTFaxDecode: libtiff decode failed: {exc}") from exc

        # If the caller declared /Rows, trim trailing scanlines libtiff
        # may have produced past EOF. (When /Rows was omitted we keep
        # everything libtiff returned.)
        if rows > 0:
            row_bytes = (actual_width + 7) // 8
            scanlines = scanlines[: rows * row_bytes]
            actual_height = rows

        bytes_written = decoded.write(scanlines)

        # Surface the resolved geometry so callers can populate the
        # image XObject's /Width / /Height when they were unknown.
        out_params = parameters if parameters is not None else COSDictionary()
        out_params.set_int(_COLUMNS, actual_width)
        out_params.set_int(_ROWS, actual_height)
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        # Encoding is not part of the read-side image pipeline. We have
        # no producer use case yet, and Pillow's TIFF writer would force
        # a temporary in-memory TIFF round-trip just to extract the
        # strip data. Defer until a real caller appears.
        raise NotImplementedError(
            "CCITTFaxDecode.encode is not implemented (decode-only)"
        )


def _estimate_rows(encoded_bytes: bytes, columns: int) -> int:
    """Generous upper bound for the row count when /Rows is missing.

    libtiff stops decoding at the natural end-of-block marker even when
    ImageLength is over-large, so any over-estimate is safe. We use a
    formula keyed off the encoded stream size; the exact constant is
    arbitrary as long as it can't undershoot any realistic fax page."""
    # A worst-case 1 bit-per-pixel run encodes to ~1 bit per pixel, so
    # ``8 * encoded / columns`` is an absolute ceiling. Add a generous
    # safety margin and clamp to 1 minimum.
    if columns <= 0:
        return 1
    upper = max(1, (8 * len(encoded_bytes) // columns) + 16)
    # Hard cap to keep the TIFF wrapper's IFD value sane (TIFF LONG
    # supports up to 2**32-1 but we never need more than a few thousand
    # scanlines for any real PDF).
    return min(upper, 65535)


FilterFactory.register("CCITTFaxDecode", CCITTFaxDecode())
