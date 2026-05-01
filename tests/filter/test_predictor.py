"""Tests for the shared PDF predictor encode/decode helpers in
``pypdfbox.filter._predictor`` and the encode-side predictor wiring of
both ``FlateDecode`` and ``LZWDecode``."""

from __future__ import annotations

import io
import random

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FlateDecode, LZWDecode
from pypdfbox.filter._predictor import (
    calculate_row_length,
    decode_predictor_row,
    predict,
    unpredict,
)

ALL_PREDICTORS = [1, 2, 10, 11, 12, 13, 14, 15]
PNG_PREDICTORS = [10, 11, 12, 13, 14, 15]


# ---------- helpers --------------------------------------------------


def _row_bytes(columns: int, colors: int, bits_per_component: int) -> int:
    return (columns * colors * bits_per_component + 7) // 8


def _make_random_image(
    rows: int,
    columns: int,
    colors: int,
    bits_per_component: int,
    seed: int,
) -> bytes:
    """Build deterministic random scanline-aligned image bytes."""
    rb = _row_bytes(columns, colors, bits_per_component)
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(rows * rb))


def _flate_params(
    predictor: int,
    columns: int,
    colors: int = 1,
    bits_per_component: int = 8,
) -> COSDictionary:
    """FlateDecode reads predictor params directly from its parameters dict."""
    p = COSDictionary()
    p.set_int("Predictor", predictor)
    p.set_int("Columns", columns)
    p.set_int("Colors", colors)
    p.set_int("BitsPerComponent", bits_per_component)
    return p


def _lzw_params(
    predictor: int,
    columns: int,
    colors: int = 1,
    bits_per_component: int = 8,
) -> COSDictionary:
    """LZWDecode reads predictor params from a /DecodeParms sub-dict."""
    inner = COSDictionary()
    inner.set_int("Predictor", predictor)
    inner.set_int("Columns", columns)
    inner.set_int("Colors", colors)
    inner.set_int("BitsPerComponent", bits_per_component)
    outer = COSDictionary()
    outer.set_item("DecodeParms", inner)
    return outer


# ---------- direct predict / unpredict round-trips -------------------


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_round_trip_random_8bit_grayscale(predictor: int) -> None:
    columns, colors, bpc = 16, 1, 8
    rows = 5
    raw = _make_random_image(rows, columns, colors, bpc, seed=1234 + predictor)
    encoded = predict(raw, predictor, columns, colors, bpc)
    decoded = unpredict(encoded, predictor, columns, colors, bpc)
    assert decoded == raw


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_round_trip_empty_input(predictor: int) -> None:
    assert predict(b"", predictor, 4, 1, 8) == b""
    assert unpredict(b"", predictor, 4, 1, 8) == b""


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_round_trip_single_row(predictor: int) -> None:
    columns, colors, bpc = 8, 1, 8
    raw = bytes(range(columns))
    encoded = predict(raw, predictor, columns, colors, bpc)
    decoded = unpredict(encoded, predictor, columns, colors, bpc)
    assert decoded == raw


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_round_trip_multi_row_rgb(predictor: int) -> None:
    # RGB image: columns=10, colors=3, bpc=8 -> 30 bytes per row.
    columns, colors, bpc = 10, 3, 8
    rows = 4
    raw = _make_random_image(rows, columns, colors, bpc, seed=42 + predictor)
    encoded = predict(raw, predictor, columns, colors, bpc)
    decoded = unpredict(encoded, predictor, columns, colors, bpc)
    assert decoded == raw


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_round_trip_16bit_grayscale(predictor: int) -> None:
    columns, colors, bpc = 6, 1, 16
    rows = 3
    raw = _make_random_image(rows, columns, colors, bpc, seed=7777 + predictor)
    encoded = predict(raw, predictor, columns, colors, bpc)
    decoded = unpredict(encoded, predictor, columns, colors, bpc)
    assert decoded == raw


@pytest.mark.parametrize("predictor", [1, 2])
def test_round_trip_1bit_smoke(predictor: int) -> None:
    # 1 bit per component, 16 columns -> 2 bytes per row.
    columns, colors, bpc = 16, 1, 1
    raw = bytes([0b10110100, 0b11001010, 0b01010101, 0b11110000])
    encoded = predict(raw, predictor, columns, colors, bpc)
    decoded = unpredict(encoded, predictor, columns, colors, bpc)
    assert decoded == raw


