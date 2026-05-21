"""Tests ported from PDFBox 3.0 ``PredictorTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/filter/PredictorTest.java``
on the apache/pdfbox 3.0 branch. Exercises the package-private
``Predictor#getBitSeq`` and ``Predictor#calcSetBitSeq`` helpers used by
the predictor decoder when ``BitsPerComponent`` is sub-byte.
"""

from __future__ import annotations

from pypdfbox.filter.predictor import Predictor


def test_get_bit_seq() -> None:
    """Port of ``PredictorTest#testGetBitSeq``."""
    assert Predictor.get_bit_seq(0b11111111, 0, 8) == 0b11111111
    assert Predictor.get_bit_seq(0b00000000, 0, 8) == 0b00000000
    assert Predictor.get_bit_seq(0b11111111, 0, 1) == 0b1
    assert Predictor.get_bit_seq(0b00000000, 0, 1) == 0b0
    assert Predictor.get_bit_seq(0b00110001, 0, 3) == 0b001
    assert Predictor.get_bit_seq(0b10101010, 0, 8) == 0b10101010
    assert Predictor.get_bit_seq(0b10101010, 0, 2) == 0b10
    assert Predictor.get_bit_seq(0b10101010, 1, 2) == 0b01
    assert Predictor.get_bit_seq(0b10101010, 2, 2) == 0b10
    assert Predictor.get_bit_seq(0b10101010, 3, 3) == 0b101
    assert Predictor.get_bit_seq(0b10101010, 1, 7) == 0b1010101
    assert Predictor.get_bit_seq(0b10101010, 3, 2) == 0b01
    assert Predictor.get_bit_seq(0b00110001, 0, 8) == 0b00110001
    assert Predictor.get_bit_seq(0b00110001, 0, 5) == 0b10001
    assert Predictor.get_bit_seq(0b00110001, 4, 4) == 0b0011
    assert Predictor.get_bit_seq(0b00110001, 3, 3) == 0b110
    assert Predictor.get_bit_seq(0b00110001, 6, 2) == 0b00
    assert Predictor.get_bit_seq(0b11110000, 4, 4) == 0b1111
    assert Predictor.get_bit_seq(0b11110000, 6, 2) == 0b11
    assert Predictor.get_bit_seq(0b11110000, 0, 4) == 0b0000


def test_calc_set_bit_seq() -> None:
    """Port of ``PredictorTest#testCalcSetBitSeq``."""
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 8, 0) == 0b00000000
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 8, 1) == 0b00000001
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 1, 1) == 0b11111111
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 2, 1) == 0b11111101
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 3, 1) == 0b11111001
    assert Predictor.calc_set_bit_seq(0b00000000, 0, 2, 1) == 0b00000001
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 4, 1) == 0b11110001
    assert Predictor.calc_set_bit_seq(0b11111111, 1, 4, 1) == 0b11100011
    assert Predictor.calc_set_bit_seq(0b00000000, 1, 1, 1) == 0b00000010
    assert Predictor.calc_set_bit_seq(0b11111111, 7, 1, 1) == 0b11111111
    assert Predictor.calc_set_bit_seq(0b11111111, 7, 1, 0) == 0b01111111
    assert Predictor.calc_set_bit_seq(0b00000000, 7, 1, 1) == 0b10000000
    assert Predictor.calc_set_bit_seq(0b00000000, 7, 1, 0) == 0b00000000
    assert Predictor.calc_set_bit_seq(0b00000000, 6, 1, 1) == 0b01000000
    assert Predictor.calc_set_bit_seq(0b00000000, 6, 1, 0) == 0b00000000
    assert Predictor.calc_set_bit_seq(0b00000000, 3, 3, 6) == 0b00110000
    assert Predictor.calc_set_bit_seq(0b00000000, 4, 3, 6) == 0b01100000
    assert Predictor.calc_set_bit_seq(0b00000000, 5, 3, 6) == 0b11000000
    assert Predictor.calc_set_bit_seq(0b00000000, 0, 8, 0xFF) == 0b11111111
    assert Predictor.calc_set_bit_seq(0b11111111, 0, 8, 0xFF) == 0b11111111
    assert Predictor.calc_set_bit_seq(0xA5, 0, 8, 0xD9 + 0xA5) == 0x7E

    # check truncation
    assert Predictor.calc_set_bit_seq(0b00000000, 1, 1, 3) == 0b00000010
