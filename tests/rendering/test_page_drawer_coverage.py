"""Coverage-boost tests for ``pypdfbox.rendering.page_drawer.PageDrawer``.

These exercises drive the per-page graphics-state walker directly —
path building, clipping, text/font hooks, shading + tiling pattern
delegation, transparency-group stack, blend-mode predicates, soft
masks, dash arrays, optional-content visibility hooks, and the
``TransparencyGroup`` inner-class API. Real content-stream rendering
remains covered by the higher-level renderer fixtures; this module
focuses on the surface area of ``PageDrawer`` itself.
"""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import (
    PageDrawerParameters,
    PDFRenderer,
    RenderDestination,
)
from pypdfbox.rendering.page_drawer import PageDrawer, TransparencyGroup

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class _XYPoint:
    """Small object with ``.x``/``.y`` attrs — what
    ``PageDrawer.append_rectangle`` expects from upstream's ``Point2D``."""

    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)


def _make_doc_and_renderer() -> tuple[PDDocument, PDFRenderer]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    # Prime the renderer's per-render state without doing a full render.
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    import aggdraw  # type: ignore[import-not-found]

    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._scale = 1.0
    from pypdfbox.rendering.pdf_renderer import _GState

    renderer._gs_stack = [_GState()]
    renderer._subpaths = []
    renderer._current_subpath = None
    renderer._current_point = (0.0, 0.0)
    renderer._pending_clip = None
    return doc, renderer


def _make_drawer() -> tuple[PDDocument, PDFRenderer, PageDrawer]:
    doc, renderer = _make_doc_and_renderer()
    page = doc.get_page(0)
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints={"AA": True},
        image_downscaling_optimization_threshold=0.5,
    )
    return doc, renderer, PageDrawer(params)


# ---------------------------------------------------------------------------
# Construction + simple accessors
# ---------------------------------------------------------------------------


def test_construct_drawer_exposes_parameters() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        assert drawer.get_renderer() is renderer
        assert drawer.get_destination() is RenderDestination.VIEW
        assert drawer.is_subsampling_allowed() is False
        assert drawer.get_rendering_hints() == {"AA": True}
        assert drawer.get_image_downscaling_optimization_threshold() == 0.5
        # ``get_graphics`` is None outside draw_page.
        assert drawer.get_graphics() is None
        assert drawer.get_line_path() == []
    finally:
        doc.close()


def test_annotation_filter_round_trip() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        default = drawer.get_annotation_filter()
        assert callable(default)
        sentinel = object()

        def custom(_a: Any) -> bool:
            return False

        drawer.set_annotation_filter(custom)
        assert drawer.get_annotation_filter() is custom
        assert drawer.should_skip_annotation(sentinel) is True
        drawer.set_annotation_filter(lambda _a: True)
        assert drawer.should_skip_annotation(sentinel) is False
        # Explicit None filter → never skip.
        drawer.set_annotation_filter(None)
        assert drawer.should_skip_annotation(sentinel) is False
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Path building & painting
# ---------------------------------------------------------------------------


def test_path_building_operators_grow_line_path_and_subpaths() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        drawer.move_to(10.0, 20.0)
        drawer.line_to(30.0, 20.0)
        drawer.curve_to(40.0, 25.0, 50.0, 30.0, 60.0, 35.0)
        drawer.close_path()
        # Local mirror.
        assert drawer.get_line_path()[0] == ("M", 10.0, 20.0)
        assert drawer.get_line_path()[-1] == ("Z",)
        # Renderer mirror.
        assert renderer._current_subpath is not None
        assert renderer._current_subpath[0] == ("M", 10.0, 20.0)
        assert renderer._current_subpath[-1] == ("Z",)
        assert renderer._current_point == (60.0, 35.0)
    finally:
        doc.close()


def test_line_to_without_prior_move_starts_new_subpath() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        drawer.line_to(5.0, 6.0)
        assert renderer._current_subpath == [("M", 5.0, 6.0)]
        assert renderer._current_point == (5.0, 6.0)
    finally:
        doc.close()


