"""Tests for :class:`DebugTextOverlay`.

The overlay subclasses :class:`PDFTextStripper` and walks a synthetic
single-page PDF — we then assert that the per-glyph ``writeString`` hook
produced at least one rectangle when the corresponding overlay flag is
enabled.

These tests intentionally don't bring in Tk: the overlay is decoupled
from the PIL draw context so a headless run can inspect the rectangle
list.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.debug_text_overlay import (
    DebugRectangle,
    DebugTextOverlay,
    _normalize_rect,
    displacement_or_one,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_one_page_doc_with_text() -> PDDocument:
    """Build a minimal 1-page PDF whose content stream paints one text run."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    content = COSStream()
    content.set_data(b"BT /F0 12 Tf 50 100 Td (hi) Tj ET")
    page.set_contents(content)
    doc.add_page(page)
    return doc


def test_overlay_all_flags_disabled_emits_no_rectangles() -> None:
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=False,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=None)
        assert rects == []
    finally:
        doc.close()


def test_overlay_text_stripper_flag_produces_red_rectangles() -> None:
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=True,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=None)
        assert len(rects) >= 1
        assert all(r.color == "red" for r in rects)
        # Each rectangle is well-ordered after _normalize_rect.
        for r in rects:
            x0, y0, x1, y1 = r.coords
            assert x0 <= x1
            assert y0 <= y1
    finally:
        doc.close()


def test_overlay_render_to_draw_paints_rectangles() -> None:
    from PIL import Image, ImageDraw

    doc = _make_one_page_doc_with_text()
    try:
        image = Image.new("RGB", (200, 200), "white")
        draw = ImageDraw.Draw(image)
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=True,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=draw)
        assert rects, "expected at least one rectangle"
        # The painted image should have at least one non-white pixel
        # where the rectangle was drawn.
        if hasattr(image, "get_flattened_data"):
            flat = image.get_flattened_data()
        else:
            flat = list(image.getdata())
        # ``get_flattened_data`` yields a flat tuple of channels; chunk back.
        if flat and isinstance(flat[0], int):
            pixels = list(zip(flat[0::3], flat[1::3], flat[2::3], strict=False))
        else:
            pixels = list(flat)
        non_white = any(p != (255, 255, 255) for p in pixels)
        assert non_white
    finally:
        doc.close()


def test_overlay_inspection_properties_round_trip() -> None:
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=2.0,
            show_text_stripper=True,
            show_text_stripper_beads=True,
            show_font_bbox=False,
            show_glyph_bounds=True,
        )
        assert overlay.show_text_stripper is True
        assert overlay.show_text_stripper_beads is True
        assert overlay.show_font_bbox is False
        assert overlay.show_glyph_bounds is True
    finally:
        doc.close()


def test_normalize_rect_orders_corners() -> None:
    assert _normalize_rect(10, 20, 30, 40) == (10, 20, 30, 40)
    assert _normalize_rect(30, 40, 10, 20) == (10, 20, 30, 40)
    assert _normalize_rect(30, 20, 10, 40) == (10, 20, 30, 40)


def test_displacement_or_one_handles_missing_get_x() -> None:
    assert displacement_or_one(None) == 1.0
    assert displacement_or_one(object()) == 1.0

    class _D:
        def get_x(self) -> float:
            return 2.5

    assert displacement_or_one(_D()) == 2.5


def test_debug_rectangle_has_default_width() -> None:
    rect = DebugRectangle(coords=(0, 0, 10, 10), color="red")
    assert rect.width == 0.5
    assert rect.color == "red"


# ---------------------------------------------------------------------------
# Direct hook exercise (Wave 1299)
#
# The realistic synthetic-page path covers the ``_collect_text_stripper_rect``
# branch but the ``_collect_font_bbox_rect`` / ``show_glyph`` / thread-bead
# branches require a fully-resolved font or a non-empty thread-beads array,
# both of which are deferred behind heavier scaffolding. We exercise the
# hooks directly with stub objects so the rectangle-collection algebra and
# coordinate flipping are still under coverage.
# ---------------------------------------------------------------------------


