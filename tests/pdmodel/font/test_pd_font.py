from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font import (
    PDFont,
    PDFontDescriptor,
    PDFontFactory,
    PDSimpleFont,
    PDTrueTypeFont,
    PDType0Font,
    PDType1Font,
)
from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_FIXED_PITCH,
    FLAG_ITALIC,
)

# ---------- subtype scaffolding ----------


def test_type1_font_construction_sets_type_and_subtype() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "Type1"  # type: ignore[attr-defined]
    assert font.get_subtype() == "Type1"


def test_true_type_font_construction_sets_type_and_subtype() -> None:
    font = PDTrueTypeFont()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert font.get_subtype() == "TrueType"


def test_type0_font_construction_sets_type_and_subtype() -> None:
    font = PDType0Font()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert font.get_subtype() == "Type0"


def test_pdfont_wraps_existing_dict_without_overwriting_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "TrueType")  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font = PDType1Font(raw)
    # Existing subtype is preserved when wrapping a pre-built dict.
    assert font.get_subtype() == "TrueType"
    assert font.get_name() == "Helvetica"


# ---------- PDSimpleFont accessors ----------


def test_simple_font_widths_and_char_range() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 34)
    widths = COSArray([COSInteger.get(250), COSInteger.get(333), COSFloat(408.5)])
    cos.set_item(COSName.get_pdf_name("Widths"), widths)

    assert font.get_first_char() == 32
    assert font.get_last_char() == 34
    assert font.get_widths() == [250.0, 333.0, 408.5]


def test_simple_font_get_encoding_returns_raw_cos() -> None:
    font = PDType1Font()
    enc = COSName.get_pdf_name("WinAnsiEncoding")
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    assert font.get_encoding() is enc


def test_simple_font_widths_default_empty() -> None:
    font = PDTrueTypeFont()
    assert font.get_widths() == []
    assert font.get_first_char() == -1


# ---------- PDSimpleFont encode / decode ----------


def _font_with_encoding(name: str) -> PDType1Font:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name(name)
    )
    return font


def test_simple_font_get_encoding_typed_resolves_winansi() -> None:
    from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding

    font = _font_with_encoding("WinAnsiEncoding")
    typed = font.get_encoding_typed()
    assert typed is WinAnsiEncoding.INSTANCE
    # Cached on second access.
    assert font.get_encoding_typed() is typed


def test_simple_font_get_encoding_typed_falls_back_to_builtin_when_absent() -> None:
    # No /Encoding entry: upstream PDSimpleFont.readEncoding falls back to
    # readEncodingFromFont(), which for a bare PDType1Font (no embedded
    # program, no AFM) bottoms out at StandardEncoding — verified against the
    # live PDFBox oracle (BuiltinEncodingProbe: bare Type1 -> StandardEncoding,
    # 65 -> A). Previously this returned None (the wave-1434 blank-render bug).
    encoding = PDType1Font().get_encoding_typed()
    assert isinstance(encoding, StandardEncoding)
    assert encoding.get_name(65) == "A"


def test_simple_font_encode_winansi_ascii() -> None:
    font = _font_with_encoding("WinAnsiEncoding")
    assert font.encode("ABC") == b"\x41\x42\x43"


def test_simple_font_decode_winansi_ascii() -> None:
    font = _font_with_encoding("WinAnsiEncoding")
    assert font.decode(b"\x41\x42\x43") == "ABC"


def test_simple_font_encode_without_encoding_falls_back_to_latin1() -> None:
    font = PDType1Font()
    assert font.encode("ABC") == b"\x41\x42\x43"


def test_simple_font_decode_without_encoding_falls_back_to_latin1() -> None:
    font = PDType1Font()
    assert font.decode(b"\x41\x42\x43") == "ABC"


def test_simple_font_encode_symbol_alpha() -> None:
    font = _font_with_encoding("SymbolEncoding")
    # 'alpha' lives at code 0o141 (0x61) in the Adobe Symbol Encoding.
    assert font.encode("α") == bytes([0o141])


def test_simple_font_decode_symbol_alpha() -> None:
    font = _font_with_encoding("SymbolEncoding")
    assert font.decode(bytes([0o141])) == "α"


def test_simple_font_round_trip_ascii_winansi() -> None:
    font = _font_with_encoding("WinAnsiEncoding")
    text = "Hello, World!"
    assert font.decode(font.encode(text)) == text


def test_simple_font_round_trip_ascii_standard() -> None:
    font = _font_with_encoding("StandardEncoding")
    text = "ABC abc 123"
    assert font.decode(font.encode(text)) == text


# ---------- PDType0Font descendant fonts ----------


