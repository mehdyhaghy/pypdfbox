from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
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


# ---------- PDType0Font descendant fonts ----------


def test_type0_font_get_descendant_font_returns_none_when_absent() -> None:
    font = PDType0Font()
    assert font.get_descendant_font() is None


def test_type0_font_get_descendant_font_returns_first_dict() -> None:
    font = PDType0Font()
    descendant = COSDictionary()
    descendant.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "Arial")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("DescendantFonts"), COSArray([descendant])
    )
    out = font.get_descendant_font()
    assert isinstance(out, COSDictionary)
    assert out is descendant


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
    raw.set_name(COSName.SUBTYPE, "Type3")  # type: ignore[attr-defined]
    assert PDFontFactory.create_font(raw) is None


# ---------- inheritance sanity ----------


def test_inheritance_chain() -> None:
    assert issubclass(PDSimpleFont, PDFont)
    assert issubclass(PDType1Font, PDSimpleFont)
    assert issubclass(PDTrueTypeFont, PDSimpleFont)
    assert issubclass(PDType0Font, PDFont)
    assert not issubclass(PDType0Font, PDSimpleFont)