def test_curve_to_without_prior_move_starts_new_subpath() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        drawer.curve_to(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        # Curve-only subpath: implicit move-to at the endpoint.
        assert renderer._current_subpath == [("M", 5.0, 6.0)]
    finally:
        doc.close()


def test_close_path_without_subpath_is_safe() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        # Renderer subpath is None → close_path is a no-op for the renderer
        # but still records on the local line_path.
        drawer.close_path()
        assert ("Z",) in drawer.get_line_path()
    finally:
        doc.close()


def test_append_rectangle_emits_closed_subpath() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        drawer.append_rectangle(
            _XYPoint(0, 0), _XYPoint(10, 0), _XYPoint(10, 20), _XYPoint(0, 20)
        )
        assert ("rect", *drawer.get_line_path()[0][1:]) == drawer.get_line_path()[0]
        # Renderer captured a 5-segment closed subpath.
        sp = renderer._subpaths[-1]
        assert sp[0] == ("M", 0.0, 0.0)
        assert sp[-1] == ("Z",)
        assert renderer._current_subpath is None
    finally:
        doc.close()


def test_stroke_fill_fillstroke_and_clip_paths_clear_line_path() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        drawer.move_to(0, 0)
        drawer.line_to(10, 0)
        drawer.line_to(10, 10)
        drawer.line_to(0, 10)
        drawer.close_path()
        drawer.stroke_path()
        assert drawer.get_line_path() == []

        drawer.move_to(0, 0)
        drawer.line_to(10, 0)
        drawer.line_to(10, 10)
        drawer.close_path()
        drawer.fill_path(winding_rule=0)  # even-odd
        assert drawer.get_line_path() == []

        drawer.move_to(0, 0)
        drawer.line_to(10, 0)
        drawer.line_to(10, 10)
        drawer.close_path()
        drawer.fill_and_stroke_path(winding_rule=1)  # non-zero
        assert drawer.get_line_path() == []

        # Clip operator stages the pending-clip flag.
        drawer.clip(winding_rule=0)
        assert renderer._pending_clip == "W*"
        drawer.clip(winding_rule=1)
        assert renderer._pending_clip == "W"
    finally:
        doc.close()


def test_end_path_resets_path_and_clears_local_mirror() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        drawer.move_to(2, 3)
        drawer.line_to(4, 5)
        drawer.end_path()
        assert drawer.get_line_path() == []
        assert renderer._subpaths == []
        assert renderer._current_subpath is None
    finally:
        doc.close()


def test_set_clip_consumes_pending_clip() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        # No path → nothing to clip, but the helper still runs without error.
        drawer.clip(winding_rule=0)
        drawer.set_clip()
        # Nothing to assert besides "didn't crash"; the renderer's pending
        # clip state is consumed.
    finally:
        doc.close()


def test_get_current_point_none_before_any_op() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.get_current_point() is None
        drawer.move_to(7, 8)
        assert drawer.get_current_point() == (7, 8)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Text-state hooks
# ---------------------------------------------------------------------------


def test_begin_text_resets_text_matrices() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        # Mutate text matrices and verify begin_text resets them to identity.
        renderer._gs.text_matrix = (1, 2, 3, 4, 5, 6)
        renderer._gs.text_line_matrix = (7, 8, 9, 10, 11, 12)
        drawer.begin_text()
        from pypdfbox.rendering.pdf_renderer import _IDENTITY

        assert renderer._gs.text_matrix == _IDENTITY
        assert renderer._gs.text_line_matrix == _IDENTITY
    finally:
        doc.close()


def test_end_text_is_no_op() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        drawer.end_text()  # just verify it doesn't raise
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Image / form / shading / glyph delegation
# ---------------------------------------------------------------------------


def test_draw_image_with_get_image_method_delegates_to_paste() -> None:
    doc, renderer, drawer = _make_drawer()
    pasted: list[Image.Image] = []

    def fake_paste(img: Image.Image) -> None:
        pasted.append(img)

    renderer._paste_image = fake_paste  # type: ignore[attr-defined]

    class _PDImage:
        def get_image(self) -> Image.Image:
            return Image.new("RGB", (5, 5), (1, 2, 3))

    try:
        drawer.draw_image(_PDImage())
        assert len(pasted) == 1
        assert pasted[0].size == (5, 5)
    finally:
        doc.close()


def test_draw_image_get_image_raises_is_swallowed() -> None:
    doc, _renderer, drawer = _make_drawer()

    class _Bad:
        def get_image(self) -> Image.Image:
            raise RuntimeError("decode boom")

    try:
        drawer.draw_image(_Bad())  # must not propagate
    finally:
        doc.close()


def test_draw_image_returns_when_pil_image_is_none() -> None:
    doc, _renderer, drawer = _make_drawer()

    class _NullImage:
        def get_image(self) -> Any:
            return None

    try:
        drawer.draw_image(_NullImage())
    finally:
        doc.close()


def test_draw_image_paste_typeerror_is_swallowed() -> None:
    doc, renderer, drawer = _make_drawer()

    def bad_paste(_img: Any) -> None:
        raise ValueError("paste boom")

    renderer._paste_image = bad_paste  # type: ignore[attr-defined]
    try:
        drawer.draw_image(Image.new("RGB", (3, 3)))
    finally:
        doc.close()


def test_shading_fill_skips_when_no_resources_or_helper() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        # Renderer's resources are None → shading_fill must early-return.
        renderer._resources = None
        drawer.shading_fill(COSName.get_pdf_name("Sh1"))
    finally:
        doc.close()


def test_shading_fill_delegates_to_paint_shading_when_resolved() -> None:
    doc, renderer, drawer = _make_drawer()
    called: list[Any] = []

    class _Resources:
        def get_shading(self, _name: COSName) -> Any:
            return "the-shading"

    renderer._resources = _Resources()

    def fake_paint_shading(shading: Any, **kwargs: Any) -> None:
        called.append((shading, kwargs))

    renderer._paint_shading = fake_paint_shading  # type: ignore[attr-defined]
    try:
        drawer.shading_fill(COSName.get_pdf_name("Sh1"))
        assert called and called[0][0] == "the-shading"
        # region_mask kwarg is forwarded.
        assert "region_mask" in called[0][1]
    finally:
        doc.close()


def test_shading_fill_swallows_helper_errors() -> None:
    doc, renderer, drawer = _make_drawer()

    class _Resources:
        def get_shading(self, _name: COSName) -> Any:
            return "x"

    renderer._resources = _Resources()

    def fake_paint_shading(_s: Any, **_kw: Any) -> None:
        raise ValueError("boom")

    renderer._paint_shading = fake_paint_shading  # type: ignore[attr-defined]
    try:
        drawer.shading_fill(COSName.get_pdf_name("Sh1"))
    finally:
        doc.close()


def test_shading_fill_get_shading_raising_returns_silently() -> None:
    doc, renderer, drawer = _make_drawer()

    class _Resources:
        def get_shading(self, _name: COSName) -> Any:
            raise RuntimeError("missing")

    renderer._resources = _Resources()
    try:
        drawer.shading_fill(COSName.get_pdf_name("X"))
    finally:
        doc.close()


def test_show_form_and_show_annotation_delegate_when_helpers_present() -> None:
    doc, renderer, drawer = _make_drawer()
    forms: list[Any] = []
    annots: list[Any] = []
    renderer._render_form_xobject = lambda form: forms.append(form)  # type: ignore[attr-defined]
    renderer._render_annotation = lambda a: annots.append(a)  # type: ignore[attr-defined]
    try:
        drawer.show_form("form-x")
        assert forms == ["form-x"]
        drawer.show_annotation("ann-1")
        assert annots == ["ann-1"]
        # Filter blocks the annotation.
        drawer.set_annotation_filter(lambda _a: False)
        drawer.show_annotation("ann-2")
        assert annots == ["ann-1"]
    finally:
        doc.close()


def test_show_font_glyph_and_type3_glyph_delegate() -> None:
    doc, renderer, drawer = _make_drawer()
    glyph_calls: list[tuple] = []
    type3_calls: list[tuple] = []
    renderer._render_glyph = lambda *a: glyph_calls.append(a)  # type: ignore[attr-defined]
    renderer._render_type3_glyph = lambda *a: type3_calls.append(a)  # type: ignore[attr-defined]
    try:
        drawer.show_font_glyph("trm", "font", 65, "disp")
        assert len(glyph_calls) == 1
        drawer.show_type3_glyph("trm", "font", 66, "disp")
        assert len(type3_calls) == 1
    finally:
        doc.close()


def test_show_type3_glyph_falls_back_to_font_glyph_when_helper_missing() -> None:
    doc, renderer, drawer = _make_drawer()
    glyph_calls: list[tuple] = []
    renderer._render_glyph = lambda *a: glyph_calls.append(a)  # type: ignore[attr-defined]
    # No _render_type3_glyph attribute on the renderer.
    try:
        drawer.show_type3_glyph("trm", "font", 67, "disp")
        assert len(glyph_calls) == 1
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Marked content / OCG visibility
# ---------------------------------------------------------------------------


def test_begin_end_marked_content_delegate_when_present() -> None:
    doc, renderer, drawer = _make_drawer()
    pushed: list[tuple] = []
    popped: list[None] = []
    renderer._push_marked_content = lambda t, p: pushed.append((t, p))  # type: ignore[attr-defined]
    renderer._pop_marked_content = lambda: popped.append(None)  # type: ignore[attr-defined]
    try:
        drawer.begin_marked_content_sequence(COSName.get_pdf_name("Span"), None)
        drawer.end_marked_content_sequence()
        assert len(pushed) == 1
        assert len(popped) == 1
    finally:
        doc.close()


def test_begin_end_marked_content_skip_when_helpers_missing() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        # No helpers on the renderer — drawer must no-op.
        drawer.begin_marked_content_sequence(COSName.get_pdf_name("Span"), None)
        drawer.end_marked_content_sequence()
    finally:
        doc.close()


def test_is_hidden_ocg_handles_missing_or_failing_renderer() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        assert drawer.is_hidden_ocg(None) is False
        # Renderer raises → drawer must treat as visible.
        renderer.is_group_enabled = lambda _g: (_ for _ in ()).throw(  # type: ignore[attr-defined]
            RuntimeError("boom")
        )
        assert drawer.is_hidden_ocg(object()) is False
        # Renderer says enabled → not hidden.
        renderer.is_group_enabled = lambda _g: True  # type: ignore[attr-defined]
        assert drawer.is_hidden_ocg(object()) is False
        renderer.is_group_enabled = lambda _g: False  # type: ignore[attr-defined]
        assert drawer.is_hidden_ocg(object()) is True
    finally:
        doc.close()


def test_visibility_expressions_default_to_visible() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.is_hidden_ocmd(object()) is False
        assert drawer.is_hidden_visibility_expression(object()) is False
        assert drawer.is_hidden_and_visibility_expression([object()]) is False
        assert drawer.is_hidden_or_visibility_expression([object()]) is False
        # Not(false) → True.
        assert drawer.is_hidden_not_visibility_expression(object()) is True
        # Empty operands.
        assert drawer.is_hidden_and_visibility_expression(None) is False
        assert drawer.is_hidden_or_visibility_expression(None) is True
        assert drawer.is_content_rendered() is True
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Paint / stroke / transfer / soft-mask accessors
# ---------------------------------------------------------------------------


def test_get_paint_uses_resolver_when_present() -> None:
    doc, renderer, drawer = _make_drawer()
    renderer._resolve_color_to_rgb = lambda c: ("rgb", c)  # type: ignore[attr-defined]
    try:
        assert drawer.get_paint("blue") == ("rgb", "blue")
    finally:
        doc.close()


def test_get_paint_returns_color_when_resolver_raises() -> None:
    doc, renderer, drawer = _make_drawer()

    def bad(_c: Any) -> Any:
        raise RuntimeError("fail")

    renderer._resolve_color_to_rgb = bad  # type: ignore[attr-defined]
    try:
        # Resolver raised → fall back to the input color value.
        assert drawer.get_paint("orange") == "orange"
    finally:
        doc.close()


def test_get_paint_without_resolver_returns_color() -> None:
    doc, renderer, drawer = _make_drawer()
    # Strip the helper attribute entirely to hit the "callable(resolver)" miss.
    if hasattr(renderer, "_resolve_color_to_rgb"):
        delattr(renderer, "_resolve_color_to_rgb")
    try:
        assert drawer.get_paint("red") == "red"
    finally:
        doc.close()


def test_get_stroking_and_non_stroking_paint() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        assert drawer.get_stroking_paint() == (0, 0, 0)
        assert drawer.get_non_stroking_paint() == (0, 0, 0)
        renderer._gs.stroke_rgb = (10, 20, 30)
        renderer._gs.fill_rgb = (40, 50, 60)
        assert drawer.get_stroking_paint() == (10, 20, 30)
        assert drawer.get_non_stroking_paint() == (40, 50, 60)
    finally:
        doc.close()


def test_get_stroke_returns_dict_with_line_width() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.line_width = 2.5
        assert drawer.get_stroke() == {"line_width": 2.5}
    finally:
        doc.close()


def test_apply_transfer_function_delegates_or_passes_through() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        # No helper → identity.
        if hasattr(renderer, "_apply_transfer_function"):
            delattr(renderer, "_apply_transfer_function")
        assert drawer.apply_transfer_function("img", "tf") == "img"
        # Helper present → delegated.
        renderer._apply_transfer_function = lambda img, tf: (img, tf)  # type: ignore[attr-defined]
        assert drawer.apply_transfer_function("img2", "tf2") == ("img2", "tf2")
        # Helper raising → identity fallback.
        renderer._apply_transfer_function = lambda *a: (_ for _ in ()).throw(  # type: ignore[attr-defined]
            RuntimeError("x")
        )
        assert drawer.apply_transfer_function("img3", "tf3") == "img3"
    finally:
        doc.close()


def test_apply_soft_mask_to_paint_passes_through() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.apply_soft_mask_to_paint("parent", None) == "parent"
    finally:
        doc.close()


def test_intersect_shading_b_box_noop() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        # No return value, no exception.
        assert drawer.intersect_shading_b_box(None, None) is None
    finally:
        doc.close()


def test_adjust_clip_and_adjust_image_pass_through() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.adjust_clip(["seg"]) == ["seg"]
        assert drawer.adjust_image("gray") == "gray"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Subsampling, dash array, blend, transparency
# ---------------------------------------------------------------------------


def test_get_subsampling_returns_one_when_disallowed() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        # subsampling_allowed=False on the params used by _make_drawer.
        assert drawer.get_subsampling(object(), None) == 1
    finally:
        doc.close()


def test_get_subsampling_returns_one_when_allowed() -> None:
    doc, renderer = _make_doc_and_renderer()
    page = doc.get_page(0)
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=True,
        destination=RenderDestination.VIEW,
        rendering_hints=None,
        image_downscaling_optimization_threshold=0.5,
    )
    drawer = PageDrawer(params)
    try:
        # Lite renderer still returns 1 (correctness over speed).
        assert drawer.get_subsampling(object(), None) == 1
    finally:
        doc.close()


