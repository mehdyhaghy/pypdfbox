"""Tests for the shared PDF predictor encode/decode helpers in
``pypdfbox.filter._predictor`` and the encode-side predictor wiring of
both ``FlateDecode`` and ``LZWDecode``."""

from __future__ import annotations

import io
import random

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FlateDecode, LZWDecode
from pypdfbox.filter._predictor import predict, unpredict

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
