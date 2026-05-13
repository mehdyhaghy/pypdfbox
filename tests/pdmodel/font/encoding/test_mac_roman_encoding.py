"""Hand-written tests for the pdmodel ``MacRomanEncoding`` wrapper."""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import Encoding, MacRomanEncoding


def test_singleton_identity():
    assert MacRomanEncoding.INSTANCE is MacRomanEncoding.INSTANCE
    assert isinstance(MacRomanEncoding.INSTANCE, MacRomanEncoding)


def test_encoding_name():
    assert MacRomanEncoding.INSTANCE.get_encoding_name() == "MacRomanEncoding"


def test_get_cos_object():
    cos = MacRomanEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "MacRomanEncoding"


def test_uppercase_letters():
    enc = MacRomanEncoding.INSTANCE
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert enc.get_name(ord(ch)) == ch


def test_lowercase_letters():
    enc = MacRomanEncoding.INSTANCE
    for ch in "abcdefghijklmnopqrstuvwxyz":
        assert enc.get_name(ord(ch)) == ch


def test_digits():
    enc = MacRomanEncoding.INSTANCE
    digits = ["zero", "one", "two", "three", "four",
              "five", "six", "seven", "eight", "nine"]
    for i, name in enumerate(digits):
        assert enc.get_name(0x30 + i) == name


def test_mac_specific_high_codes():
    # MacRoman has a distinct high-code layout, e.g. 0x80 = Adieresis
    # (whereas WinAnsi has Euro at 0x80).
    enc = MacRomanEncoding.INSTANCE
    assert enc.get_name(0x80) == "Adieresis"
    assert enc.get_name(0xA9) == "copyright"


def test_round_trip_get_code():
    enc = MacRomanEncoding.INSTANCE
    assert enc.get_code("A") == 0x41
    assert enc.get_code("Adieresis") == 0x80


def test_factory_resolves_to_singleton():
    assert Encoding.get_instance("MacRomanEncoding") is MacRomanEncoding.INSTANCE
    name = COSName.get_pdf_name("MacRomanEncoding")
    assert Encoding.get_instance(name) is MacRomanEncoding.INSTANCE


def test_unmapped_low_control_returns_notdef():
    assert MacRomanEncoding.INSTANCE.get_name(0x01) == ".notdef"