def test_type0_font_get_descendant_font_returns_none_when_absent() -> None:
    font = PDType0Font()
    assert font.get_descendant_font() is None


def test_type0_font_get_descendant_font_returns_first_dict() -> None:
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    font = PDType0Font()
    descendant = COSDictionary()
    descendant.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "Arial")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("DescendantFonts"), COSArray([descendant])
    )
    out = font.get_descendant_font()
    assert isinstance(out, PDCIDFontType2)
    assert out.get_cos_object() is descendant


# ---------- PDFontDescriptor round-trips ----------


def test_font_descriptor_round_trip_basic_fields() -> None:
    fd = PDFontDescriptor()
    fd.set_font_name("Helvetica-Bold")
    fd.set_flags(FLAG_FIXED_PITCH | FLAG_ITALIC)
    fd.set_ascent(718.0)
    fd.set_descent(-207.0)
    bbox = COSArray(
        [COSInteger.get(-170), COSInteger.get(-228), COSInteger.get(1003), COSInteger.get(962)]
    )
    fd.set_font_b_box(bbox)

    # Round-trip via a fresh wrapper over the same dict.
    fd2 = PDFontDescriptor(fd.get_cos_object())
    assert fd2.get_font_name() == "Helvetica-Bold"
    assert fd2.get_flags() == FLAG_FIXED_PITCH | FLAG_ITALIC
    assert fd2.get_ascent() == 718.0
    assert fd2.get_descent() == -207.0
    assert fd2.get_font_b_box() is bbox


def test_font_descriptor_more_metrics_round_trip() -> None:
    fd = PDFontDescriptor()
    fd.set_cap_height(700.0)
    fd.set_x_height(523.0)
    fd.set_italic_angle(-12.0)
    fd.set_stem_v(88.0)
    assert fd.get_cap_height() == 700.0
    assert fd.get_x_height() == 523.0
    assert fd.get_italic_angle() == -12.0
    assert fd.get_stem_v() == 88.0


def test_font_descriptor_flag_helpers() -> None:
    fd = PDFontDescriptor()
    assert fd.is_fixed_pitch() is False
    assert fd.is_italic() is False

    fd.set_fixed_pitch(True)
    assert fd.is_fixed_pitch() is True
    assert fd.get_flags() & FLAG_FIXED_PITCH == FLAG_FIXED_PITCH

    fd.set_italic(True)
    assert fd.is_italic() is True
    assert fd.get_flags() == FLAG_FIXED_PITCH | FLAG_ITALIC

    # Clearing one flag leaves the other intact.
    fd.set_fixed_pitch(False)
    assert fd.is_fixed_pitch() is False
    assert fd.is_italic() is True


def test_font_descriptor_constructor_writes_type_for_fresh_dict() -> None:
    fd = PDFontDescriptor()
    assert fd.get_cos_object().get_name(COSName.TYPE) == "FontDescriptor"  # type: ignore[attr-defined]


def test_font_descriptor_constructor_does_not_overwrite_existing_dict_type() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Custom")  # type: ignore[attr-defined]
    fd = PDFontDescriptor(raw)
    # Wrapping an existing dict must not stomp the /Type entry.
    assert fd.get_cos_object().get_name(COSName.TYPE) == "Custom"  # type: ignore[attr-defined]


# ---------- PDFontDescriptor descriptive entries ----------


def test_font_descriptor_font_family_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_family() is None
    fd.set_font_family("Helvetica")
    assert fd.get_font_family() == "Helvetica"
    fd.set_font_family(None)
    assert fd.get_font_family() is None
    assert fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontFamily")) is None


def test_font_descriptor_font_stretch_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_stretch() is None
    fd.set_font_stretch("Condensed")
    assert fd.get_font_stretch() == "Condensed"
    # /FontStretch is a name, not a string — verify the COS type.
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontStretch"))
    assert isinstance(raw, COSName)
    fd.set_font_stretch(None)
    assert fd.get_font_stretch() is None


def test_font_descriptor_font_weight_round_trip_and_default() -> None:
    fd = PDFontDescriptor()
    # Default when absent must be 0.
    assert fd.get_font_weight() == 0
    fd.set_font_weight(700)
    assert fd.get_font_weight() == 700.0
    fd.set_font_weight(400.0)
    assert fd.get_font_weight() == 400.0


def test_font_descriptor_char_set_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_char_set() is None
    fd.set_char_set("/A/B/space")
    assert fd.get_char_set() == "/A/B/space"
    fd.set_char_set(None)
    assert fd.get_char_set() is None


# ---------- PDFontDescriptor /FontFile* PDStream accessors ----------


