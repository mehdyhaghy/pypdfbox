"""Upstream-equivalence checks for ``GlyphData``.

Apache PDFBox ships no dedicated ``GlyphDataTest.java`` in
``fontbox/src/test/java/org/apache/fontbox/ttf/``. The class is exercised
indirectly through ``GlyphTable`` and the rendering tests in
``pdfbox-app``. To keep the upstream-mirror surface meaningful we encode
the *behavioural contracts* the Java class documents — anchored to
upstream source line numbers in
``fontbox/src/main/java/org/apache/fontbox/ttf/GlyphData.java`` — as
Python tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import (
    BoundingBox,
    GlyphData,
    GlyphDescription,
    TrueTypeFont,
)
from pypdfbox.fontbox.ttf.glyph_data import _GlyphRenderer

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture
def liberation_sans() -> TrueTypeFont:
    # Function-scoped intentionally: several tests below mutate the
    # cached GlyphData via init_empty_data() / init_data(), so we want
    # a fresh font (and fresh GlyphTable cache) for every test.
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


# ---------- initEmptyData (upstream line 75) -----------------------------


def test_init_empty_data_zero_bounding_box() -> None:
    """Upstream ``initEmptyData`` (GlyphData.java:75) constructs a
    zero-rect BoundingBox + empty simple descript. After calling it,
    every dimension is zero and ``getBoundingBox()`` returns a default
    BoundingBox().
    """
    g = GlyphData()
    g.init_empty_data()
    bb = g.get_bounding_box()
    assert isinstance(bb, BoundingBox)
    assert bb.as_tuple() == (0.0, 0.0, 0.0, 0.0)
    assert g.get_number_of_contours() == 0
    assert g.get_x_minimum() == 0
    assert g.get_y_minimum() == 0
    assert g.get_x_maximum() == 0
    assert g.get_y_maximum() == 0


def test_init_empty_data_description_is_empty() -> None:
    """An empty GlyphData yields a no-points GlyphDescription."""
    g = GlyphData()
    g.init_empty_data()
    desc = g.get_description()
    assert isinstance(desc, GlyphDescription)
    assert desc.is_composite() is False
    assert desc.get_contour_count() == 0
    assert desc.get_point_count() == 0


def test_init_empty_data_path_is_empty() -> None:
    """An empty GlyphData yields an empty path
    (parity with ``initEmptyData`` + ``getPath`` round trip)."""
    g = GlyphData()
    g.init_empty_data()
    assert g.get_path().value == []


def test_init_empty_data_resets_after_real_glyph(
    liberation_sans: TrueTypeFont,
) -> None:
    """``initEmptyData`` must clear any previously bound glyph."""
    g = liberation_sans.get_glyph(0)
    assert g is not None
    # Force initialisation to populate non-zero state.
    assert g.get_x_maximum() > 0
    g.init_empty_data()
    assert g.get_bounding_box().as_tuple() == (0.0, 0.0, 0.0, 0.0)
    assert g.get_number_of_contours() == 0


# ---------- initData (upstream line 47) ----------------------------------


def test_init_data_rebinds_glyf_table(liberation_sans: TrueTypeFont) -> None:
    """Upstream ``initData(GlyphTable, TTFDataStream, int, int)``
    (GlyphData.java:47) reads the bbox + numberOfContours and dispatches
    the descript constructor. In the wrapper port, re-binding the parent
    ``glyf`` table is the substantive work — accessor calls afterwards
    must reflect the new parent.
    """
    g = liberation_sans.get_glyph(0)
    assert g is not None
    glyph_table = liberation_sans.get_glyph_table()
    assert glyph_table is not None
    # Re-binding to the same parent is a no-op semantically; the
    # accessors must continue to return the same bbox and contour count
    # as before.
    expected_bbox = g.get_bounding_box().as_tuple()
    expected_contours = g.get_number_of_contours()
    g.init_data(glyph_table, None, 0, 0)
    assert g.get_bounding_box().as_tuple() == expected_bbox
    assert g.get_number_of_contours() == expected_contours


def test_init_data_followed_by_init_empty_data() -> None:
    """initData -> initEmptyData round trip must end up empty."""
    g = GlyphData()
    g.init_empty_data()
    assert g.get_bounding_box().as_tuple() == (0.0, 0.0, 0.0, 0.0)
    g.init_data(None, None, 0, 0)
    g.init_empty_data()
    assert g.get_bounding_box().as_tuple() == (0.0, 0.0, 0.0, 0.0)


# ---------- glyph_renderer (upstream line 111) ---------------------------


def test_glyph_renderer_returns_renderer_on_empty_glyph() -> None:
    """``getPath`` upstream constructs ``new GlyphRenderer(...)``
    (GlyphData.java:111). The wrapper exposes the renderer factory as
    ``glyph_renderer()``; on empty glyphs the renderer's path is empty.
    """
    g = GlyphData()
    renderer = g.glyph_renderer()
    assert isinstance(renderer, _GlyphRenderer)
    assert renderer.get_path().value == []


def test_glyph_renderer_path_matches_get_path(
    liberation_sans: TrueTypeFont,
) -> None:
    """Upstream ``getPath()`` is sugar for
    ``new GlyphRenderer(glyphDescription).getPath()``. The two paths
    must agree byte-for-byte.
    """
    g = liberation_sans.get_glyph(0)
    assert g is not None
    direct = g.get_path().value
    via_renderer = g.glyph_renderer().get_path().value
    assert direct == via_renderer
    assert direct, "real glyph should produce a non-empty path"


# ---------- accessor parity surface --------------------------------------


def test_bounding_box_accessor_matches_min_max(
    liberation_sans: TrueTypeFont,
) -> None:
    """Upstream's ``getBoundingBox()`` (line 86) returns a
    ``BoundingBox(xMin, yMin, xMax, yMax)``. The four scalar accessors
    (lines 117/126/135/144) must report the same numbers.
    """
    g = liberation_sans.get_glyph(0)
    assert g is not None
    bb = g.get_bounding_box()
    assert bb.get_lower_left_x() == g.get_x_minimum()
    assert bb.get_lower_left_y() == g.get_y_minimum()
    assert bb.get_upper_right_x() == g.get_x_maximum()
    assert bb.get_upper_right_y() == g.get_y_maximum()


def test_get_description_returns_glyph_description(
    liberation_sans: TrueTypeFont,
) -> None:
    """Upstream ``getDescription()`` (line 100) returns a
    ``GlyphDescription``. A real glyph must produce a populated one.
    """
    g = liberation_sans.get_glyph(0)
    assert g is not None
    desc = g.get_description()
    assert isinstance(desc, GlyphDescription)
    assert desc.get_point_count() > 0
