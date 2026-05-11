"""Tests for :class:`Predictor`, :class:`PredictorOutputStream`."""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import Predictor, PredictorOutputStream


class TestPredictorStatics:
    def test_calculate_row_length_basic(self) -> None:
        # 4 columns × 3 colors × 8 bits = 96 bits = 12 bytes
        assert Predictor.calculate_row_length(3, 8, 4) == 12

    def test_calculate_row_length_rounds_up(self) -> None:
        # 7 columns × 1 color × 1 bit = 7 bits → 1 byte
        assert Predictor.calculate_row_length(1, 1, 7) == 1
        # 9 columns × 1 color × 1 bit = 9 bits → 2 bytes
        assert Predictor.calculate_row_length(1, 1, 9) == 2

    def test_get_bit_seq(self) -> None:
        # Upper nibble of 0b10110000 from bit 4, 4 bits wide → 0b1011 = 11
        assert Predictor.get_bit_seq(0b10110000, 4, 4) == 0b1011

    def test_calc_set_bit_seq(self) -> None:
        # Set the upper nibble of 0b00000000 to 0b1101 at bit 4
        assert Predictor.calc_set_bit_seq(0b00000000, 4, 4, 0b1101) == 0b11010000

    def test_decode_predictor_row_passthrough(self) -> None:
        row = bytearray(b"\x01\x02\x03")
        Predictor.decode_predictor_row(1, 1, 8, 3, row, b"\x00\x00\x00")
        assert bytes(row) == b"\x01\x02\x03"

    def test_decode_predictor_row_sub(self) -> None:
        # PNG Sub: each byte += previous byte (with bpp=1 for 1-color 8bit)
        row = bytearray(b"\x05\x03\x02")  # decode: 5, 5+3=8, 8+2=10
        Predictor.decode_predictor_row(11, 1, 8, 3, row, b"\x00\x00\x00")
        assert bytes(row) == b"\x05\x08\x0a"


class TestPredictorWrapPredictor:
    def test_wrap_returns_passthrough_when_predictor_one(self) -> None:
        sink = io.BytesIO()
        params = COSDictionary()
        params.set_int(COSName.get_pdf_name("Predictor").get_name(), 1)
        result = Predictor.wrap_predictor(sink, params)
        assert result is sink

    def test_wrap_returns_predictor_stream_when_predictor_set(self) -> None:
        sink = io.BytesIO()
        params = COSDictionary()
        params.set_int(COSName.get_pdf_name("Predictor").get_name(), 12)
        params.set_int(COSName.get_pdf_name("Columns").get_name(), 3)
        result = Predictor.wrap_predictor(sink, params)
        assert isinstance(result, PredictorOutputStream)
        del result  # keep sink alive


class TestPredictorOutputStream:
    def test_png_none_strip_tags(self) -> None:
        sink = io.BytesIO()
        pos = PredictorOutputStream(sink, predictor=15, colors=1, bits_per_component=8, columns=3)
        pos.write(b"\x00abc\x00def\x00ghi")
        pos.flush()
        assert sink.getvalue() == b"abcdefghi"
        del pos

    def test_png_sub_decodes(self) -> None:
        sink = io.BytesIO()
        pos = PredictorOutputStream(sink, predictor=15, colors=1, bits_per_component=8, columns=3)
        # Predictor tag 1 = Sub. raw bytes: 5, 3, 2 → decoded: 5, 8, 10
        pos.write(b"\x01\x05\x03\x02")
        pos.flush()
        assert sink.getvalue() == b"\x05\x08\x0a"
        del pos

    def test_write_int_raises(self) -> None:
        sink = io.BytesIO()
        pos = PredictorOutputStream(sink, predictor=2, colors=1, bits_per_component=8, columns=3)
        with pytest.raises(NotImplementedError):
            pos.write(42)
        del pos

    def test_tiff_predictor_decode(self) -> None:
        sink = io.BytesIO()
        pos = PredictorOutputStream(sink, predictor=2, colors=1, bits_per_component=8, columns=3)
        # TIFF Predictor 2 (Sub): bytes 5, 3, 2 → 5, 8, 10
        pos.write(b"\x05\x03\x02")
        pos.flush()
        assert sink.getvalue() == b"\x05\x08\x0a"
        del pos
