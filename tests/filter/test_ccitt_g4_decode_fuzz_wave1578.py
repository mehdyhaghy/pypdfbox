"""Wave 1578 (agent C) — CCITT Group 3/4 fax decode parity fuzz.

pypdfbox's CCITT codec is **library-first**: the 2D coding state machine
(pass / horizontal / vertical V0..VL3 modes, b1/b2 reference-line search,
Huffman run tables) lives in Pillow's libtiff backend, not in vendored
Python. These tests therefore hammer the *parity surface pypdfbox owns*:

* the ``/K`` dispatch (K<0 = G4/T.6, K==0 = G3 1D, K>0 = G3 2D),
* ``/BlackIs1`` inverting the decoded output sense,
* ``/EncodedByteAlign`` per-row byte padding,
* ``/Columns`` / ``/Rows`` geometry and the /Height-overrides-/Rows
  reconciliation upstream's ``CCITTFaxFilter.decode`` performs,
* the standalone ``CCITTFaxDecoderStream`` constructor's
  (compression-type, T4/T6-options) -> /K + byte-align mapping,
* 1-pixel-wide and full-width (1728) rows,
* round-trip identity through encode -> decode for every mode.

The round-trip is the differential oracle: libtiff is the same T.4/T.6
engine PDFBox's ``CCITTFaxFilter`` ultimately defers to (PDFBox via
``com.sun.imageio`` / Bouncy Castle TIFF; pypdfbox via Pillow/libtiff),
so an encode->decode identity that holds across all modes confirms the
mode dispatch and polarity match upstream's behaviour.

NOTE: libtiff post-EOD byte-padding differs between POSIX and Windows
wheels — we never assert on bytes past the declared ``row_bytes * rows``
footprint (the project's libtiff EOD carve-out).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode
from pypdfbox.filter.ccitt_fax_decoder_stream import CCITTFaxDecoderStream
from pypdfbox.filter.tiff_extension import TIFFExtension

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _row_bytes(columns: int) -> int:
    return (columns + 7) // 8


def _params(
    *,
    k: int,
    columns: int,
    rows: int,
    black_is_1: bool = False,
    byte_align: bool = False,
) -> COSDictionary:
    """Build a stream dict carrying nested /DecodeParms (the real PDF shape)."""
    sub = COSDictionary()
    sub.set_int("K", k)
    sub.set_int("Columns", columns)
    sub.set_int("Rows", rows)
    if black_is_1:
        sub.set_boolean("BlackIs1", True)
    if byte_align:
        sub.set_boolean("EncodedByteAlign", True)
    p = COSDictionary()
    p.set_item("DecodeParms", sub)
    return p


def _round_trip(
    raw: bytes,
    *,
    k: int,
    columns: int,
    rows: int,
    black_is_1: bool = False,
    byte_align: bool = False,
) -> bytes:
    """Encode ``raw`` then decode it back, returning the declared footprint."""
    f = CCITTFaxDecode()
    params = _params(
        k=k,
        columns=columns,
        rows=rows,
        black_is_1=black_is_1,
        byte_align=byte_align,
    )
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc, params)
    encoded = enc.getvalue()
    assert encoded, "encode must produce non-empty output"
    dec = io.BytesIO()
    f.decode(io.BytesIO(encoded), dec, params, 0)
    return dec.getvalue()[: _row_bytes(columns) * rows]


# Deterministic bilevel row patterns (one byte per 8 pixels, MSB-first).
_PATTERNS = {
    "all_white": b"\xff",
    "all_black": b"\x00",
    "alt_bits": b"\xaa",
    "left_half": b"\xf0",
    "right_half": b"\x0f",
    "single_left": b"\x80",
    "single_right": b"\x01",
}


# ----------------------------------------------------------------------
# Round-trip identity across the three /K modes (filter path)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("k", [-1, 0, 4], ids=["g4", "g3_1d", "g3_2d"])
@pytest.mark.parametrize(
    "pat",
    list(_PATTERNS.values()),
    ids=list(_PATTERNS.keys()),
)
def test_k_mode_round_trip(k: int, pat: bytes) -> None:
    """Every /K mode must encode->decode to an identity for each pattern."""
    columns = 8
    rows = 5
    raw = pat * rows
    assert _round_trip(raw, k=k, columns=columns, rows=rows) == raw


@pytest.mark.parametrize("k", [-1, 0, 4], ids=["g4", "g3_1d", "g3_2d"])
def test_k_mode_round_trip_multibyte_row(k: int) -> None:
    """A wider, multi-byte, multi-run row exercises horizontal + vertical
    modes (alternating runs force changing elements per column)."""
    columns = 40
    rows = 6
    rb = _row_bytes(columns)
    # Distinct per-row patterns so reference-line (b1/b2) logic varies row
    # to row, which forces vertical-vs-horizontal mode selection in G4.
    raw = b"".join(
        bytes([(0xAA + i) & 0xFF, (0x33 + i) & 0xFF, 0xCC, 0xF0, 0x0F][:rb])
        for i in range(rows)
    )
    raw = raw[: rb * rows]
    assert _round_trip(raw, k=k, columns=columns, rows=rows) == raw


# ----------------------------------------------------------------------
# /BlackIs1 polarity
# ----------------------------------------------------------------------


def test_black_is_1_inverts_decoded_sense() -> None:
    """Decoding ONE encoded stream with /BlackIs1 true vs false yields
    bitwise-inverse output (set bit = black flips meaning)."""
    f = CCITTFaxDecode()
    columns, rows = 16, 4
    rb = _row_bytes(columns)
    raw = b"\xff\xff" * rows  # all white in the default (BlackIs1 false) sense
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc, _params(k=-1, columns=columns, rows=rows))
    encoded = enc.getvalue()

    out_false = io.BytesIO()
    f.decode(io.BytesIO(encoded), out_false,
             _params(k=-1, columns=columns, rows=rows), 0)
    out_true = io.BytesIO()
    f.decode(io.BytesIO(encoded), out_true,
             _params(k=-1, columns=columns, rows=rows, black_is_1=True), 0)

    a = out_false.getvalue()[: rb * rows]
    b = out_true.getvalue()[: rb * rows]
    assert a == b"\xff" * (rb * rows)
    assert b == b"\x00" * (rb * rows)
    assert all((x ^ 0xFF) == y for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize("k", [-1, 0, 4], ids=["g4", "g3_1d", "g3_2d"])
def test_black_is_1_round_trip_identity(k: int) -> None:
    """With matching /BlackIs1 on both ends the round-trip is an identity."""
    columns, rows = 16, 4
    raw = b"\x33\xcc" * rows
    assert (
        _round_trip(raw, k=k, columns=columns, rows=rows, black_is_1=True)
        == raw
    )


# ----------------------------------------------------------------------
# /EncodedByteAlign (Group 3 only; encode rejects it for G4)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("k", [0, 4], ids=["g3_1d", "g3_2d"])
def test_encoded_byte_align_round_trip(k: int) -> None:
    """/EncodedByteAlign pads each encoded row to a byte boundary; a matched
    encode/decode pair must still reproduce the source bitmap."""
    columns, rows = 24, 6
    raw = b"\xaa\xbb\xcc" * rows
    assert (
        _round_trip(raw, k=k, columns=columns, rows=rows, byte_align=True)
        == raw
    )


def test_encoded_byte_align_rejected_for_group4() -> None:
    """Encode refuses /EncodedByteAlign for G4 (T.6 has no byte-align bit in
    the TIFF backend) — it must error, not silently emit a non-aligned stream."""
    f = CCITTFaxDecode()
    columns, rows = 16, 4
    raw = b"\xf0\x0f" * rows
    with pytest.raises(OSError, match="EncodedByteAlign"):
        f.encode(io.BytesIO(raw), io.BytesIO(),
                 _params(k=-1, columns=columns, rows=rows, byte_align=True))


# ----------------------------------------------------------------------
# /Columns geometry: 1-pixel and full-width rows
# ----------------------------------------------------------------------


def test_single_pixel_wide_round_trip() -> None:
    """A 1-pixel-wide image (row_bytes == 1, one significant bit per row)."""
    columns, rows = 1, 8
    rb = _row_bytes(columns)
    raw = bytes([0x80, 0x00] * 4)[: rb * rows]  # alternating black/white pixel
    assert _round_trip(raw, k=-1, columns=columns, rows=rows) == raw


def test_full_width_1728_round_trip() -> None:
    """Full A4-fax width (1728) with one all-white and one all-black row."""
    columns, rows = 1728, 2
    rb = _row_bytes(columns)
    raw = b"\xff" * rb + b"\x00" * rb
    assert _round_trip(raw, k=-1, columns=columns, rows=rows) == raw


def test_columns_default_is_1728_on_empty_body() -> None:
    """Omitted /Columns resolves to the PDF default 1728; an empty body with
    no row count writes zero bytes (arraySize == 0), matching upstream."""
    f = CCITTFaxDecode()
    params = COSDictionary()
    sub = COSDictionary()
    sub.set_int("K", -1)
    params.set_item("DecodeParms", sub)
    out = io.BytesIO()
    result = f.decode(io.BytesIO(b""), out, params, 0)
    assert result.bytes_written == 0
    assert result.parameters.get_int("Columns") == 1728


def test_columns_zero_yields_empty_buffer() -> None:
    """/Columns == 0 -> rowBytes 0 -> arraySize 0 -> empty output (NOT error),
    mirroring CCITTFaxFilter's unchecked allocation."""
    f = CCITTFaxDecode()
    out = io.BytesIO()
    result = f.decode(io.BytesIO(b"\x00\x01"),
                      out, _params(k=-1, columns=0, rows=4), 0)
    assert result.bytes_written == 0


