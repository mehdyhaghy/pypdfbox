"""Wave 1368 (agent D) — TIFF Predictor 2 (horizontal differencing).

PDF predictor 2 mirrors TIFF 6.0 §14: each sample subtracts the previous
sample of the same colour component within the same row, modulo the
sample width. Rows are not coupled (unlike PNG predictors 12..14).

Covered:

* 8-bit gray (Colors=1, Bits=8): canonical case.
* 8-bit RGB (Colors=3, Bits=8): bpp=3, so 'left' is the same-channel
  sample three bytes back.
* 16-bit gray (Colors=1, Bits=16): two-byte big-endian samples.
* 16-bit RGB (Colors=3, Bits=16): six-byte stride per pixel.
* 4-bit gray (Bits=4): sub-byte component widths via ``_untiff_bits``.
* 1-bit (Bits=1): pathological narrow width.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FlateDecode
from pypdfbox.filter._predictor import predict, unpredict


def _params(predictor: int, columns: int, colors: int,
            bits_per_component: int) -> COSDictionary:
    p = COSDictionary()
    p.set_int("Predictor", predictor)
    p.set_int("Columns", columns)
    p.set_int("Colors", colors)
    p.set_int("BitsPerComponent", bits_per_component)
    return p


def test_tiff_predictor_8bit_gray_known_vector() -> None:
    """Canonical small case: row [10, 11, 12, 13] → diffs [10, 1, 1, 1]."""
    raw = bytes([10, 11, 12, 13])
    enc = predict(raw, 2, columns=4, colors=1, bits_per_component=8)
    assert enc == bytes([10, 1, 1, 1])
    dec = unpredict(enc, 2, columns=4, colors=1, bits_per_component=8)
    assert dec == raw


def test_tiff_predictor_8bit_rgb_known_vector() -> None:
    """RGB row: 2 pixels of 3 bytes each. Diff is per-channel."""
    # Pixel 0: (10, 20, 30), pixel 1: (15, 25, 35).
    # After TIFF predictor 2: pixel 0 unchanged, pixel 1 channels are
    # subtracted from same channel of pixel 0 → (5, 5, 5).
    raw = bytes([10, 20, 30, 15, 25, 35])
    enc = predict(raw, 2, columns=2, colors=3, bits_per_component=8)
    assert enc == bytes([10, 20, 30, 5, 5, 5])
    dec = unpredict(enc, 2, columns=2, colors=3, bits_per_component=8)
    assert dec == raw


def test_tiff_predictor_8bit_wraparound() -> None:
    """Subtraction wraps modulo 256."""
    # 5 - 200 = -195 mod 256 = 61.
    raw = bytes([200, 5])
    enc = predict(raw, 2, columns=2, colors=1, bits_per_component=8)
    assert enc == bytes([200, 61])
    assert unpredict(enc, 2, columns=2, colors=1, bits_per_component=8) == raw


def test_tiff_predictor_16bit_gray_round_trip() -> None:
    """16-bit samples — big-endian, two bytes per sample."""
    # Pixel 0: 0x0102, pixel 1: 0x0205, pixel 2: 0x0308.
    raw = bytes([0x01, 0x02, 0x02, 0x05, 0x03, 0x08])
    enc = predict(raw, 2, columns=3, colors=1, bits_per_component=16)
    # Diff to previous: 0x0205-0x0102=0x0103, 0x0308-0x0205=0x0103
    assert enc[0:2] == bytes([0x01, 0x02])
    assert enc[2:4] == bytes([0x01, 0x03])
    assert enc[4:6] == bytes([0x01, 0x03])
    dec = unpredict(enc, 2, columns=3, colors=1, bits_per_component=16)
    assert dec == raw


def test_tiff_predictor_16bit_wraparound() -> None:
    """16-bit subtraction wraps modulo 65536."""
    # 0x0001 - 0xFFFF = -65534 mod 65536 = 2
    raw = bytes([0xFF, 0xFF, 0x00, 0x01])
    enc = predict(raw, 2, columns=2, colors=1, bits_per_component=16)
    assert enc[2:4] == bytes([0x00, 0x02])
    dec = unpredict(enc, 2, columns=2, colors=1, bits_per_component=16)
    assert dec == raw


def test_tiff_predictor_16bit_rgb_round_trip() -> None:
    """16-bit RGB — bpp = 6 (3 colors * 2 bytes)."""
    raw = bytes((i * 7 + 3) & 0xFF for i in range(24))  # 2 pixels × 6 bytes × 2 rows
    enc = predict(raw, 2, columns=2, colors=3, bits_per_component=16)
    dec = unpredict(enc, 2, columns=2, colors=3, bits_per_component=16)
    assert dec == raw


def test_tiff_predictor_4bit_gray_round_trip() -> None:
    """Sub-byte width (4 bits): exercises ``_untiff_bits``."""
    raw = bytes([0x12, 0x34, 0x56, 0x78])  # 8 samples of 4 bits
    enc = predict(raw, 2, columns=8, colors=1, bits_per_component=4)
    dec = unpredict(enc, 2, columns=8, colors=1, bits_per_component=4)
    assert dec == raw


def test_tiff_predictor_1bit_round_trip() -> None:
    """1-bit width: sample mask = 1, exercises the narrowest bit path."""
    raw = bytes([0xAA, 0x55, 0xFF])  # 24 bits = 24 samples
    enc = predict(raw, 2, columns=24, colors=1, bits_per_component=1)
    dec = unpredict(enc, 2, columns=24, colors=1, bits_per_component=1)
    assert dec == raw


def test_tiff_predictor_multi_row_independence() -> None:
    """Rows do NOT carry state to each other for predictor 2."""
    # Two identical rows: TIFF Predictor 2 produces identical encoded rows.
    row = bytes([1, 5, 9, 13])
    raw = row + row
    enc = predict(raw, 2, columns=4, colors=1, bits_per_component=8)
    # Both rows should encode the same — confirming no cross-row state.
    assert enc[:4] == enc[4:]
    dec = unpredict(enc, 2, columns=4, colors=1, bits_per_component=8)
    assert dec == raw


def test_flate_decode_tiff_predictor_round_trip() -> None:
    """End-to-end FlateDecode + TIFF predictor 2."""
    raw = bytes((i * 11 + 7) & 0xFF for i in range(80))  # 10 rows of 8 bytes
    f = FlateDecode()
    params = _params(2, columns=8, colors=1, bits_per_component=8)
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc, params)
    dec = io.BytesIO()
    f.decode(io.BytesIO(enc.getvalue()), dec, params, 0)
    assert dec.getvalue() == raw


def test_flate_decode_tiff_predictor_16bit_round_trip() -> None:
    raw = bytes((i * 31) & 0xFF for i in range(48))  # 6 rows of 8 bytes (4 samples × 16-bit)
    f = FlateDecode()
    params = _params(2, columns=4, colors=1, bits_per_component=16)
    enc = io.BytesIO()
    f.encode(io.BytesIO(raw), enc, params)
    dec = io.BytesIO()
    f.decode(io.BytesIO(enc.getvalue()), dec, params, 0)
    assert dec.getvalue() == raw