class _StubBBox:
    """Tiny duck-typed ``PDRectangle`` (glyph-space, 1/1000 em values)."""

    def __init__(
        self, llx: float = -50.0, lly: float = -200.0, urx: float = 1000.0, ury: float = 800.0
    ) -> None:
        self._llx, self._lly, self._urx, self._ury = llx, lly, urx, ury

    def get_lower_left_x(self) -> float:
        return self._llx

    def get_lower_left_y(self) -> float:
        return self._lly

    def get_upper_right_x(self) -> float:
        return self._urx

    def get_upper_right_y(self) -> float:
        return self._ury


class _StubFont:
    def __init__(self, bbox: _StubBBox | None = None) -> None:
        self._bbox = bbox if bbox is not None else _StubBBox()

    def get_bounding_box(self) -> _StubBBox | None:
        return self._bbox


def _make_stripper(
    *,
    show_text_stripper: bool = False,
    show_text_stripper_beads: bool = False,
    show_font_bbox: bool = False,
    show_glyph_bounds: bool = False,
    scale: float = 1.0,
    crop_height: float = 200.0,
):
    """Return a ``(DebugTextStripper, overlay)`` pair primed with a
    realistic crop-box height so ``_flip_y`` produces sensible coordinates.
    """
    from pypdfbox.debugger.pagepane.debug_text_overlay import DebugTextStripper

    doc = _make_one_page_doc_with_text()
    overlay = DebugTextOverlay(
        doc,
        page_index=0,
        scale=scale,
        show_text_stripper=show_text_stripper,
        show_text_stripper_beads=show_text_stripper_beads,
        show_font_bbox=show_font_bbox,
        show_glyph_bounds=show_glyph_bounds,
    )
    stripper = DebugTextStripper(overlay=overlay)
    stripper._crop_box_height = crop_height  # noqa: SLF001
    return stripper, overlay, doc


def test_collect_font_bbox_rect_emits_blue_when_font_has_bbox() -> None:
    from pypdfbox.text.text_position import TextPosition

    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        tp = TextPosition(
            text="h",
            x=50.0,
            y=100.0,
            font_size=12.0,
            font=_StubFont(),
            width=10.0,
        )
        stripper._collect_font_bbox_rect(tp)  # noqa: SLF001
        rects = list(stripper._collector.rectangles)  # noqa: SLF001
        assert len(rects) == 1
        rect = rects[0]
        assert rect.color == "blue"
        x0, y0, x1, y1 = rect.coords
        assert x0 <= x1
        assert y0 <= y1
    finally:
        doc.close()


