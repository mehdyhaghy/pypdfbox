"""Coverage-focused tests for ``LegacyPDFStreamEngine``.

Targets the ``process_page`` translate-matrix bookkeeping and the
``compute_font_height`` heuristic branches (bbox sentinel, cap-height
clamp, ascent/descent average, Type3 font-matrix transform).
"""

from __future__ import annotations

from unittest.mock import patch

from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.legacy_pdf_stream_engine import LegacyPDFStreamEngine
from pypdfbox.util.matrix import Matrix


# ---------- helpers ---------------------------------------------------


class _FakeFont:
    """Minimal stand-in: just the surface ``compute_font_height`` consumes."""

    def __init__(
        self,
        bbox: PDRectangle,
        descriptor: PDFontDescriptor | None = None,
    ) -> None:
        self._bbox = bbox
        self._descriptor = descriptor

    def get_bounding_box(self) -> PDRectangle:
        return self._bbox

    def get_font_descriptor(self) -> PDFontDescriptor | None:
        return self._descriptor


# ---------- process_page ----------------------------------------------


def test_process_page_origin_crop_box_clears_translate_matrix() -> None:
    """When the crop box starts at (0, 0) the engine skips the translate
    matrix entirely (translate_matrix stays ``None``)."""
    engine = LegacyPDFStreamEngine()
    page = PDPage()  # default crop box at origin (Letter at 0, 0)
    engine.process_page(page)
    assert engine._translate_matrix is None
    assert engine._page_rotation == 0
    assert isinstance(engine._page_size, PDRectangle)
    assert engine._page_size.get_lower_left_x() == 0
    assert engine._page_size.get_lower_left_y() == 0


def test_process_page_offset_crop_box_builds_translate_matrix() -> None:
    """A non-origin crop box installs a translate matrix at
    ``(-llx, -lly)`` so glyph coordinates land in page-relative space."""
    engine = LegacyPDFStreamEngine()
    page = PDPage()
    page.set_crop_box(PDRectangle(50.0, 100.0, 500.0, 700.0))
    engine.process_page(page)
    assert isinstance(engine._translate_matrix, Matrix)
    # get_translate_instance(-50, -100) -> identity with tx=-50, ty=-100
    assert engine._translate_matrix.get_translate_x() == -50.0
    assert engine._translate_matrix.get_translate_y() == -100.0
    assert engine._page_size.get_lower_left_x() == 50.0
    assert engine._page_size.get_lower_left_y() == 100.0


def test_process_page_records_rotation() -> None:
    """``process_page`` captures ``page.get_rotation()`` on the engine."""
    engine = LegacyPDFStreamEngine()
    page = PDPage()
    page.set_rotation(90)
    engine.process_page(page)
    assert engine._page_rotation == 90


# ---------- compute_font_height ---------------------------------------


def test_compute_font_height_no_descriptor_uses_half_bbox_height() -> None:
    """With no font descriptor the result is ``bbox.height / 2 / 1000``."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 800.0)  # height = 800
    font = _FakeFont(bbox)
    height = engine.compute_font_height(font)
    # glyph_height = 800/2 = 400; non-Type3 -> divide by 1000 -> 0.4
    assert height == 0.4


def test_compute_font_height_negative_bbox_y_is_normalized() -> None:
    """The < -32768 sentinel triggers the (-y + 65536) repair."""
    engine = LegacyPDFStreamEngine()
    # lly = -40000 < -32768 -> set_lower_left_y(-(-40000 + 65536)) = -25536
    bbox = PDRectangle(0.0, -40000.0, 1000.0, 800.0)
    font = _FakeFont(bbox)
    engine.compute_font_height(font)
    # After mutation, lly should be -25536 (the repair branch fired).
    assert bbox.get_lower_left_y() == -25536.0


def test_compute_font_height_cap_height_clamps_glyph_height() -> None:
    """When ``cap_height < glyph_height`` (and non-zero), cap_height wins."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 2000.0)  # glyph_height = 1000
    desc = PDFontDescriptor()
    desc.set_cap_height(600.0)  # < 1000 and != 0
    font = _FakeFont(bbox, desc)
    height = engine.compute_font_height(font)
    # glyph_height becomes 600 -> divide by 1000 -> 0.6
    assert height == 0.6


