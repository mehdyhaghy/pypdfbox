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


# ---------- Class-level FLAG_* constants ----------


def test_class_level_flag_constants_match_module_constants() -> None:
    """``PDFontDescriptor.FLAG_*`` mirrors the module-level masks.

    Mirrors upstream's ``private static final int FLAG_*`` declarations on
    the Java class — we expose them as public class attributes so callers
    can write ``PDFontDescriptor.FLAG_FORCE_BOLD`` after porting.
    """
    assert PDFontDescriptor.FLAG_FIXED_PITCH == 1
    assert PDFontDescriptor.FLAG_SERIF == 2
    assert PDFontDescriptor.FLAG_SYMBOLIC == 4
    assert PDFontDescriptor.FLAG_SCRIPT == 8
    assert PDFontDescriptor.FLAG_NON_SYMBOLIC == 32
    assert PDFontDescriptor.FLAG_ITALIC == 64
    assert PDFontDescriptor.FLAG_ALL_CAP == 65536
    assert PDFontDescriptor.FLAG_SMALL_CAP == 131072
    assert PDFontDescriptor.FLAG_FORCE_BOLD == 262144


def test_class_level_flag_constants_round_trip_through_set_flags() -> None:
    """The class-level constants are usable in ``set_flags`` / ``is_*`` calls."""
    fd = PDFontDescriptor()
    fd.set_flags(PDFontDescriptor.FLAG_FORCE_BOLD | PDFontDescriptor.FLAG_ITALIC)
    assert fd.is_force_bold() is True
    assert fd.is_italic() is True
    assert fd.is_serif() is False


# ---------- has_font_file / has_font_file2 / has_font_file3 ----------


def test_has_font_file_predicates_default_false() -> None:
    fd = PDFontDescriptor()
    assert fd.has_font_file() is False
    assert fd.has_font_file2() is False
    assert fd.has_font_file3() is False


def test_has_font_file_predicates_track_each_key_independently() -> None:
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    assert fd.has_font_file() is False
    assert fd.has_font_file2() is True
    assert fd.has_font_file3() is False

    fd.set_font_file(COSStream())
    fd.set_font_file3(COSStream())
    assert fd.has_font_file() is True
    assert fd.has_font_file2() is True
    assert fd.has_font_file3() is True


def test_has_font_file_predicates_clear_on_none() -> None:
    fd = PDFontDescriptor()
    fd.set_font_file3(COSStream())
    assert fd.has_font_file3() is True
    fd.set_font_file3(None)
    assert fd.has_font_file3() is False


# ---------- PDPanose.with_panose_classification ----------


def test_with_panose_classification_preserves_family_class() -> None:
    """Replacing the 10-byte PANOSE block keeps bytes 0-1 untouched."""
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDPanose

    original = PDPanose(b"\x01\x02" + bytes(range(2, 12)))
    updated = original.with_panose_classification(bytes(range(20, 30)))

    assert updated.get_family_class() == original.get_family_class()
    assert updated.get_panose().get_bytes() == bytes(range(20, 30))
    # Original is not mutated (immutable value semantics).
    assert original.get_panose().get_bytes() == bytes(range(2, 12))


def test_with_panose_classification_accepts_classification_object() -> None:
    from pypdfbox.pdmodel.font.pd_font_descriptor import (
        PDPanose,
        PDPanoseClassification,
    )

    original = PDPanose(b"\xff\x80" + b"\x00" * 10)
    new_cls = PDPanoseClassification(bytes(range(100, 110)))
    updated = original.with_panose_classification(new_cls)

    # Family-class bytes (signed) are preserved verbatim.
    assert updated.get_bytes()[:2] == b"\xff\x80"
    assert updated.get_panose() == new_cls


# ---------- clear_flags() ----------


def test_clear_flags_zeroes_existing_flags() -> None:
    """``clear_flags`` is a hard reset to /Flags == 0."""
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_FIXED_PITCH | FLAG_ITALIC | FLAG_SERIF)
    assert fd.get_flags() != 0

    fd.clear_flags()
    assert fd.get_flags() == 0
    assert fd.is_fixed_pitch() is False
    assert fd.is_italic() is False
    assert fd.is_serif() is False


def test_clear_flags_writes_zero_even_when_already_unset() -> None:
    """Calling on a fresh descriptor still writes /Flags=0 (no-op semantically)."""
    fd = PDFontDescriptor()
    fd.clear_flags()
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Flags"))
    # Stored as a COSInteger of value 0 (not removed entirely, mirroring set_flags(0)).
    assert isinstance(raw, COSInteger)
    assert raw.int_value() == 0


# ---------- has_font_bounding_box ----------


def test_has_font_bounding_box_default_false() -> None:
    fd = PDFontDescriptor()
    assert fd.has_font_bounding_box() is False


