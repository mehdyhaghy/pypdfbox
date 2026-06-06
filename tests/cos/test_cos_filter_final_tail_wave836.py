from __future__ import annotations

import io

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.filter import _predictor
from pypdfbox.filter._predictor import decode_predictor_row, predict, unpredict


def test_wave836_cos_float_preserves_exponent_negative_and_plain_format() -> None:
    parsed = COSFloat("1.4e-46")

    assert parsed.float_value() == 0.0
    assert parsed.get_original_form() == "1.4e-46"

    value = COSFloat(-1e100)
    assert value.float_value() == pytest.approx(-3.4028234663852886e38)
    # PDFBox Float.toString(-Float.MAX_VALUE) → "-340282350000…"; the earlier
    # "-…46638528860…" expectation was float64 representation noise unified away
    # in wave 1415/1416 (verified live vs PDFBox in the COS write oracle).
    assert value.format_string() == "-340282350000000000000000000000000000000"


def test_wave836_cos_float_duplicate_internal_negative_is_rejected() -> None:
    # ``0.-26-2`` carries a second interior ``-`` so it matches none of the
    # three malformed-number repair regexes; upstream COSFloat(String) raises
    # IOException "Error expected floating point number actual='0.-26-2'".
    with pytest.raises(OSError, match="Error expected floating point number"):
        COSFloat("0.-26-2")


def test_wave836_cos_float_write_pdf_uses_iso_8859_1_original_bytes() -> None:
    value = COSFloat("2.500")
    output = io.BytesIO()

    value.write_pdf(output)

    assert output.getvalue() == b"2.500"


def test_wave836_decode_predictor_row_unknown_predictor_keeps_row() -> None:
    row = bytearray(b"\x10\x20\x30")

    decode_predictor_row(
        99,
        colors=1,
        bits_per_component=8,
        columns=3,
        actline=row,
        lastline=b"\xff\xff\xff",
    )

    assert row == bytearray(b"\x10\x20\x30")


def test_wave836_png_average_and_paeth_filters_round_trip_multirow_rgb() -> None:
    raw = bytes(
        [
            10,
            20,
            30,
            20,
            30,
            40,
            12,
            21,
            33,
            23,
            35,
            45,
        ]
    )

    for predictor in (13, 14):
        encoded = predict(
            raw,
            predictor=predictor,
            columns=2,
            colors=3,
            bits_per_component=8,
        )

        assert unpredict(
            encoded,
            predictor=predictor,
            columns=2,
            colors=3,
            bits_per_component=8,
        ) == raw


def test_wave836_tiff_predictor_16bit_rgb_round_trip() -> None:
    raw = bytes.fromhex(
        "001000200030"
        "001100230037"
        "002000300040"
        "002100330047"
    )

    encoded = predict(
        raw,
        predictor=2,
        columns=2,
        colors=3,
        bits_per_component=16,
    )

    assert encoded != raw
    assert unpredict(
        encoded,
        predictor=2,
        columns=2,
        colors=3,
        bits_per_component=16,
    ) == raw


def test_wave836_predictor_private_unknown_png_filter_rejections() -> None:
    # ENCODE side: applying an undefined PNG filter tag is a programming error
    # (the encoder only ever picks 0..4), so it still raises.
    with pytest.raises(OSError, match="unknown PNG filter type 7"):
        _predictor._png_apply_filter(7, b"\x01\x02", b"\x00\x00", 1)  # noqa: SLF001

    # DECODE side: an unknown per-row tag (> 4) from a malformed / mis-aligned
    # stream is NOT an error — upstream's decodePredictorRow hits
    # ``default: break`` and writes the row through unchanged. pypdfbox now
    # matches (oracle-verified, wave 1505): tag 7 over two data bytes yields
    # those two bytes verbatim.
    assert unpredict(
        b"\x07\x01\x02", predictor=10, columns=2, colors=1, bits_per_component=8
    ) == b"\x01\x02"