def test_get_dash_array_handles_none_empty_and_values() -> None:
    doc, _renderer, drawer = _make_drawer()

    class _Dash:
        def __init__(self, values: list[float] | None) -> None:
            self._v = values

        def get_dash_array(self) -> list[float] | None:
            return self._v

    class _BadDash:
        def get_dash_array(self) -> list[float]:
            raise RuntimeError("boom")

    try:
        assert drawer.get_dash_array(None) == []
        assert drawer.get_dash_array(_Dash(None)) == []
        assert drawer.get_dash_array(_Dash([1.0, 2.0, 3.5])) == [1.0, 2.0, 3.5]
        assert drawer.get_dash_array(_BadDash()) == []
        # Object without get_dash_array.
        assert drawer.get_dash_array(object()) == []
    finally:
        doc.close()


def test_is_all_zero_dash() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.is_all_zero_dash([]) is True
        assert drawer.is_all_zero_dash(None) is True
        assert drawer.is_all_zero_dash([0.0, 0]) is True
        assert drawer.is_all_zero_dash([0.0, 1.0]) is False
    finally:
        doc.close()


def test_has_blend_mode_false_when_normal_or_none() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.blend_mode = None
        assert drawer.has_blend_mode() is False
        from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

        renderer._gs.blend_mode = BlendMode.NORMAL
        assert drawer.has_blend_mode() is False
        # Pick a non-normal blend mode if available.
        non_normal = getattr(BlendMode, "MULTIPLY", None) or getattr(
            BlendMode, "SCREEN", None
        )
        if non_normal is not None and non_normal is not BlendMode.NORMAL:
            renderer._gs.blend_mode = non_normal
            assert drawer.has_blend_mode() is True
    finally:
        doc.close()


