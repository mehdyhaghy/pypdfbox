"""Hand-written tests for the pdmodel ``StandardEncoding`` wrapper.

The 256-entry code -> glyph-name table is sourced from the fontbox tier
(``pypdfbox.fontbox.encoding.standard_encoding``); these tests cover the
pdmodel surface — singleton identity, encoding name, COS form,
representative glyphs, and the ``Encoding.get_instance`` factory.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import Encoding, StandardEncoding


def test_singleton_identity():
    a = StandardEncoding.INSTANCE
    b = StandardEncoding.INSTANCE
    assert a is b
    assert isinstance(a, StandardEncoding)
    assert isinstance(a, Encoding)


def test_encoding_name():
    assert StandardEncoding.INSTANCE.get_encoding_name() == "StandardEncoding"
    # Polymorphic getName() with no argument returns the encoding identifier.
    assert StandardEncoding.INSTANCE.get_name() == "StandardEncoding"


def test_get_cos_object_returns_cosname():
    cos = StandardEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "StandardEncoding"


def test_uppercase_letters_map_to_themselves():
    enc = StandardEncoding.INSTANCE
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert enc.get_name(ord(ch)) == ch


def test_lowercase_letters_map_to_themselves():
    enc = StandardEncoding.INSTANCE
    for ch in "abcdefghijklmnopqrstuvwxyz":
        assert enc.get_name(ord(ch)) == ch


def test_digits_map_to_named_glyphs():
    enc = StandardEncoding.INSTANCE
    digit_names = ["zero", "one", "two", "three", "four",
                   "five", "six", "seven", "eight", "nine"]
    for i, name in enumerate(digit_names):
        assert enc.get_name(0x30 + i) == name


def test_unmapped_low_control_codes_return_notdef():
    # Standard encoding leaves codes 0x00 through 0x20 (except space)
    # unmapped per the Adobe specification.
    enc = StandardEncoding.INSTANCE
    assert enc.get_name(0x01) == ".notdef"
    assert enc.get_name(0x10) == ".notdef"


def test_space_is_mapped():
    assert StandardEncoding.INSTANCE.get_name(0x20) == "space"


def test_get_code_round_trip():
    enc = StandardEncoding.INSTANCE
    assert enc.get_code("A") == 0x41
    assert enc.get_code("zero") == 0x30
    assert enc.get_code("space") == 0x20


def test_get_code_unknown_glyph_returns_none():
    assert StandardEncoding.INSTANCE.get_code("xyzzy-not-real") is None


def test_contains_polymorphic():
    enc = StandardEncoding.INSTANCE
    assert enc.contains("A") is True
    assert enc.contains(0x41) is True
    assert enc.contains("xyzzy-not-real") is False
    assert enc.contains(0x01) is False
    # Booleans are not codes.
    assert enc.contains(True) is False


def test_dunder_contains():
    enc = StandardEncoding.INSTANCE
    assert "A" in enc
    assert 0x41 in enc
    assert "xyzzy-not-real" not in enc


def test_factory_resolves_to_singleton():
    assert Encoding.get_instance("StandardEncoding") is StandardEncoding.INSTANCE
    assert Encoding.get_instance(COSName.get_pdf_name("StandardEncoding")) is StandardEncoding.INSTANCE


def test_snapshot_maps_are_independent():
    enc = StandardEncoding.INSTANCE
    m1 = enc.get_code_to_name_map()
    m1[0xFF] = "BOGUS"
    # Mutating snapshot does not corrupt the singleton.
    assert enc.get_name(0xFF) == ".notdef" or enc.get_name(0xFF) != "BOGUS"