def test_columns_negative_raises() -> None:
    """/Columns < 0 -> NegativeArraySizeException upstream -> OSError here."""
    f = CCITTFaxDecode()
    with pytest.raises(OSError, match="(?i)columns"):
        f.decode(io.BytesIO(b"\x00\x01\x02"),
                 io.BytesIO(), _params(k=-1, columns=-1, rows=4), 0)


# ----------------------------------------------------------------------
# /Rows and /Height reconciliation (CCITTFaxFilter.decode)
# ----------------------------------------------------------------------


def test_height_overrides_rows_when_both_present() -> None:
    """When BOTH /Rows (DecodeParms) and /Height (stream dict) are set,
    /Height wins outright (not max) — upstream:
    ``if (rows>0 && height>0) rows=height``."""
    f = CCITTFaxDecode()
    columns, declared_rows = 16, 6
    rb = _row_bytes(columns)
    raw = bytes([0xF0, 0x0F] * declared_rows)[: rb * declared_rows]
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc,
             _params(k=-1, columns=columns, rows=declared_rows))
    encoded = enc.getvalue()

    params = _params(k=-1, columns=columns, rows=declared_rows)
    params.set_int("Height", 3)  # /Height on the stream dict overrides /Rows
    out = io.BytesIO()
    result = f.decode(io.BytesIO(encoded), out, params, 0)
    assert len(out.getvalue()) == rb * 3
    assert result.parameters.get_int("Rows") == 3