def test_has_transparency_reflects_stack_and_blend() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.has_transparency() is False
        drawer._transparency_group_stack.append(
            TransparencyGroup(form=None, ctm=None)
        )
        assert drawer.has_transparency() is True
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Transparency group rendering
# ---------------------------------------------------------------------------


def test_show_transparency_group_pushes_and_pops_stack() -> None:
    doc, renderer, drawer = _make_drawer()
    snapshots: list[int] = []

    def fake_render(_form: Any) -> None:
        snapshots.append(len(drawer._transparency_group_stack))

    renderer._render_form_xobject = fake_render  # type: ignore[attr-defined]
    try:
        drawer.show_transparency_group(form="form-tx")
        # The stack had exactly one entry during the form render…
        assert snapshots == [1]
        # …and was popped after the render completed.
        assert drawer._transparency_group_stack == []
    finally:
        doc.close()


def test_show_transparency_group_returns_when_no_image() -> None:
    doc, renderer, drawer = _make_drawer()
    renderer._image = None
    try:
        drawer.show_transparency_group(form="x")
        assert drawer._transparency_group_stack == []
    finally:
        doc.close()


def test_show_transparency_group_on_graphics_swaps_image() -> None:
    doc, renderer, drawer = _make_drawer()
    seen_image_size: list[tuple[int, int] | None] = []

    def fake_render(_form: Any) -> None:
        seen_image_size.append(
            renderer._image.size if renderer._image is not None else None
        )

    renderer._render_form_xobject = fake_render  # type: ignore[attr-defined]
    target = Image.new("RGBA", (20, 30), (0, 0, 0, 0))
    original_image = renderer._image
    try:
        drawer.show_transparency_group_on_graphics(form="x", graphics=target)
        # During the render, the renderer's _image was the swapped target.
        assert seen_image_size == [(20, 30)]
        # After: restored.
        assert renderer._image is original_image
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Text clip + draw glyph + tiling pattern delegation
# ---------------------------------------------------------------------------