def test_font_descriptor_font_file2_wraps_cos_stream_round_trip() -> None:
    fd = PDFontDescriptor()
    cos = COSStream()
    cos.set_raw_data(b"\x00\x01TTF-bytes")
    fd.set_font_file2(cos)

    pd = fd.get_font_file2()
    assert isinstance(pd, PDStream)
    # The PDStream must wrap the same underlying COSStream we stored.
    assert pd.get_cos_object() is cos

    # Setting via PDStream must store the underlying COSStream verbatim.
    fd2 = PDFontDescriptor()
    fd2.set_font_file2(PDStream(cos))
    assert (
        fd2.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontFile2")) is cos
    )


def test_font_descriptor_font_file_and_file3_round_trip_and_set_none_removes() -> None:
    fd = PDFontDescriptor()

    # /FontFile (Type 1)
    pfb_stream = COSStream()
    pfb_stream.set_raw_data(b"PFB-bytes")
    fd.set_font_file(pfb_stream)
    out1 = fd.get_font_file()
    assert isinstance(out1, PDStream)
    assert out1.get_cos_object() is pfb_stream

    # /FontFile3 (CFF / OpenType)
    cff_stream = COSStream()
    cff_stream.set_raw_data(b"CFF-bytes")
    fd.set_font_file3(cff_stream)
    out3 = fd.get_font_file3()
    assert isinstance(out3, PDStream)
    assert out3.get_cos_object() is cff_stream

    # set_font_file*(None) must remove the entry on each variant.
    fd.set_font_file(None)
    fd.set_font_file3(None)
    assert fd.get_font_file() is None
    assert fd.get_font_file3() is None
    cos = fd.get_cos_object()
    assert cos.get_dictionary_object(COSName.get_pdf_name("FontFile")) is None
    assert cos.get_dictionary_object(COSName.get_pdf_name("FontFile3")) is None


def test_font_descriptor_font_file_accessors_return_none_when_absent() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_file() is None
    assert fd.get_font_file2() is None
    assert fd.get_font_file3() is None


# ---------- PDFont <-> PDFontDescriptor wiring ----------


def test_pdfont_get_set_font_descriptor_round_trip() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_name("Times-Roman")
    fd.set_ascent(683.0)
    font.set_font_descriptor(fd)

    out = font.get_font_descriptor()
    assert isinstance(out, PDFontDescriptor)
    assert out.get_cos_object() is fd.get_cos_object()
    assert out.get_font_name() == "Times-Roman"
    assert out.get_ascent() == 683.0


def test_pdfont_set_font_descriptor_none_removes_entry() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    font.set_font_descriptor(fd)
    assert font.get_font_descriptor() is not None
    font.set_font_descriptor(None)
    assert font.get_font_descriptor() is None


def test_pdfont_get_font_descriptor_none_when_absent() -> None:
    assert PDType1Font().get_font_descriptor() is None


# ---------- PDFontFactory dispatch ----------


def test_font_factory_dispatches_type1() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert out.get_cos_object() is raw


def test_font_factory_dispatches_true_type() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "TrueType")  # type: ignore[attr-defined]
    assert isinstance(PDFontFactory.create_font(raw), PDTrueTypeFont)


def test_font_factory_dispatches_type0() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    assert isinstance(PDFontFactory.create_font(raw), PDType0Font)


def test_font_factory_raises_for_top_level_cid_font_subtype() -> None:
    # A CIDFont is only legal as a /Type0 descendant; a top-level
    # /CIDFontType0 dict raises (upstream IOException -> pypdfbox OSError),
    # matching PDFBox PDFontFactory.createFont.
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "CIDFontType0")  # type: ignore[attr-defined]
    with pytest.raises(OSError, match="Type 0 descendant font not allowed"):
        PDFontFactory.create_font(raw)


# ---------- inheritance sanity ----------


def test_inheritance_chain() -> None:
    assert issubclass(PDSimpleFont, PDFont)
    assert issubclass(PDType1Font, PDSimpleFont)
    assert issubclass(PDTrueTypeFont, PDSimpleFont)
    assert issubclass(PDType0Font, PDFont)
    assert not issubclass(PDType0Font, PDSimpleFont)


# ---------- upstream-faithful name parity (Wave 1251) ----------


def test_get_sub_type_matches_get_subtype() -> None:
    """``getSubType`` snake-cases to ``get_sub_type`` per parity rules."""
    font = PDType1Font()
    assert font.get_sub_type() == font.get_subtype()
    assert font.get_sub_type() == "Type1"