def test_collect_font_bbox_rect_skips_when_font_missing() -> None:
    from pypdfbox.text.text_position import TextPosition

    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        tp = TextPosition(text="h", x=0.0, y=0.0, font_size=12.0, font=None)
        stripper._collect_font_bbox_rect(tp)  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_font_bbox_rect_skips_when_bbox_none() -> None:
    from pypdfbox.text.text_position import TextPosition

    class _NoBBoxFont:
        def get_bounding_box(self) -> None:
            return None

    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        tp = TextPosition(text="h", x=0.0, y=0.0, font_size=12.0, font=_NoBBoxFont())
        stripper._collect_font_bbox_rect(tp)  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_font_bbox_rect_skips_when_bbox_get_raises() -> None:
    from pypdfbox.text.text_position import TextPosition

    class _BoomBBoxFont:
        def get_bounding_box(self) -> None:
            raise OSError("disk gone")

    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        tp = TextPosition(text="h", x=0.0, y=0.0, font_size=12.0, font=_BoomBBoxFont())
        stripper._collect_font_bbox_rect(tp)  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_font_bbox_rect_skips_on_attribute_error_font() -> None:
    from pypdfbox.text.text_position import TextPosition

    # ``object()`` has no ``get_bounding_box`` — hits the ``except
    # AttributeError`` branch in ``_collect_font_bbox_rect``.
    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        tp = TextPosition(text="h", x=0.0, y=0.0, font_size=12.0, font=object())
        stripper._collect_font_bbox_rect(tp)  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_text_stripper_rect_skips_on_zero_width() -> None:
    """A 0-width text position must not append a rectangle."""
    from pypdfbox.text.text_position import TextPosition

    stripper, _overlay, doc = _make_stripper(show_text_stripper=True)
    try:
        tp = TextPosition(text="", x=0.0, y=0.0, font_size=12.0, width=0.0)
        stripper._collect_text_stripper_rect(tp)  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_text_stripper_rect_skips_on_type_error() -> None:
    """A position whose accessor raises ``TypeError`` is dropped silently."""

    class _BadTp:
        def get_x(self) -> float:
            raise TypeError("nope")

        def get_y(self) -> float:
            return 0.0

        def get_width_dir_adj(self) -> float:
            return 1.0

        def get_height_dir(self) -> float:
            return 1.0

    stripper, _overlay, doc = _make_stripper(show_text_stripper=True)
    try:
        stripper._collect_text_stripper_rect(_BadTp())  # noqa: SLF001 — duck-typed
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def _stub_super_show_glyph(monkeypatch) -> None:
    """Neutralise ``PDFTextStripper.show_glyph`` so the hook can be invoked
    directly in unit tests without the full content-stream engine plumbing.

    The production ``PDFTextStripper`` does not (yet) expose ``show_glyph``
    so ``super().show_glyph(...)`` inside ``DebugTextStripper.show_glyph``
    raises ``AttributeError`` if called without the host engine. We stub
    it for the duration of each test.
    """
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    monkeypatch.setattr(
        PDFTextStripper,
        "show_glyph",
        lambda *_args, **_kwargs: None,
        raising=False,
    )


def test_show_glyph_emits_cyan_rectangle_with_full_stub_state(monkeypatch) -> None:
    """Exercises the cyan glyph-bounds branch end-to-end with stubs."""
    _stub_super_show_glyph(monkeypatch)

    class _Matrix:
        def get_translate_x(self) -> float:
            return 50.0

        def get_translate_y(self) -> float:
            return 100.0

    class _Disp:
        def get_x(self) -> float:
            return 0.5

    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=True)
    try:
        stripper.show_glyph(_Matrix(), _StubFont(), 0x68, _Disp())
        rects = list(stripper._collector.rectangles)  # noqa: SLF001
        assert len(rects) == 1
        assert rects[0].color == "cyan"
        x0, y0, x1, y1 = rects[0].coords
        assert x0 <= x1
        assert y0 <= y1
    finally:
        doc.close()


def test_show_glyph_skips_when_flag_disabled(monkeypatch) -> None:
    _stub_super_show_glyph(monkeypatch)
    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=False)
    try:
        stripper.show_glyph(None, _StubFont(), 0, None)
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_show_glyph_skips_when_font_none(monkeypatch) -> None:
    _stub_super_show_glyph(monkeypatch)
    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=True)
    try:
        stripper.show_glyph(None, None, 0, None)
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_show_glyph_skips_when_bbox_none(monkeypatch) -> None:
    _stub_super_show_glyph(monkeypatch)

    class _NoBBoxFont:
        def get_bounding_box(self) -> None:
            return None

    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=True)
    try:
        stripper.show_glyph(None, _NoBBoxFont(), 0, None)
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_show_glyph_swallows_bbox_oserror(monkeypatch) -> None:
    _stub_super_show_glyph(monkeypatch)

    class _BoomFont:
        def get_bounding_box(self) -> None:
            raise OSError("read failed")

    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=True)
    try:
        stripper.show_glyph(None, _BoomFont(), 0, None)
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_show_glyph_handles_missing_matrix_translate(monkeypatch) -> None:
    """When the matrix has no ``get_translate_*``, tx/ty fall back to 0."""
    _stub_super_show_glyph(monkeypatch)
    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=True)
    try:
        stripper.show_glyph(object(), _StubFont(), 0, None)
        rects = list(stripper._collector.rectangles)  # noqa: SLF001
        assert len(rects) == 1
        assert rects[0].color == "cyan"
    finally:
        doc.close()