def test_begin_and_end_text_clip_manage_renderer_state() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        # Renderer has no _text_clippings attribute initially.
        drawer.begin_text_clip()
        assert renderer._text_clippings == []
        renderer._text_clippings.append("glyph-path")
        drawer.end_text_clip()
        assert renderer._text_clippings == []
    finally:
        doc.close()


def test_draw_glyph_delegates() -> None:
    doc, renderer, drawer = _make_drawer()
    captured: list[tuple] = []
    renderer._draw_glyph_path = lambda *a: captured.append(a)  # type: ignore[attr-defined]
    try:
        drawer.draw_glyph("path", "font", 42, "disp", "at")
        assert captured == [("path", "font", 42, "disp", "at")]
    finally:
        doc.close()


def test_draw_buffered_image_uses_paste_pil_when_present() -> None:
    doc, renderer, drawer = _make_drawer()
    calls: list[tuple] = []
    renderer._paste_pil_image = lambda img, at: calls.append((img, at))  # type: ignore[attr-defined]
    img = Image.new("RGB", (3, 3))
    try:
        drawer.draw_buffered_image("pd", img, "at")
        assert calls == [(img, "at")]
    finally:
        doc.close()


def test_draw_buffered_image_fallback_calls_draw_image() -> None:
    doc, _renderer, drawer = _make_drawer()
    captured: list[Any] = []
    drawer.draw_image = lambda pd: captured.append(pd)  # type: ignore[method-assign]
    try:
        drawer.draw_buffered_image("pd", object(), None)
        assert captured == ["pd"]
    finally:
        doc.close()


