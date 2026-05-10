"""Wave 1275 — explicit ``to_string()`` parity for PDPanoseClassification."""

from __future__ import annotations

from pypdfbox.pdmodel.font.pd_font_descriptor import PDPanoseClassification


def test_to_string_matches_upstream_format() -> None:
    cls_obj = PDPanoseClassification(bytes([2, 1, 5, 4, 3, 2, 1, 1, 1, 1]))
    expected = (
        "{ FamilyKind = 2, SerifStyle = 1, Weight = 5, Proportion = 4, "
        "Contrast = 3, StrokeVariation = 2, ArmStyle = 1, Letterform = 1, "
        "Midline = 1, XHeight = 1}"
    )
    assert cls_obj.to_string() == expected


def test_str_delegates_to_to_string() -> None:
    cls_obj = PDPanoseClassification(bytes(10))
    assert str(cls_obj) == cls_obj.to_string()
    assert str(cls_obj) == (
        "{ FamilyKind = 0, SerifStyle = 0, Weight = 0, Proportion = 0, "
        "Contrast = 0, StrokeVariation = 0, ArmStyle = 0, Letterform = 0, "
        "Midline = 0, XHeight = 0}"
    )


def test_to_string_negative_signed_bytes() -> None:
    # 0xFF is -1 as signed byte (matches Java's signed byte behavior).
    cls_obj = PDPanoseClassification(bytes([0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0]))
    out = cls_obj.to_string()
    assert "FamilyKind = -1" in out
    assert "SerifStyle = -1" in out