# ---------- predictor 15 picks an actual filter type ----------------


def test_optimum_picks_a_real_tag() -> None:
    # Run optimum on a row that should clearly favor the Sub filter
    # (linear ramp -> Sub gives all-1s, the smallest-magnitude row).
    columns, colors, bpc = 32, 1, 8
    raw = bytes(range(columns))
    encoded = predict(raw, 15, columns, colors, bpc)
    # 1 tag byte per row + columns data bytes.
    assert len(encoded) == columns + 1
    tag = encoded[0]
    # Should be 1 (Sub) or 4 (Paeth) — both reduce a ramp to small deltas.
    assert tag in (1, 2, 3, 4)
    decoded = unpredict(encoded, 15, columns, colors, bpc)
    assert decoded == raw


def test_optimum_constant_row_picks_zero_filter_or_better() -> None:
    # All-zero row: every filter produces all zeros, encoder may pick any.
    columns, colors, bpc = 16, 1, 8
    raw = bytes(2 * columns)  # two zero rows
    encoded = predict(raw, 15, columns, colors, bpc)
    # Each row: 1 tag + columns zeros.
    assert len(encoded) == 2 * (columns + 1)
    decoded = unpredict(encoded, 15, columns, colors, bpc)
    assert decoded == raw


# ---------- unsupported predictor errors ----------------------------


def test_predict_rejects_unknown_predictor() -> None:
    with pytest.raises(OSError):
        predict(b"abcd", 7, 4, 1, 8)


def test_unpredict_rejects_unknown_predictor() -> None:
    with pytest.raises(OSError):
        unpredict(b"abcd", 7, 4, 1, 8)


