"""Wave 1275 — explicit ``to_string()`` parity for BoundingBox."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyph_data import BoundingBox


def test_to_string_matches_upstream_format() -> None:
    bbox = BoundingBox(1.0, 2.0, 3.0, 4.0)
    assert bbox.to_string() == "[1.0,2.0,3.0,4.0]"


def test_str_delegates_to_to_string() -> None:
    bbox = BoundingBox(0.0, 0.0, 0.0, 0.0)
    assert str(bbox) == bbox.to_string()
    assert str(bbox) == "[0.0,0.0,0.0,0.0]"


def test_to_string_negative_values() -> None:
    bbox = BoundingBox(-1.5, -2.5, 3.5, 4.5)
    assert bbox.to_string() == "[-1.5,-2.5,3.5,4.5]"
