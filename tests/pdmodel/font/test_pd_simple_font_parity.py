from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont, PDType1Font
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_ALL_CAP,
    FLAG_FIXED_PITCH,
    FLAG_FORCE_BOLD,
    FLAG_ITALIC,
    FLAG_SCRIPT,
    FLAG_SERIF,
    FLAG_SMALL_CAP,
    FLAG_SYMBOLIC,
)
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _font_with_flags(flags: int) -> PDType1Font:
    """Build a PDType1Font with a /FontDescriptor whose /Flags is set."""
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_flags(flags)
    font.set_font_descriptor(fd)
    return font


# ---------- /Flags bit accessors ----------


def test_is_symbolic_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_SYMBOLIC)
    assert font.is_symbolic() is True
    # Other bits stay false when only Symbolic is set.
    assert font.is_italic() is False
    assert font.is_fixed_pitch() is False
    assert font.is_serif() is False


def test_is_symbolic_false_when_bit_clear() -> None:
    font = _font_with_flags(0)
    assert font.is_symbolic() is False


def test_is_italic_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_ITALIC)
    assert font.is_italic() is True
    assert font.is_symbolic() is False


def test_is_fixed_pitch_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_FIXED_PITCH)
    assert font.is_fixed_pitch() is True


def test_is_serif_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_SERIF)
    assert font.is_serif() is True


def test_is_script_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_SCRIPT)
    assert font.is_script() is True


def test_is_force_bold_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_FORCE_BOLD)
    assert font.is_force_bold() is True


def test_is_all_cap_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_ALL_CAP)
    assert font.is_all_cap() is True
    assert font.is_small_cap() is False


def test_is_small_cap_true_when_bit_set() -> None:
    font = _font_with_flags(FLAG_SMALL_CAP)
    assert font.is_small_cap() is True
    assert font.is_all_cap() is False


def test_combined_flags_distinct_bits() -> None:
    # Italic + Serif + FixedPitch all set together — each accessor must
    # only see its own bit.
    font = _font_with_flags(FLAG_ITALIC | FLAG_SERIF | FLAG_FIXED_PITCH)
    assert font.is_italic() is True
    assert font.is_serif() is True
    assert font.is_fixed_pitch() is True
    assert font.is_symbolic() is False
    assert font.is_force_bold() is False


def test_flag_value_constants_match_pdf_spec() -> None:
    # Sanity check that the imported constants match the PDF 32000-1 §9.8.2
    # decimal values in the user contract.
    assert FLAG_FIXED_PITCH == 1
    assert FLAG_SERIF == 2
    assert FLAG_SYMBOLIC == 4
    assert FLAG_SCRIPT == 8
    assert FLAG_ITALIC == 64
    assert FLAG_ALL_CAP == 65536
    assert FLAG_SMALL_CAP == 131072
    assert FLAG_FORCE_BOLD == 262144


# ---------- defaults (no /FontDescriptor) ----------


def test_all_flags_false_when_no_font_descriptor() -> None:
    font = PDType1Font()
    assert font.get_font_descriptor() is None
    assert font.is_symbolic() is False
    assert font.is_italic() is False
    assert font.is_bold() is False
    assert font.is_fixed_pitch() is False
    assert font.is_serif() is False
    assert font.is_script() is False
    assert font.is_force_bold() is False
    assert font.is_all_cap() is False
    assert font.is_small_cap() is False


def test_all_flags_false_when_descriptor_has_no_flags_entry() -> None:
    # /FontDescriptor present but /Flags entry absent — get_flags() returns
    # 0, so every accessor must report False.
    font = PDType1Font()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_symbolic() is False
    assert font.is_italic() is False
    assert font.is_fixed_pitch() is False
    assert font.is_serif() is False
    assert font.is_script() is False
    assert font.is_force_bold() is False
    assert font.is_all_cap() is False
    assert font.is_small_cap() is False


# ---------- is_bold (derived from /FontWeight) ----------


def test_is_bold_true_when_font_weight_is_700() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_weight(700)
    font.set_font_descriptor(fd)
    assert font.is_bold() is True


def test_is_bold_true_when_font_weight_is_900() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_weight(900)
    font.set_font_descriptor(fd)
    assert font.is_bold() is True


def test_is_bold_false_when_font_weight_is_400() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_weight(400)
    font.set_font_descriptor(fd)
    assert font.is_bold() is False


# ---------- /FirstChar, /LastChar, /Widths round-trip ----------


def test_first_char_round_trip() -> None:
    font = PDType1Font()
    font.get_cos_object().set_int(COSName.get_pdf_name("FirstChar"), 32)
    assert font.get_first_char() == 32


def test_first_char_default_when_absent() -> None:
    assert PDType1Font().get_first_char() == -1


def test_last_char_round_trip() -> None:
    font = PDType1Font()
    font.get_cos_object().set_int(COSName.get_pdf_name("LastChar"), 255)
    assert font.get_last_char() == 255


