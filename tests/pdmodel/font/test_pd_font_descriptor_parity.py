"""Parity-style tests for ``PDFontDescriptor`` flag bits + numeric metrics.

Mirrors the surface exercised by upstream
``org.apache.pdfbox.pdmodel.font.PDFontDescriptorTest`` plus the bit
predicates documented in PDF 32000-1 §9.8.2 Table 123.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_ALL_CAP,
    FLAG_FIXED_PITCH,
    FLAG_FORCE_BOLD,
    FLAG_ITALIC,
    FLAG_NON_SYMBOLIC,
    FLAG_SCRIPT,
    FLAG_SERIF,
    FLAG_SMALL_CAP,
    FLAG_SYMBOLIC,
    PDFontDescriptor,
    PDPanose,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# Each tuple: (1-based bit index, predicate name, setter name, mask).
_FLAG_CASES = [
    (1, "is_fixed_pitch", "set_fixed_pitch", FLAG_FIXED_PITCH),
    (2, "is_serif", "set_serif", FLAG_SERIF),
    (3, "is_symbolic", "set_symbolic", FLAG_SYMBOLIC),
    (4, "is_script", "set_script", FLAG_SCRIPT),
    (6, "is_non_symbolic", "set_non_symbolic", FLAG_NON_SYMBOLIC),
    (7, "is_italic", "set_italic", FLAG_ITALIC),
    (17, "is_all_cap", "set_all_cap", FLAG_ALL_CAP),
    (18, "is_small_cap", "set_small_cap", FLAG_SMALL_CAP),
    (19, "is_force_bold", "set_force_bold", FLAG_FORCE_BOLD),
]


@pytest.mark.parametrize(("bit", "is_name", "set_name", "mask"), _FLAG_CASES)
def test_flag_round_trip(bit: int, is_name: str, set_name: str, mask: int) -> None:
    fd = PDFontDescriptor()
    assert fd.get_flags() == 0
    assert getattr(fd, is_name)() is False

    getattr(fd, set_name)(True)
    assert getattr(fd, is_name)() is True
    # The exact bit ends up in /Flags, no others.
    assert fd.get_flags() == mask
    # Generic helper agrees with the named predicate.
    assert fd.get_flag(bit) is True

    getattr(fd, set_name)(False)
    assert getattr(fd, is_name)() is False
    assert fd.get_flags() == 0
    assert fd.get_flag(bit) is False


def test_flags_are_independent() -> None:
    fd = PDFontDescriptor()
    fd.set_fixed_pitch(True)
    fd.set_italic(True)
    fd.set_force_bold(True)

    expected = FLAG_FIXED_PITCH | FLAG_ITALIC | FLAG_FORCE_BOLD
    assert fd.get_flags() == expected
    assert fd.is_fixed_pitch() is True
    assert fd.is_italic() is True
    assert fd.is_force_bold() is True
    # An unrelated bit must remain unset.
    assert fd.is_serif() is False
    assert fd.is_symbolic() is False

    # Clearing one bit leaves the others.
    fd.set_italic(False)
    assert fd.get_flags() == FLAG_FIXED_PITCH | FLAG_FORCE_BOLD


def test_set_flag_generic_helper() -> None:
    fd = PDFontDescriptor()
    # Bit 1 == FixedPitch; toggling via the generic helper must agree
    # with the named predicate.
    fd.set_flag(1, True)
    assert fd.is_fixed_pitch() is True
    assert fd.get_flag(1) is True

    fd.set_flag(19, True)
    assert fd.is_force_bold() is True
    assert fd.get_flags() == FLAG_FIXED_PITCH | FLAG_FORCE_BOLD

    fd.set_flag(1, False)
    assert fd.is_fixed_pitch() is False
    assert fd.get_flags() == FLAG_FORCE_BOLD


def test_set_flags_replaces_value() -> None:
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SERIF | FLAG_ITALIC)
    assert fd.is_serif() is True
    assert fd.is_italic() is True
    assert fd.is_fixed_pitch() is False

    # set_flags is a hard overwrite — not OR-merge.
    fd.set_flags(FLAG_FIXED_PITCH)
    assert fd.is_fixed_pitch() is True
    assert fd.is_serif() is False
    assert fd.is_italic() is False


# ---------- numeric metrics ----------


@pytest.mark.parametrize(
    ("getter", "setter", "value"),
    [
        ("get_ascent", "set_ascent", 750.0),
        ("get_descent", "set_descent", -250.0),
        ("get_cap_height", "set_cap_height", 700.0),
        ("get_x_height", "set_x_height", 480.5),
        ("get_italic_angle", "set_italic_angle", -12.0),
        ("get_stem_v", "set_stem_v", 80.0),
        ("get_stem_h", "set_stem_h", 50.0),
        ("get_avg_width", "set_avg_width", 432.0),
        ("get_max_width", "set_max_width", 1000.0),
        ("get_missing_width", "set_missing_width", 250.0),
        ("get_leading", "set_leading", 14.5),
    ],
)
def test_numeric_metric_round_trip(getter: str, setter: str, value: float) -> None:
    fd = PDFontDescriptor()
    # Defaults are zero (Leading and MissingWidth default to 0 per Table 122,
    # the rest of the metrics aren't required so we surface 0.0 too).
    assert getattr(fd, getter)() == 0.0

    getattr(fd, setter)(value)
    assert getattr(fd, getter)() == pytest.approx(value)


def test_get_font_bounding_box_typed() -> None:
    fd = PDFontDescriptor()
    bbox = COSArray([COSFloat(-100.0), COSFloat(-250.0), COSFloat(1000.0), COSFloat(900.0)])
    fd.set_font_b_box(bbox)

    rect = fd.get_font_bounding_box()
    assert isinstance(rect, PDRectangle)
    assert rect.lower_left_x == pytest.approx(-100.0)
    assert rect.lower_left_y == pytest.approx(-250.0)
    assert rect.upper_right_x == pytest.approx(1000.0)
    assert rect.upper_right_y == pytest.approx(900.0)


def test_get_font_bounding_box_missing_returns_none() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_bounding_box() is None


def test_set_font_bounding_box_round_trip() -> None:
    fd = PDFontDescriptor()
    rect = PDRectangle(-50.0, -200.0, 750.0, 850.0)
    fd.set_font_bounding_box(rect)

    out = fd.get_font_bounding_box()
    assert isinstance(out, PDRectangle)
    assert out.lower_left_x == pytest.approx(-50.0)
    assert out.lower_left_y == pytest.approx(-200.0)
    assert out.upper_right_x == pytest.approx(750.0)
    assert out.upper_right_y == pytest.approx(850.0)

    # None clears the entry.
    fd.set_font_bounding_box(None)
    assert fd.get_font_bounding_box() is None
    assert fd.get_font_b_box() is None


# ---------- string/name fields ----------


def test_font_name_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_name() is None

    fd.set_font_name("Helvetica-Bold")
    assert fd.get_font_name() == "Helvetica-Bold"

    fd.set_font_name(None)
    assert fd.get_font_name() is None


def test_font_family_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_family() is None

    fd.set_font_family("Helvetica")
    assert fd.get_font_family() == "Helvetica"

    fd.set_font_family(None)
    assert fd.get_font_family() is None


def test_font_stretch_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_stretch() is None

    fd.set_font_stretch("SemiCondensed")
    assert fd.get_font_stretch() == "SemiCondensed"

    fd.set_font_stretch(None)
    assert fd.get_font_stretch() is None


def test_font_weight_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_font_weight() == 0.0

    fd.set_font_weight(700.0)
    assert fd.get_font_weight() == pytest.approx(700.0)


def test_char_set_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_char_set() is None

    fd.set_char_set("/A/B/C/space")
    assert fd.get_char_set() == "/A/B/C/space"

    # set_character_set is the upstream-named alias.
    fd.set_character_set("/X/Y")
    assert fd.get_char_set() == "/X/Y"

    fd.set_char_set(None)
    assert fd.get_char_set() is None


def test_lang_round_trip() -> None:
    fd = PDFontDescriptor()
    assert fd.get_lang() is None

    fd.set_lang("en-US")
    assert fd.get_lang() == "en-US"

    fd.set_lang(None)
    assert fd.get_lang() is None


# ---------- AverageWidth alias ----------


def test_average_width_alias_matches_avg_width() -> None:
    fd = PDFontDescriptor()
    assert fd.get_average_width() == 0.0
    assert fd.get_avg_width() == 0.0

    fd.set_average_width(425.0)
    assert fd.get_average_width() == pytest.approx(425.0)
    assert fd.get_avg_width() == pytest.approx(425.0)

    fd.set_avg_width(500.0)
    assert fd.get_average_width() == pytest.approx(500.0)


# ---------- has_widths / has_missing_width ----------


def test_has_widths_and_has_missing_width() -> None:
    fd = PDFontDescriptor()
    assert fd.has_widths() is False
    assert fd.has_missing_width() is False

    fd.set_missing_width(250.0)
    assert fd.has_missing_width() is True
    assert fd.has_widths() is True

    fd2 = PDFontDescriptor()
    fd2.get_cos_object().set_item(COSName.get_pdf_name("Widths"), COSArray())
    assert fd2.has_widths() is True
    assert fd2.has_missing_width() is False


# ---------- CapHeight / XHeight abs() semantics (PDFBOX-429) ----------


def test_cap_height_returns_absolute_value() -> None:
    fd = PDFontDescriptor()
    fd.set_cap_height(-700.0)
    # Upstream returns abs() to work around buggy fonts (Scheherazade).
    assert fd.get_cap_height() == pytest.approx(700.0)


def test_x_height_returns_absolute_value() -> None:
    fd = PDFontDescriptor()
    fd.set_x_height(-450.0)
    assert fd.get_x_height() == pytest.approx(450.0)


# ---------- font program streams ----------


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_font_file", "set_font_file"),
        ("get_font_file2", "set_font_file2"),
        ("get_font_file3", "set_font_file3"),
        ("get_cid_set", "set_cid_set"),
    ],
)
def test_font_file_streams_round_trip(getter: str, setter: str) -> None:
    fd = PDFontDescriptor()
    assert getattr(fd, getter)() is None

    cos_stream = COSStream()
    pd_stream = PDStream(cos_stream)
    getattr(fd, setter)(pd_stream)

    out = getattr(fd, getter)()
    assert isinstance(out, PDStream)
    assert out.get_cos_object() is cos_stream

    # Also accept a raw COSStream.
    other = COSStream()
    getattr(fd, setter)(other)
    assert getattr(fd, getter)().get_cos_object() is other

    getattr(fd, setter)(None)
    assert getattr(fd, getter)() is None


# ---------- /Style /Panose ----------


def test_panose_returns_none_when_style_missing() -> None:
    fd = PDFontDescriptor()
    assert fd.get_panose() is None


def test_panose_returns_none_when_data_too_short() -> None:
    fd = PDFontDescriptor()
    style = COSDictionary()
    style.set_item(COSName.get_pdf_name("Panose"), COSString(b"\x00\x01\x02"))  # < 12 bytes
    fd.get_cos_object().set_item(COSName.get_pdf_name("Style"), style)
    assert fd.get_panose() is None


def test_panose_round_trip_from_style_dict() -> None:
    fd = PDFontDescriptor()
    style = COSDictionary()
    # 12 bytes: bytes 0-1 = sFamilyClass (0x0008), bytes 2-11 = PANOSE-10.
    payload = bytes([0x00, 0x08, 2, 11, 6, 3, 5, 4, 5, 2, 2, 4])
    style.set_item(COSName.get_pdf_name("Panose"), COSString(payload))
    fd.get_cos_object().set_item(COSName.get_pdf_name("Style"), style)

    panose = fd.get_panose()
    assert isinstance(panose, PDPanose)
    assert panose.get_bytes() == payload
    assert panose.get_family_class() == 8

    classification = panose.get_panose()
    assert classification.get_family_kind() == 2
    assert classification.get_serif_style() == 11
    assert classification.get_weight() == 6
    assert classification.get_proportion() == 3
    assert classification.get_contrast() == 5
    assert classification.get_stroke_variation() == 4
    assert classification.get_arm_style() == 5
    assert classification.get_letterform() == 2
    assert classification.get_midline() == 2
    assert classification.get_x_height() == 4


def test_panose_constructor_accepts_any_length() -> None:
    """Upstream stores bytes verbatim with no length check — mirror that."""
    PDPanose(bytes(12))  # nominal
    PDPanose(bytes(24))  # over-long, ok
    PDPanose(bytes(5))  # short, ok — accessors raise IndexError on demand


# ---------- /Type entry written by the no-arg constructor ----------


def test_constructor_sets_type_font_descriptor() -> None:
    fd = PDFontDescriptor()
    cos = fd.get_cos_object()
    type_value = cos.get_dictionary_object(COSName.get_pdf_name("Type"))
    assert isinstance(type_value, COSName)
    assert type_value.name == "FontDescriptor"


def test_existing_dictionary_type_not_overwritten() -> None:
    cos = COSDictionary()
    fd = PDFontDescriptor(cos)
    # Pre-existing dict had no /Type — wrapper does not synthesize one when
    # an explicit dict is passed in (mirrors upstream's package-private vs
    # public constructor split).
    assert cos.get_dictionary_object(COSName.get_pdf_name("Type")) is None
    assert fd.get_cos_object() is cos


# ---------- mask-based flag accessors (is_flag_bit_on / set_flag_bit) ----------


def test_is_flag_bit_on_with_mask() -> None:
    """``is_flag_bit_on`` mirrors upstream's private ``isFlagBitOn(int bit)``
    where ``bit`` is the *mask* (e.g. ``FLAG_FIXED_PITCH``), not a 1-based
    index. Distinct semantics from ``get_flag(1)``."""
    fd = PDFontDescriptor()
    assert fd.is_flag_bit_on(FLAG_FIXED_PITCH) is False
    assert fd.is_flag_bit_on(FLAG_FORCE_BOLD) is False

    fd.set_flags(FLAG_FIXED_PITCH | FLAG_FORCE_BOLD)
    assert fd.is_flag_bit_on(FLAG_FIXED_PITCH) is True
    assert fd.is_flag_bit_on(FLAG_FORCE_BOLD) is True
    assert fd.is_flag_bit_on(FLAG_SERIF) is False


def test_set_flag_bit_with_mask_round_trip() -> None:
    """Mask-based mutator agrees with the named predicates."""
    fd = PDFontDescriptor()
    fd.set_flag_bit(FLAG_SERIF, True)
    assert fd.is_serif() is True
    assert fd.is_flag_bit_on(FLAG_SERIF) is True
    assert fd.get_flags() == FLAG_SERIF

    fd.set_flag_bit(FLAG_ITALIC, True)
    assert fd.is_italic() is True
    assert fd.get_flags() == FLAG_SERIF | FLAG_ITALIC

    fd.set_flag_bit(FLAG_SERIF, False)
    assert fd.is_serif() is False
    assert fd.get_flags() == FLAG_ITALIC


def test_get_flag_index_vs_is_flag_bit_on_mask_disagree_on_call_args() -> None:
    """``get_flag(1)`` and ``is_flag_bit_on(1)`` happen to agree because
    ``1 << 0 == 1``, but ``get_flag(2)`` (bit index 2 == mask 2) and
    ``is_flag_bit_on(2)`` agree only by coincidence at low bits.
    For ``FLAG_ALL_CAP`` (mask 65536), the *index* form takes 17."""
    fd = PDFontDescriptor()
    fd.set_all_cap(True)
    # Mask form: pass FLAG_ALL_CAP directly.
    assert fd.is_flag_bit_on(FLAG_ALL_CAP) is True
    # Index form: pass 17 (1-based bit index).
    assert fd.get_flag(17) is True
    # Crosscheck: passing the mask to the *index* form would be wrong.
    assert fd.get_flag(FLAG_ALL_CAP) is False  # 65536th bit, definitely unset


# ---------- set_panose writer (pypdfbox extension) ----------


def test_set_panose_creates_style_dict_from_pd_panose() -> None:
    fd = PDFontDescriptor()
    payload = bytes([0x00, 0x08, 2, 11, 6, 3, 5, 4, 5, 2, 2, 4])
    fd.set_panose(PDPanose(payload))

    cos = fd.get_cos_object()
    style = cos.get_dictionary_object(COSName.get_pdf_name("Style"))
    assert isinstance(style, COSDictionary)
    raw = style.get_dictionary_object(COSName.get_pdf_name("Panose"))
    assert isinstance(raw, COSString)
    assert raw.get_bytes() == payload

    # And the round-trip via get_panose works.
    rebuilt = fd.get_panose()
    assert isinstance(rebuilt, PDPanose)
    assert rebuilt.get_bytes() == payload


def test_set_panose_accepts_raw_bytes() -> None:
    fd = PDFontDescriptor()
    payload = bytes(range(12))
    fd.set_panose(payload)

    out = fd.get_panose()
    assert isinstance(out, PDPanose)
    assert out.get_bytes() == payload


def test_set_panose_accepts_bytearray() -> None:
    fd = PDFontDescriptor()
    payload = bytearray(b"\x00\x08" + bytes(10))
    fd.set_panose(payload)
    assert fd.get_panose().get_bytes() == bytes(payload)


def test_set_panose_none_removes_entry_and_empty_style_dict() -> None:
    fd = PDFontDescriptor()
    fd.set_panose(bytes(12))
    assert fd.get_panose() is not None

    fd.set_panose(None)
    assert fd.get_panose() is None
    # Empty Style dict is removed entirely.
    style = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Style"))
    assert style is None


def test_set_panose_none_preserves_non_empty_style_dict() -> None:
    """If /Style carries other keys, removing /Panose leaves the dict in place."""
    fd = PDFontDescriptor()
    fd.set_panose(bytes(12))
    style = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Style"))
    assert isinstance(style, COSDictionary)
    style.set_name(COSName.get_pdf_name("Custom"), "Value")

    fd.set_panose(None)
    surviving = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Style"))
    assert isinstance(surviving, COSDictionary)
    assert surviving.get_dictionary_object(COSName.get_pdf_name("Panose")) is None
    assert surviving.get_name(COSName.get_pdf_name("Custom")) == "Value"


def test_set_panose_none_no_op_when_style_missing() -> None:
    fd = PDFontDescriptor()
    fd.set_panose(None)  # must not raise
    assert fd.get_panose() is None


def test_set_panose_overwrites_existing_panose() -> None:
    fd = PDFontDescriptor()
    fd.set_panose(bytes(12))
    new_payload = bytes([0xFF, 0x80] + list(range(10, 20)))
    fd.set_panose(new_payload)
    assert fd.get_panose().get_bytes() == new_payload
