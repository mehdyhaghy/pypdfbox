from __future__ import annotations

import io

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.filter import _predictor
from pypdfbox.filter._predictor import calculate_row_length, predict, unpredict


def test_wave826_cos_float_set_value_clears_original_and_clamps() -> None:
    value = COSFloat("2.500")

    value.set_value(1e100)

    assert value.get_original_form() is None
    assert value.float_value() == pytest.approx(3.4028234663852886e38)
    # PDFBox Float.toString(Float.MAX_VALUE) is "3.4028235E38" → plain-string
    # "340282350000…"; the earlier "…46638528860…" expectation was the float64
    # representation noise wave 1415/1416 unified away (verified live vs PDFBox
    # in tests/cos/oracle/test_cos_write_oracle.py).
    assert value.format_string() == "340282350000000000000000000000000000000"


def test_wave826_cos_float_repaired_literal_reformats_not_preserved() -> None:
    # A literal that only parses after malformed-number repair (PDFBOX-2990 /
    # -3500 path) does NOT keep its raw bytes: upstream leaves valueAsString
    # null so the value reformats from the float on output. ``0.00000-33917698``
    # repairs to ``-0.0000033917698`` then serialises as the shortest float32
    # form ``-0.0000033917697`` (verified live vs PDFBox in
    # tests/cos/oracle/test_cos_number_oracle.py).
    value = COSFloat("0.00000-33917698")
    out = io.BytesIO()

    value.write_pdf(out)

    assert value == COSFloat("-0.0000033917698")
    assert value.get_original_form() is None
    assert out.getvalue() == b"-0.0000033917697"


def test_wave826_predictor_row_length_rounds_sub_byte_components() -> None:
    assert calculate_row_length(colors=3, bits_per_component=1, columns=5) == 2
    assert calculate_row_length(colors=4, bits_per_component=4, columns=3) == 6


def test_wave826_predictor_15_selects_up_filter_when_previous_row_matches() -> None:
    raw = b"\x10\x20\x30\x10\x20\x31"

    encoded = predict(raw, predictor=15, columns=3, colors=1, bits_per_component=8)

    assert encoded == b"\x01\x10\x10\x10\x02\x00\x00\x01"
    assert unpredict(encoded, predictor=15, columns=3, colors=1, bits_per_component=8) == raw


def test_wave826_tiff_sub_byte_round_trip_pads_short_final_row() -> None:
    raw = b"\xb1\xf0"

    encoded = predict(raw, predictor=2, columns=5, colors=1, bits_per_component=4)

    assert encoded == b"\xb6\xe1\x00"
    assert unpredict(encoded, predictor=2, columns=5, colors=1, bits_per_component=4) == (
        raw + b"\x00"
    )


def test_wave826_signed_abs_sum_treats_bytes_as_signed() -> None:
    assert _predictor._signed_abs_sum(bytes([0, 1, 127, 128, 200, 255])) == (  # noqa: SLF001
        0 + 1 + 127 + 128 + 56 + 1
    )