def test_last_char_default_when_absent() -> None:
    assert PDType1Font().get_last_char() == -1


def test_widths_round_trip_mixed_int_and_float() -> None:
    font = PDTrueTypeFont()
    arr = COSArray(
        [COSInteger.get(250), COSInteger.get(333), COSFloat(408.5), COSInteger.get(500)]
    )
    font.get_cos_object().set_item(COSName.get_pdf_name("Widths"), arr)
    assert font.get_widths() == [250.0, 333.0, 408.5, 500.0]


def test_widths_default_empty_when_absent() -> None:
    assert PDType1Font().get_widths() == []


def test_widths_empty_when_value_not_an_array() -> None:
    font = PDType1Font()
    # Stick something that isn't a COSArray under /Widths.
    font.get_cos_object().set_int(COSName.get_pdf_name("Widths"), 42)
    assert font.get_widths() == []


def test_full_simple_font_dict_round_trip() -> None:
    """End-to-end: build a Type1 font dict the way a parser would have, and
    verify every parity accessor reads the expected value."""
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica-Bold")
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 126)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(500) for _ in range(95)]),
    )
    fd = PDFontDescriptor()
    fd.set_font_name("Helvetica-Bold")
    fd.set_flags(FLAG_FIXED_PITCH | FLAG_ITALIC)
    fd.set_font_weight(700)
    font.set_font_descriptor(fd)

    # Wrap the same dict in a fresh PDType1Font so we exercise the read path.
    parsed = PDType1Font(cos)
    assert parsed.get_first_char() == 32
    assert parsed.get_last_char() == 126
    assert len(parsed.get_widths()) == 95
    assert parsed.is_fixed_pitch() is True
    assert parsed.is_italic() is True
    assert parsed.is_symbolic() is False
    assert parsed.is_bold() is True
    assert parsed.is_standard_14() is True


# ---------- is_standard_14 ----------


def test_is_standard_14_true_for_canonical_name() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_standard_14() is True


def test_is_standard_14_true_for_alias() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ArialMT")
    assert font.is_standard_14() is True


def test_is_standard_14_false_for_non_standard_name() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "MyCustomFont")
    assert font.is_standard_14() is False


def test_is_standard_14_false_when_base_font_absent() -> None:
    # No /BaseFont — get_name() returns None; lookup must safely report False.
    assert PDType1Font().is_standard_14() is False


def test_is_standard_14_no_underscore_alias_matches() -> None:
    # Upstream's canonical name is ``isStandard14`` (no underscore between
    # ``Standard`` and ``14``). We expose both spellings — the alias must
    # delegate to the underscored version.
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_standard14() is True
    assert font.is_standard14() == font.is_standard_14()


def test_is_standard_14_false_when_dictionary_encoding_has_real_differences() -> None:
    # Standard 14 status is forfeited when /Encoding is a /Differences
    # overlay that *actually* changes the base mapping (PDFBOX-2372).
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    enc = COSDictionary()
    enc.set_name(COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding")
    # Differences: code 65 ('A' in WinAnsi) -> 'beta' instead of 'A'.
    diffs = COSArray([COSInteger.get(65), COSName.get_pdf_name("beta")])
    enc.set_item(COSName.get_pdf_name("Differences"), diffs)
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    assert font.is_standard_14() is False


def test_is_standard_14_true_when_differences_only_restate_base_mapping() -> None:
    # /Differences entries that simply restate the base encoding's own
    # mapping for that code do not disqualify a Standard 14 font
    # (PDFBOX-1900 with the file from PDFBOX-2192).
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    enc = COSDictionary()
    enc.set_name(COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding")
    # Code 65 in WinAnsiEncoding *is* 'A' — re-stating that is a no-op.
    diffs = COSArray([COSInteger.get(65), COSName.get_pdf_name("A")])
    enc.set_item(COSName.get_pdf_name("Differences"), diffs)
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    assert font.is_standard_14() is True


def test_is_standard_14_false_when_font_program_embedded() -> None:
    # Embedded fonts are never Standard 14 — inherits base-class rule.
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    fd = PDFontDescriptor()
    from pypdfbox.cos import COSStream

    fd.get_cos_object().set_item(COSName.get_pdf_name("FontFile"), COSStream())
    font.set_font_descriptor(fd)
    assert font.is_standard_14() is False


# ---------- TrueType inherits the same accessors ----------


def test_true_type_font_uses_same_flag_accessors() -> None:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC | FLAG_SERIF)
    font.set_font_descriptor(fd)
    assert font.is_symbolic() is True
    assert font.is_serif() is True
    assert font.is_italic() is False


# ---------- direct dict construction (mirrors parser path) ----------


def test_is_italic_via_raw_dict_with_flags_64() -> None:
    """A simple font with /FontDescriptor /Flags = 64 → is_italic() True."""
    descriptor = COSDictionary()
    descriptor.set_int(COSName.get_pdf_name("Flags"), 64)
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    raw.set_item(COSName.get_pdf_name("FontDescriptor"), descriptor)
    font = PDType1Font(raw)
    assert font.is_italic() is True
    assert font.is_symbolic() is False


def test_is_symbolic_via_raw_dict_with_flags_4() -> None:
    """A simple font with /FontDescriptor /Flags = 4 → is_symbolic() True."""
    descriptor = COSDictionary()
    descriptor.set_int(COSName.get_pdf_name("Flags"), 4)
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    raw.set_item(COSName.get_pdf_name("FontDescriptor"), descriptor)
    font = PDType1Font(raw)
    assert font.is_symbolic() is True
    assert font.is_italic() is False


# ---------- is_vertical (PDFontLike contract) ----------


def test_is_vertical_always_false_for_simple_font() -> None:
    """Mirrors upstream ``PDSimpleFont.isVertical`` — always False."""
    assert PDType1Font().is_vertical() is False
    assert PDTrueTypeFont().is_vertical() is False


def test_is_vertical_does_not_depend_on_descriptor_or_widths() -> None:
    """Even with a fully-populated dict, simple fonts never flip to vertical."""
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_int(COSName.get_pdf_name("LastChar"), 126)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(500) for _ in range(95)]),
    )
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC)
    font.set_font_descriptor(fd)
    assert font.is_vertical() is False


