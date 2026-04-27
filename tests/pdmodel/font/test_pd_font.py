from __future__ import annotations

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


def test_simple_font_get_encoding_typed_returns_none_when_absent() -> None:
    assert PDType1Font().get_encoding_typed() is None


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


def test_font_factory_returns_none_for_unsupported_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "CIDFontType0")  # type: ignore[attr-defined]
    assert PDFontFactory.create_font(raw) is None


# ---------- inheritance sanity ----------


def test_inheritance_chain() -> None:
    assert issubclass(PDSimpleFont, PDFont)
    assert issubclass(PDType1Font, PDSimpleFont)
    assert issubclass(PDTrueTypeFont, PDSimpleFont)
    assert issubclass(PDType0Font, PDFont)
    assert not issubclass(PDType0Font, PDSimpleFont)