def test_compute_font_height_cap_height_above_glyph_height_ignored() -> None:
    """A cap_height larger than glyph_height does not shrink the result."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 800.0)  # glyph_height = 400
    desc = PDFontDescriptor()
    desc.set_cap_height(700.0)  # > glyph_height, ignored
    font = _FakeFont(bbox, desc)
    height = engine.compute_font_height(font)
    assert height == 0.4  # 400 / 1000 unchanged


def test_compute_font_height_zero_cap_height_skipped() -> None:
    """``cap_height == 0`` short-circuits the cap-height branch."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 800.0)
    desc = PDFontDescriptor()  # cap_height defaults to 0.0
    font = _FakeFont(bbox, desc)
    height = engine.compute_font_height(font)
    assert height == 0.4


def test_compute_font_height_glyph_height_zero_picks_cap_height() -> None:
    """When glyph_height is 0, even a cap_height >= 0 is accepted."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 0.0)  # glyph_height = 0
    desc = PDFontDescriptor()
    desc.set_cap_height(800.0)
    font = _FakeFont(bbox, desc)
    height = engine.compute_font_height(font)
    assert height == 0.8  # cap_height 800 wins, 800/1000


def test_compute_font_height_ascent_descent_average_overrides() -> None:
    """``cap_height > ascent > 0`` and ``descent < 0`` with the average
    smaller than glyph_height swaps in ``(ascent - descent) / 2``."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 2000.0)  # glyph_height = 1000
    desc = PDFontDescriptor()
    desc.set_cap_height(900.0)  # < 1000 -> glyph_height becomes 900
    desc.set_ascent(800.0)  # 900 > 800 > 0
    desc.set_descent(-200.0)  # < 0; (800 - (-200))/2 = 500 < 900
    font = _FakeFont(bbox, desc)
    height = engine.compute_font_height(font)
    # glyph_height becomes 500 -> /1000 -> 0.5
    assert height == 0.5


def test_compute_font_height_ascent_descent_skipped_when_cap_le_ascent() -> None:
    """When ``cap_height <= ascent`` the ascent/descent average is skipped."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 2000.0)
    desc = PDFontDescriptor()
    desc.set_cap_height(500.0)  # <= ascent below
    desc.set_ascent(800.0)
    desc.set_descent(-200.0)
    font = _FakeFont(bbox, desc)
    height = engine.compute_font_height(font)
    # glyph_height = min(1000, 500) = 500 -> /1000 -> 0.5
    assert height == 0.5


def test_compute_font_height_type3_uses_font_matrix_transform() -> None:
    """Type3 fonts run the glyph height through ``font_matrix.transform_point``
    rather than the ``/1000`` fast path."""
    engine = LegacyPDFStreamEngine()
    bbox = PDRectangle(0.0, 0.0, 1000.0, 800.0)  # glyph_height = 400
    font = PDType3Font()
    # Patch the bounding box + descriptor + matrix so the Type3 branch
    # actually returns. The real ``get_font_matrix`` returns a list, but
    # upstream's branch expects a Matrix; force the Matrix shape here.
    matrix = Matrix.get_scale_instance(0.001, 0.002)
    with (
        patch.object(font, "get_bounding_box", return_value=bbox),
        patch.object(font, "get_font_descriptor", return_value=None),
        patch.object(font, "get_font_matrix", return_value=matrix),
    ):
        height = engine.compute_font_height(font)
    # transform_point(0, 400) -> (0 + 0, 400 * 0.002 + 0) = (0, 0.8)
    assert height == 0.8