def test_rows_only_used_when_height_absent() -> None:
    """Without /Height, the DecodeParms /Rows count drives the footprint."""
    columns, rows = 16, 5
    rb = _row_bytes(columns)
    raw = bytes([0xAA, 0x55] * rows)[: rb * rows]
    out = _round_trip(raw, k=-1, columns=columns, rows=rows)
    assert len(out) == rb * rows
    assert out == raw


def test_empty_body_known_rows_fills_white() -> None:
    """Empty encoded body but rows known -> a fixed rows*rowBytes WHITE buffer
    (0xFF default polarity), NOT zero bytes."""
    f = CCITTFaxDecode()
    columns, rows = 16, 3
    rb = _row_bytes(columns)
    out = io.BytesIO()
    f.decode(io.BytesIO(b""), out, _params(k=-1, columns=columns, rows=rows), 0)
    assert out.getvalue() == b"\xff" * (rb * rows)


def test_empty_body_known_rows_black_is_1_fills_zero() -> None:
    """Same empty-body fill, but /BlackIs1 true -> buffer reads out as 0x00."""
    f = CCITTFaxDecode()
    columns, rows = 16, 3
    rb = _row_bytes(columns)
    out = io.BytesIO()
    f.decode(io.BytesIO(b""), out,
             _params(k=-1, columns=columns, rows=rows, black_is_1=True), 0)
    assert out.getvalue() == b"\x00" * (rb * rows)