# ---------- FlateDecode end-to-end via predictor --------------------


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_flate_round_trip_predictor(predictor: int) -> None:
    columns, colors, bpc = 8, 1, 8
    rows = 4
    raw = _make_random_image(rows, columns, colors, bpc, seed=999 + predictor)
    params = _flate_params(predictor, columns, colors, bpc)
    flate = FlateDecode()
    enc = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc, params)
    dec = io.BytesIO()
    flate.decode(io.BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == raw


def test_flate_round_trip_rgb_predictor_15() -> None:
    columns, colors, bpc = 10, 3, 8
    rows = 6
    raw = _make_random_image(rows, columns, colors, bpc, seed=2024)
    params = _flate_params(15, columns, colors, bpc)
    flate = FlateDecode()
    enc = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc, params)
    dec = io.BytesIO()
    flate.decode(io.BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == raw


def test_flate_predictor_1_passthrough_encode() -> None:
    # /Predictor 1 should not invoke any pre-pass.
    flate = FlateDecode()
    params = _flate_params(1, columns=4)
    enc = io.BytesIO()
    flate.encode(io.BytesIO(b"hello world"), enc, params)
    dec = io.BytesIO()
    flate.decode(io.BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == b"hello world"


# ---------- LZWDecode end-to-end via predictor ----------------------


@pytest.mark.parametrize("predictor", ALL_PREDICTORS)
def test_lzw_round_trip_predictor(predictor: int) -> None:
    columns, colors, bpc = 8, 1, 8
    rows = 4
    raw = _make_random_image(rows, columns, colors, bpc, seed=333 + predictor)
    params = _lzw_params(predictor, columns, colors, bpc)
    lzw = LZWDecode()
    enc = io.BytesIO()
    lzw.encode(io.BytesIO(raw), enc, params)
    dec = io.BytesIO()
    lzw.decode(io.BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == raw


def test_lzw_round_trip_rgb_predictor_14() -> None:
    columns, colors, bpc = 10, 3, 8
    rows = 6
    raw = _make_random_image(rows, columns, colors, bpc, seed=1010)
    params = _lzw_params(14, columns, colors, bpc)
    lzw = LZWDecode()
    enc = io.BytesIO()
    lzw.encode(io.BytesIO(raw), enc, params)
    dec = io.BytesIO()
    lzw.decode(io.BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == raw


def test_lzw_predictor_1_passthrough_encode() -> None:
    lzw = LZWDecode()
    params = _lzw_params(1, columns=4)
    enc = io.BytesIO()
    lzw.encode(io.BytesIO(b"hello LZW"), enc, params)
    dec = io.BytesIO()
    lzw.decode(io.BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == b"hello LZW"


# ---------- calculate_row_length parity (Predictor#calculateRowLength) ----


@pytest.mark.parametrize(
    ("colors", "bpc", "columns", "expected"),
    [
        # 8-bit grayscale, 16 columns -> 16 bytes
        (1, 8, 16, 16),
        # 8-bit RGB, 10 columns -> 30 bytes
        (3, 8, 10, 30),
        # 16-bit grayscale, 6 columns -> 12 bytes
        (1, 16, 6, 12),
        # 1-bit grayscale, 17 columns -> ceil(17/8) = 3 bytes
        (1, 1, 17, 3),
        # 4-bit grayscale, 5 columns -> ceil(20/8) = 3 bytes
        (1, 4, 5, 3),
        # zero columns -> zero bytes
        (1, 8, 0, 0),
    ],
)
def test_calculate_row_length_matches_upstream_signature(
    colors: int, bpc: int, columns: int, expected: int
) -> None:
    # Note the (colors, bitsPerComponent, columns) parameter order, which
    # mirrors the Java method.
    assert calculate_row_length(colors, bpc, columns) == expected


# ---------- decode_predictor_row parity ----------------------------------


def test_decode_predictor_row_passthrough_predictor_1() -> None:
    row = bytearray(b"\x01\x02\x03\x04")
    last = bytearray(4)
    decode_predictor_row(1, 1, 8, 4, row, last)
    assert bytes(row) == b"\x01\x02\x03\x04"


def test_decode_predictor_row_png_sub_first_row() -> None:
    # Predictor 11 (PNG Sub): each byte was encoded as cur - left.
    # Encoded ramp 1, 1, 1, 1 -> decoded ramp 1, 2, 3, 4.
    row = bytearray(b"\x01\x01\x01\x01")
    last = bytearray(4)  # zero-filled for first row
    decode_predictor_row(11, 1, 8, 4, row, last)
    assert bytes(row) == b"\x01\x02\x03\x04"


def test_decode_predictor_row_png_up() -> None:
    # Predictor 12 (PNG Up): cur += prior_row[i].
    last = bytearray(b"\x10\x20\x30\x40")
    row = bytearray(b"\x01\x02\x03\x04")
    decode_predictor_row(12, 1, 8, 4, row, last)
    assert bytes(row) == b"\x11\x22\x33\x44"


def test_decode_predictor_row_round_trips_against_bulk_unpredict() -> None:
    # Build a multi-row image, run the bulk unpredict, then replay the
    # same operation row-by-row with decode_predictor_row and ensure we
    # get the same answer. Validates the per-row helper against the
    # already-tested bulk path.
    columns, colors, bpc = 8, 1, 8
    rows = 5
    raw = bytes(range(columns * rows))

    # Encode the whole thing with predictor 12 (PNG Up).
    encoded = predict(raw, 12, columns, colors, bpc)
    expected = unpredict(encoded, 12, columns, colors, bpc)

    # Now reproduce row-by-row through decode_predictor_row.
    rb = calculate_row_length(colors, bpc, columns)
    stride = rb + 1  # +1 for PNG filter-tag byte
    out = bytearray()
    last = bytearray(rb)
    for row_start in range(0, len(encoded), stride):
        tag = encoded[row_start]
        cur = bytearray(encoded[row_start + 1 : row_start + 1 + rb])
        # decode_predictor_row takes the predictor value (10..14),
        # which is tag + 10 per the upstream contract.
        decode_predictor_row(tag + 10, colors, bpc, columns, cur, last)
        out.extend(cur)
        last = cur
    assert bytes(out) == expected


def test_decode_predictor_row_tiff_predictor_2() -> None:
    # Predictor 2 (TIFF) on 8-bit grayscale, 4 columns: encoded row is
    # cur - left, so decoded ramp 1,2,3,4 -> encoded 1,1,1,1.
    row = bytearray(b"\x01\x01\x01\x01")
    last = bytearray(4)
    decode_predictor_row(2, 1, 8, 4, row, last)
    assert bytes(row) == b"\x01\x02\x03\x04"


def test_decode_predictor_row_unknown_predictor_is_noop() -> None:
    # Upstream's switch falls through silently for unknown predictors.
    row = bytearray(b"\x01\x02\x03\x04")
    last = bytearray(4)
    decode_predictor_row(99, 1, 8, 4, row, last)
    assert bytes(row) == b"\x01\x02\x03\x04"
