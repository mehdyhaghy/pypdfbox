"""Hand-written round-out tests for ``PDFontDescriptor``.

Complements the parity-style tests in ``test_pd_font_descriptor_parity.py``
by exercising the API as pypdfbox callers actually use it: descriptor
construction patterns, end-to-end metric population, font program stream
handoff, and the combinations that surface most often in real PDFs.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_FIXED_PITCH,
    FLAG_ITALIC,
    FLAG_NON_SYMBOLIC,
    FLAG_SERIF,
    PDFontDescriptor,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_default_constructor_writes_type_font_descriptor() -> None:
    fd = PDFontDescriptor()
    cos = fd.get_cos_object()
    type_value = cos.get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(type_value, COSName)
    assert type_value.name == "FontDescriptor"


def test_wrap_existing_dictionary_preserves_entries() -> None:
    cos = COSDictionary()
    cos.set_name(COSName.get_pdf_name("FontName"), "TimesNewRomanPS-Italic")
    cos.set_int(COSName.get_pdf_name("Flags"), FLAG_SERIF | FLAG_ITALIC)
    cos.set_float(COSName.get_pdf_name("ItalicAngle"), -12.0)

    fd = PDFontDescriptor(cos)
    assert fd.get_cos_object() is cos
    assert fd.get_font_name() == "TimesNewRomanPS-Italic"
    assert fd.get_flags() == FLAG_SERIF | FLAG_ITALIC
    assert fd.is_serif() is True
    assert fd.is_italic() is True
    assert fd.get_italic_angle() == pytest.approx(-12.0)


def test_full_helvetica_like_descriptor_round_trip() -> None:
    """Fill in a Helvetica-like descriptor end-to-end and read it back."""
    fd = PDFontDescriptor()
    fd.set_font_name("Helvetica")
    fd.set_font_family("Helvetica")
    fd.set_font_stretch("Normal")
    fd.set_font_weight(400.0)
    fd.set_flags(FLAG_NON_SYMBOLIC)
    fd.set_font_bounding_box(PDRectangle(-166.0, -225.0, 1000.0, 931.0))
    fd.set_italic_angle(0.0)
    fd.set_ascent(718.0)
    fd.set_descent(-207.0)
    fd.set_cap_height(718.0)
    fd.set_x_height(523.0)
    fd.set_stem_v(88.0)
    fd.set_stem_h(76.0)
    fd.set_avg_width(441.0)
    fd.set_max_width(1500.0)
    fd.set_missing_width(0.0)
    fd.set_leading(0.0)

    assert fd.get_font_name() == "Helvetica"
    assert fd.get_font_family() == "Helvetica"
    assert fd.get_font_stretch() == "Normal"
    assert fd.get_font_weight() == pytest.approx(400.0)
    assert fd.get_flags() == FLAG_NON_SYMBOLIC
    assert fd.is_non_symbolic() is True

    bbox = fd.get_font_bounding_box()
    assert isinstance(bbox, PDRectangle)
    assert bbox.lower_left_x == pytest.approx(-166.0)
    assert bbox.upper_right_y == pytest.approx(931.0)

    assert fd.get_ascent() == pytest.approx(718.0)
    assert fd.get_descent() == pytest.approx(-207.0)
    assert fd.get_cap_height() == pytest.approx(718.0)
    assert fd.get_x_height() == pytest.approx(523.0)
    assert fd.get_stem_v() == pytest.approx(88.0)
    assert fd.get_stem_h() == pytest.approx(76.0)
    assert fd.get_avg_width() == pytest.approx(441.0)
    assert fd.get_average_width() == pytest.approx(441.0)
    assert fd.get_max_width() == pytest.approx(1500.0)
    assert fd.get_missing_width() == pytest.approx(0.0)
    assert fd.get_leading() == pytest.approx(0.0)


@pytest.mark.parametrize(
    "stretch",
    [
        "UltraCondensed",
        "ExtraCondensed",
        "Condensed",
        "SemiCondensed",
        "Normal",
        "SemiExpanded",
        "Expanded",
        "ExtraExpanded",
        "UltraExpanded",
    ],
)
def test_font_stretch_accepts_spec_names(stretch: str) -> None:
    """All nine values from PDF 32000-1 Table 122 must round-trip."""
    fd = PDFontDescriptor()
    fd.set_font_stretch(stretch)
    assert fd.get_font_stretch() == stretch
    # Stored as a name, not a string.
    cos = fd.get_cos_object()
    raw = cos.get_dictionary_object(COSName.get_pdf_name("FontStretch"))
    assert isinstance(raw, COSName)
    assert raw.name == stretch


@pytest.mark.parametrize("weight", [100, 200, 300, 400, 500, 600, 700, 800, 900])
def test_font_weight_full_range(weight: int) -> None:
    """All standard CSS-style weights from 100 to 900 must round-trip."""
    fd = PDFontDescriptor()
    fd.set_font_weight(float(weight))
    assert fd.get_font_weight() == pytest.approx(weight)


def test_font_weight_default_is_zero() -> None:
    """Missing /FontWeight surfaces as 0.0 (caller treats as 'unspecified')."""
    fd = PDFontDescriptor()
    assert fd.get_font_weight() == 0.0


def test_set_font_name_clears_when_none() -> None:
    fd = PDFontDescriptor()
    fd.set_font_name("Foo")
    assert fd.get_font_name() == "Foo"
    fd.set_font_name(None)
    assert fd.get_font_name() is None
    assert (
        fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontName"))
        is None
    )


def test_set_font_family_clears_when_none() -> None:
    fd = PDFontDescriptor()
    fd.set_font_family("Foo")
    fd.set_font_family(None)
    assert fd.get_font_family() is None
    assert (
        fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontFamily"))
        is None
    )


def test_set_font_stretch_clears_when_none() -> None:
    fd = PDFontDescriptor()
    fd.set_font_stretch("Condensed")
    fd.set_font_stretch(None)
    assert fd.get_font_stretch() is None


def test_set_char_set_clears_when_none() -> None:
    fd = PDFontDescriptor()
    fd.set_char_set("/A/B")
    fd.set_char_set(None)
    assert fd.get_char_set() is None


def test_flag_helpers_use_one_based_bit_indices() -> None:
    """Bit 1 is FixedPitch (mask 1), bit 2 is Serif (mask 2), etc."""
    fd = PDFontDescriptor()
    fd.set_flag(1, True)
    assert fd.get_flags() == 1
    fd.set_flag(2, True)
    assert fd.get_flags() == 3
    fd.set_flag(1, False)
    assert fd.get_flags() == 2


def test_flag_helpers_round_trip_high_bits() -> None:
    """Flag bits 17-19 are sparse; verify masks survive."""
    fd = PDFontDescriptor()
    fd.set_all_cap(True)
    fd.set_small_cap(True)
    fd.set_force_bold(True)
    expected = (1 << 16) | (1 << 17) | (1 << 18)
    assert fd.get_flags() == expected
    assert fd.is_all_cap() is True
    assert fd.is_small_cap() is True
    assert fd.is_force_bold() is True


def test_font_bounding_box_via_cos_array_setter() -> None:
    """The COSArray setter (``set_font_b_box``) and the typed setter agree."""
    fd = PDFontDescriptor()
    arr = COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(500.0), COSFloat(500.0)])
    fd.set_font_b_box(arr)
    assert fd.get_font_b_box() is arr

    rect = fd.get_font_bounding_box()
    assert isinstance(rect, PDRectangle)
    assert rect.upper_right_x == pytest.approx(500.0)


def test_font_bounding_box_short_array_returns_none() -> None:
    """A /FontBBox with fewer than four entries does not crash; it returns None."""
    fd = PDFontDescriptor()
    short = COSArray([COSFloat(0.0), COSFloat(0.0)])
    fd.set_font_b_box(short)
    assert fd.get_font_bounding_box() is None


def test_cap_height_negative_value_returns_absolute() -> None:
    """PDFBOX-429: Scheherazade-style negative CapHeight comes back positive."""
    fd = PDFontDescriptor()
    fd.set_cap_height(-700.0)
    assert fd.get_cap_height() == pytest.approx(700.0)
    # The raw stored value is still negative (we only abs() on read).
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CapHeight"))
    assert isinstance(raw, COSFloat)
    assert raw.float_value() == pytest.approx(-700.0)


def test_x_height_negative_value_returns_absolute() -> None:
    fd = PDFontDescriptor()
    fd.set_x_height(-450.0)
    assert fd.get_x_height() == pytest.approx(450.0)


def test_font_file_aliases_distinct_keys() -> None:
    """Setting /FontFile2 must not overwrite /FontFile or /FontFile3."""
    fd = PDFontDescriptor()
    s1, s2, s3 = COSStream(), COSStream(), COSStream()
    fd.set_font_file(s1)
    fd.set_font_file2(s2)
    fd.set_font_file3(s3)

    assert fd.get_font_file().get_cos_object() is s1
    assert fd.get_font_file2().get_cos_object() is s2
    assert fd.get_font_file3().get_cos_object() is s3


def test_font_file_accepts_pd_stream_and_cos_stream() -> None:
    fd = PDFontDescriptor()
    raw = COSStream()
    fd.set_font_file2(PDStream(raw))
    assert fd.get_font_file2().get_cos_object() is raw

    other = COSStream()
    fd.set_font_file2(other)
    assert fd.get_font_file2().get_cos_object() is other


def test_font_file_clear_with_none() -> None:
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    assert fd.get_font_file2() is not None
    fd.set_font_file2(None)
    assert fd.get_font_file2() is None


def test_has_widths_with_widths_array_only() -> None:
    fd = PDFontDescriptor()
    assert fd.has_widths() is False

    fd.get_cos_object().set_item(COSName.get_pdf_name("Widths"), COSArray())
    assert fd.has_widths() is True
    assert fd.has_missing_width() is False


def test_has_widths_with_missing_width_only() -> None:
    fd = PDFontDescriptor()
    fd.set_missing_width(100.0)
    assert fd.has_widths() is True
    assert fd.has_missing_width() is True


def test_charset_round_trip_long_string() -> None:
    fd = PDFontDescriptor()
    payload = "/A/B/C/D/E/F/G/space/comma/period"
    fd.set_char_set(payload)
    assert fd.get_char_set() == payload


def test_lang_uses_name_storage() -> None:
    """``/Lang`` is stored as a COSName per PDF 32000-1 Table 122."""
    fd = PDFontDescriptor()
    fd.set_lang("en-US")
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Lang"))
    assert isinstance(raw, COSName)
    assert raw.name == "en-US"


def test_get_flags_default_is_zero_when_missing() -> None:
    fd = PDFontDescriptor()
    assert fd.get_flags() == 0
    # No flag predicates report true.
    for predicate in (
        fd.is_fixed_pitch,
        fd.is_serif,
        fd.is_symbolic,
        fd.is_script,
        fd.is_non_symbolic,
        fd.is_italic,
        fd.is_all_cap,
        fd.is_small_cap,
        fd.is_force_bold,
    ):
        assert predicate() is False


def test_set_flags_with_int_or_cos_integer_round_trip() -> None:
    """Storage type is COSInteger; ``set_flags`` should write that exact form."""
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_FIXED_PITCH | FLAG_ITALIC)
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Flags"))
    assert isinstance(raw, COSInteger)
    assert raw.int_value() == FLAG_FIXED_PITCH | FLAG_ITALIC


# ---------- Panose 12-byte block (sFamilyClass + PANOSE-10) ----------


def test_panose_family_class_is_signed_16_bit() -> None:
    """Upstream's ``getFamilyClass`` returns a signed 16-bit value built from
    ``(bytes[0] << 8) | (bytes[1] & 0xff)`` where ``bytes[0]`` is a *signed*
    Java byte. A high byte of 0xFF yields a negative result."""
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDPanose

    panose = PDPanose(b"\xff\x80" + b"\x00" * 10)
    # In Java: ((byte)0xff) << 8 | 0x80 == (-1 << 8) | 0x80 == -256 | 128 == -128.
    assert panose.get_family_class() == -128


def test_panose_classification_full_layout() -> None:
    """All ten PANOSE classification accessors line up with their byte
    indices (0..9 of the embedded 10-byte block)."""
    from pypdfbox.pdmodel.font.pd_font_descriptor import (
        PDPanose,
        PDPanoseClassification,
    )

    raw = bytes([0x00, 0x08]) + bytes(range(10, 20))  # PANOSE bytes 10..19
    panose = PDPanose(raw)
    cls = panose.get_panose()
    assert isinstance(cls, PDPanoseClassification)
    assert cls.get_bytes() == bytes(range(10, 20))
    assert cls.get_family_kind() == 10
    assert cls.get_serif_style() == 11
    assert cls.get_weight() == 12
    assert cls.get_proportion() == 13
    assert cls.get_contrast() == 14
    assert cls.get_stroke_variation() == 15
    assert cls.get_arm_style() == 16
    assert cls.get_letterform() == 17
    assert cls.get_midline() == 18
    assert cls.get_x_height() == 19


def test_panose_classification_str_formatting_matches_upstream() -> None:
    """``__str__`` mirrors upstream Java ``toString`` exactly."""
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDPanoseClassification

    cls = PDPanoseClassification(bytes(range(10)))
    expected = (
        "{ FamilyKind = 0, SerifStyle = 1, Weight = 2, Proportion = 3, "
        "Contrast = 4, StrokeVariation = 5, ArmStyle = 6, Letterform = 7, "
        "Midline = 8, XHeight = 9}"
    )
    assert str(cls) == expected