def test_show_glyph_skips_when_bbox_accessor_raises(monkeypatch) -> None:
    _stub_super_show_glyph(monkeypatch)

    class _BadBBox:
        def get_lower_left_x(self) -> float:
            raise ValueError("nope")

        def get_lower_left_y(self) -> float:
            return 0.0

        def get_upper_right_x(self) -> float:
            return 0.0

        def get_upper_right_y(self) -> float:
            return 0.0

    class _Font:
        def get_bounding_box(self) -> _BadBBox:
            return _BadBBox()

    stripper, _overlay, doc = _make_stripper(show_glyph_bounds=True)
    try:
        stripper.show_glyph(None, _Font(), 0, None)
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_thread_beads_emits_green_rectangles() -> None:
    """When the page exposes one or more thread beads, the overlay should
    record a green rectangle for each.
    """

    class _BeadRect:
        def __init__(
            self, llx: float, lly: float, urx: float, ury: float
        ) -> None:
            self._llx, self._lly, self._urx, self._ury = llx, lly, urx, ury

        def get_lower_left_x(self) -> float:
            return self._llx

        def get_lower_left_y(self) -> float:
            return self._lly

        def get_upper_right_x(self) -> float:
            return self._urx

        def get_upper_right_y(self) -> float:
            return self._ury

    class _Bead:
        def __init__(self, rect: _BeadRect | None) -> None:
            self._rect = rect

        def get_rectangle(self) -> _BeadRect | None:
            return self._rect

    class _FakePage:
        def __init__(self, beads: list[_Bead | None]) -> None:
            self._beads = beads

        def get_thread_beads(self) -> list[_Bead | None]:
            return self._beads

    stripper, _overlay, doc = _make_stripper(show_text_stripper_beads=True)
    try:
        page = _FakePage(
            [
                _Bead(_BeadRect(10.0, 20.0, 60.0, 40.0)),
                _Bead(None),  # bead with no rectangle — skipped
                None,  # bead is None — skipped
                _Bead(_BeadRect(80.0, 90.0, 120.0, 110.0)),
            ]
        )
        stripper._collect_thread_beads(page)  # noqa: SLF001
        rects = list(stripper._collector.rectangles)  # noqa: SLF001
        assert len(rects) == 2
        assert all(r.color == "green" for r in rects)
    finally:
        doc.close()


def test_collect_thread_beads_swallows_attribute_error_on_page() -> None:
    stripper, _overlay, doc = _make_stripper(show_text_stripper_beads=True)
    try:
        stripper._collect_thread_beads(object())  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_thread_beads_swallows_oserror_on_page() -> None:
    class _OopsPage:
        def get_thread_beads(self) -> None:
            raise OSError("io")

    stripper, _overlay, doc = _make_stripper(show_text_stripper_beads=True)
    try:
        stripper._collect_thread_beads(_OopsPage())  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_thread_beads_skips_bead_without_rect_method() -> None:
    """A bead with no ``get_rectangle`` triggers ``except AttributeError``."""

    class _BadBead:
        pass

    class _FakePage:
        def get_thread_beads(self) -> list[object]:
            return [_BadBead()]

    stripper, _overlay, doc = _make_stripper(show_text_stripper_beads=True)
    try:
        stripper._collect_thread_beads(_FakePage())  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_thread_beads_skips_bead_rect_with_bad_coords() -> None:
    class _BadRect:
        def get_lower_left_x(self) -> float:
            raise TypeError("nope")

        def get_lower_left_y(self) -> float:
            return 0.0

        def get_upper_right_x(self) -> float:
            return 0.0

        def get_upper_right_y(self) -> float:
            return 0.0

    class _Bead:
        def get_rectangle(self) -> _BadRect:
            return _BadRect()

    class _FakePage:
        def get_thread_beads(self) -> list[_Bead]:
            return [_Bead()]

    stripper, _overlay, doc = _make_stripper(show_text_stripper_beads=True)
    try:
        stripper._collect_thread_beads(_FakePage())  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_overlay_threads_beads_flag_runs_collect_thread_beads() -> None:
    """End-to-end check that the ``show_text_stripper_beads`` flag wires
    through to ``_collect_thread_beads`` on the actual page during
    ``render_to``.
    """
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=False,
            show_text_stripper_beads=True,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )
        # PDPage with no thread beads returns an empty list — that's fine,
        # we just want to drive the conditional and the loop body's
        # ``page.get_thread_beads()`` call without throwing.
        rects = overlay.render_to(draw=None)
        assert rects == []
    finally:
        doc.close()