def test_draw_tiling_pattern_delegates_with_full_canvas_mask() -> None:
    doc, renderer, drawer = _make_drawer()
    seen: list[tuple] = []
    renderer._paint_tiling_pattern = lambda p, **kw: seen.append((p, kw))  # type: ignore[attr-defined]
    try:
        drawer.draw_tiling_pattern("pat", "color", "cs")
        assert seen and seen[0][0] == "pat"
        mask = seen[0][1].get("region_mask")
        assert mask is not None
        assert mask.size == renderer._image.size
    finally:
        doc.close()


def test_draw_tiling_pattern_with_clip_mask_multiplies() -> None:
    doc, renderer, drawer = _make_drawer()
    seen: list[tuple] = []
    renderer._paint_tiling_pattern = lambda p, **kw: seen.append((p, kw))  # type: ignore[attr-defined]
    # Set a partial clip mask so the multiply branch runs.
    clip = Image.new("L", renderer._image.size, 128)
    renderer._gs.clip_mask = clip
    try:
        drawer.draw_tiling_pattern("pat", "color", "cs")
        assert seen
        mask = seen[0][1]["region_mask"]
        # Multiply collapses the 255 base with the 128 clip → ~128.
        assert mask.getpixel((0, 0)) == 128
    finally:
        doc.close()