def test_get_sub_type_returns_none_when_subtype_absent() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    font = PDType1Font(raw)
    # PDType1Font's __init__ writes /Subtype only on a fresh dict — wrapping
    # an existing dict without /Subtype leaves it absent.
    raw.remove_item(COSName.SUBTYPE)  # type: ignore[attr-defined]
    assert font.get_sub_type() is None


def test_get_to_unicode_c_map_alias_returns_same_instance() -> None:
    """``getToUnicodeCMap`` snake-cases to ``get_to_unicode_c_map``."""
    font = PDType1Font()
    raw_cmap = COSName.get_pdf_name("Identity-H")
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), raw_cmap)
    first = font.get_to_unicode_c_map()
    second = font.get_to_unicode_cmap()
    assert first is second  # both spellings share the cache


def test_get_to_unicode_c_map_returns_none_when_absent() -> None:
    assert PDType1Font().get_to_unicode_c_map() is None


def test_load_font_descriptor_returns_wrapper_when_present() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_name("Helvetica-Bold")
    font.set_font_descriptor(fd)
    out = font.load_font_descriptor()
    assert isinstance(out, PDFontDescriptor)
    assert out.get_cos_object() is fd.get_cos_object()


def test_load_font_descriptor_returns_none_when_absent() -> None:
    assert PDType1Font().load_font_descriptor() is None


def test_load_unicode_cmap_returns_none_when_absent() -> None:
    assert PDType1Font().load_unicode_cmap() is None


def test_load_unicode_cmap_parses_predefined_name() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSName.get_pdf_name("Identity-H")
    )
    cmap = font.load_unicode_cmap()
    assert cmap is not None
    # Each call returns a freshly parsed CMap (no caching at this layer);
    # callers wanting cached access use get_to_unicode_cmap.
    cmap2 = font.load_unicode_cmap()
    assert cmap2 is not None


def test_load_unicode_cmap_returns_none_for_non_name_non_stream_entry() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSInteger.get(42)
    )
    assert font.load_unicode_cmap() is None


def test_read_c_map_resolves_predefined_name() -> None:
    font = PDType1Font()
    cmap = font.read_c_map(COSName.get_pdf_name("Identity-H"))
    assert cmap is not None


def test_read_c_map_raises_on_unsupported_cos_type() -> None:
    import pytest

    font = PDType1Font()
    with pytest.raises(OSError, match="Expected Name or Stream"):
        font.read_c_map(COSInteger.get(42))


def test_equals_method_delegates_to_eq() -> None:
    """``equals`` mirrors upstream ``PDFont.equals(Object)`` — same dict ⇒ equal."""
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    a = PDType1Font(raw)
    b = PDType1Font(raw)
    assert a.equals(b) is True
    assert a.equals(a) is True


def test_equals_method_returns_false_for_distinct_dicts() -> None:
    a = PDType1Font()
    b = PDType1Font()
    # Each PDType1Font default-constructs a fresh dict, so they differ.
    assert a.equals(b) is False
    assert a.equals(None) is False
    assert a.equals("not a font") is False


def test_hash_code_method_matches_builtin_hash() -> None:
    """``hash_code`` mirrors upstream ``PDFont.hashCode`` — must match ``hash(self)``."""
    font = PDType1Font()
    assert font.hash_code() == hash(font)


def test_hash_code_method_consistent_with_equals() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    a = PDType1Font(raw)
    b = PDType1Font(raw)
    assert a.equals(b) is True
    assert a.hash_code() == b.hash_code()


def test_to_string_method_matches_repr() -> None:
    """``to_string`` mirrors upstream ``PDFont.toString`` — same as ``str(font)``."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.to_string() == "PDType1Font Helvetica"
    assert font.to_string() == str(font)


def test_to_string_method_falls_back_to_class_name_when_basefont_absent() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font = PDType1Font(raw)
    # /BaseFont is absent, so to_string is just the class name.
    assert font.to_string() == "PDType1Font"


def test_read_c_map_parses_embedded_stream() -> None:
    cmap_text = (
        b"/CIDInit /ProcSet findresource begin\n"
        b"12 dict begin\n"
        b"begincmap\n"
        b"/CMapName /TestCMap def\n"
        b"/CMapType 2 def\n"
        b"1 begincodespacerange\n"
        b"<00> <FF>\n"
        b"endcodespacerange\n"
        b"1 beginbfchar\n"
        b"<41> <0041>\n"
        b"endbfchar\n"
        b"endcmap\n"
    )
    stream = COSStream()
    stream.set_raw_data(cmap_text)
    font = PDType1Font()
    out = font.read_c_map(stream)
    assert out is not None
    # 'A' (0x41) → 'A' (U+0041)
    assert out.to_unicode(0x41) == "A"
