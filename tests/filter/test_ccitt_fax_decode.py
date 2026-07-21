from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode, FilterFactory

# ---------- helpers ----------------------------------------------------


def _g4_strip(image: Image.Image) -> bytes:
    """Encode a 1-bit Pillow image as a Group 4 TIFF and return the
    encoded strip bytes (i.e. just the CCITT payload).

    The raster is bit-inverted before libtiff encodes it: libtiff's fax
    foreground-run convention is the opposite of Apache PDFBox's (and of
    pypdfbox's :meth:`CCITTFaxDecode.encode`, which inverts for the same
    reason), so inverting here produces a stream whose polarity matches
    the PDFBox-anchored decode path — the decoded scanlines then equal the
    source ``image.tobytes()`` (a true round-trip identity)."""
    image = image.point(lambda v: 0 if v else 255)
    buf = io.BytesIO()
    image.save(buf, format="TIFF", compression="group4")
    raw = buf.getvalue()
    # Re-parse to find the strip offset/length so we never assume layout.
    parsed = Image.open(io.BytesIO(raw))
    offsets = parsed.tag_v2[273]
    counts = parsed.tag_v2[279]
    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return raw[offset : offset + count]


def _g3_strip(image: Image.Image, *, two_d: bool = False) -> bytes:
    """Encode a 1-bit Pillow image as a Group 3 TIFF and extract the
    encoded strip. Pillow exposes group3 1D via ``compression='group3'``.

    The raster is bit-inverted before encoding for the same polarity
    reason described in :func:`_g4_strip`."""
    image = image.point(lambda v: 0 if v else 255)
    buf = io.BytesIO()
    image.save(
        buf,
        format="TIFF",
        compression="group3",
    )
    raw = buf.getvalue()
    parsed = Image.open(io.BytesIO(raw))
    offsets = parsed.tag_v2[273]
    counts = parsed.tag_v2[279]
    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return raw[offset : offset + count]


def _decode(encoded: bytes, params: COSDictionary) -> bytes:
    """Run ``CCITTFaxDecode`` and return the decoded scanline bytes."""
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), out, params)
    return out.getvalue()


def _decode_params(**kwargs: object) -> COSDictionary:
    """Build a flat decode-params dict (single-filter form)."""
    params = COSDictionary()
    for key, value in kwargs.items():
        if isinstance(value, bool):
            params.set_boolean(key, value)
        elif isinstance(value, int):
            params.set_int(key, value)
        else:  # pragma: no cover — defensive
            raise TypeError(f"unsupported type for {key}: {type(value).__name__}")
    return params


# ---------- registry --------------------------------------------------


def test_factory_resolves_long_and_short_names() -> None:
    long_filter = FilterFactory.get("CCITTFaxDecode")
    short_filter = FilterFactory.get("CCF")
    assert isinstance(long_filter, CCITTFaxDecode)
    assert long_filter is short_filter


def test_factory_is_registered() -> None:
    assert FilterFactory.is_registered("CCITTFaxDecode")
    assert FilterFactory.is_registered("CCF")


# ---------- G4 round-trip ---------------------------------------------


def test_g4_round_trip_4x4() -> None:
    # 4×4 image: white (PDF "1") everywhere except (0,0).
    img = Image.new("1", (4, 4), 255)
    img.putpixel((0, 0), 0)
    encoded = _g4_strip(img)

    params = _decode_params(K=-1, Columns=4, Rows=4)
    decoded = _decode(encoded, params)
    # 4 columns padded to 1 byte/row × 4 rows = 4 bytes.
    assert decoded == img.tobytes()


def test_g4_round_trip_alternating_pattern() -> None:
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded = _g4_strip(img)

    params = _decode_params(K=-1, Columns=8, Rows=4)
    decoded = _decode(encoded, params)
    # 0xAA repeated for each row (alternating 1010...).
    assert decoded == b"\xaa\xaa\xaa\xaa"


def test_g4_omitted_rows_no_height_raises() -> None:
    """Rows omitted AND no /Height → reconciled rows == 0 → PDFBOX-6189
    (3.0.8) rejects the geometry up front with an IOException (OSError here).

    Formerly (3.0.7 parity) upstream allocated ``(cols+7)/8 * 0 == 0`` bytes
    and emitted nothing; 3.0.8's dimension guard turns that silent empty
    decode into a hard error before any body byte is read. For a real image
    XObject the stream dict always carries /Height, so this "neither
    dimension known" case is synthetic."""
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded = _g4_strip(img)

    params = _decode_params(K=-1, Columns=8)  # /Rows omitted, no /Height
    with pytest.raises(OSError, match=r"Invalid CCITT image dimensions: cols=8, rows=0"):
        _decode(encoded, params)


def test_g4_omitted_rows_uses_height_from_stream_dict() -> None:
    """Rows omitted but /Height present on the stream dict → upstream
    reconciles ``rows = max(0, height)`` and decodes that many scanlines.

    This is the real image-XObject path: /Height always rides on the stream
    dict, so the filter never needs to discover rows."""
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded = _g4_strip(img)

    # /Height on the parameters (stream) dict; /Rows lives in nested
    # /DecodeParms. The filter reads /Height off ``parameters`` directly.
    params = COSDictionary()
    params.set_int("Height", 4)
    dp = COSDictionary()
    dp.set_int("K", -1)
    dp.set_int("Columns", 8)
    params.set_item("DecodeParms", dp)
    decoded = _decode(encoded, params)
    assert decoded == b"\xaa\xaa\xaa\xaa"


# ---------- BlackIs1 polarity -----------------------------------------