# ---------- has_explicit_width ----------


def test_has_explicit_width_true_for_code_inside_widths_window() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(250 + i) for i in range(95)]),  # 32..126
    )
    # 'A' = 65 → in window
    assert font.has_explicit_width(65) is True
    # FirstChar boundary (inclusive)
    assert font.has_explicit_width(32) is True
    # FirstChar + len(Widths) - 1 (inclusive)
    assert font.has_explicit_width(126) is True


def test_has_explicit_width_false_when_widths_absent() -> None:
    font = PDType1Font()
    # No /Widths in the dict at all.
    assert font.has_explicit_width(65) is False


def test_has_explicit_width_false_below_first_char() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(500) for _ in range(95)]),
    )
    assert font.has_explicit_width(31) is False
    assert font.has_explicit_width(0) is False


def test_has_explicit_width_false_above_widths_window() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), 32)
    cos.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(500) for _ in range(95)]),  # 32..126
    )
    assert font.has_explicit_width(127) is False
    assert font.has_explicit_width(255) is False


# ---------- subset / will_be_subset / add_to_subset ----------


def test_will_be_subset_default_false_for_simple_font() -> None:
    """Mirrors upstream ``PDSimpleFont.willBeSubset`` — always False."""
    assert PDType1Font().will_be_subset() is False


def test_add_to_subset_raises_for_unsupported_simple_font() -> None:
    """Type1 has no subsetter — upstream raises UnsupportedOperationException
    which we mirror as NotImplementedError."""
    with pytest.raises(NotImplementedError):
        PDType1Font().add_to_subset(ord("A"))


def test_subset_raises_for_unsupported_simple_font() -> None:
    """Type1 has no subsetter — upstream raises UnsupportedOperationException."""
    with pytest.raises(NotImplementedError):
        PDType1Font().subset()


# ---------- is_non_zero_bounding_box (static helper) ----------


def test_is_non_zero_bounding_box_true_for_real_bbox() -> None:
    bbox = PDRectangle(-100.0, -200.0, 1000.0, 800.0)
    assert PDSimpleFont.is_non_zero_bounding_box(bbox) is True


def test_is_non_zero_bounding_box_false_for_all_zero_bbox() -> None:
    """An all-zero bbox is the defaulted / unset case."""
    assert PDSimpleFont.is_non_zero_bounding_box(PDRectangle()) is False
    assert PDSimpleFont.is_non_zero_bounding_box(PDRectangle(0.0, 0.0, 0.0, 0.0)) is False


def test_is_non_zero_bounding_box_false_for_none() -> None:
    """Mirrors upstream's ``bbox != null`` short-circuit."""
    assert PDSimpleFont.is_non_zero_bounding_box(None) is False


def test_is_non_zero_bounding_box_true_when_only_one_corner_nonzero() -> None:
    """Any single non-zero corner is enough — upstream tests each via Float.compare."""
    assert PDSimpleFont.is_non_zero_bounding_box(PDRectangle(0.0, 0.0, 0.0, 1.0)) is True
    assert PDSimpleFont.is_non_zero_bounding_box(PDRectangle(0.0, 0.0, 1.0, 0.0)) is True
    assert PDSimpleFont.is_non_zero_bounding_box(PDRectangle(0.0, 1.0, 0.0, 0.0)) is True
    assert PDSimpleFont.is_non_zero_bounding_box(PDRectangle(-1.0, 0.0, 0.0, 0.0)) is True