def test_draw_tiling_pattern_returns_when_no_image() -> None:
    doc, renderer, drawer = _make_drawer()
    renderer._image = None
    seen: list[tuple] = []
    renderer._paint_tiling_pattern = lambda *a, **kw: seen.append((a, kw))  # type: ignore[attr-defined]
    try:
        drawer.draw_tiling_pattern("pat", "c", "cs")
        assert seen == []
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def test_get_inv_lookup_table_lazy_and_cached() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        t1 = drawer.get_inv_lookup_table()
        t2 = drawer.get_inv_lookup_table()
        assert t1 is t2
        assert t1[0] == 255 and t1[255] == 0 and len(t1) == 256
    finally:
        doc.close()


def test_clamp_color_handles_iterables_floats_and_garbage() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        assert drawer.clamp_color([2.0, -1.0, 0.5]) == [1.0, 0.0, 0.5]
        assert drawer.clamp_color(0.3) == pytest.approx(0.3)
        assert drawer.clamp_color(2.5) == 1.0
        assert drawer.clamp_color(-1.0) == 0.0
        # Non-iterable, non-float passes through unchanged.
        sentinel = object()
        assert drawer.clamp_color(sentinel) is sentinel
    finally:
        doc.close()


def test_is_rectangular_classifies_basic_paths() -> None:
    doc, _renderer, drawer = _make_drawer()
    try:
        # Axis-aligned rect-shaped path → True.
        rect_path = [
            ("M", 0, 0),
            ("L", 10, 0),
            ("L", 10, 5),
            ("L", 0, 5),
            ("Z",),
        ]
        assert drawer.is_rectangular(rect_path) is True
        # Triangle → False.
        tri = [("M", 0, 0), ("L", 10, 0), ("L", 5, 5), ("Z",)]
        assert drawer.is_rectangular(tri) is False
        # Skewed quad — diagonal edge → not axis-aligned → False.
        skew = [
            ("M", 0, 0),
            ("L", 10, 1),
            ("L", 10, 5),
            ("L", 0, 5),
            ("Z",),
        ]
        assert drawer.is_rectangular(skew) is False
        # Empty path with empty local mirror → False.
        assert drawer.is_rectangular([]) is False
    finally:
        doc.close()