def test_g4_black_is_1_inverts_output() -> None:
    img = Image.new("1", (8, 2), 0)
    for x in range(0, 8, 2):
        for y in range(2):
            img.putpixel((x, y), 255)
    encoded = _g4_strip(img)

    default_params = _decode_params(K=-1, Columns=8, Rows=2)
    inverted_params = _decode_params(K=-1, Columns=8, Rows=2, BlackIs1=True)

    default_bytes = _decode(encoded, default_params)
    inverted_bytes = _decode(encoded, inverted_params)

    assert default_bytes == b"\xaa\xaa"
    # Each bit flipped — 0xAA -> 0x55.
    assert inverted_bytes == b"\x55\x55"


# ---------- G3 ---------------------------------------------------------


def test_g3_1d_round_trip() -> None:
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded = _g3_strip(img)

    params = _decode_params(K=0, Columns=8, Rows=4)
    decoded = _decode(encoded, params)
    assert decoded == b"\xaa\xaa\xaa\xaa"


# ---------- /EncodedByteAlign -----------------------------------------


def test_g3_encoded_byte_align_flag_passes_through() -> None:
    """When ``/EncodedByteAlign`` is set, the wrapper sets T4Options bit 2.
    Pillow's libtiff backend accepts and round-trips byte-aligned G3
    streams the same way."""
    img = Image.new("1", (8, 2), 0)
    img.putpixel((0, 0), 255)
    img.putpixel((4, 1), 255)
    encoded = _g3_strip(img)

    # Without the alignment flag the wrapper omits T4Options bit 2 and
    # libtiff decodes the (non-byte-aligned) G3 stream normally.
    params = _decode_params(K=0, Columns=8, Rows=2, EncodedByteAlign=False)
    no_align = _decode(encoded, params)
    assert len(no_align) == 2  # 8 cols / 8 bits × 2 rows

    # With the flag set the wrapper toggles T4Options bit 2; libtiff
    # accepts the option and produces output of the same shape (here we
    # just pin "decode does not raise" — exact bytes depend on whether
    # the encoder emitted byte-aligned EOLs).
    aligned_params = _decode_params(K=0, Columns=8, Rows=2, EncodedByteAlign=True)
    aligned = _decode(encoded, aligned_params)
    assert len(aligned) == 2


# ---------- error handling --------------------------------------------


def test_zero_columns_raises() -> None:
    # PDFBOX-6189 (3.0.8): /Columns == 0 is rejected up front with an
    # IOException (OSError here). Formerly upstream's unchecked
    # ``rowBytes = (columns + 7) / 8`` allocation silently produced an
    # empty buffer; the 3.0.8 dimension guard makes it a hard error.
    params = _decode_params(K=-1, Columns=0, Rows=4)
    with pytest.raises(OSError, match=r"Invalid CCITT image dimensions: cols=0, rows=4"):
        _decode(b"\x00\x01", params)


def test_negative_columns_raises() -> None:
    # /Columns < 0: PDFBOX-6189 (3.0.8) rejects non-positive dimensions with
    # an IOException (OSError here); formerly upstream threw
    # NegativeArraySizeException from the unchecked allocation.
    params = _decode_params(K=-1, Columns=-4, Rows=4)
    with pytest.raises(OSError, match=r"Invalid CCITT image dimensions"):
        _decode(b"\x00\x01", params)


def test_empty_body_zero_fills_to_row_footprint() -> None:
    # Upstream CCITTFaxFilter.decode pre-allocates ``(cols+7)/8 * rows`` and
    # decodes zero rows from an empty stream, then inverts when /BlackIs1 is
    # false — so an empty body with /Rows known yields a WHITE buffer of the
    # full footprint (4 rows × 1 row-byte = 0xFF × 4), NOT zero bytes. Pinned
    # byte-exact vs the live oracle in test_filter_decode_fuzz_oracle.py.
    params = _decode_params(K=-1, Columns=8, Rows=4)
    assert _decode(b"", params) == b"\xff\xff\xff\xff"


def test_empty_body_no_rows_raises() -> None:
    # With no /Rows (and no /Height) the reconciled row count is 0, which
    # PDFBOX-6189 (3.0.8) rejects before the body is even read (formerly an
    # arraySize == 0 allocation yielding zero bytes).
    params = _decode_params(K=-1, Columns=8)  # /Rows omitted
    with pytest.raises(OSError, match=r"Invalid CCITT image dimensions: cols=8, rows=0"):
        _decode(b"", params)


def test_empty_body_black_is_1_zero_fills_black() -> None:
    # /BlackIs1 true skips the inversion, so the zero-decode buffer reads out
    # all 0x00 (black) rather than 0xFF.
    params = _decode_params(K=-1, Columns=8, Rows=4, BlackIs1=True)
    assert _decode(b"", params) == b"\x00\x00\x00\x00"


def test_garbage_payload_zero_fills() -> None:
    # libtiff rejects random non-CCITT bytes, but PDFBox's pure-Java decoder
    # never throws — it decodes zero rows and zero-fills. pypdfbox now matches
    # that lenient contract (libtiff failure -> deterministic zero-fill buffer)
    # instead of raising OSError. Pinned vs the live oracle in
    # test_filter_decode_fuzz_oracle.py.
    params = _decode_params(K=-1, Columns=8, Rows=4)
    assert _decode(b"\x00\x00\x00\x00\x00", params) == b"\xff\xff\xff\xff"


def test_encode_requires_columns_and_rows() -> None:
    """Encode mirrors decode's parameter shape: /DecodeParms must
    declare /Columns and /Rows. A bare call with no parameters fails
    fast rather than guessing geometry."""
    with pytest.raises(OSError):
        CCITTFaxDecode().encode(io.BytesIO(b""), io.BytesIO())
