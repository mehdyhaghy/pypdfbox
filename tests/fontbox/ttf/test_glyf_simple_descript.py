"""Tests for :class:`pypdfbox.fontbox.ttf.glyf_simple_descript.GlyfSimpleDescript`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def test_empty_descript_construction() -> None:
    d = GlyfSimpleDescript()
    assert d.get_point_count() == 0
    assert d.get_contour_count() == 0
    assert d.is_composite() is False


def test_zero_contour_construction_does_not_read_stream() -> None:
    # numberOfContours == 0 → constructor returns immediately, even
    # with an empty stream (matches upstream lines 67-71).
    stream = MemoryTTFDataStream(b"")
    d = GlyfSimpleDescript(0, stream, 0)
    assert d.get_point_count() == 0
    assert d.get_contour_count() == 0


def test_empty_single_contour_sentinel() -> None:
    # PDFBOX-2939: a single contour with endPt == 0xFFFF should be
    # treated as the "no points" sentinel (line 77).
    stream = MemoryTTFDataStream(bytes([0xFF, 0xFF]))
    d = GlyfSimpleDescript(1, stream, 0)
    assert d.get_point_count() == 0
    assert d.get_contour_count() == 1


def test_simple_three_point_triangle() -> None:
    """Hand-construct a one-contour 3-point triangle and verify decode."""
    # Layout:
    #   endPtsOfContours: [0x0002]  (3 points)
    #   instructionLength: 0
    #   flags (3 bytes, all ON_CURVE + X_DUAL + Y_DUAL = 0x31 keeps
    #   short-vector bit clear, so x/y read as signed shorts):
    #     0x01 = ON_CURVE only (so signed-short deltas for x/y)
    #     0x01
    #     0x01
    #   xCoordinates: 10, 20, -30 (signed shorts, relative)
    #     -> absolute x: 10, 30, 0
    #   yCoordinates: 0, 100, -50
    #     -> absolute y: 0, 100, 50
    payload = bytes(
        [
            0x00, 0x02,  # endPtsOfContours[0] = 2
            0x00, 0x00,  # instructionLength = 0
            0x01, 0x01, 0x01,  # flags
            # x deltas (signed shorts)
            0x00, 0x0A,  # +10
            0x00, 0x14,  # +20
            0xFF, 0xE2,  # -30
            # y deltas (signed shorts)
            0x00, 0x00,  # 0
            0x00, 0x64,  # +100
            0xFF, 0xCE,  # -50
        ]
    )
    stream = MemoryTTFDataStream(payload)
    d = GlyfSimpleDescript(1, stream, 0)
    assert d.get_contour_count() == 1
    assert d.get_point_count() == 3
    assert d.get_end_pt_of_contours(0) == 2
    for i in range(3):
        assert d.get_flags(i) == GlyfDescript.ON_CURVE
    assert d.get_x_coordinate(0) == 10
    assert d.get_x_coordinate(1) == 30
    assert d.get_x_coordinate(2) == 0
    assert d.get_y_coordinate(0) == 0
    assert d.get_y_coordinate(1) == 100
    assert d.get_y_coordinate(2) == 50
    assert d.is_composite() is False
    # No instructions were read.
    assert d.get_instructions() == []


def test_flag_repeat_overflow_raises() -> None:
    # A REPEAT flag asking for more bytes than remain must raise OSError
    # to match the upstream IOException at line 219.
    # Single contour, 2 points; flag stream emits a REPEAT-once but
    # repeat count overflows.
    payload = bytes(
        [
            0x00, 0x01,  # endPtsOfContours[0] = 1 -> 2 points
            0x00, 0x00,  # instructionLength = 0
            0x08, 0x05,  # flag with REPEAT (0x08), repeat count 5 (overflow)
        ]
    )
    stream = MemoryTTFDataStream(payload)
    with pytest.raises(OSError, match="repeat count"):
        GlyfSimpleDescript(1, stream, 0)


def test_from_glyph_wraps_fonttools_simple_glyph(liberation_sans: TrueTypeFont) -> None:
    glyf = liberation_sans._tt["glyf"]
    # Find a non-composite glyph with at least one contour.
    name = next(
        n
        for n in glyf.glyphs
        if int(getattr(glyf[n], "numberOfContours", 0)) > 0
    )
    glyph = glyf[name]
    d = GlyfSimpleDescript.from_glyph(glyph, glyf)
    assert d.is_composite() is False
    assert d.get_contour_count() == int(glyph.numberOfContours)
    assert d.get_point_count() > 0
    # End-points must be monotonically non-decreasing.
    last = -1
    for i in range(d.get_contour_count()):
        end = d.get_end_pt_of_contours(i)
        assert end >= last
        last = end


def test_from_glyph_rejects_composite(liberation_sans: TrueTypeFont) -> None:
    glyf = liberation_sans._tt["glyf"]
    composites = [n for n in glyf.glyphs if glyf[n].isComposite()]
    if not composites:
        pytest.skip("font has no composite glyphs")
    with pytest.raises(ValueError):
        GlyfSimpleDescript.from_glyph(glyf[composites[0]], glyf)
