"""BuiltInEncoding read from a Type 1 /Encoding entry.

Wave 1369 round-out — exercises the fallback path where a Type 1 font has
no /Encoding dictionary on the PDF side and the encoding is reconstructed
from the font program's own ``Encoding`` array. Mirrors upstream
PDType1Font.readEncoding's symbolic-font fallback branch.
"""

from __future__ import annotations

from collections import OrderedDict

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    Encoding,
)


def test_built_in_from_type1_encoding_array() -> None:
    # A Type 1 font's /Encoding array is a 256-entry vector of glyph names.
    # The builtin is constructed from the (index, name) pairs where the name
    # is not ``.notdef``.
    type1_encoding_array = {
        0x20: "space",
        0x21: "exclam",
        0x41: "A",
        0x61: "a",
        0x80: "bullet",
    }
    enc = BuiltInEncoding(type1_encoding_array)
    # Forward map.
    assert enc.get_name(0x20) == "space"
    assert enc.get_name(0x41) == "A"
    assert enc.get_name(0x80) == "bullet"
    # Reverse map.
    assert enc.get_code("A") == 0x41
    assert enc.get_code("space") == 0x20
    # Unmapped slot is ``.notdef``.
    assert enc.get_name(0x42) == ".notdef"


def test_symbolic_dictionary_encoding_inherits_built_in() -> None:
    # Symbolic font with a built-in encoding and no /BaseEncoding entry —
    # the DictionaryEncoding inherits from the built-in.
    built_in = BuiltInEncoding({0x41: "A", 0x42: "B", 0x80: "myglyph"})
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))

    enc = DictionaryEncoding(
        font_encoding=font_enc,
        is_non_symbolic=False,
        built_in=built_in,
    )
    assert enc.get_base_encoding() is built_in
    assert enc.get_name(0x41) == "A"
    assert enc.get_name(0x80) == "myglyph"
    # is_predefined is False — BuiltInEncoding is not a PDF-spec predefined.
    assert enc.is_predefined() is False


def test_built_in_encoding_get_cos_object_unsupported() -> None:
    # Per PDF 32000-1 §9.6.5 a built-in encoding has no PDF representation;
    # serializing one is a logic error.
    import pytest

    enc = BuiltInEncoding({0x41: "A"})
    with pytest.raises(NotImplementedError):
        enc.get_cos_object()


def test_built_in_size_and_iter_codes() -> None:
    od: OrderedDict[int, str] = OrderedDict()
    od[0x41] = "A"
    od[0x42] = "B"
    od[0x43] = "C"
    enc = BuiltInEncoding(od)
    assert enc.size() == 3
    assert len(enc) == 3
    # iter_codes yields in ascending order regardless of insertion order.
    assert list(enc.iter_codes()) == [0x41, 0x42, 0x43]


def test_built_in_is_not_predefined_and_not_font_specific() -> None:
    # BuiltInEncoding sits outside both classification predicates — it is
    # tied to a specific font program but not to one of the Adobe Symbol /
    # ZapfDingbats fonts.
    enc = BuiltInEncoding({0x41: "A"})
    assert enc.is_predefined() is False
    assert enc.is_font_specific() is False
    # Its encoding name is "built-in (TTF)" — outside both predefined sets.
    assert enc.get_encoding_name() == "built-in (TTF)"


def test_built_in_inherits_from_base_encoding() -> None:
    # Sanity: BuiltInEncoding shares the Encoding base contract.
    enc = BuiltInEncoding({0x41: "A"})
    assert isinstance(enc, Encoding)
    # All base predicates flow through.
    assert enc.contains_code(0x41) is True
    assert enc.contains_name("A") is True
    assert enc.contains_code(0xFF) is False


def test_built_in_codes_for_name_returns_all_codes() -> None:
    # When multiple Type 1 /Encoding slots map to the same glyph (a common
    # /bullet pattern for unused slots) the multi-code lookup returns all.
    od = OrderedDict()
    od[0x41] = "A"
    od[0x81] = "bullet"
    od[0x82] = "bullet"
    od[0x83] = "bullet"
    enc = BuiltInEncoding(od)
    assert enc.get_codes_for_name("bullet") == [0x81, 0x82, 0x83]
    # get_code returns the first reverse-mapped code (Java putIfAbsent).
    assert enc.get_code("bullet") == 0x81


def test_built_in_max_code_min_code() -> None:
    enc = BuiltInEncoding({0x20: "space", 0x41: "A", 0xFE: "tail"})
    assert enc.get_min_code() == 0x20
    assert enc.get_max_code() == 0xFE
