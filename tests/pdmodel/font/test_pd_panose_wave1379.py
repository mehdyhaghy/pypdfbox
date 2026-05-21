"""Wave 1379 — per-byte PANOSE category accessors closure (agent B).

The 10 ``get_*`` byte accessors on :class:`PDPanoseClassification` already
ship (wave 41+); wave 1379 adds the matched ``set_*`` setters plus the
named integer constants for each category's enumerated values (Family
Kind, Serif Style, Weight, Proportion, Contrast, Stroke Variation, Arm
Style, Letterform, Midline, X-Height). The OS/2 PANOSE specification
defines the value-to-name mapping; these tests pin both the constant
values and the setter round-trips.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.pd_font_descriptor import PDPanoseClassification

# ---------------------------------------------------------------------------
# Universal "Any" / "No Fit" constants — apply to every byte
# ---------------------------------------------------------------------------


def test_universal_any_and_no_fit_constants() -> None:
    assert PDPanoseClassification.ANY == 0
    assert PDPanoseClassification.NO_FIT == 1


# ---------------------------------------------------------------------------
# Serif Style (byte 1) — Latin Text family enumeration
# ---------------------------------------------------------------------------


def test_serif_style_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.SERIF_STYLE_COVE == 2
    assert PDPanoseClassification.SERIF_STYLE_OBTUSE_COVE == 3
    assert PDPanoseClassification.SERIF_STYLE_SQUARE_COVE == 4
    assert PDPanoseClassification.SERIF_STYLE_OBTUSE_SQUARE_COVE == 5
    assert PDPanoseClassification.SERIF_STYLE_SQUARE == 6
    assert PDPanoseClassification.SERIF_STYLE_THIN == 7
    assert PDPanoseClassification.SERIF_STYLE_BONE == 8
    assert PDPanoseClassification.SERIF_STYLE_EXAGGERATED == 9
    assert PDPanoseClassification.SERIF_STYLE_TRIANGLE == 10
    assert PDPanoseClassification.SERIF_STYLE_NORMAL_SANS == 11
    assert PDPanoseClassification.SERIF_STYLE_OBTUSE_SANS == 12
    assert PDPanoseClassification.SERIF_STYLE_PERP_SANS == 13
    assert PDPanoseClassification.SERIF_STYLE_FLARED == 14
    assert PDPanoseClassification.SERIF_STYLE_ROUNDED == 15


# ---------------------------------------------------------------------------
# Weight (byte 2)
# ---------------------------------------------------------------------------


def test_weight_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.WEIGHT_VERY_LIGHT == 2
    assert PDPanoseClassification.WEIGHT_LIGHT == 3
    assert PDPanoseClassification.WEIGHT_THIN == 4
    assert PDPanoseClassification.WEIGHT_BOOK == 5
    assert PDPanoseClassification.WEIGHT_MEDIUM == 6
    assert PDPanoseClassification.WEIGHT_DEMI == 7
    assert PDPanoseClassification.WEIGHT_BOLD == 8
    assert PDPanoseClassification.WEIGHT_HEAVY == 9
    assert PDPanoseClassification.WEIGHT_BLACK == 10
    assert PDPanoseClassification.WEIGHT_NORD == 11


# ---------------------------------------------------------------------------
# Proportion (byte 3)
# ---------------------------------------------------------------------------


def test_proportion_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.PROPORTION_OLD_STYLE == 2
    assert PDPanoseClassification.PROPORTION_MODERN == 3
    assert PDPanoseClassification.PROPORTION_EVEN_WIDTH == 4
    assert PDPanoseClassification.PROPORTION_EXPANDED == 5
    assert PDPanoseClassification.PROPORTION_CONDENSED == 6
    assert PDPanoseClassification.PROPORTION_USUAL_WIDTH == 7
    assert PDPanoseClassification.PROPORTION_VERY_EXPANDED == 8
    assert PDPanoseClassification.PROPORTION_VERY_CONDENSED == 9
    assert PDPanoseClassification.PROPORTION_MONOSPACED == 10


# ---------------------------------------------------------------------------
# Contrast (byte 4)
# ---------------------------------------------------------------------------


def test_contrast_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.CONTRAST_NONE == 2
    assert PDPanoseClassification.CONTRAST_VERY_LOW == 3
    assert PDPanoseClassification.CONTRAST_LOW == 4
    assert PDPanoseClassification.CONTRAST_MEDIUM_LOW == 5
    assert PDPanoseClassification.CONTRAST_MEDIUM == 6
    assert PDPanoseClassification.CONTRAST_MEDIUM_HIGH == 7
    assert PDPanoseClassification.CONTRAST_HIGH == 8
    assert PDPanoseClassification.CONTRAST_VERY_HIGH == 9


# ---------------------------------------------------------------------------
# Stroke Variation (byte 5)
# ---------------------------------------------------------------------------


def test_stroke_variation_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.STROKE_VARIATION_NO_VARIATION == 2
    assert PDPanoseClassification.STROKE_VARIATION_GRADUAL_DIAGONAL == 3
    assert PDPanoseClassification.STROKE_VARIATION_GRADUAL_TRANSITIONAL == 4
    assert PDPanoseClassification.STROKE_VARIATION_GRADUAL_VERTICAL == 5
    assert PDPanoseClassification.STROKE_VARIATION_GRADUAL_HORIZONTAL == 6
    assert PDPanoseClassification.STROKE_VARIATION_RAPID_VERTICAL == 7
    assert PDPanoseClassification.STROKE_VARIATION_RAPID_HORIZONTAL == 8
    assert PDPanoseClassification.STROKE_VARIATION_INSTANT_VERTICAL == 9
    assert PDPanoseClassification.STROKE_VARIATION_INSTANT_HORIZONTAL == 10


# ---------------------------------------------------------------------------
# Arm Style (byte 6)
# ---------------------------------------------------------------------------


def test_arm_style_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_HORZ == 2
    assert PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_WEDGE == 3
    assert PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_VERT == 4
    assert PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_SINGLE_SERIF == 5
    assert PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_DOUBLE_SERIF == 6
    assert PDPanoseClassification.ARM_STYLE_NON_STRAIGHT_ARMS_HORZ == 7
    assert PDPanoseClassification.ARM_STYLE_NON_STRAIGHT_ARMS_WEDGE == 8
    assert PDPanoseClassification.ARM_STYLE_NON_STRAIGHT_ARMS_VERT == 9
    assert PDPanoseClassification.ARM_STYLE_NON_STRAIGHT_ARMS_SINGLE_SERIF == 10
    assert PDPanoseClassification.ARM_STYLE_NON_STRAIGHT_ARMS_DOUBLE_SERIF == 11


# ---------------------------------------------------------------------------
# Letterform (byte 7)
# ---------------------------------------------------------------------------


def test_letterform_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.LETTERFORM_NORMAL_CONTACT == 2
    assert PDPanoseClassification.LETTERFORM_NORMAL_WEIGHTED == 3
    assert PDPanoseClassification.LETTERFORM_NORMAL_BOXED == 4
    assert PDPanoseClassification.LETTERFORM_NORMAL_FLATTENED == 5
    assert PDPanoseClassification.LETTERFORM_NORMAL_ROUNDED == 6
    assert PDPanoseClassification.LETTERFORM_NORMAL_OFF_CENTER == 7
    assert PDPanoseClassification.LETTERFORM_NORMAL_SQUARE == 8
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_CONTACT == 9
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_WEIGHTED == 10
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_BOXED == 11
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_FLATTENED == 12
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_ROUNDED == 13
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_OFF_CENTER == 14
    assert PDPanoseClassification.LETTERFORM_OBLIQUE_SQUARE == 15


# ---------------------------------------------------------------------------
# Midline (byte 8)
# ---------------------------------------------------------------------------


def test_midline_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.MIDLINE_STANDARD_TRIMMED == 2
    assert PDPanoseClassification.MIDLINE_STANDARD_POINTED == 3
    assert PDPanoseClassification.MIDLINE_STANDARD_SERIFED == 4
    assert PDPanoseClassification.MIDLINE_HIGH_TRIMMED == 5
    assert PDPanoseClassification.MIDLINE_HIGH_POINTED == 6
    assert PDPanoseClassification.MIDLINE_HIGH_SERIFED == 7
    assert PDPanoseClassification.MIDLINE_CONSTANT_TRIMMED == 8
    assert PDPanoseClassification.MIDLINE_CONSTANT_POINTED == 9
    assert PDPanoseClassification.MIDLINE_CONSTANT_SERIFED == 10
    assert PDPanoseClassification.MIDLINE_LOW_TRIMMED == 11
    assert PDPanoseClassification.MIDLINE_LOW_POINTED == 12
    assert PDPanoseClassification.MIDLINE_LOW_SERIFED == 13


# ---------------------------------------------------------------------------
# X-Height (byte 9)
# ---------------------------------------------------------------------------


def test_x_height_constants_match_panose_spec() -> None:
    assert PDPanoseClassification.X_HEIGHT_CONSTANT_SMALL == 2
    assert PDPanoseClassification.X_HEIGHT_CONSTANT_STANDARD == 3
    assert PDPanoseClassification.X_HEIGHT_CONSTANT_LARGE == 4
    assert PDPanoseClassification.X_HEIGHT_DUCKING_SMALL == 5
    assert PDPanoseClassification.X_HEIGHT_DUCKING_STANDARD == 6
    assert PDPanoseClassification.X_HEIGHT_DUCKING_LARGE == 7


# ---------------------------------------------------------------------------
# Setters — round-trip with the matched getters
# ---------------------------------------------------------------------------


def _fresh() -> PDPanoseClassification:
    return PDPanoseClassification(b"\x00" * 10)


def test_set_family_kind_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_family_kind(PDPanoseClassification.FAMILY_KIND_LATIN_TEXT)
    assert cls_obj.get_family_kind() == 2
    assert cls_obj.get_bytes()[0] == 2


def test_set_serif_style_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_serif_style(PDPanoseClassification.SERIF_STYLE_BONE)
    assert cls_obj.get_serif_style() == 8
    assert cls_obj.get_bytes()[1] == 8


def test_set_weight_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_weight(PDPanoseClassification.WEIGHT_BOLD)
    assert cls_obj.get_weight() == 8
    assert cls_obj.get_bytes()[2] == 8


def test_set_proportion_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_proportion(PDPanoseClassification.PROPORTION_MONOSPACED)
    assert cls_obj.get_proportion() == 10
    assert cls_obj.get_bytes()[3] == 10


def test_set_contrast_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_contrast(PDPanoseClassification.CONTRAST_HIGH)
    assert cls_obj.get_contrast() == 8
    assert cls_obj.get_bytes()[4] == 8


def test_set_stroke_variation_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_stroke_variation(
        PDPanoseClassification.STROKE_VARIATION_RAPID_VERTICAL
    )
    assert cls_obj.get_stroke_variation() == 7
    assert cls_obj.get_bytes()[5] == 7


def test_set_arm_style_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_arm_style(PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_WEDGE)
    assert cls_obj.get_arm_style() == 3
    assert cls_obj.get_bytes()[6] == 3


def test_set_letterform_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_letterform(PDPanoseClassification.LETTERFORM_OBLIQUE_ROUNDED)
    assert cls_obj.get_letterform() == 13
    assert cls_obj.get_bytes()[7] == 13


def test_set_midline_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_midline(PDPanoseClassification.MIDLINE_HIGH_SERIFED)
    assert cls_obj.get_midline() == 7
    assert cls_obj.get_bytes()[8] == 7


def test_set_x_height_round_trip() -> None:
    cls_obj = _fresh()
    cls_obj.set_x_height(PDPanoseClassification.X_HEIGHT_DUCKING_LARGE)
    assert cls_obj.get_x_height() == 7
    assert cls_obj.get_bytes()[9] == 7


# ---------------------------------------------------------------------------
# Generic get_byte / set_byte (0..9 index)
# ---------------------------------------------------------------------------


def test_get_byte_matches_per_category_getter() -> None:
    cls_obj = PDPanoseClassification(bytes(range(2, 12)))
    for index in range(10):
        assert cls_obj.get_byte(index) == 2 + index


def test_set_byte_matches_per_category_setter() -> None:
    cls_obj = _fresh()
    for index in range(10):
        cls_obj.set_byte(index, index * 3)
    expected = bytes(i * 3 for i in range(10))
    assert cls_obj.get_bytes() == expected


@pytest.mark.parametrize("bad_index", [-1, 10, 11, 100])
def test_get_byte_out_of_range_raises(bad_index: int) -> None:
    cls_obj = _fresh()
    with pytest.raises(IndexError):
        cls_obj.get_byte(bad_index)


@pytest.mark.parametrize("bad_index", [-1, 10, 11, 100])
def test_set_byte_out_of_range_raises(bad_index: int) -> None:
    cls_obj = _fresh()
    with pytest.raises(IndexError):
        cls_obj.set_byte(bad_index, 0)


# ---------------------------------------------------------------------------
# Setter range validation — accepts -128..255, rejects beyond
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [-128, -1, 0, 127, 128, 255])
def test_set_byte_accepts_signed_and_unsigned_range(value: int) -> None:
    cls_obj = _fresh()
    cls_obj.set_byte(0, value)
    # Read-back goes through signed widening (-128..127); 128..255 wraps
    # to negative for parity with Java byte semantics.
    expected = value - 0x100 if value >= 0x80 else value
    assert cls_obj.get_byte(0) == expected


@pytest.mark.parametrize("value", [-129, 256, 1024, -1024])
def test_set_byte_rejects_out_of_range(value: int) -> None:
    cls_obj = _fresh()
    with pytest.raises(ValueError, match="out of range"):
        cls_obj.set_byte(0, value)


# ---------------------------------------------------------------------------
# Setter mutates the wrapper in place (replaces the underlying bytes)
# ---------------------------------------------------------------------------


def test_setters_mutate_existing_classification_wrapper() -> None:
    cls_obj = _fresh()
    original_id = id(cls_obj)
    cls_obj.set_family_kind(2)
    cls_obj.set_weight(8)
    assert id(cls_obj) == original_id
    # The whole buffer is now the new state.
    assert cls_obj.get_bytes() == bytes([2, 0, 8, 0, 0, 0, 0, 0, 0, 0])


def test_setters_pad_short_buffer_to_required_index() -> None:
    """Upstream stores bytes verbatim — when the buffer is shorter than
    the required category byte, the setter pads with zeros so the
    write succeeds."""
    cls_obj = PDPanoseClassification(b"\x01")  # only 1 byte
    cls_obj.set_x_height(PDPanoseClassification.X_HEIGHT_CONSTANT_STANDARD)
    # Buffer should now span at least 10 bytes.
    data = cls_obj.get_bytes()
    assert len(data) >= 10
    assert data[0] == 1  # preserved
    assert data[9] == 3  # new x-height


# ---------------------------------------------------------------------------
# Round-trip every category through the constant tables
# ---------------------------------------------------------------------------


def test_full_round_trip_all_categories() -> None:
    cls_obj = _fresh()
    cls_obj.set_family_kind(PDPanoseClassification.FAMILY_KIND_LATIN_TEXT)
    cls_obj.set_serif_style(PDPanoseClassification.SERIF_STYLE_ROUNDED)
    cls_obj.set_weight(PDPanoseClassification.WEIGHT_MEDIUM)
    cls_obj.set_proportion(PDPanoseClassification.PROPORTION_USUAL_WIDTH)
    cls_obj.set_contrast(PDPanoseClassification.CONTRAST_LOW)
    cls_obj.set_stroke_variation(
        PDPanoseClassification.STROKE_VARIATION_NO_VARIATION
    )
    cls_obj.set_arm_style(
        PDPanoseClassification.ARM_STYLE_STRAIGHT_ARMS_HORZ
    )
    cls_obj.set_letterform(
        PDPanoseClassification.LETTERFORM_NORMAL_CONTACT
    )
    cls_obj.set_midline(PDPanoseClassification.MIDLINE_STANDARD_TRIMMED)
    cls_obj.set_x_height(PDPanoseClassification.X_HEIGHT_CONSTANT_SMALL)

    assert cls_obj.get_family_kind() == 2
    assert cls_obj.get_serif_style() == 15
    assert cls_obj.get_weight() == 6
    assert cls_obj.get_proportion() == 7
    assert cls_obj.get_contrast() == 4
    assert cls_obj.get_stroke_variation() == 2
    assert cls_obj.get_arm_style() == 2
    assert cls_obj.get_letterform() == 2
    assert cls_obj.get_midline() == 2
    assert cls_obj.get_x_height() == 2


# ---------------------------------------------------------------------------
# Existing predicates still work after setters mutate
# ---------------------------------------------------------------------------


def test_is_latin_text_after_set_family_kind() -> None:
    cls_obj = _fresh()
    cls_obj.set_family_kind(PDPanoseClassification.FAMILY_KIND_LATIN_TEXT)
    assert cls_obj.is_latin_text() is True
    assert cls_obj.is_any() is False
    assert cls_obj.is_no_fit() is False


def test_setters_preserve_other_bytes() -> None:
    """Each setter only touches its byte — confirm by sequencing."""
    cls_obj = PDPanoseClassification(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    cls_obj.set_weight(PDPanoseClassification.WEIGHT_BLACK)
    # All other bytes preserved; only byte 2 changed.
    assert cls_obj.get_bytes() == bytes([1, 2, 10, 4, 5, 6, 7, 8, 9, 10])
