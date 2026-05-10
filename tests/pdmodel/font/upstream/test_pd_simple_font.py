"""Parity tests for ``PDSimpleFont``.

Upstream PDFBox does not ship a dedicated ``PDSimpleFontTest`` — the
class is exercised indirectly through ``PDType1Font`` / ``PDTrueTypeFont``
fixtures and the integration-test corpus. The cases below mirror the
documented behaviours in
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDSimpleFont.java``:

* ``readEncoding`` (lines 88–140): name resolution, Symbol/ZapfDingbats
  carve-out, dictionary encoding with /Differences, fallback to
  ``readEncodingFromFont``.
* ``getEncoding`` / ``getGlyphList`` (lines 156–169).
* ``getStandard14Width`` (lines 343–372): .notdef → 250, nbspace →
  space, sfthyphen → hyphen.
* ``isNonZeroBoundingBox`` (lines 399–407).
* ``isVertical`` (lines 337–341): always False.
* ``hasExplicitWidth`` (lines 456–467): /Widths-driven, FirstChar
  bounded.
* ``addToSubset`` / ``subset`` / ``willBeSubset`` (lines 437–453):
  subsetting unsupported by default.
* ``toUnicode(int)`` / ``toUnicode(int, GlyphList)`` (lines 272–335).
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font import PDFontDescriptor, PDType1Font
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    StandardEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- read_encoding (PDSimpleFont.java:88) ----------


def test_read_encoding_resolves_named_winansi() -> None:
    """``/Encoding /WinAnsiEncoding`` → :class:`WinAnsiEncoding`."""
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    assert isinstance(font.get_encoding_typed(), WinAnsiEncoding)


def test_read_encoding_resolves_named_standard() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("StandardEncoding")
    )
    font.read_encoding()
    assert isinstance(font.get_encoding_typed(), StandardEncoding)


def test_read_encoding_zapf_dingbats_non_embedded_ignores_named_encoding() -> None:
    """PDFBOX-/PDF.js issue 16464: a non-embedded ZapfDingbats font ignores
    its declared ``/Encoding`` and uses the built-in ZapfDingbatsEncoding."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    assert isinstance(font.get_encoding_typed(), ZapfDingbatsEncoding)


def test_read_encoding_dictionary_with_differences() -> None:
    font = PDType1Font()
    enc = COSDictionary()
    enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    diffs = COSArray([COSInteger.get(65), COSName.get_pdf_name("A")])
    enc.set_item(COSName.get_pdf_name("Differences"), diffs)
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    font.read_encoding()
    typed = font.get_encoding_typed()
    assert isinstance(typed, DictionaryEncoding)
    assert typed.get_differences().get(65) == "A"


def test_read_encoding_missing_falls_back_to_read_encoding_from_font() -> None:
    """No ``/Encoding`` entry → the embedded program's encoding (Type 1
    falls back to ``StandardEncoding`` for non-embedded Standard 14)."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font.read_encoding()
    typed = font.get_encoding_typed()
    assert isinstance(typed, StandardEncoding)


# ---------- assign_glyph_list (PDSimpleFont.java:470) ----------


def test_assign_glyph_list_zapf_dingbats() -> None:
    font = PDType1Font()
    font.assign_glyph_list("ZapfDingbats")
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_assign_glyph_list_default_for_helvetica() -> None:
    font = PDType1Font()
    font.assign_glyph_list("Helvetica")
    assert font.get_glyph_list() is GlyphList.DEFAULT


# ---------- get_encoding / get_glyph_list (PDSimpleFont.java:156) ----------


def test_get_encoding_returns_raw_cos_name() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    raw = font.get_encoding()
    assert isinstance(raw, COSName)
    assert raw.name == "WinAnsiEncoding"


def test_get_glyph_list_default_for_unmapped_font() -> None:
    font = PDType1Font()
    assert font.get_glyph_list() is GlyphList.DEFAULT


def test_get_glyph_list_zapf_for_zapf_font() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


# ---------- get_standard14_width (PDSimpleFont.java:343) ----------


def test_get_standard14_width_uses_afm_for_named_glyph() -> None:
    """A non-embedded Standard 14 Helvetica picks widths from the bundled AFM."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    # 'A' (code 0x41) advance width in Helvetica AFM is 667.
    width = font.get_standard14_width(0x41)
    assert width == pytest.approx(667.0)


