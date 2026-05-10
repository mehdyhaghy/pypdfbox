"""Hand-written tests for DictionaryEncoding predicate / typed-accessor helpers.

Covers ``is_type3``, ``has_base_encoding``, ``get_base_encoding_name``, and
``get_differences_array`` — small ergonomic helpers around the existing
``get_base_encoding`` / ``get_differences`` surface.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    StandardEncoding,
    WinAnsiEncoding,
)

# ---------- has_base_encoding / is_type3 ----------------------------------


def test_writer_path_with_base_has_base_encoding_true():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.has_base_encoding() is True
    assert enc.is_type3() is False


def test_writer_path_no_base_is_type3():
    # Bare DictionaryEncoding() has no base.
    enc = DictionaryEncoding()
    assert enc.has_base_encoding() is False
    assert enc.is_type3() is True


def test_reader_type3_no_implicit_base_is_type3_true():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.is_type3() is True
    assert enc.has_base_encoding() is False


def test_reader_non_symbolic_falls_back_to_standard_has_base():
    # No /BaseEncoding key but is_non_symbolic=True -> StandardEncoding base.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.has_base_encoding() is True
    assert enc.is_type3() is False


def test_reader_symbolic_with_built_in_has_base():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    built_in = BuiltInEncoding({0x41: "X"})
    enc = DictionaryEncoding(
        font_encoding=font_enc, is_non_symbolic=False, built_in=built_in
    )
    assert enc.has_base_encoding() is True
    assert enc.is_type3() is False


def test_set_base_encoding_none_flips_to_type3():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.is_type3() is False
    enc.set_base_encoding(None)
    assert enc.is_type3() is True
    assert enc.has_base_encoding() is False


def test_set_base_encoding_back_flips_off_type3():
    enc = DictionaryEncoding()
    assert enc.is_type3() is True
    enc.set_base_encoding("WinAnsiEncoding")
    assert enc.is_type3() is False
    assert enc.has_base_encoding() is True


# ---------- get_base_encoding_name ----------------------------------------


def test_get_base_encoding_name_winansi():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_base_encoding_name() == "WinAnsiEncoding"


def test_get_base_encoding_name_standard_via_non_symbolic_default():
    # Non-symbolic with no /BaseEncoding -> StandardEncoding.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.get_base_encoding_name() == "StandardEncoding"


def test_get_base_encoding_name_none_for_type3():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_base_encoding_name() is None


def test_get_base_encoding_name_built_in_flavor():
    # Symbolic font with a built-in encoding -> name comes from the built-in.
    built_in = BuiltInEncoding({0x41: "X"})
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(
        font_encoding=font_enc, is_non_symbolic=False, built_in=built_in
    )
    # BuiltInEncoding.get_encoding_name() returns "built-in (TTF)".
    assert enc.get_base_encoding_name() == "built-in (TTF)"


def test_get_base_encoding_name_matches_get_base_encoding_value():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_base_encoding_name() == enc.get_base_encoding().get_encoding_name()


# ---------- get_differences_array -----------------------------------------


def test_get_differences_array_none_when_no_entry():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_differences_array() is None


def test_get_differences_array_returns_underlying_cos_array():
    diffs = COSArray()
    diffs.add(COSInteger.get(0x80))
    diffs.add(COSName.get_pdf_name("myglyph"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    arr = enc.get_differences_array()
    assert arr is diffs
    assert isinstance(arr, COSArray)


def test_get_differences_array_reflects_set_differences_dict_form():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "Aacute", 0x42: "Acircumflex"})
    arr = enc.get_differences_array()
    assert isinstance(arr, COSArray)
    # Coalesced under one leading int marker: [INT(0x41), Aacute, Acircumflex].
    assert arr.size() == 3
    assert isinstance(arr.get_object(0), COSInteger)
    assert isinstance(arr.get_object(1), COSName)
    assert isinstance(arr.get_object(2), COSName)


def test_get_differences_array_reflects_set_differences_cos_array_form():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    arr = COSArray()
    arr.add(COSInteger.get(0x41))
    arr.add(COSName.get_pdf_name("Aacute"))
    enc.set_differences(arr)
    # The same array instance is now exposed via the typed accessor.
    assert enc.get_differences_array() is arr


def test_get_differences_array_consistent_with_get_dictionary_object():
    # Typed accessor agrees with the raw COSDictionary lookup.
    diffs = COSArray()
    diffs.add(COSInteger.get(0x10))
    diffs.add(COSName.get_pdf_name("foo"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    raw = enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Differences")
    )
    assert enc.get_differences_array() is raw


def test_get_differences_array_none_for_type3_without_differences():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_differences_array() is None
    assert enc.is_type3() is True


# ---------- combined helpers behave consistently --------------------------


def test_predicates_agree_writer_with_base():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.has_base_encoding() is True
    assert enc.is_type3() is False
    assert enc.get_base_encoding_name() == "WinAnsiEncoding"
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE


def test_predicates_agree_reader_non_symbolic_default():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.has_base_encoding() is True
    assert enc.is_type3() is False
    assert enc.get_base_encoding_name() == "StandardEncoding"
    assert enc.get_base_encoding() is StandardEncoding.INSTANCE


def test_get_encoding_name_consistent_with_helpers():
    # When is_type3() is True the encoding name is just "differences".
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.is_type3() is True
    assert enc.get_encoding_name() == "differences"

    # Otherwise the name embeds the base encoding's name.
    enc_with_base = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding")
    )
    assert enc_with_base.is_type3() is False
    assert enc_with_base.get_encoding_name() == "WinAnsiEncoding with differences"
    assert enc_with_base.get_base_encoding_name() == "WinAnsiEncoding"