def test_has_font_bounding_box_true_after_typed_setter() -> None:
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, 0.0, 100.0, 100.0))
    assert fd.has_font_bounding_box() is True


def test_has_font_bounding_box_true_after_array_setter() -> None:
    """The lower-level COSArray setter also flips the predicate."""
    fd = PDFontDescriptor()
    fd.set_font_b_box(COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(1.0), COSFloat(1.0)]))
    assert fd.has_font_bounding_box() is True


def test_has_font_bounding_box_true_for_malformed_short_array() -> None:
    """Presence check tolerates bad shape — distinct from get_font_bounding_box()."""
    fd = PDFontDescriptor()
    fd.set_font_b_box(COSArray([COSFloat(0.0), COSFloat(0.0)]))  # only 2 entries
    assert fd.has_font_bounding_box() is True
    # Typed accessor still rejects the short array.
    assert fd.get_font_bounding_box() is None


def test_has_font_bounding_box_clears_when_set_to_none() -> None:
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, 0.0, 1.0, 1.0))
    fd.set_font_bounding_box(None)
    assert fd.has_font_bounding_box() is False


# ---------- has_cid_set ----------


def test_has_cid_set_default_false() -> None:
    fd = PDFontDescriptor()
    assert fd.has_cid_set() is False


def test_has_cid_set_round_trip() -> None:
    fd = PDFontDescriptor()
    fd.set_cid_set(COSStream())
    assert fd.has_cid_set() is True

    fd.set_cid_set(None)
    assert fd.has_cid_set() is False


def test_has_cid_set_independent_of_font_file_predicates() -> None:
    """Setting /FontFile2 must not flip ``has_cid_set``."""
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    assert fd.has_font_file2() is True
    assert fd.has_cid_set() is False


# ---------- has_panose ----------


def test_has_panose_default_false() -> None:
    fd = PDFontDescriptor()
    assert fd.has_panose() is False


def test_has_panose_false_when_style_dict_lacks_panose() -> None:
    """A /Style dict without /Panose must not register as ``has_panose``."""
    fd = PDFontDescriptor()
    style = COSDictionary()
    style.set_name(COSName.get_pdf_name("Custom"), "Value")
    fd.get_cos_object().set_item(COSName.get_pdf_name("Style"), style)
    assert fd.has_panose() is False


def test_has_panose_true_after_set_panose() -> None:
    fd = PDFontDescriptor()
    fd.set_panose(bytes(12))
    assert fd.has_panose() is True


def test_has_panose_true_for_short_buffer_unlike_get_panose() -> None:
    """``has_panose`` reports presence; ``get_panose`` enforces length."""
    from pypdfbox.cos import COSString

    fd = PDFontDescriptor()
    style = COSDictionary()
    style.set_item(COSName.get_pdf_name("Panose"), COSString(b"\x00" * 5))  # < 12 bytes
    fd.get_cos_object().set_item(COSName.get_pdf_name("Style"), style)

    # Presence check sees the entry; typed getter rejects the short buffer.
    assert fd.has_panose() is True
    assert fd.get_panose() is None


def test_has_panose_clears_after_set_panose_none() -> None:
    fd = PDFontDescriptor()
    fd.set_panose(bytes(12))
    fd.set_panose(None)
    assert fd.has_panose() is False


# ---------- is_embedded ----------


def test_is_embedded_default_false() -> None:
    fd = PDFontDescriptor()
    assert fd.is_embedded() is False


@pytest.mark.parametrize("setter", ["set_font_file", "set_font_file2", "set_font_file3"])
def test_is_embedded_true_for_any_font_file_slot(setter: str) -> None:
    """Any of /FontFile, /FontFile2, /FontFile3 flips ``is_embedded``."""
    fd = PDFontDescriptor()
    getattr(fd, setter)(COSStream())
    assert fd.is_embedded() is True


def test_is_embedded_clears_when_all_streams_removed() -> None:
    fd = PDFontDescriptor()
    fd.set_font_file(COSStream())
    fd.set_font_file2(COSStream())
    assert fd.is_embedded() is True

    fd.set_font_file(None)
    assert fd.is_embedded() is True  # FontFile2 still there
    fd.set_font_file2(None)
    assert fd.is_embedded() is False


def test_is_embedded_ignores_cid_set() -> None:
    """``/CIDSet`` is not a font program — it must not register as embedded."""
    fd = PDFontDescriptor()
    fd.set_cid_set(COSStream())
    assert fd.has_cid_set() is True
    assert fd.is_embedded() is False


# ---------- get_type / set_type ----------


def test_get_type_default_is_font_descriptor() -> None:
    """Fresh descriptors carry ``/Type = /FontDescriptor`` per spec."""
    fd = PDFontDescriptor()
    assert fd.get_type() == "FontDescriptor"