def test_transfer_clip_uses_set_clip_when_available() -> None:
    doc, renderer, drawer = _make_drawer()
    renderer._gs.clip_mask = Image.new("L", (5, 5), 200)

    class _Target:
        def __init__(self) -> None:
            self.clip: Any = None

        def set_clip(self, c: Any) -> None:
            self.clip = c

    t = _Target()
    try:
        drawer.transfer_clip(t)
        assert t.clip is renderer._gs.clip_mask
    finally:
        doc.close()


def test_transfer_clip_noops_when_target_has_no_setter() -> None:
    doc, renderer, drawer = _make_drawer()
    renderer._gs.clip_mask = Image.new("L", (5, 5), 200)
    try:
        # Plain object — no set_clip method, must not raise.
        drawer.transfer_clip(object())
    finally:
        doc.close()


def test_transfer_clip_noop_when_clip_or_graphics_none() -> None:
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.clip_mask = None
        drawer.transfer_clip(object())  # clip None → early return
        renderer._gs.clip_mask = Image.new("L", (5, 5), 0)
        drawer.transfer_clip(None)  # graphics None → early return
    finally:
        doc.close()


def test_set_rendering_hints_populates_when_none() -> None:
    doc, renderer = _make_doc_and_renderer()
    page = doc.get_page(0)
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints=None,
        image_downscaling_optimization_threshold=0.5,
    )
    drawer = PageDrawer(params)
    try:
        # Active graphics not yet bound — but set_rendering_hints still works.
        drawer._graphics = renderer._image
        drawer.set_rendering_hints()
        hints = drawer.get_rendering_hints()
        assert isinstance(hints, dict)
        assert "KEY_INTERPOLATION" in hints
    finally:
        doc.close()


def test_clip_from_static_helper() -> None:
    # Class-level static method — exercise both branches.
    assert PageDrawer._clip_from(None) is None
    img = Image.new("RGB", (12, 34))
    assert PageDrawer._clip_from(img) == (0, 0, 12, 34)

    class _NoSize:
        pass

    assert PageDrawer._clip_from(_NoSize()) is None


# ---------------------------------------------------------------------------
# TransparencyGroup inner class
# ---------------------------------------------------------------------------


def test_transparency_group_image_and_bbox_round_trip() -> None:
    tg = TransparencyGroup(form="f")
    assert tg.get_image() is None
    assert tg.get_b_box() is None
    assert tg.get_width() == 0
    assert tg.get_height() == 0
    assert tg.is_gray() is False
    assert tg.get_bounds() is None
    img = Image.new("LA", (16, 24))
    tg.set_image(img)
    assert tg.get_image() is img
    assert tg.get_width() == 16
    assert tg.get_height() == 24
    assert tg.is_gray() is True
    assert tg.get_bounds() == (0, 0, 16, 24)
    tg.set_b_box("bbox-val")
    assert tg.get_b_box() == "bbox-val"


def test_transparency_group_bounds_uses_bbox_when_no_image() -> None:
    tg = TransparencyGroup(form=None, ctm="ctm")
    tg.set_b_box("bbox")
    assert tg.get_bounds() == "bbox"


def test_transparency_group_create2_byte_gray_alpha_image() -> None:
    tg = TransparencyGroup(form=None)
    img = tg.create2_byte_gray_alpha_image(10, 20)
    assert img.mode == "LA"
    assert img.size == (10, 20)
    # Defends min size of 1.
    small = tg.create2_byte_gray_alpha_image(0, -3)
    assert small.size == (1, 1)


def test_transparency_group_is_gray_with_rgb_mode_is_false() -> None:
    tg = TransparencyGroup(form=None)
    tg.set_image(Image.new("RGB", (5, 5)))
    assert tg.is_gray() is False
