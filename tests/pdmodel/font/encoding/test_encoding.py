from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    Encoding,
    MacExpertEncoding,
    MacRomanEncoding,
    StandardEncoding,
    SymbolEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)

# ---------- predefined singletons -----------------------------------------


def test_predefined_encodings_have_singleton_instance():
    classes = [
        StandardEncoding,
        WinAnsiEncoding,
        MacRomanEncoding,
        MacExpertEncoding,
        SymbolEncoding,
        ZapfDingbatsEncoding,
    ]
    for cls in classes:
        # Singleton attribute exists and is an instance of the class.
        assert isinstance(cls.INSTANCE, cls)
        # Re-fetching returns the same object (Java parity).
        assert cls.INSTANCE is cls.INSTANCE


def test_predefined_encoding_names():
    assert StandardEncoding.INSTANCE.get_encoding_name() == "StandardEncoding"
    assert WinAnsiEncoding.INSTANCE.get_encoding_name() == "WinAnsiEncoding"
    assert MacRomanEncoding.INSTANCE.get_encoding_name() == "MacRomanEncoding"
    assert MacExpertEncoding.INSTANCE.get_encoding_name() == "MacExpertEncoding"
    assert SymbolEncoding.INSTANCE.get_encoding_name() == "SymbolEncoding"
    assert ZapfDingbatsEncoding.INSTANCE.get_encoding_name() == "ZapfDingbatsEncoding"


def test_predefined_encoding_get_cos_object_returns_cosname():
    cos = WinAnsiEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "WinAnsiEncoding"


# ---------- basic glyph mappings ------------------------------------------


def test_win_ansi_get_name_basic_ascii():
    assert WinAnsiEncoding.INSTANCE.get_name(0x41) == "A"
    assert WinAnsiEncoding.INSTANCE.get_name(0x61) == "a"
    assert WinAnsiEncoding.INSTANCE.get_name(0x30) == "zero"


def test_standard_get_name_lowercase_e():
    assert StandardEncoding.INSTANCE.get_name(0x65) == "e"


def test_unmapped_code_returns_notdef():
    # Standard encoding leaves many low control codes unmapped.
    assert StandardEncoding.INSTANCE.get_name(0x01) == ".notdef"


def test_zapf_dingbats_does_not_use_text_glyph_names():
    # Zapf Dingbats overrides ASCII range with dingbat names (a1, a2, ...).
    assert ZapfDingbatsEncoding.INSTANCE.get_name(0x21) == "a1"
    # Confirm it is NOT the Latin "exclam" glyph.
    assert ZapfDingbatsEncoding.INSTANCE.get_name(0x21) != "exclam"


def test_contains_name_and_code():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.contains_name("A") is True
    assert enc.contains_name("not-a-real-glyph-xyzzy") is False
    assert enc.contains_code(0x41) is True


def test_code_to_name_and_name_to_code_maps_are_snapshots():
    m1 = WinAnsiEncoding.INSTANCE.get_code_to_name_map()
    m2 = WinAnsiEncoding.INSTANCE.get_code_to_name_map()
    assert m1 == m2
    # Mutating the snapshot must not affect the encoding.
    m1[0x41] = "BOGUS"
    assert WinAnsiEncoding.INSTANCE.get_name(0x41) == "A"

    name_map = WinAnsiEncoding.INSTANCE.get_name_to_code_map()
    assert name_map["A"] == 0x41


# ---------- Encoding.get_instance factory ---------------------------------


def test_get_instance_resolves_predefined_names():
    assert Encoding.get_instance("WinAnsiEncoding") is WinAnsiEncoding.INSTANCE
    assert Encoding.get_instance("StandardEncoding") is StandardEncoding.INSTANCE
    assert Encoding.get_instance(COSName.get_pdf_name("MacRomanEncoding")) is MacRomanEncoding.INSTANCE
    assert Encoding.get_instance("BogusEncoding") is None
    assert Encoding.get_instance(None) is None


# ---------- DictionaryEncoding --------------------------------------------


def test_dictionary_encoding_round_trip_add():
    enc = DictionaryEncoding()
    enc.add(0x80, "myglyph")
    assert enc.get_name(0x80) == "myglyph"
    assert enc.get_code("myglyph") == 0x80
    assert enc.contains_name("myglyph") is True


def test_dictionary_encoding_get_cos_object_returns_dict():
    enc = DictionaryEncoding()
    cos = enc.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "Encoding"


def test_dictionary_encoding_with_base_winansi_inherits_codes():
    base_name = COSName.get_pdf_name("WinAnsiEncoding")
    enc = DictionaryEncoding(base_encoding=base_name)
    # Inherited from WinAnsi base.
    assert enc.get_name(0x41) == "A"
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    # /BaseEncoding written back to the dictionary.
    assert enc.get_cos_object().get_name(COSName.get_pdf_name("BaseEncoding")) == "WinAnsiEncoding"


def test_dictionary_encoding_differences_overlay_base():
    # Construct a font encoding dictionary by hand: WinAnsi base + override 0x41.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    diffs = COSArray()
    diffs.add(COSInteger.get(0x41))
    diffs.add(COSName.get_pdf_name("Aacute"))
    diffs.add(COSName.get_pdf_name("Acircumflex"))  # auto-incremented to 0x42
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.get_name(0x41) == "Aacute"
    assert enc.get_name(0x42) == "Acircumflex"
    # Untouched code still inherited from WinAnsi.
    assert enc.get_name(0x61) == "a"
    # Differences map records what was overridden.
    assert enc.get_differences() == {0x41: "Aacute", 0x42: "Acircumflex"}


def test_dictionary_encoding_non_symbolic_falls_back_to_standard():
    # No /BaseEncoding key: non-symbolic path -> StandardEncoding.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.get_base_encoding() is StandardEncoding.INSTANCE
    assert enc.get_name(0x65) == "e"


def test_dictionary_encoding_type3_no_implicit_base():
    # No flags passed -> Type 3 mode -> no implicit base encoding.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_base_encoding() is None
    # Without a base, all codes are .notdef unless added via differences.
    assert enc.get_name(0x41) == ".notdef"
