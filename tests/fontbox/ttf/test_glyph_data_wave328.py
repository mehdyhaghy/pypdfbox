from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphData, TrueTypeFont

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans_wave328() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def test_wave328_glyph_data_camelcase_aliases_match_pythonic_empty() -> None:
    glyph = GlyphData()

    assert glyph.getBoundingBox() is glyph.get_bounding_box()
    assert glyph.getNumberOfContours() == glyph.get_number_of_contours() == 0
    assert glyph.getXMinimum() == glyph.get_x_minimum() == 0
    assert glyph.getXMaximum() == glyph.get_x_maximum() == 0
    assert glyph.getYMinimum() == glyph.get_y_minimum() == 0
    assert glyph.getYMaximum() == glyph.get_y_maximum() == 0
    assert glyph.getPath().value == glyph.get_path().value == []


def test_wave328_glyph_description_camelcase_aliases_match_pythonic(
    liberation_sans_wave328: TrueTypeFont,
) -> None:
    glyph = liberation_sans_wave328.get_glyph(0)
    assert glyph is not None

    description = glyph.getDescription()
    assert description.isComposite() == description.is_composite() is False
    assert description.getContourCount() == description.get_contour_count() == 2
    assert description.getPointCount() == description.get_point_count() == 8

    for index in range(description.getPointCount()):
        assert description.getXCoordinate(index) == description.get_x_coordinate(index)
        assert description.getYCoordinate(index) == description.get_y_coordinate(index)
        assert description.getFlags(index) == description.get_flags(index)

    for index in range(description.getContourCount()):
        assert description.getEndPtOfContours(index) == description.get_end_pt_of_contours(
            index
        )
