from __future__ import annotations

import pytest

from pypdfbox.filter import _predictor
from pypdfbox.filter._predictor import decode_predictor_row, predict, unpredict


def test_decode_predictor_row_empty_row_returns_before_geometry_validation() -> None:
    row = bytearray()

    decode_predictor_row(
        11,
        colors=0,
        bits_per_component=0,
        columns=0,
        actline=row,
        lastline=b"",
    )

    assert row == bytearray()


def test_decode_predictor_row_png_none_is_noop() -> None:
    row = bytearray(b"\x10\x20\x30")

    decode_predictor_row(10, 1, 8, 3, row, b"\xff\xff\xff")

    assert row == bytearray(b"\x10\x20\x30")


def test_decode_predictor_row_png_average_uses_decoded_left_byte() -> None:
    row = bytearray([10, 20, 30])
    previous = bytes([2, 4, 6])

    decode_predictor_row(13, 1, 8, 3, row, previous)

    assert row == bytearray([11, 27, 46])


def test_decode_predictor_row_png_paeth_matches_bulk_filter_round_trip() -> None:
    raw = bytes([10, 20, 40, 80])
    previous = bytes([7, 19, 41, 79])
    row = bytearray(_predictor._png_apply_filter(4, raw, previous, 1))

    decode_predictor_row(14, 1, 8, 4, row, previous)

    assert row == bytearray(raw)


def test_unpredict_png_short_final_row_is_zero_padded() -> None:
    assert unpredict(b"\x00\x7f", 10, columns=4, colors=1, bits_per_component=8) == (
        b"\x7f\x00\x00\x00"
    )


def test_unpredict_png_unknown_filter_type_raises() -> None:
    with pytest.raises(OSError, match="unknown PNG filter type 5"):
        unpredict(b"\x05abcd", 10, columns=4, colors=1, bits_per_component=8)


def test_tiff_encode_pads_short_final_row_before_delta_encoding() -> None:
    assert predict(b"\x01\x02", 2, columns=4, colors=1, bits_per_component=8) == (
        b"\x01\x01\xfe\x00"
    )


def test_png_encode_pads_short_final_row_after_filter_tag() -> None:
    assert predict(b"\x01\x02", 10, columns=4, colors=1, bits_per_component=8) == (
        b"\x00\x01\x02\x00\x00"
    )


def test_private_zero_width_guards_return_empty_bytes() -> None:
    assert _predictor._unpng(b"\x00", row_bytes=0, bytes_per_pixel=1) == b""
    assert _predictor._tiff_encode(b"\x01", 0, 1, 8) == b""
    assert _predictor._png_encode(b"\x01", 10, 0, 1, 8) == b""


def test_png_apply_filter_rejects_unknown_tag() -> None:
    with pytest.raises(OSError, match="unknown PNG filter type 9"):
        _predictor._png_apply_filter(9, b"\x01", b"\x00", 1)