def test_get_standard14_width_notdef_returns_250() -> None:
    """PDFBOX-2334: ``.notdef`` is missing from Adobe AFMs, return 250."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    # Code 0 is .notdef in WinAnsi.
    assert font.get_standard14_width(0) == pytest.approx(250.0)


def test_get_standard14_width_raises_when_no_afm() -> None:
    font = PDType1Font()
    # No /BaseFont set → Standard 14 lookup misses → no AFM.
    with pytest.raises(RuntimeError, match="No AFM"):
        font.get_standard14_width(0x41)


# ---------- is_non_zero_bounding_box (PDSimpleFont.java:399) ----------


def test_is_non_zero_bounding_box_none() -> None:
    assert PDSimpleFont.is_non_zero_bounding_box(None) is False


def test_is_non_zero_bounding_box_all_zero() -> None:
    bbox = PDRectangle()
    bbox.set_lower_left_x(0.0)
    bbox.set_lower_left_y(0.0)
    bbox.set_upper_right_x(0.0)
    bbox.set_upper_right_y(0.0)
    assert PDSimpleFont.is_non_zero_bounding_box(bbox) is False


def test_is_non_zero_bounding_box_with_one_nonzero() -> None:
    bbox = PDRectangle()
    bbox.set_upper_right_x(100.0)
    assert PDSimpleFont.is_non_zero_bounding_box(bbox) is True


# ---------- is_vertical (PDSimpleFont.java:337) ----------


def test_is_vertical_always_false() -> None:
    assert PDType1Font().is_vertical() is False


# ---------- has_explicit_width (PDSimpleFont.java:456) ----------


def test_has_explicit_width_true_when_in_range() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSFloat(500.0) for _ in range(95)]),
    )
    assert font.has_explicit_width(32) is True
    assert font.has_explicit_width(126) is True


def test_has_explicit_width_false_when_below_first_char() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSFloat(500.0) for _ in range(95)]),
    )
    assert font.has_explicit_width(31) is False


def test_has_explicit_width_false_when_above_widths_range() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSFloat(500.0) for _ in range(10)]),
    )
    assert font.has_explicit_width(50) is False


def test_has_explicit_width_false_without_widths_entry() -> None:
    assert PDType1Font().has_explicit_width(65) is False


# ---------- subsetting contract (PDSimpleFont.java:437) ----------


def test_will_be_subset_default_false() -> None:
    assert PDType1Font().will_be_subset() is False


def test_add_to_subset_raises() -> None:
    with pytest.raises(NotImplementedError):
        PDType1Font().add_to_subset(0x41)


def test_subset_raises() -> None:
    with pytest.raises(NotImplementedError):
        PDType1Font().subset()


# ---------- to_unicode (PDSimpleFont.java:272) ----------


def test_to_unicode_uses_encoding_when_no_cmap() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    # 0x41 → 'A'
    assert font.to_unicode(0x41) == "A"


def test_to_unicode_returns_none_for_unmapped_code() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    # 0x00 in WinAnsi maps to .notdef → no unicode.
    assert font.to_unicode(0x00) is None


def test_to_unicode_custom_glyph_list_overrides_default() -> None:
    """Upstream allows callers to pass a custom glyph list when the font is
    using the AGL (so Zapf isn't disturbed)."""
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    # Passing the AGL itself is a no-op but exercises the override path.
    assert font.to_unicode(0x41, GlyphList.DEFAULT) == "A"


# ---------- get_symbolic_flag (PDSimpleFont.java:262) ----------


def test_get_symbolic_flag_none_when_no_descriptor() -> None:
    assert PDType1Font().get_symbolic_flag() is None


def test_get_symbolic_flag_true_when_bit_set() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_flags(1 << 2)  # FLAG_SYMBOLIC
    font.set_font_descriptor(fd)
    assert font.get_symbolic_flag() is True


def test_get_symbolic_flag_false_when_bit_clear() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_flags(0)
    font.set_font_descriptor(fd)
    assert font.get_symbolic_flag() is False


# ---------- is_font_symbolic (PDSimpleFont.java:199) ----------


def test_is_font_symbolic_uses_descriptor_flag_when_present() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_flags(1 << 2)
    font.set_font_descriptor(fd)
    assert font.is_font_symbolic() is True


def test_is_font_symbolic_standard14_symbol_returns_true() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Symbol")
    assert font.is_font_symbolic() is True


def test_is_font_symbolic_winansi_returns_false() -> None:
    """WinAnsi/MacRoman/StandardEncoding fonts are nonsymbolic."""
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font.read_encoding()
    assert font.is_font_symbolic() is False
