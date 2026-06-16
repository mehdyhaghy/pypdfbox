"""Wave 1570 (agent B) — predictor apply/unapply fuzz vs upstream arithmetic.

Hammers the per-row PNG predictor filters (None/Sub/Up/Average/Paeth) and
TIFF Predictor 2 horizontal differencing exactly as Apache PDFBox 3.0.7's
``Predictor#decodePredictorRow`` implements them
(``pdfbox/src/main/java/org/apache/pdfbox/filter/Predictor.java``):

* PNG Sub / Up / Average / Paeth round-trips per filter type, per row.
* The Paeth predictor pick (``a + b - c`` then nearest of a/b/c, ties to a
  then b) — exact integer arithmetic and the ``<=`` tie-break chain.
* Average flooring: ``floor((left + up) / 2)`` (Java integer division).
* Multi-byte pixels (Colors=3, BitsPerComponent=8 → bytes-per-pixel=3 byte
  stride for the "left" neighbour lookup).
* Sub-byte BitsPerComponent (1/2/4) with Columns not a byte multiple — row
  byte width = ceil(Columns*Colors*bpc/8) and bytes-per-pixel clamps to 1.
* TIFF Predictor 2 for 8-bit and 16-bit (big-endian) samples and sub-byte
  widths, plus multi-byte stride.
* Mismatched / truncated last row: pypdfbox pads with zeros, matching the
  real ``PredictorOutputStream.flush()`` (Arrays.fill … then decode).

The reference helpers below are line-for-line transcriptions of the upstream
Java so the assertions are an oracle, not a re-derivation of pypdfbox itself.
A live differential run against the PDFBox 3.0.7 jar (``PredictorDecodeProbe``
/ ``PredictorProbe``) over 1150+ random geometries during authoring found
zero divergence; these tests freeze that parity.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.filter._predictor import (
    _bytes_per_pixel,
    _paeth,
    calculate_row_length,
    decode_predictor_row,
    predict,
    unpredict,
)

# ---------------------------------------------------------------------------
# Upstream reference transcriptions (org.apache.pdfbox.filter.Predictor)
# ---------------------------------------------------------------------------


def _ref_bytes_per_pixel(colors: int, bpc: int) -> int:
    """Upstream: ``bytesPerPixel = (colors*bitsPerComponent + 7) / 8``."""
    return (colors * bpc + 7) // 8


def _ref_row_length(colors: int, bpc: int, columns: int) -> int:
    """Upstream ``calculateRowLength``: ``(columns*colors*bpc + 7) / 8``."""
    return (columns * colors * bpc + 7) // 8


def _ref_paeth(a: int, b: int, c: int) -> int:
    """Upstream Paeth pick from predictor 14 (the a/b/c branch)."""
    value = a + b - c
    absa = abs(value - a)
    absb = abs(value - b)
    absc = abs(value - c)
    if absa <= absb and absa <= absc:
        return a
    if absb <= absc:
        return b
    return c


def _ref_decode_row(
    predictor: int,
    colors: int,
    bpc: int,
    columns: int,
    actline: bytearray,
    lastline: bytes,
) -> None:
    """Transcription of ``decodePredictorRow`` for predictors 2 and 10..14."""
    if predictor == 1:
        return
    bpp = _ref_bytes_per_pixel(colors, bpc)
    rowlength = len(actline)
    if predictor == 2:
        if bpc == 8:
            for p in range(bpp, rowlength):
                actline[p] = (actline[p] + actline[p - bpp]) & 0xFF
            return
        if bpc == 16:
            for p in range(bpp, rowlength - 1, 2):
                sub = (actline[p] << 8) + actline[p + 1]
                left = (actline[p - bpp] << 8) + actline[p - bpp + 1]
                actline[p] = ((sub + left) >> 8) & 0xFF
                actline[p + 1] = (sub + left) & 0xFF
            return
        if bpc == 1 and colors == 1:
            for p in range(rowlength):
                for bit in range(7, -1, -1):
                    sub = (actline[p] >> bit) & 1
                    if p == 0 and bit == 7:
                        continue
                    left = (
                        actline[p - 1] & 1
                        if bit == 7
                        else (actline[p] >> (bit + 1)) & 1
                    )
                    if ((sub + left) & 1) == 0:
                        actline[p] &= ~(1 << bit) & 0xFF
                    else:
                        actline[p] |= 1 << bit
            return
        elements = columns * colors
        for p in range(colors, elements):
            byte_pos_sub = p * bpc // 8
            bit_pos_sub = 8 - p * bpc % 8 - bpc
            byte_pos_left = (p - colors) * bpc // 8
            bit_pos_left = 8 - (p - colors) * bpc % 8 - bpc
            mask = (1 << bpc) - 1
            sub = (actline[byte_pos_sub] >> bit_pos_sub) & mask
            left = (actline[byte_pos_left] >> bit_pos_left) & mask
            new_val = (sub + left) & mask
            keep = ~(mask << bit_pos_sub) & 0xFF
            actline[byte_pos_sub] = (actline[byte_pos_sub] & keep) | (
                new_val << bit_pos_sub
            )
        return
    if predictor == 10:
        return
    if predictor == 11:
        for p in range(bpp, rowlength):
            actline[p] = (actline[p] + actline[p - bpp]) & 0xFF
        return
    if predictor == 12:
        for p in range(rowlength):
            actline[p] = (actline[p] + lastline[p]) & 0xFF
        return
    if predictor == 13:
        for p in range(rowlength):
            left = actline[p - bpp] if p - bpp >= 0 else 0
            up = lastline[p]
            actline[p] = (actline[p] + (left + up) // 2) & 0xFF
        return
    if predictor == 14:
        for p in range(rowlength):
            a = actline[p - bpp] if p - bpp >= 0 else 0
            b = lastline[p]
            c = lastline[p - bpp] if p - bpp >= 0 else 0
            actline[p] = (actline[p] + _ref_paeth(a, b, c)) & 0xFF
        return


def _decode_stream(
    data: bytes, predictor: int, colors: int, bpc: int, columns: int
) -> bytes:
    """Drive ``decode_predictor_row`` row-by-row like ``PredictorOutputStream``.

    Mirrors the live ``PredictorDecodeProbe`` loop: PNG rows carry a 1-byte
    filter tag (predictor = 10 + tag); TIFF rows are bare with constant
    predictor 2. The real stream pads a short trailing row with zeros on
    flush; this driver drops it to stay byte-aligned with the probe.
    """
    rowlen = _ref_row_length(colors, bpc, columns)
    if rowlen <= 0:
        return b""
    out = bytearray()
    last = bytearray(rowlen)
    if predictor == 2:
        pos = 0
        while pos + rowlen <= len(data):
            act = bytearray(data[pos : pos + rowlen])
            decode_predictor_row(2, colors, bpc, columns, act, last)
            out += act
            last = act
            pos += rowlen
    else:
        stride = rowlen + 1
        pos = 0
        while pos + stride <= len(data):
            tag = data[pos]
            act = bytearray(data[pos + 1 : pos + 1 + rowlen])
            decode_predictor_row(10 + tag, colors, bpc, columns, act, last)
            out += act
            last = act
            pos += stride
    return bytes(out)


def _ref_decode_stream(
    data: bytes, predictor: int, colors: int, bpc: int, columns: int
) -> bytes:
    """Same loop but driven by the upstream-transcribed ``_ref_decode_row``."""
    rowlen = _ref_row_length(colors, bpc, columns)
    if rowlen <= 0:
        return b""
    out = bytearray()
    last = bytearray(rowlen)
    if predictor == 2:
        pos = 0
        while pos + rowlen <= len(data):
            act = bytearray(data[pos : pos + rowlen])
            _ref_decode_row(2, colors, bpc, columns, act, last)
            out += act
            last = act
            pos += rowlen
    else:
        stride = rowlen + 1
        pos = 0
        while pos + stride <= len(data):
            tag = data[pos]
            act = bytearray(data[pos + 1 : pos + 1 + rowlen])
            _ref_decode_row(10 + tag, colors, bpc, columns, act, last)
            out += act
            last = act
            pos += stride
    return bytes(out)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def test_calculate_row_length_matches_upstream() -> None:
    for colors in (1, 2, 3, 4):
        for bpc in (1, 2, 4, 8, 16):
            for columns in range(1, 33):
                assert calculate_row_length(colors, bpc, columns) == _ref_row_length(
                    colors, bpc, columns
                )


def test_bytes_per_pixel_byte_stride_not_bits() -> None:
    # bpp is the *byte* stride between adjacent pixels, never bits.
    assert _bytes_per_pixel(3, 8) == 3  # RGB8 → 3 bytes
    assert _bytes_per_pixel(1, 16) == 2  # gray16 → 2 bytes
    assert _bytes_per_pixel(4, 8) == 4  # CMYK8 → 4 bytes
    assert _bytes_per_pixel(3, 16) == 6  # RGB16 → 6 bytes
    # Sub-byte pixels clamp the stride up to 1 byte (PNG convention).
    assert _bytes_per_pixel(1, 1) == 1
    assert _bytes_per_pixel(1, 2) == 1
    assert _bytes_per_pixel(1, 4) == 1
    assert _bytes_per_pixel(3, 1) == 1  # 3 bits → still 1 byte
    for colors in (1, 2, 3, 4):
        for bpc in (1, 2, 4, 8, 16):
            assert _bytes_per_pixel(colors, bpc) == _ref_bytes_per_pixel(colors, bpc)


def test_sub_byte_row_width_ceiling() -> None:
    # Columns not a byte multiple: ceil(Columns*Colors*bpc/8).
    assert calculate_row_length(1, 1, 13) == 2  # 13 bits → 2 bytes
    assert calculate_row_length(1, 2, 5) == 2  # 10 bits → 2 bytes
    assert calculate_row_length(1, 4, 3) == 2  # 12 bits → 2 bytes
    assert calculate_row_length(3, 1, 5) == 2  # 15 bits → 2 bytes
    assert calculate_row_length(1, 1, 8) == 1  # exactly 1 byte


# ---------------------------------------------------------------------------
# Paeth exact arithmetic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "c", "expected"),
    [
        (0, 0, 0, 0),
        (10, 20, 30, 10),  # value=0 → |0-10|=10,|0-20|=20,|0-30|=30 → a
        (200, 100, 50, 200),  # value=250 → pa=50,pb=150,pc=200 → a
        (5, 5, 5, 5),  # all equal → ties to a
        (10, 10, 0, 10),  # value=20 → pa=10,pb=10,pc=20; pa<=pb,pa<=pc → a
        (0, 10, 10, 0),  # value=0 → pa=0 → a
        (100, 0, 0, 100),  # value=100 → pa=0 → a
        (0, 100, 0, 100),  # value=100 → pa=100,pb=0 → b
        (0, 0, 100, 0),  # value=-100 → pa=100,pb=100,pc=200 → ties a
        (255, 255, 0, 255),
        (1, 254, 200, 1),  # value=55 → pa=54,pb=199,pc=145 → a
    ],
)
def test_paeth_pick(a: int, b: int, c: int, expected: int) -> None:
    assert _paeth(a, b, c) == expected
    assert _paeth(a, b, c) == _ref_paeth(a, b, c)


def test_paeth_tie_break_chain_matches_upstream() -> None:
    rng = random.Random(20240616)
    for _ in range(4000):
        a = rng.randint(0, 255)
        b = rng.randint(0, 255)
        c = rng.randint(0, 255)
        assert _paeth(a, b, c) == _ref_paeth(a, b, c)


# ---------------------------------------------------------------------------
# Average flooring
# ---------------------------------------------------------------------------


def test_average_floors_division() -> None:
    # Average filter (predictor 13): cur + floor((left+up)/2).
    # left=3, up=2 → floor(5/2)=2, so decoded = (0 + 2) = 2.
    act = bytearray([0])
    decode_predictor_row(13, 1, 8, 1, act, bytes([2]))
    assert act[0] == 1  # left=0 (p<bpp), up=2 → floor(2/2)=1
    # Two-pixel row to exercise a non-zero left.
    act = bytearray([0, 0])
    decode_predictor_row(13, 1, 8, 2, act, bytes([2, 4]))
    # p0: left=0, up=2 → +1 → 1 ; p1: left=act[0]=1, up=4 → floor(5/2)=2 → 2
    assert bytes(act) == bytes([1, 2])


def test_average_odd_sum_floors_not_rounds() -> None:
    # left=255, up=254 → (255+254)//2 = 254 (floor), not 255 (round).
    act = bytearray([0, 0])
    decode_predictor_row(13, 1, 8, 2, act, bytes([0, 254]))
    # p0: left=0, up=0 → 0 ; p1: left=act[0]=0, up=254 → 127
    assert act[1] == 127
    act = bytearray([0, 1])
    decode_predictor_row(13, 1, 8, 2, act, bytes([255, 255]))
    # p0: left=0, up=255 → 127 ; p1: left=127, up=255 → floor(382/2)=191 → 1+191=192
    assert act[0] == 127
    assert act[1] == 192


# ---------------------------------------------------------------------------
# Per-PNG-filter round-trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("predictor", [10, 11, 12, 13, 14, 15])
@pytest.mark.parametrize(
    ("colors", "bpc", "columns"),
    [
        (1, 8, 8),
        (3, 8, 5),  # RGB8, bpp=3 stride
        (4, 8, 4),  # CMYK8, bpp=4
        (1, 16, 4),
        (3, 16, 3),  # RGB16, bpp=6
        (1, 1, 13),  # sub-byte, non-multiple columns
        (1, 2, 5),
        (1, 4, 3),
        (3, 1, 5),  # sub-byte multi-color
    ],
)
def test_png_round_trip(predictor: int, colors: int, bpc: int, columns: int) -> None:
    rng = random.Random(hash((predictor, colors, bpc, columns)) & 0xFFFFFFFF)
    rowlen = calculate_row_length(colors, bpc, columns)
    raw = bytes(rng.randint(0, 255) for _ in range(rowlen * 3))
    enc = predict(raw, predictor, columns, colors, bpc)
    assert unpredict(enc, predictor, columns, colors, bpc) == raw


@pytest.mark.parametrize(
    ("colors", "bpc", "columns"),
    [
        (1, 8, 8),
        (3, 8, 5),
        (4, 8, 4),
        (1, 16, 4),
        (3, 16, 3),
        (1, 1, 13),
        (1, 2, 5),
        (1, 4, 3),
    ],
)
def test_tiff_round_trip(colors: int, bpc: int, columns: int) -> None:
    rng = random.Random(hash(("tiff", colors, bpc, columns)) & 0xFFFFFFFF)
    rowlen = calculate_row_length(colors, bpc, columns)
    raw = bytes(rng.randint(0, 255) for _ in range(rowlen * 3))
    enc = predict(raw, 2, columns, colors, bpc)
    assert unpredict(enc, 2, columns, colors, bpc) == raw


# ---------------------------------------------------------------------------
# TIFF 16-bit big-endian exactness
# ---------------------------------------------------------------------------


def test_tiff_16bit_big_endian_order() -> None:
    # Two 16-bit samples 0x0102, then delta 0x0103 → decoded sample 0x0205.
    act = bytearray([0x01, 0x02, 0x01, 0x03])
    decode_predictor_row(2, 1, 16, 2, act, bytes(4))
    assert bytes(act) == bytes([0x01, 0x02, 0x02, 0x05])


def test_tiff_16bit_wraps_modulo_65536() -> None:
    # prev=0xFFFF, delta=0x0002 → 0x0001.
    act = bytearray([0xFF, 0xFF, 0x00, 0x02])
    decode_predictor_row(2, 1, 16, 2, act, bytes(4))
    assert bytes(act[2:4]) == bytes([0x00, 0x01])


# ---------------------------------------------------------------------------
# Up predictor uses the prior *decoded* row
# ---------------------------------------------------------------------------


def test_up_predictor_uses_prior_row() -> None:
    # Up (predictor 12): cur + lastline[p].
    act = bytearray([5, 6, 7])
    decode_predictor_row(12, 1, 8, 3, act, bytes([10, 20, 30]))
    assert bytes(act) == bytes([15, 26, 37])


def test_up_predictor_chains_across_rows() -> None:
    # Stream of two Up-filtered rows: row2 must use row1's *decoded* output.
    rowlen = 3
    data = bytearray()
    data.append(2)  # tag Up
    data += bytes([1, 2, 3])
    data.append(2)  # tag Up
    data += bytes([4, 5, 6])
    out = _decode_stream(bytes(data), 12, 1, 8, rowlen)
    # row1 (prev zeros): [1,2,3]; row2: [1+4, 2+5, 3+6] = [5,7,9]
    assert out == bytes([1, 2, 3, 5, 7, 9])


# ---------------------------------------------------------------------------
# Truncated / short trailing row padding (matches PredictorOutputStream.flush)
# ---------------------------------------------------------------------------


def test_truncated_last_row_padded_with_zeros() -> None:
    # bulk unpredict pads a short final PNG row to full width, as the real
    # PredictorOutputStream.flush() does (Arrays.fill … then decode).
    rowlen = calculate_row_length(1, 8, 4)  # 4
    data = bytearray()
    data.append(0)  # None
    data += bytes([1, 2, 3, 4])
    data.append(0)  # None
    data += bytes([9, 9])  # short final row (2 of 4 bytes)
    out = unpredict(bytes(data), 12, 4, 1, 8)
    assert len(out) == rowlen * 2  # both rows emitted at full width
    assert out[:rowlen] == bytes([1, 2, 3, 4])
    assert out[rowlen:] == bytes([9, 9, 0, 0])  # short row zero-padded


def test_truncated_tiff_row_padded() -> None:
    rowlen = calculate_row_length(1, 8, 4)  # 4
    raw = bytes([10, 11, 12])  # one short row
    enc = predict(raw, 2, 4, 1, 8)
    dec = unpredict(enc, 2, 4, 1, 8)
    # padded to 4 bytes; first 3 round-trip.
    assert dec[:3] == raw
    assert len(dec) == rowlen


# ---------------------------------------------------------------------------
# Broad randomized differential against the upstream transcription
# ---------------------------------------------------------------------------


def test_decode_stream_matches_upstream_transcription_fuzz() -> None:
    rng = random.Random(15700001)
    checked = 0
    for _ in range(600):
        predictor = rng.choice([2, 10, 11, 12, 13, 14])
        colors = rng.choice([1, 2, 3, 4])
        bpc = rng.choice([1, 2, 4, 8, 16])
        columns = rng.randint(1, 17)
        nrows = rng.randint(1, 4)
        rowlen = calculate_row_length(colors, bpc, columns)
        if rowlen <= 0:
            continue
        if predictor == 2:
            data = bytes(rng.randint(0, 255) for _ in range(rowlen * nrows))
        else:
            buf = bytearray()
            for _ in range(nrows):
                buf.append(rng.randint(0, 4))
                buf += bytes(rng.randint(0, 255) for _ in range(rowlen))
            data = bytes(buf)
        got = _decode_stream(data, predictor, colors, bpc, columns)
        ref = _ref_decode_stream(data, predictor, colors, bpc, columns)
        assert got == ref, (predictor, colors, bpc, columns)
        checked += 1
    assert checked > 400


def test_bulk_unpredict_matches_stream_for_aligned_data() -> None:
    # When data is row-aligned (no truncation), bulk unpredict == the
    # row-by-row stream decode (and thus == upstream).
    rng = random.Random(15700002)
    for _ in range(300):
        predictor = rng.choice([2, 10, 11, 12, 13, 14])
        colors = rng.choice([1, 2, 3, 4])
        bpc = rng.choice([1, 2, 4, 8, 16])
        columns = rng.randint(1, 17)
        nrows = rng.randint(1, 3)
        rowlen = calculate_row_length(colors, bpc, columns)
        if rowlen <= 0:
            continue
        if predictor == 2:
            data = bytes(rng.randint(0, 255) for _ in range(rowlen * nrows))
        else:
            buf = bytearray()
            for _ in range(nrows):
                buf.append(rng.randint(0, 4))
                buf += bytes(rng.randint(0, 255) for _ in range(rowlen))
            data = bytes(buf)
        bulk = unpredict(data, predictor, columns, colors, bpc)
        stream = _decode_stream(data, predictor, colors, bpc, columns)
        assert bulk == stream, (predictor, colors, bpc, columns)


def test_predict_unpredict_round_trip_fuzz() -> None:
    rng = random.Random(15700003)
    for _ in range(300):
        predictor = rng.choice([2, 10, 11, 12, 13, 14, 15])
        colors = rng.choice([1, 2, 3, 4])
        bpc = rng.choice([1, 2, 4, 8, 16])
        columns = rng.randint(1, 15)
        nrows = rng.randint(1, 4)
        rowlen = calculate_row_length(colors, bpc, columns)
        raw = bytes(rng.randint(0, 255) for _ in range(rowlen * nrows))
        enc = predict(raw, predictor, columns, colors, bpc)
        assert unpredict(enc, predictor, columns, colors, bpc) == raw
