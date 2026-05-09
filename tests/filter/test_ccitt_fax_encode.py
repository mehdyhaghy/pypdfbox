"""Hand-written tests for ``CCITTFaxDecode.encode``.

The encoder routes raw 1-bit packed scanlines through Pillow's
libtiff Group 3/4 codecs and extracts the encoded strip. Each test
encodes a small bitmap, then round-trips through ``decode()`` to
confirm the output reproduces the input byte-for-byte.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode

# ---------- helpers ---------------------------------------------------


def _params(**kwargs: object) -> COSDictionary:
    """Build a flat decode-params dict (single-filter form)."""
    params = COSDictionary()
    for key, value in kwargs.items():
        if isinstance(value, bool):
            params.set_boolean(key, value)
        elif isinstance(value, int):
            params.set_int(key, value)
        else:  # pragma: no cover - defensive
            raise TypeError(f"unsupported type for {key}: {type(value).__name__}")
    return params


def _round_trip(
    raw: bytes, columns: int, rows: int, *, k: int = -1, **extra: object
) -> bytes:
    params = _params(K=k, Columns=columns, Rows=rows, **extra)
    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()

    dec_buf = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), dec_buf, params)
    return dec_buf.getvalue()


# ---------- 100x100 round-trip (the contract from the task spec) ------


def test_encode_decode_round_trip_100x100() -> None:
    """100x100 1-bit image with a diagonal + every-fourth-column pattern
    survives encode -> decode unchanged."""
    img = Image.new("1", (100, 100), 1)  # white background
    for x in range(100):
        img.putpixel((x, x), 0)
    for x in range(0, 100, 4):
        for y in range(100):
            img.putpixel((x, y), 0)

    raw = img.tobytes()
    decoded = _round_trip(raw, 100, 100)
    assert decoded == raw


def test_encode_decode_round_trip_all_white() -> None:
    img = Image.new("1", (32, 16), 1)
    raw = img.tobytes()
    decoded = _round_trip(raw, 32, 16)
    assert decoded == raw


def test_encode_decode_round_trip_all_black() -> None:
    img = Image.new("1", (32, 16), 0)
    raw = img.tobytes()
    decoded = _round_trip(raw, 32, 16)
    assert decoded == raw


def test_encode_decode_round_trip_non_byte_aligned_width() -> None:
    """13-pixel-wide image forces per-row padding; encode must respect
    Pillow's row stride convention."""
    img = Image.new("1", (13, 7), 1)
    img.putpixel((0, 0), 0)
    img.putpixel((12, 6), 0)
    raw = img.tobytes()
    decoded = _round_trip(raw, 13, 7)
    assert decoded == raw


def test_encode_group3_1d_round_trips() -> None:
    """K=0 emits CCITT Group 3 1D and decodes back through the same
    T.4 path used for existing input files."""
    img = Image.new("1", (32, 16), 1)
    for x in range(32):
        img.putpixel((x, x % 16), 0)
    raw = img.tobytes()

    decoded = _round_trip(raw, 32, 16, k=0)

    assert decoded == raw


def test_encode_compresses_large_uniform_bitmap() -> None:
    """Sanity: G4 should compress a 200x200 all-white bitmap to far
    fewer bytes than the raw 5000-byte payload."""
    img = Image.new("1", (200, 200), 1)
    raw = img.tobytes()  # 200/8 * 200 = 5000 bytes
    enc_buf = io.BytesIO()
    params = _params(K=-1, Columns=200, Rows=200)
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()
    # G4 should crush a uniform bitmap to << 5% of original.
    assert len(encoded) < len(raw) // 20


# ---------- BlackIs1 polarity ----------------------------------------


def test_encode_black_is_1_round_trips() -> None:
    """When /BlackIs1 is set, the input bytes use 1=black/0=white. The
    encoder inverts before passing to libtiff and decode inverts back,
    so the byte-level round-trip still matches."""
    img = Image.new("1", (16, 8), 1)
    img.putpixel((0, 0), 0)
    img.putpixel((15, 7), 0)
    raw = img.tobytes()
    decoded = _round_trip(raw, 16, 8, BlackIs1=True)
    assert decoded == raw


# ---------- error handling -------------------------------------------


def test_encode_missing_columns_raises() -> None:
    params = _params(K=-1, Rows=4)
    with pytest.raises(OSError):
        CCITTFaxDecode().encode(io.BytesIO(b"\x00"), io.BytesIO(), params)


def test_encode_missing_rows_raises() -> None:
    params = _params(K=-1, Columns=8)
    with pytest.raises(OSError):
        CCITTFaxDecode().encode(io.BytesIO(b"\x00"), io.BytesIO(), params)


def test_encode_short_payload_raises() -> None:
    """Declaring more rows than the raw buffer covers is a caller bug."""
    params = _params(K=-1, Columns=64, Rows=64)  # needs 64*8 = 512 bytes
    with pytest.raises(OSError):
        CCITTFaxDecode().encode(io.BytesIO(b"\x00" * 16), io.BytesIO(), params)


def test_encode_group3_2d_not_implemented() -> None:
    """Pillow/libtiff does not expose a stable T.4 2D encoder option."""
    params = _params(K=1, Columns=8, Rows=4)
    with pytest.raises(NotImplementedError):
        CCITTFaxDecode().encode(io.BytesIO(b"\x00" * 4), io.BytesIO(), params)


# ---------- /DecodeParms shapes --------------------------------------


def test_encode_reads_decode_parms_from_stream_dict() -> None:
    """Like decode, encode accepts the *stream dictionary* shape: the
    actual parameters live under /DecodeParms."""
    img = Image.new("1", (8, 4), 1)
    img.putpixel((0, 0), 0)
    raw = img.tobytes()

    inner = _params(K=-1, Columns=8, Rows=4)
    stream_dict = COSDictionary()
    stream_dict.set_item("DecodeParms", inner)

    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, stream_dict)
    encoded = enc_buf.getvalue()
    assert len(encoded) > 0

    dec_buf = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), dec_buf, stream_dict)
    assert dec_buf.getvalue() == raw
