"""Wave 1275 round-out: ``COSObject.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.cos.cos_object import COSObject


def test_to_string_default_generation() -> None:
    obj = COSObject(7)
    # Mirrors upstream ``COSObject.toString`` —
    # ``COSObject{<num> <gen> R}`` (COSObject.java line 149).
    assert obj.to_string() == "COSObject{7 0 R}"


def test_to_string_with_generation() -> None:
    obj = COSObject(12, 3)
    assert obj.to_string() == "COSObject{12 3 R}"


def test_to_string_matches_str() -> None:
    obj = COSObject(42, 5)
    assert obj.to_string() == str(obj)