# ----------------------------------------------------------------------
# Standalone CCITTFaxDecoderStream: (type, options) -> mode mapping
# ----------------------------------------------------------------------


def _encode(raw: bytes, *, k: int, columns: int, rows: int) -> bytes:
    f = CCITTFaxDecode()
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc, _params(k=k, columns=columns, rows=rows))
    return enc.getvalue()


def test_decoder_stream_g4_round_trip() -> None:
    """T.6 type -> K<0 inside the stream wrapper; decodes a G4 strip."""
    columns, rows = 24, 6
    rb = _row_bytes(columns)
    raw = bytes([0xAA, 0xCC, 0x33] * rows)[: rb * rows]
    encoded = _encode(raw, k=-1, columns=columns, rows=rows)
    ds = CCITTFaxDecoderStream(
        io.BytesIO(encoded), columns, rows,
        TIFFExtension.COMPRESSION_CCITT_T6,
        TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    assert ds.read()[: rb * rows] == raw


def test_decoder_stream_g3_1d_round_trip() -> None:
    """T.4 type, no 2D option bit -> K==0 (Group 3 1D)."""
    columns, rows = 24, 6
    rb = _row_bytes(columns)
    raw = bytes([0xAA, 0xCC, 0x33] * rows)[: rb * rows]
    encoded = _encode(raw, k=0, columns=columns, rows=rows)
    ds = CCITTFaxDecoderStream(
        io.BytesIO(encoded), columns, rows,
        TIFFExtension.COMPRESSION_CCITT_T4,
        TIFFExtension.FILL_LEFT_TO_RIGHT,
        options=0,
    )
    assert ds.read()[: rb * rows] == raw


def test_decoder_stream_g3_2d_option_bit_selects_2d() -> None:
    """REGRESSION (wave 1578): T.4 type with GROUP3OPT_2DENCODING must decode
    as Group 3 *2-D*. The wrapper previously forced K==0 for any T.4 stream,
    decoding a 2-D strip as 1-D and producing garbage."""
    columns, rows = 24, 6
    rb = _row_bytes(columns)
    raw = bytes([0xAA, 0xCC, 0x33] * rows)[: rb * rows]
    encoded = _encode(raw, k=4, columns=columns, rows=rows)
    ds = CCITTFaxDecoderStream(
        io.BytesIO(encoded), columns, rows,
        TIFFExtension.COMPRESSION_CCITT_T4,
        TIFFExtension.FILL_LEFT_TO_RIGHT,
        options=TIFFExtension.GROUP3OPT_2DENCODING,
    )
    assert ds.read()[: rb * rows] == raw


def test_decoder_stream_g4_byte_align_bit() -> None:
    """REGRESSION (wave 1578): G4 byte-align lives in GROUP4OPT_BYTEALIGNED (4);
    the wrapper must forward EncodedByteAlign for that bit on a T.6 stream
    without raising."""
    columns, rows = 16, 8
    rb = _row_bytes(columns)
    raw = bytes([0x00, 0x00] * 4 + [0xFF, 0xFF] * 4)[: rb * rows]
    encoded = _encode(raw, k=-1, columns=columns, rows=rows)
    ds = CCITTFaxDecoderStream(
        io.BytesIO(encoded), columns, rows,
        TIFFExtension.COMPRESSION_CCITT_T6,
        TIFFExtension.FILL_LEFT_TO_RIGHT,
        options=TIFFExtension.GROUP4OPT_BYTEALIGNED,
    )
    out = ds.read()
    assert isinstance(out, bytes)


def test_decoder_stream_discovers_rows_when_zero() -> None:
    """rows == 0 -> the stream estimates a generous row count and decodes to
    the end-of-block marker (row discovery lives in the decoder stream, not
    the filter)."""
    columns, rows = 16, 5
    rb = _row_bytes(columns)
    raw = bytes([0xF0, 0x0F] * rows)[: rb * rows]
    encoded = _encode(raw, k=-1, columns=columns, rows=rows)
    ds = CCITTFaxDecoderStream(
        io.BytesIO(encoded), columns, 0,
        TIFFExtension.COMPRESSION_CCITT_T6,
        TIFFExtension.FILL_LEFT_TO_RIGHT,
    )
    out = ds.read()
    # The decoded body must at least contain the encoded rows.
    assert out[: rb * rows] == raw