def test_collect_font_bbox_rect_skips_when_get_font_raises_attribute() -> None:
    """A text position whose ``get_font`` itself raises ``AttributeError``
    (e.g. a dataclass missing ``font``) hits the outer ``except``."""

    class _NoFontTp:
        # ``get_font`` raises rather than returning ``None`` — exercises
        # the dedicated ``except AttributeError`` arm above the ``is
        # None`` guard.
        def get_font(self) -> None:
            raise AttributeError("no font attribute")

    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        stripper._collect_font_bbox_rect(_NoFontTp())  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_collect_font_bbox_rect_skips_when_bbox_coord_raises() -> None:
    """When bbox-coordinate getters raise after the ``font_size`` step the
    inner ``except (AttributeError, TypeError, ValueError)`` swallows it.
    """
    from pypdfbox.text.text_position import TextPosition

    class _BadBBox:
        def get_lower_left_x(self) -> float:
            raise ValueError("malformed")

        def get_lower_left_y(self) -> float:
            return 0.0

        def get_upper_right_x(self) -> float:
            return 0.0

        def get_upper_right_y(self) -> float:
            return 0.0

    class _Font:
        def get_bounding_box(self) -> _BadBBox:
            return _BadBBox()

    stripper, _overlay, doc = _make_stripper(show_font_bbox=True)
    try:
        tp = TextPosition(text="h", x=10.0, y=20.0, font_size=12.0, font=_Font())
        stripper._collect_font_bbox_rect(tp)  # noqa: SLF001
        assert stripper._collector.rectangles == []  # noqa: SLF001
    finally:
        doc.close()


def test_write_string_runs_font_bbox_branch_when_flag_enabled() -> None:
    """End-to-end: enable both ``show_text_stripper`` and ``show_font_bbox``
    on a real synthetic page so the conditional at line 213-214 of
    ``DebugTextStripper.write_string`` evaluates the ``True`` branch.
    """
    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=True,
            show_text_stripper_beads=False,
            show_font_bbox=True,
            show_glyph_bounds=False,
        )
        rects = overlay.render_to(draw=None)
        # The font for /F0 in the synthetic page isn't resolvable so the
        # font_bbox branch falls through silently — we still want at
        # least one red rect from the text-stripper branch.
        assert any(r.color == "red" for r in rects)
    finally:
        doc.close()


def test_strip_page_handles_get_text_oserror(monkeypatch) -> None:
    """The ``except OSError`` arm inside ``strip_page`` swallows extraction
    failure so the overlay still returns whatever rectangles were
    collected before the failure (here: none).
    """
    from pypdfbox.debugger.pagepane import debug_text_overlay as mod

    doc = _make_one_page_doc_with_text()
    try:
        overlay = DebugTextOverlay(
            doc,
            page_index=0,
            scale=1.0,
            show_text_stripper=True,
            show_text_stripper_beads=False,
            show_font_bbox=False,
            show_glyph_bounds=False,
        )

        def _boom(self, _doc):  # noqa: ANN001
            raise OSError("simulated")

        monkeypatch.setattr(mod.DebugTextStripper, "get_text", _boom)
        rects = overlay.render_to(draw=None)
        assert rects == []
    finally:
        doc.close()
