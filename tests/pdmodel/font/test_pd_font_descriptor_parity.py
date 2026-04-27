"""Parity-style tests for ``PDFontDescriptor`` flag bits + numeric metrics.

Mirrors the surface exercised by upstream
``org.apache.pdfbox.pdmodel.font.PDFontDescriptorTest`` plus the bit
predicates documented in PDF 32000-1 §9.8.2 Table 123.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat
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
