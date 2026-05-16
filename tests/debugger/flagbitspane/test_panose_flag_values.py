"""Coverage for :class:`PanoseFlag` per-byte accessor lookups.

Each of the ten PANOSE bytes has its own English-name lookup table. These
tests pin every accessor to its first valid slot (``"Any"``), one mid-range
value lifted from the upstream lookup table, and confirm that out-of-range
indices raise ``IndexError`` (upstream Java raises ``ArrayIndexOutOfBounds``
— the closest Python equivalent).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.debugger.flagbitspane.panose_flag import PanoseFlag

_PANOSE = COSName.get_pdf_name("Panose")


def _panose_dict(block: bytes) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_PANOSE, COSString(block))
    return d


# 12 bytes: 2-byte sFamilyClass header + 10 PANOSE bytes, all zeros.
_ZERO_BLOCK = bytes(12)


# -- get_family_kind_value --------------------------------------------------

def test_family_kind_zero_is_any():
    assert PanoseFlag.get_family_kind_value(0) == "Any"


def test_family_kind_known():
    assert PanoseFlag.get_family_kind_value(2) == "Latin Text"
    assert PanoseFlag.get_family_kind_value(5) == "Latin Symbol"


def test_family_kind_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_family_kind_value(6)


# -- get_serif_style_value --------------------------------------------------

def test_serif_style_zero_is_any():
    assert PanoseFlag.get_serif_style_value(0) == "Any"


def test_serif_style_known():
    assert PanoseFlag.get_serif_style_value(2) == "Cove"
    assert PanoseFlag.get_serif_style_value(15) == "Rounded"


def test_serif_style_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_serif_style_value(16)


# -- get_weight_value -------------------------------------------------------

def test_weight_zero_is_any():
    assert PanoseFlag.get_weight_value(0) == "Any"


def test_weight_known():
    assert PanoseFlag.get_weight_value(5) == "Book"
    assert PanoseFlag.get_weight_value(11) == "Extra Black"


def test_weight_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_weight_value(12)


# -- get_proportion_value ---------------------------------------------------

def test_proportion_zero_is_any():
    assert PanoseFlag.get_proportion_value(0) == "Any"


def test_proportion_known():
    # Upstream spells "No fit" with a lowercase 'f' in this table only.
    assert PanoseFlag.get_proportion_value(1) == "No fit"
    assert PanoseFlag.get_proportion_value(9) == "Monospaced"


def test_proportion_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_proportion_value(10)


# -- get_contrast_value -----------------------------------------------------

def test_contrast_zero_is_any():
    assert PanoseFlag.get_contrast_value(0) == "Any"


def test_contrast_known():
    assert PanoseFlag.get_contrast_value(6) == "Medium"
    assert PanoseFlag.get_contrast_value(9) == "Very High"


def test_contrast_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_contrast_value(10)


# -- get_stroke_variation_value ---------------------------------------------

def test_stroke_variation_zero_is_any():
    assert PanoseFlag.get_stroke_variation_value(0) == "Any"


def test_stroke_variation_known():
    assert PanoseFlag.get_stroke_variation_value(4) == "Gradual/Transitional"
    assert PanoseFlag.get_stroke_variation_value(10) == "Instant/Horizontal"


def test_stroke_variation_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_stroke_variation_value(11)


# -- get_arm_style_value ----------------------------------------------------

def test_arm_style_zero_is_any():
    assert PanoseFlag.get_arm_style_value(0) == "Any"


def test_arm_style_known():
    assert PanoseFlag.get_arm_style_value(2) == "Straight Arms/Horizontal"
    assert PanoseFlag.get_arm_style_value(11) == "Non-Straight/Double Serif"


def test_arm_style_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_arm_style_value(12)


# -- get_letterform_value ---------------------------------------------------

def test_letterform_zero_is_any():
    assert PanoseFlag.get_letterform_value(0) == "Any"


def test_letterform_known():
    assert PanoseFlag.get_letterform_value(2) == "Normal/Contact"
    assert PanoseFlag.get_letterform_value(15) == "Oblique/Square"


def test_letterform_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_letterform_value(16)


# -- get_midline_value ------------------------------------------------------

def test_midline_zero_is_any():
    assert PanoseFlag.get_midline_value(0) == "Any"


def test_midline_known():
    assert PanoseFlag.get_midline_value(2) == "Standard/Trimmed"
    assert PanoseFlag.get_midline_value(13) == "Low/Serifed"


def test_midline_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_midline_value(14)


# -- get_x_height_value -----------------------------------------------------

def test_x_height_zero_is_any():
    assert PanoseFlag.get_x_height_value(0) == "Any"


def test_x_height_known():
    assert PanoseFlag.get_x_height_value(2) == "Constant/Small"
    assert PanoseFlag.get_x_height_value(7) == "Ducking/Large"


def test_x_height_out_of_range():
    with pytest.raises(IndexError):
        PanoseFlag.get_x_height_value(8)


# -- PANOSE byte-vector input shape -----------------------------------------

def test_panose_block_shape_is_twelve_bytes():
    """The PANOSE COSString carries 12 bytes (2-byte sFamilyClass + 10-byte PANOSE)."""
    pf = PanoseFlag(_panose_dict(_ZERO_BLOCK))
    rows = pf.get_flag_bits()
    # Rows describe PANOSE byte positions 2..11 (10 rows).
    assert len(rows) == 10
    assert [r[0] for r in rows] == list(range(2, 12))


def test_accessors_consumed_by_get_flag_bits():
    """Every row's description must equal what its accessor returns standalone."""
    block = bytes(
        [
            0x00, 0x00,            # sFamilyClass
            0x02,                  # FamilyKind   -> "Latin Text"
            0x0F,                  # SerifStyle   -> "Rounded"
            0x05,                  # Weight       -> "Book"
            0x03,                  # Proportion   -> "Modern"
            0x06,                  # Contrast     -> "Medium"
            0x04,                  # StrokeVar    -> "Gradual/Transitional"
            0x02,                  # ArmStyle     -> "Straight Arms/Horizontal"
            0x01,                  # Letterform   -> "No Fit"
            0x0D,                  # Midline      -> "Low/Serifed"
            0x07,                  # XHeight      -> "Ducking/Large"
        ]
    )
    pf = PanoseFlag(_panose_dict(block))
    rows = pf.get_flag_bits()
    by_name = {row[1]: row[3] for row in rows}
    assert by_name["Family Kind"] == PanoseFlag.get_family_kind_value(2)
    assert by_name["Serif Style"] == PanoseFlag.get_serif_style_value(15)
    assert by_name["Weight"] == PanoseFlag.get_weight_value(5)
    assert by_name["Proportion"] == PanoseFlag.get_proportion_value(3)
    assert by_name["Contrast"] == PanoseFlag.get_contrast_value(6)
    assert by_name["Stroke Variation"] == PanoseFlag.get_stroke_variation_value(4)
    assert by_name["Arm Style"] == PanoseFlag.get_arm_style_value(2)
    assert by_name["Letterform"] == PanoseFlag.get_letterform_value(1)
    assert by_name["Midline"] == PanoseFlag.get_midline_value(13)
    assert by_name["X-height"] == PanoseFlag.get_x_height_value(7)
