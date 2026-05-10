from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    Encoding,
    StandardEncoding,
    WinAnsiEncoding,
)

# ---------- Encoding base parity ------------------------------------------


def test_standard_encoding_contains_name_uppercase_a():
    assert StandardEncoding.INSTANCE.contains_name("A") is True


def test_standard_encoding_contains_code_0x41():
    assert StandardEncoding.INSTANCE.contains_code(0x41) is True


def test_standard_encoding_does_not_contain_unknown_glyph():
    assert StandardEncoding.INSTANCE.contains_name("xyzzy-not-a-glyph") is False


def test_standard_encoding_does_not_contain_unmapped_code():
    # Standard encoding leaves 0x01 unmapped.
    assert StandardEncoding.INSTANCE.contains_code(0x01) is False


def test_get_name_no_arg_returns_encoding_name():
    # Polymorphic get_name(): no argument -> encoding identifier.
    assert StandardEncoding.INSTANCE.get_name() == "StandardEncoding"
    assert WinAnsiEncoding.INSTANCE.get_name() == "WinAnsiEncoding"


def test_get_name_with_code_returns_glyph_name():
    assert WinAnsiEncoding.INSTANCE.get_name(0x41) == "A"


def test_get_name_with_unmapped_code_returns_notdef():
    # Upstream getName(int) returns ".notdef" for unmapped codes (never None).
    assert StandardEncoding.INSTANCE.get_name(0x01) == ".notdef"


def test_get_code_returns_int_for_known_glyph():
    code = WinAnsiEncoding.INSTANCE.get_code("A")
    assert code == 0x41


def test_get_code_returns_none_for_unknown_glyph():
    assert WinAnsiEncoding.INSTANCE.get_code("xyzzy-not-a-glyph") is None


def test_get_code_repeated_lookup_stable():
    # Reverse lookup is map-backed; repeated calls stay consistent.
    enc = WinAnsiEncoding.INSTANCE
    first = enc.get_code("A")
    second = enc.get_code("A")
    assert first == second == 0x41


def test_get_code_to_name_map_matches_get_name_to_code_map_inverse():
    enc = StandardEncoding.INSTANCE
    code_to_name = enc.get_code_to_name_map()
    name_to_code = enc.get_name_to_code_map()
    # Every code -> name pair is reflected in name -> code (with possible
    # collisions resolved to the first-added code, matching putIfAbsent).
    for code, name in code_to_name.items():
        assert name in name_to_code
        assert name_to_code[name] == code or code_to_name[name_to_code[name]] == name


def test_to_glyph_name_returns_name():
    assert WinAnsiEncoding.INSTANCE.to_glyph_name(0x41) == "A"


def test_to_glyph_name_falls_back_to_notdef():
    assert StandardEncoding.INSTANCE.to_glyph_name(0x01) == ".notdef"


# ---------- DictionaryEncoding round-trip ---------------------------------


def test_dictionary_encoding_round_trip_via_differences_and_base_encoding():
    # Build wire-form font encoding dict: WinAnsi base + 0x41 -> Aacute.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    diffs = COSArray()
    diffs.add(COSInteger.get(0x41))
    diffs.add(COSName.get_pdf_name("Aacute"))
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)

    # base_encoding is exposed.
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    # differences map is exposed.
    assert enc.get_differences() == {0x41: "Aacute"}
    # to_cos_object alias returns the same dictionary as get_cos_object.
    assert enc.to_cos_object() is enc.get_cos_object()
    assert isinstance(enc.to_cos_object(), COSDictionary)


def test_dictionary_encoding_get_name_unmapped_returns_notdef():
    # Type 3 mode (no implicit base) -> all codes start unmapped.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    # Upstream getName(int) returns ".notdef" for unmapped, never None.
    assert enc.get_name(0x41) == ".notdef"
    # to_glyph_name agrees.
    assert enc.to_glyph_name(0x41) == ".notdef"


def test_dictionary_encoding_set_base_encoding_with_cos_name():
    enc = DictionaryEncoding()
    enc.set_base_encoding(COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    cos = enc.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("BaseEncoding")) == "WinAnsiEncoding"


def test_dictionary_encoding_set_base_encoding_with_string():
    enc = DictionaryEncoding()
    enc.set_base_encoding("StandardEncoding")
    assert enc.get_base_encoding() is StandardEncoding.INSTANCE


def test_dictionary_encoding_set_base_encoding_with_encoding_instance():
    enc = DictionaryEncoding()
    enc.set_base_encoding(WinAnsiEncoding.INSTANCE)
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    cos = enc.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("BaseEncoding")) == "WinAnsiEncoding"


def test_dictionary_encoding_set_base_encoding_none_removes_entry():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    enc.set_base_encoding(None)
    assert enc.get_base_encoding() is None
    cos = enc.get_cos_object()
    assert cos.get_dictionary_object(COSName.get_pdf_name("BaseEncoding")) is None


def test_dictionary_encoding_set_differences_from_dict_round_trip():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "Aacute", 0x42: "Acircumflex", 0x80: "myglyph"})
    # Differences view reflects the new entries.
    diffs = enc.get_differences()
    assert diffs == {0x41: "Aacute", 0x42: "Acircumflex", 0x80: "myglyph"}
    # Underlying COSArray is updated.
    arr = enc.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Differences"))
    assert isinstance(arr, COSArray)


def test_dictionary_encoding_set_differences_from_cos_array():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    arr = COSArray()
    arr.add(COSInteger.get(0x41))
    arr.add(COSName.get_pdf_name("Aacute"))
    enc.set_differences(arr)
    assert enc.get_differences() == {0x41: "Aacute"}
    assert enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Differences")
    ) is arr


# ---------- Encoding.get_instance factory parity --------------------------


def test_encoding_get_instance_returns_singleton():
    # get_instance must return the same module-level singleton each call.
    a = Encoding.get_instance("StandardEncoding")
    b = Encoding.get_instance("StandardEncoding")
    assert a is b is StandardEncoding.INSTANCE
