"""Wave 1369 — LegacyPDFStreamEngine adapter behaviour.

The legacy engine is the thin subclass that PDFTextStripper sits on
upstream. In pypdfbox the heuristic glyph-positioning lives inside
PDFTextStripper itself; the ``LegacyPDFStreamEngine`` shim retains the
class so user subclasses keep compiling and so the bookkeeping in
``process_page`` (page rotation, crop-box translate matrix) is
testable independently.

These tests live under ``tests/contentstream/`` because the *adapter
surface* (subclass-of-PDFStreamEngine semantics) is what's being pinned
— not the text-extraction pipeline. The PDFTextStripper-specific
heuristics already have a dedicated test file under ``tests/text/``.
"""

from __future__ import annotations

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.legacy_pdf_stream_engine import LegacyPDFStreamEngine

# ---------- adapter identity ----------


def test_legacy_engine_is_subclass_of_pdf_stream_engine() -> None:
    """``LegacyPDFStreamEngine`` extends ``PDFStreamEngine`` so user
    subclasses can plug into the regular dispatch pipeline."""
    assert issubclass(LegacyPDFStreamEngine, PDFStreamEngine)


def test_legacy_engine_default_state_initialised() -> None:
    """Constructor initialises every legacy-specific slot:
    rotation=0, no page size, no translate matrix, empty font-height
    cache."""
    engine = LegacyPDFStreamEngine()
    assert engine._page_rotation == 0
    assert engine._page_size is None
    assert engine._translate_matrix is None
    assert engine._font_height_map == {}


# ---------- process_page bookkeeping ----------


def test_process_page_records_rotation_and_crop_box() -> None:
    """``process_page`` captures the page's rotation and crop box on
    its private slots before delegating to the parent."""
    engine = LegacyPDFStreamEngine()
    page = PDPage()
    page.set_rotation(90)
    custom_crop = PDRectangle(10.0, 20.0, 110.0, 220.0)
    page.set_crop_box(custom_crop)
    engine.process_page(page)
    assert engine._page_rotation == 90
    # ``get_crop_box`` returns a fresh wrapper but the COS object is
    # the same instance — compare against the rectangle's lower-left.
    assert engine._page_size is not None
    assert engine._page_size.get_lower_left_x() == 10.0
    assert engine._page_size.get_lower_left_y() == 20.0


def test_process_page_origin_crop_box_leaves_translate_matrix_none() -> None:
    """When the crop box's lower-left is (0, 0) no translation is
    needed, so ``_translate_matrix`` stays ``None`` — saves the
    overhead of instantiating a Matrix object on every page."""
    engine = LegacyPDFStreamEngine()
    page = PDPage()  # default crop box is at (0, 0)
    engine.process_page(page)
    assert engine._translate_matrix is None


def test_process_page_non_origin_crop_box_builds_translate_matrix() -> None:
    """A crop box with non-zero lower-left forces a translation so the
    page origin maps back to (0, 0) for downstream text positions."""
    engine = LegacyPDFStreamEngine()
    page = PDPage()
    page.set_crop_box(PDRectangle(50.0, 25.0, 200.0, 200.0))
    engine.process_page(page)
    assert engine._translate_matrix is not None


# ---------- hook overridability ----------


def test_show_glyph_default_is_noop() -> None:
    """The legacy ``show_glyph`` is intentionally a no-op so user
    subclasses can override without worrying about base-class side
    effects. Returns ``None`` and does not mutate state."""
    engine = LegacyPDFStreamEngine()
    # Should not raise; should return None.
    assert engine.show_glyph(None, None, 0x41, None) is None


def test_process_text_position_default_is_noop() -> None:
    """Same contract for ``process_text_position``: defaults to a no-op
    so subclasses (PDFTextStripper) can plug in their own logic."""
    engine = LegacyPDFStreamEngine()
    assert engine.process_text_position(None) is None


# ---------- subclass intercepts hook events ----------


def test_subclass_can_intercept_show_glyph() -> None:
    """A subclass overriding ``show_glyph`` receives every event the
    base engine routes through it — proves the adapter surface still
    routes upstream-equivalently."""

    class _Capture(LegacyPDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.codes: list[int] = []

        def show_glyph(self, text_rendering_matrix, font, code, displacement) -> None:  # type: ignore[override]
            self.codes.append(code)

    engine = _Capture()
    # The base engine's ``show_font_glyph`` forwards to ``show_glyph`` —
    # one call per dispatch.
    engine.show_font_glyph(None, None, 0x41, None)
    engine.show_font_glyph(None, None, 0x42, None)
    assert engine.codes == [0x41, 0x42]


def test_subclass_can_intercept_process_text_position() -> None:
    """Subclass overriding ``process_text_position`` receives every
    explicit invocation — the legacy adapter does not gate or filter
    events out."""

    class _Capture(LegacyPDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.positions: list[object] = []

        def process_text_position(self, text) -> None:  # type: ignore[override]
            self.positions.append(text)

    engine = _Capture()
    engine.process_text_position("first")
    engine.process_text_position("second")
    assert engine.positions == ["first", "second"]


# ---------- compute_font_height is intentionally not tested here ----------
# The heuristic is exercised by ``tests/text/test_legacy_pdf_stream_engine_coverage.py``
# which has access to the font / descriptor fixtures it needs. This file
# focuses on the adapter surface only.
