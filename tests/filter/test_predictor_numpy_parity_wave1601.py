"""Wave 1601 — numpy predictor-decode fast paths must be byte-identical.

The PNG/TIFF predictor decode grew numpy fast paths (PNG Sub/Up, TIFF
Predictor 2 for 8/16-bit) to replace per-byte Python loops that taxed every
predictor-compressed image and every /Predictor 12 cross-reference stream.
These tests pin the numpy output to the pure-Python fallback across the full
matrix of {predictor} x {colors} x {bits-per-component} x {columns}, through
both decode surfaces (the one-shot ``unpredict`` bulk path and the row-by-row
``PredictorOutputStream`` used by FlateDecode/LZWDecode).
"""

from __future__ import annotations

import io

import pytest

import pypdfbox.filter._predictor as _predictor
from pypdfbox.filter._predictor import predict, unpredict
from pypdfbox.filter.predictor_output_stream import PredictorOutputStream

PREDICTORS = [2, 10, 11, 12, 13, 14, 15]
COLORS = [1, 3, 4]
BITS = [1, 2, 4, 8, 16]
COLUMNS = [1, 3, 7, 16, 64]


def _row_bytes(columns: int, colors: int, bpc: int) -> int:
    return (columns * colors * bpc + 7) // 8


def _make_raw(columns: int, colors: int, bpc: int, nrows: int = 5) -> bytes:
    rb = _row_bytes(columns, colors, bpc)
    return bytes(
        bytearray(
            (i * 37 + j * 101 + 7) & 0xFF for j in range(nrows) for i in range(rb)
        )
    )


def _stream_decode(encoded: bytes, predictor: int, columns: int, colors: int, bpc: int) -> bytes:
    out = io.BytesIO()
    ps = PredictorOutputStream(out, predictor, colors, bpc, columns)
    ps.write(encoded)
    ps.flush()
    return out.getvalue()


def _decode_all(encoded: bytes, predictor: int, columns: int, colors: int, bpc: int):
    return (
        unpredict(encoded, predictor, columns, colors, bpc),
        _stream_decode(encoded, predictor, columns, colors, bpc),
    )


@pytest.mark.parametrize("predictor", PREDICTORS)
@pytest.mark.parametrize("colors", COLORS)
@pytest.mark.parametrize("bpc", BITS)
@pytest.mark.parametrize("columns", COLUMNS)
def test_numpy_matches_pure_python(predictor, colors, bpc, columns):
    """numpy fast path and pure-Python fallback decode to identical bytes."""
    rb = _row_bytes(columns, colors, bpc)
    if rb == 0:
        pytest.skip("degenerate geometry")
    raw = _make_raw(columns, colors, bpc)
    encoded = predict(raw, predictor, columns, colors, bpc)

    # numpy path (default: _HAS_NP is True in this environment)
    assert _predictor._HAS_NP is True
    np_bulk, np_stream = _decode_all(encoded, predictor, columns, colors, bpc)

    # force the pure-Python fallback and re-decode
    _predictor._HAS_NP = False
    try:
        py_bulk, py_stream = _decode_all(encoded, predictor, columns, colors, bpc)
    finally:
        _predictor._HAS_NP = True

    assert np_bulk == py_bulk
    assert np_stream == py_stream
    # bulk and stream surfaces agree with each other too
    assert np_bulk == np_stream


def test_round_trip_up_and_tiff_8bit():
    """Sanity: predict->decode round-trips for the hot 8-bit Up/TIFF cases."""
    columns, colors, bpc = 64, 3, 8
    raw = _make_raw(columns, colors, bpc)
    for predictor in (12, 2, 11):
        encoded = predict(raw, predictor, columns, colors, bpc)
        assert unpredict(encoded, predictor, columns, colors, bpc) == raw
        assert _stream_decode(encoded, predictor, columns, colors, bpc) == raw
