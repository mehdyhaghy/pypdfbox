"""Hand-written tests for ``CCITTFaxDecode.encode`` with K>0 (mixed
Group 3 2D coding per ITU-T T.4).

Wave 1303 closed the deferred K>0 encode path: libtiff's ``T4Options``
bit 0 (two-dimensional coding) is enabled via Pillow's ``tiffinfo``
hook, so encode now produces a real mixed-2D stream that decode can
round-trip. The K value in PDF/T.4 controls *decoding* framing (how
many 2D-coded lines may follow a 1D-coded reference) and libtiff picks
its own emit-side interval, so any K>0 round-trips through our decoder
under the same wrapper bit.
"""
from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import CCITTFaxDecode


def _params(**kwargs: object) -> COSDictionary:
    params = COSDictionary()
    for key, value in kwargs.items():
        if isinstance(value, bool):
            params.set_boolean(key, value)
        elif isinstance(value, int):
            params.set_int(key, value)
        else:  # pragma: no cover - defensive
            raise TypeError(f"unsupported type for {key}: {type(value).__name__}")
    return params


def _round_trip(raw: bytes, columns: int, rows: int, *, k: int) -> bytes:
    params = _params(K=k, Columns=columns, Rows=rows)
    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()

    dec_buf = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), dec_buf, params)
    return dec_buf.getvalue()


def _pattern_bitmap(width: int, height: int) -> bytes:
    """Build a non-trivial 1-bit bitmap with vertical + diagonal runs.

    Mixed 2D coding shines on bitmaps where consecutive scanlines share
    structure (vertical bars), so the test fixture intentionally has
    enough vertical correlation for the 2D pass to produce a different
    bitstream from pure 1D coding.
    """
    img = Image.new("1", (width, height), 1)
    for x in range(width):
        img.putpixel((x, x % height), 0)
    for x in range(0, width, 4):
        for y in range(height):
            img.putpixel((x, y), 0)
    return img.tobytes()


def test_encode_group3_2d_k1_round_trips() -> None:
    """K=1: maximally aggressive 2D coding (every line after the first
    may reference its predecessor) — round-trip must reproduce the
    input byte-for-byte."""
    raw = _pattern_bitmap(64, 32)

    decoded = _round_trip(raw, 64, 32, k=1)

    assert decoded == raw


def test_encode_group3_2d_k4_round_trips() -> None:
    """K=4: typical mixed 2D coding (every 4th line is 1D-coded) —
    round-trip parity matches K=1 because the decoder doesn't depend
    on the encoder's chosen 2D-line interval."""
    raw = _pattern_bitmap(128, 64)

    decoded = _round_trip(raw, 128, 64, k=4)

    assert decoded == raw


def test_encode_group3_2d_differs_from_1d_for_correlated_bitmap() -> None:
    """For a bitmap with vertical correlation the 2D-coded strip
    should differ from the 1D-coded strip (otherwise libtiff silently
    fell back to 1D-only and the wrapper isn't actually engaging the
    T.4 2D mode)."""
    raw = _pattern_bitmap(128, 64)

    params_1d = _params(K=0, Columns=128, Rows=64)
    params_2d = _params(K=1, Columns=128, Rows=64)
    enc_1d = io.BytesIO()
    enc_2d = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_1d, params_1d)
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_2d, params_2d)

    assert enc_1d.getvalue() != enc_2d.getvalue()


def test_encode_group3_2d_black_is_1_round_trips() -> None:
    """The /BlackIs1 polarity flip applies the same way for K>0 as it
    does for K=0 and K<0."""
    img = Image.new("1", (32, 16), 1)
    img.putpixel((0, 0), 0)
    img.putpixel((31, 15), 0)
    raw = img.tobytes()

    params = _params(K=1, Columns=32, Rows=16, BlackIs1=True)
    enc_buf = io.BytesIO()
    CCITTFaxDecode().encode(io.BytesIO(raw), enc_buf, params)
    encoded = enc_buf.getvalue()

    dec_buf = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(encoded), dec_buf, params)

    assert dec_buf.getvalue() == raw


def test_encode_group3_2d_all_white_round_trips() -> None:
    """Uniform bitmaps are the edge case most likely to surface
    libtiff/EOL framing bugs."""
    img = Image.new("1", (96, 48), 1)
    raw = img.tobytes()

    decoded = _round_trip(raw, 96, 48, k=1)

    assert decoded == raw


def test_encode_group3_2d_non_byte_aligned_width() -> None:
    """13-pixel-wide image with K=1 forces per-row padding; libtiff
    must still emit a coherent 2D stream."""
    img = Image.new("1", (13, 11), 1)
    for i in range(11):
        img.putpixel((i % 13, i), 0)
    raw = img.tobytes()

    decoded = _round_trip(raw, 13, 11, k=1)

    assert decoded == raw