def test_get_type_returns_none_when_dict_lacks_type() -> None:
    """Hand-rolled dicts without /Type surface as None (not silently defaulted)."""
    fd = PDFontDescriptor(COSDictionary())
    assert fd.get_type() is None


def test_set_type_default_writes_font_descriptor() -> None:
    """The default argument re-applies the spec-mandated value."""
    fd = PDFontDescriptor(COSDictionary())
    assert fd.get_type() is None
    fd.set_type()
    assert fd.get_type() == "FontDescriptor"
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(raw, COSName)
    assert raw.name == "FontDescriptor"


def test_set_type_explicit_value_round_trips() -> None:
    fd = PDFontDescriptor()
    fd.set_type("CustomType")
    assert fd.get_type() == "CustomType"
    raw = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(raw, COSName)
    assert raw.name == "CustomType"


def test_set_type_none_removes_entry() -> None:
    fd = PDFontDescriptor()
    assert fd.get_type() == "FontDescriptor"
    fd.set_type(None)
    assert fd.get_type() is None
    assert (
        fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Type")) is None
    )


def test_get_type_ignores_non_name_storage() -> None:
    """A /Type stored as a COSString returns None — only COSName resolves."""
    from pypdfbox.cos import COSString

    fd = PDFontDescriptor()
    fd.get_cos_object().set_item(COSName.get_pdf_name("Type"), COSString("FontDescriptor"))
    assert fd.get_type() is None  # strict — get_name only resolves COSName


# ---------- __eq__ / __hash__ (identity) ----------


def test_pd_font_descriptor_equality_is_identity_based() -> None:
    """Two wrappers around the same dict compare equal; distinct dicts don't."""
    cos = COSDictionary()
    a = PDFontDescriptor(cos)
    b = PDFontDescriptor(cos)
    c = PDFontDescriptor(COSDictionary())

    assert a == b
    assert a is not b
    assert a != c


def test_pd_font_descriptor_equality_rejects_non_descriptor() -> None:
    fd = PDFontDescriptor()
    assert fd != fd.get_cos_object()  # underlying dict is not equivalent
    assert fd != "FontDescriptor"
    assert fd != 42
    assert fd is not None


def test_pd_font_descriptor_hash_matches_identity_equality() -> None:
    """Hash agrees with __eq__: equal wrappers hash to the same int."""
    cos = COSDictionary()
    a = PDFontDescriptor(cos)
    b = PDFontDescriptor(cos)
    assert hash(a) == hash(b)
    # Usable as dict key — last-write-wins because a == b.
    bucket = {a: "first"}
    bucket[b] = "second"
    assert bucket[a] == "second"
    assert len(bucket) == 1


def test_pd_font_descriptor_hash_differs_for_distinct_dicts() -> None:
    a = PDFontDescriptor()
    b = PDFontDescriptor()
    # Different underlying dicts — hash should (almost certainly) differ.
    assert hash(a) != hash(b)


def test_pd_font_descriptor_equality_survives_mutation() -> None:
    """Mutating the wrapped dict does not break wrapper equality (still same id)."""
    cos = COSDictionary()
    a = PDFontDescriptor(cos)
    b = PDFontDescriptor(cos)
    a.set_font_name("Helvetica")
    assert a == b
    assert b.get_font_name() == "Helvetica"


# ---------- __contains__ ----------


def test_pd_font_descriptor_contains_with_string_key() -> None:
    """Pythonic ``"Key" in fd`` mirrors COSDictionary's __contains__."""
    fd = PDFontDescriptor()
    # Constructor wrote /Type.
    assert "Type" in fd
    # Untouched keys are absent.
    assert "FontFile" not in fd
    assert "Lang" not in fd

    fd.set_font_file2(COSStream())
    assert "FontFile2" in fd
    assert "FontFile" not in fd
    assert "FontFile3" not in fd


def test_pd_font_descriptor_contains_with_cos_name_key() -> None:
    fd = PDFontDescriptor()
    fd.set_lang("en-US")
    assert COSName.get_pdf_name("Lang") in fd
    assert COSName.get_pdf_name("FontFamily") not in fd


def test_pd_font_descriptor_contains_rejects_non_key_types() -> None:
    """Non-key types (int, list) return False rather than raising."""
    fd = PDFontDescriptor()
    assert (42 in fd) is False  # type: ignore[operator]
    assert (None in fd) is False  # type: ignore[operator]


def test_pd_font_descriptor_contains_clears_after_remove() -> None:
    """``in`` flips back to False once the entry is removed."""
    fd = PDFontDescriptor()
    fd.set_font_family("Helvetica")
    assert "FontFamily" in fd
    fd.set_font_family(None)
    assert "FontFamily" not in fd
