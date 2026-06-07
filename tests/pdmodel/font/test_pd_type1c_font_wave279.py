from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font import PDFontDescriptor
from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE3 = COSName.get_pdf_name("FontFile3")
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


def test_default_constructor_uses_type1_font_dictionary_shape() -> None:
    font = PDType1CFont()

    assert font.get_type() == "Font"
    assert font.get_subtype() == "Type1"
    assert font.get_name() is None
    assert font.get_font_descriptor() is None
    assert font.get_font_program() is None
    assert font.get_cff_font() is None
    assert font.get_cff_type1_font() is None
    assert font.is_embedded() is False
    assert font.is_damaged() is False
    assert font.get_units_per_em() == 1000


def test_constructor_preserves_existing_subtype_and_base_font_name() -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "Font")
    raw.set_name(_SUBTYPE, "MMType1")
    raw.set_name(_BASE_FONT, "ABCDEF+EmbeddedCFF")

    font = PDType1CFont(raw)

    assert font.get_cos_object() is raw
    assert font.get_subtype() == "MMType1"
    assert font.get_name() == "ABCDEF+EmbeddedCFF"


def test_descriptor_round_trips_font_file3_through_cos_dictionary() -> None:
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Type1C")
    stream.set_data(b"not parsed in this test")
    descriptor = PDFontDescriptor()
    descriptor.set_font_name("EmbeddedCFF")
    descriptor.set_font_file3(stream)

    raw = COSDictionary()
    raw.set_name(_BASE_FONT, "EmbeddedCFF")
    raw.set_item(_FONT_DESCRIPTOR, descriptor.get_cos_object())

    font = PDType1CFont(raw)
    round_tripped = PDType1CFont(font.get_cos_object())
    round_tripped_descriptor = round_tripped.get_font_descriptor()

    assert round_tripped_descriptor is not None
    assert round_tripped_descriptor.get_font_name() == "EmbeddedCFF"
    font_file3 = round_tripped_descriptor.get_font_file3()
    assert font_file3 is not None
    assert font_file3.to_byte_array() == b"not parsed in this test"
    assert stream.get_name(_SUBTYPE) == "Type1C"


def test_set_font_descriptor_none_removes_descriptor() -> None:
    font = PDType1CFont()
    descriptor = PDFontDescriptor()
    descriptor.set_font_file3(COSStream())
    font.set_font_descriptor(descriptor)

    assert font.get_font_descriptor() is not None
    # Wave 1510: an empty /FontFile3 is damaged -> not embedded (matches
    # upstream ``cffFont != null``). The descriptor is still attached; this
    # test's subject is set_font_descriptor(None) removing it, below.
    assert font.is_embedded() is False

    font.set_font_descriptor(None)

    assert font.get_font_descriptor() is None
    assert font.is_embedded() is False
    assert font.get_cos_object().get_dictionary_object(_FONT_DESCRIPTOR) is None


def test_get_font_program_is_cff_backed_and_symmetric_with_setter() -> None:
    font = PDType1CFont()
    cff = CFFFont()
    cff.set_name("InjectedCFF")

    font.set_font_program(cff)

    assert font.get_font_program() is cff
    assert font.get_cff_font() is cff
    assert font.get_cff_type1_font() is cff

    font.set_font_program(None)

    assert font.get_font_program() is None
    assert font.get_cff_font() is None


def test_get_font_program_ignores_type1_font_file_slot() -> None:
    font = PDType1CFont()
    descriptor = PDFontDescriptor()
    type1_stream = COSStream()
    type1_stream.set_data(b"not a Type 1 program")
    descriptor.set_font_file(type1_stream)
    font.set_font_descriptor(descriptor)

    assert font.is_embedded() is False
    assert font.is_damaged() is False
    assert font.get_font_program() is None
    assert font.get_cff_font() is None


def test_defaults_without_encoding_resolve_standard_and_have_empty_glyph_surface() -> None:
    font = PDType1CFont()

    # No /Encoding entry: upstream PDSimpleFont.readEncoding falls back to
    # readEncodingFromFont(), which for a bare PDType1CFont bottoms out at
    # StandardEncoding (verified against the live PDFBox oracle: bare Type1C ->
    # StandardEncoding, 65 -> A). Pre-wave-1434 the encoding was wrongly None
    # and the font fell back to a Latin-1 default (the blank-render bug).
    assert isinstance(font.get_encoding_typed(), StandardEncoding)
    # StandardEncoding round-trips ASCII; code 65 == "A".
    assert font.code_to_name(65) == "A"
    # 'A' encodes to its StandardEncoding code (0x41); '\u00e9' is not in
    # StandardEncoding so it falls back to the '?' substitute byte.
    assert font.encode("A") == b"A"
    assert font.encode("A\u00e9") == b"A?"
    # decode maps each byte through StandardEncoding -> glyph -> unicode;
    # 0xE9 is "Oslash" -> U+00D8.
    assert font.decode(b"A\xe9") == "A\u00d8"
    # No embedded CFF program -> no glyph surface (unchanged by the fix).
    assert font.code_to_gid(65) == 0
    assert font.get_glyph_path(65) == []
    assert font.get_path("A") == []
    assert font.has_glyph("A") is False
    assert font.get_height(65) == 0.0
    assert font.get_average_font_width() == 0.0


def test_winansi_encoding_drives_type1c_code_to_name_without_program() -> None:
    raw = COSDictionary()
    raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(raw)

    assert font.code_to_name(65) == "A"
    assert font.code_to_name(0) is None


def test_malformed_descriptor_shapes_are_treated_as_unembedded() -> None:
    raw = COSDictionary()
    raw.set_item(_FONT_DESCRIPTOR, COSName.get_pdf_name("NotADictionary"))
    font = PDType1CFont(raw)

    assert font.get_font_descriptor() is None
    assert font.is_embedded() is False
    assert font.is_damaged() is False
    assert font.get_font_program() is None

    descriptor_dict = COSDictionary()
    descriptor_dict.set_item(_FONT_FILE3, COSName.get_pdf_name("NotAStream"))
    raw.set_item(_FONT_DESCRIPTOR, descriptor_dict)
    malformed_font_file3 = PDType1CFont(raw)

    assert malformed_font_file3.get_font_descriptor() is not None
    assert malformed_font_file3.is_embedded() is False
    assert malformed_font_file3.is_damaged() is False
    assert malformed_font_file3.get_font_program() is None


def test_unparseable_font_file3_is_damaged_but_safe_to_query() -> None:
    bogus = COSStream()
    bogus.set_name(_SUBTYPE, "Type1C")
    bogus.set_data(b"not a cff program")
    descriptor = PDFontDescriptor()
    descriptor.set_font_file3(bogus)
    font = PDType1CFont()
    font.set_font_descriptor(descriptor)

    # Wave 1510: an unparseable /FontFile3 is damaged, and upstream's
    # ``isEmbedded == cffFont != null`` means a damaged program is NOT
    # embedded (verified vs PDFBox 3.0.7: emb=false dmg=true).
    assert font.is_embedded() is False
    assert font.get_font_program() is None
    assert font.get_cff_font() is None
    assert font.is_damaged() is True
    assert font.get_units_per_em() == 1000
    assert font.get_glyph_width(65) == 0.0


def test_simple_font_subsetting_placeholders_remain_not_implemented() -> None:
    font = PDType1CFont()

    with pytest.raises(NotImplementedError):
        font.add_to_subset(65)

    with pytest.raises(NotImplementedError):
        font.subset()
