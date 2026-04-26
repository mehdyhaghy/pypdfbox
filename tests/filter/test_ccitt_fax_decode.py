from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode, FilterFactory

# ---------- helpers ----------------------------------------------------


def _g4_strip(image: Image.Image) -> bytes:
    """Encode a 1-bit Pillow image as a Group 4 TIFF and return the
    encoded strip bytes (i.e. just the CCITT payload)."""
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
    encoded strip. Pillow exposes group3 1D via ``compression='group3'``."""
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


def test_g4_round_trip_omitted_rows() -> None:
    """Rows=0 / missing → libtiff fills our generous wrapper height with
    decoded data plus zero-padding past end-of-data. Real callers should
    supply /Rows; this test pins the behavior so it doesn't regress."""
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded = _g4_strip(img)

    params = _decode_params(K=-1, Columns=8)  # /Rows omitted
    decoded = _decode(encoded, params)
    # The first four rows reproduce the original payload; trailing
    # bytes are zero-padding from libtiff's over-allocated buffer.
    assert decoded[:4] == b"\xaa\xaa\xaa\xaa"
    assert all(b == 0 for b in decoded[4:])


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


def test_invalid_columns_raises() -> None:
    params = _decode_params(K=-1, Columns=0, Rows=4)
    with pytest.raises(OSError):
        _decode(b"\x00\x01", params)


def test_empty_body_returns_empty() -> None:
    params = _decode_params(K=-1, Columns=8, Rows=4)
    assert _decode(b"", params) == b""


def test_garbage_payload_raises() -> None:
    params = _decode_params(K=-1, Columns=8, Rows=4)
    # Random non-CCITT bytes should fail libtiff decode.
    with pytest.raises(OSError):
        _decode(b"\x00\x00\x00\x00\x00", params)


def test_encode_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        CCITTFaxDecode().encode(io.BytesIO(b""), io.BytesIO())
