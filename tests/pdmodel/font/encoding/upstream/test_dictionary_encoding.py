"""Ported upstream-style tests for ``DictionaryEncoding``.

Upstream PDFBox 3.0 has limited dedicated unit coverage for
``DictionaryEncoding`` — it is exercised primarily through the font test
suite (Type 1, Type 3, TrueType). These tests exercise the same contract
surface a direct upstream test would have asserted, in the same style as
the upstream JUnit tests for sibling encoding classes.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    Encoding,
    StandardEncoding,
    WinAnsiEncoding,
)

# -- writer / embedding path -----------------------------------------------


def test_empty_dictionary_encoding_has_type_entry():
    enc = DictionaryEncoding()
    cos = enc.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "Encoding"


def test_writer_path_with_base_encoding_only():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    # Codes flow through from the base encoding.
    assert enc.get_name(0x41) == "A"
    # /BaseEncoding entry exists on the wire.
    cos = enc.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("BaseEncoding")) == "WinAnsiEncoding"


def test_writer_path_with_base_and_differences():
    diffs = COSArray()
    diffs.add(COSInteger.get(0x80))
    diffs.add(COSName.get_pdf_name("myglyph"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    # Base entries flow through.
    assert enc.get_name(0x41) == "A"
    # Differences override.
    assert enc.get_name(0x80) == "myglyph"
    assert enc.get_differences() == {0x80: "myglyph"}


# -- reader path: Type 3 (no implicit base) --------------------------------


def test_reader_type3_no_implicit_base():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_base_encoding() is None
    # Without a base, all codes are .notdef.
    assert enc.get_name(0x41) == ".notdef"


def test_reader_type3_with_differences_only():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    diffs.add(COSInteger.get(0x20))
    diffs.add(COSName.get_pdf_name("space"))
    diffs.add(COSName.get_pdf_name("a"))  # auto-incremented to 0x21
    diffs.add(COSName.get_pdf_name("b"))  # auto-incremented to 0x22
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_name(0x20) == "space"
    assert enc.get_name(0x21) == "a"
    assert enc.get_name(0x22) == "b"
    # No base, so anything not in differences is .notdef.
    assert enc.get_name(0x41) == ".notdef"


# -- reader path: non-symbolic (defaults to StandardEncoding) --------------


def test_reader_non_symbolic_defaults_to_standard():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.get_base_encoding() is StandardEncoding.INSTANCE
    # Inherits Standard encoding.
    assert enc.get_name(0x41) == "A"
    assert enc.get_name(0x65) == "e"


def test_reader_non_symbolic_explicit_base_overrides_default():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    # Explicit /BaseEncoding wins over the non-symbolic default.
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE


# -- reader path: symbolic with built-in encoding --------------------------


def test_reader_symbolic_uses_built_in_encoding():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    built_in = BuiltInEncoding({0x41: "X", 0x42: "Y"})
    enc = DictionaryEncoding(
        font_encoding=font_enc,
        is_non_symbolic=False,
        built_in=built_in,
    )
    # Symbolic font with no /BaseEncoding -> inherits built-in.
    assert enc.get_base_encoding() is built_in
    assert enc.get_name(0x41) == "X"
    assert enc.get_name(0x42) == "Y"


def test_reader_symbolic_explicit_base_overrides_built_in():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    built_in = BuiltInEncoding({0x41: "X"})
    enc = DictionaryEncoding(
        font_encoding=font_enc,
        is_non_symbolic=False,
        built_in=built_in,
    )
    # Explicit /BaseEncoding wins over the built-in.
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE


# -- /Differences parsing edge cases ---------------------------------------


def test_differences_with_multiple_runs():
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    # First run: starting at 0x10, two glyphs.
    diffs.add(COSInteger.get(0x10))
    diffs.add(COSName.get_pdf_name("glyphA"))
    diffs.add(COSName.get_pdf_name("glyphB"))
    # Second run: starting at 0x80, one glyph.
    diffs.add(COSInteger.get(0x80))
    diffs.add(COSName.get_pdf_name("glyphC"))
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_name(0x10) == "glyphA"
    assert enc.get_name(0x11) == "glyphB"
    assert enc.get_name(0x80) == "glyphC"
    # Slots between runs are still .notdef.
    assert enc.get_name(0x12) == ".notdef"
    assert enc.get_differences() == {
        0x10: "glyphA",
        0x11: "glyphB",
        0x80: "glyphC",
    }


def test_differences_glyph_before_integer_is_ignored():
    # A name at the start with no preceding integer must be silently dropped
    # (matches upstream parser behavior — code starts at -1).
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    diffs.add(COSName.get_pdf_name("orphan"))  # ignored: no preceding int
    diffs.add(COSInteger.get(0x20))
    diffs.add(COSName.get_pdf_name("space"))
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_name(0x20) == "space"
    assert "orphan" not in enc.get_name_to_code_map()


def test_differences_overwrites_base_glyph():
    # Base provides 0x41 -> "A"; differences override to "Aacute". The reverse
    # mapping for "A" must also be cleaned up because it pointed to 0x41.
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
    assert enc.get_name(0x41) == "Aacute"
    # Reverse map for the displaced "A" should no longer resolve to 0x41.
    assert enc.get_code("A") != 0x41 or enc.get_code("A") is None


# -- COS round-trip --------------------------------------------------------


def test_get_cos_object_returns_underlying_dict():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    cos1 = enc.get_cos_object()
    cos2 = enc.get_cos_object()
    # Same dict on each call.
    assert cos1 is cos2
    # to_cos_object alias agrees.
    assert enc.to_cos_object() is cos1


def test_set_differences_dict_form_coalesces_runs():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "Aacute", 0x42: "Acircumflex", 0x80: "myglyph"})
    arr = enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Differences")
    )
    assert isinstance(arr, COSArray)
    # 0x41/0x42 should coalesce under one integer marker; 0x80 starts a new run.
    # Layout: [INT(0x41), NAME(Aacute), NAME(Acircumflex), INT(0x80), NAME(myglyph)]
    assert arr.size() == 5
    assert isinstance(arr.get_object(0), COSInteger)
    assert isinstance(arr.get_object(1), COSName)
    assert isinstance(arr.get_object(2), COSName)
    assert isinstance(arr.get_object(3), COSInteger)
    assert isinstance(arr.get_object(4), COSName)


# -- Encoding factory ------------------------------------------------------


def test_get_instance_with_unknown_name_returns_none():
    assert Encoding.get_instance("DoesNotExistEncoding") is None


def test_get_instance_with_none_returns_none():
    assert Encoding.get_instance(None) is None
