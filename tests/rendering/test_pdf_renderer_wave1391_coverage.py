"""Wave 1391 — close residual missing-line coverage in pdf_renderer."""

from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import (
    _coerce_color_components,
    _flatten_cubic_bezier,
    _GState,
)

from .test_pdf_renderer_extgstate_wave1385 import _attach_renderer


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _bare_renderer(gs: _GState | None = None) -> PDFRenderer:
    from pypdfbox.rendering.render_destination import RenderDestination

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [gs or _GState()]
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    r._resources = None
    r._default_destination = RenderDestination.VIEW
    return r


# ---------- _coerce_color_components ----------


def test_coerce_color_components_with_native_float_falls_through() -> None:
    class _PlainFloat:
        def __float__(self) -> float:
            return 0.25

    assert _coerce_color_components([_PlainFloat(), _PlainFloat()]) == (0.25, 0.25)  # type: ignore[list-item]


def test_coerce_color_components_with_int_value_path() -> None:
    assert _coerce_color_components([COSInteger(0), COSInteger(1)]) == (0.0, 1.0)


def test_coerce_color_components_unconvertible_returns_none() -> None:
    class _Unconvertible:
        pass

    assert _coerce_color_components([_Unconvertible()]) is None  # type: ignore[list-item]


def test_coerce_color_components_cosname_returns_none() -> None:
    assert _coerce_color_components([COSName.get_pdf_name("Pat0")]) is None


# ---------- _initial_color_rgb ----------


def test_initial_color_rgb_none_returns_none() -> None:
    r = _bare_renderer()
    assert r._initial_color_rgb(None) is None  # noqa: SLF001


def test_initial_color_rgb_no_method_returns_none() -> None:
    r = _bare_renderer()

    class _NoGetInitial:
        pass

    assert r._initial_color_rgb(_NoGetInitial()) is None  # noqa: SLF001


def test_initial_color_rgb_raising_get_initial_returns_none() -> None:
    r = _bare_renderer()

    class _Raising:
        def get_initial_color(self) -> Any:
            raise RuntimeError("boom")

    assert r._initial_color_rgb(_Raising()) is None  # noqa: SLF001


def test_initial_color_rgb_none_initial_returns_none() -> None:
    r = _bare_renderer()

    class _Owner:
        def get_initial_color(self) -> Any:
            return None

    assert r._initial_color_rgb(_Owner()) is None  # noqa: SLF001


def test_initial_color_rgb_no_components_returns_none() -> None:
    r = _bare_renderer()

    class _Empty:
        _components = ()

    class _Owner:
        def get_initial_color(self) -> Any:
            return _Empty()

    assert r._initial_color_rgb(_Owner()) is None  # noqa: SLF001


def test_initial_color_rgb_components_attribute_alternate() -> None:
    """When ``_components`` is missing but ``components`` is present, the
    fallback branch fires (line 1892). The colour space must also be
    able to convert via to_rgb — wrap a real DeviceGray-shaped CS."""
    r = _bare_renderer()

    class _AltInitial:
        components = (0.5,)

    class _Owner:
        def get_initial_color(self) -> Any:
            return _AltInitial()

        def to_rgb(self, comps: tuple[float, ...]) -> tuple[float, float, float]:
            v = comps[0]
            return (v, v, v)

    # The branch falls through to ``_color_components_to_rgb`` which
    # uses the colour space's to_rgb; we built one above.
    assert r._initial_color_rgb(_Owner()) == (128, 128, 128)  # noqa: SLF001


# ---------- _resolve_color_space ----------


def test_resolve_color_space_no_resources_returns_none() -> None:
    r = _bare_renderer()
    r._resources = None  # noqa: SLF001
    assert r._resolve_color_space(COSName.get_pdf_name("CSCustom")) is None  # noqa: SLF001


def test_resolve_color_space_raising_returns_none() -> None:
    r = _bare_renderer()

    class _RaisingRes:
        def get_color_space(self, name: COSName) -> Any:
            raise RuntimeError("bad cs")

    r._resources = _RaisingRes()  # noqa: SLF001
    assert r._resolve_color_space(COSName.get_pdf_name("CSCustom")) is None  # noqa: SLF001


# ---------- _op_set_stroke_color_n / _op_set_fill_color_n ----------


def test_scn_without_pattern_sets_fill_rgb() -> None:
    r = _bare_renderer()
    r._op_set_fill_color_n(  # noqa: SLF001
        None, [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0)]
    )
    assert r._gs.fill_rgb == (255, 0, 0)  # noqa: SLF001


def test_scn_clears_pattern_when_solid_colour() -> None:
    r = _bare_renderer()
    r._gs.fill_pattern = object()  # noqa: SLF001
    r._gs.fill_pattern_tint = (1, 2, 3)  # noqa: SLF001
    r._op_set_fill_color_n(  # noqa: SLF001
        None, [COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)]
    )
    assert r._gs.fill_pattern is None  # noqa: SLF001
    assert r._gs.fill_pattern_tint is None  # noqa: SLF001


def test_scn_uppercase_stroke_path() -> None:
    r = _bare_renderer()
    r._gs.stroke_pattern = object()  # noqa: SLF001
    r._op_set_stroke_color_n(  # noqa: SLF001
        None, [COSFloat(0.0), COSFloat(1.0), COSFloat(0.0)]
    )
    assert r._gs.stroke_rgb == (0, 255, 0)  # noqa: SLF001
    assert r._gs.stroke_pattern is None  # noqa: SLF001


# ---------- _extract_pattern_tint_rgb ----------


def test_extract_pattern_tint_rgb_empty_returns_none() -> None:
    r = _bare_renderer()
    assert r._extract_pattern_tint_rgb([], None) is None  # noqa: SLF001


def test_extract_pattern_tint_rgb_leading_cosname() -> None:
    r = _bare_renderer()
    assert r._extract_pattern_tint_rgb(  # noqa: SLF001
        [COSName.get_pdf_name("Foo"), COSName.get_pdf_name("Pat0")], None,
    ) is None


def test_extract_pattern_tint_rgb_with_int_components() -> None:
    r = _bare_renderer()
    out = r._extract_pattern_tint_rgb(  # noqa: SLF001
        [COSInteger(0), COSInteger(1), COSInteger(0), COSName.get_pdf_name("Pat0")],
        None,
    )
    assert out == (0, 255, 0)


def test_extract_pattern_tint_rgb_with_unconvertible_returns_none() -> None:
    r = _bare_renderer()

    class _Bad:
        pass

    assert r._extract_pattern_tint_rgb(  # noqa: SLF001
        [_Bad(), COSName.get_pdf_name("Pat0")], None,
    ) is None


# ---------- _color_components_to_rgb ----------


def test_color_components_to_rgb_raising_cs_returns_none() -> None:
    r = _bare_renderer()

    class _RaisingCS:
        def to_rgb(self, comps: tuple[float, ...]) -> Any:
            raise RuntimeError("conversion failed")

    assert r._color_components_to_rgb((0.5,), _RaisingCS()) is None  # noqa: SLF001


def test_color_components_to_rgb_short_result_returns_none() -> None:
    r = _bare_renderer()

    class _ShortCS:
        def to_rgb(self, comps: tuple[float, ...]) -> tuple[float, ...]:
            return (0.5,)

    assert r._color_components_to_rgb((0.5,), _ShortCS()) is None  # noqa: SLF001


def test_color_components_to_rgb_non_iterable_returns_none() -> None:
    r = _bare_renderer()

    class _NonIterableCS:
        def to_rgb(self, comps: tuple[float, ...]) -> Any:
            return None

    assert r._color_components_to_rgb((0.5,), _NonIterableCS()) is None  # noqa: SLF001


def test_color_components_to_rgb_unknown_length_returns_none() -> None:
    r = _bare_renderer()
    assert r._color_components_to_rgb((0.1, 0.2), None) is None  # noqa: SLF001


# ---------- transfer-function helpers ----------


def test_apply_transfer_to_rgb_bytes_no_gs_stack_returns_unchanged() -> None:
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = []  # noqa: SLF001
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    assert r._apply_transfer_to_rgb_bytes((100, 50, 0)) == (100, 50, 0)  # noqa: SLF001


def test_apply_transfer_to_rgb_bytes_no_transfer_returns_unchanged() -> None:
    r = _bare_renderer()
    assert r._apply_transfer_to_rgb_bytes((100, 50, 0)) == (100, 50, 0)  # noqa: SLF001


def test_apply_transfer_to_rgb_bytes_with_failing_transfer_returns_unchanged() -> None:
    class _BadTransfer:
        def eval(self, x: list[float]) -> Any:
            raise RuntimeError("broke")

    r = _bare_renderer()
    r._gs.transfer_function = _BadTransfer()  # noqa: SLF001
    assert r._apply_transfer_to_rgb_bytes((100, 50, 0)) == (100, 50, 0)  # noqa: SLF001


def test_apply_transfer_to_byte_empty_list_returns_value() -> None:
    assert PDFRenderer._apply_transfer_to_byte(128, [], 0) == 128


def test_apply_transfer_to_byte_none_function_returns_value() -> None:
    assert PDFRenderer._apply_transfer_to_byte(128, [None, None, None], 0) == 128  # type: ignore[list-item]


def test_apply_transfer_to_byte_raising_eval_returns_value() -> None:
    class _Raising:
        def eval(self, x: list[float]) -> Any:
            raise ValueError("err")

    assert PDFRenderer._apply_transfer_to_byte(128, _Raising(), 0) == 128


def test_apply_transfer_to_byte_empty_eval_returns_value() -> None:
    class _Empty:
        def eval(self, x: list[float]) -> list[float]:
            return []

    assert PDFRenderer._apply_transfer_to_byte(128, _Empty(), 0) == 128


def test_apply_transfer_to_byte_non_numeric_eval_returns_value() -> None:
    class _NonNumeric:
        def eval(self, x: list[float]) -> Any:
            return ["abc"]

    assert PDFRenderer._apply_transfer_to_byte(128, _NonNumeric(), 0) == 128


def test_apply_transfer_to_byte_clamps_below_zero() -> None:
    class _Negative:
        def eval(self, x: list[float]) -> list[float]:
            return [-0.5]

    assert PDFRenderer._apply_transfer_to_byte(128, _Negative(), 0) == 0


def test_apply_transfer_to_byte_clamps_above_one() -> None:
    class _Over:
        def eval(self, x: list[float]) -> list[float]:
            return [2.0]

    assert PDFRenderer._apply_transfer_to_byte(128, _Over(), 0) == 255


def test_apply_transfer_to_pil_image_no_transfer_returns_same() -> None:
    r = _bare_renderer()
    img = Image.new("RGB", (4, 4), (200, 100, 50))
    assert r._apply_transfer_to_pil_image(img) is img  # noqa: SLF001


def test_apply_transfer_to_pil_image_l_mode() -> None:
    class _Invert:
        def eval(self, x: list[float]) -> list[float]:
            return [1.0 - x[0]]

    r = _bare_renderer()
    r._gs.transfer_function = _Invert()  # noqa: SLF001
    img = Image.new("L", (2, 2), 200)
    out = r._apply_transfer_to_pil_image(img)  # noqa: SLF001
    assert abs(out.getpixel((0, 0)) - 55) <= 2


def test_apply_transfer_to_pil_image_1_bit_returns_same() -> None:
    class _Identity:
        def eval(self, x: list[float]) -> list[float]:
            return x

    r = _bare_renderer()
    r._gs.transfer_function = _Identity()  # noqa: SLF001
    img = Image.new("1", (2, 2), 1)
    assert r._apply_transfer_to_pil_image(img) is img  # noqa: SLF001


def test_apply_transfer_to_pil_image_rgba_preserves_alpha() -> None:
    class _Identity:
        def eval(self, x: list[float]) -> list[float]:
            return x

    r = _bare_renderer()
    r._gs.transfer_function = _Identity()  # noqa: SLF001
    img = Image.new("RGBA", (2, 2), (100, 150, 200, 64))
    out = r._apply_transfer_to_pil_image(img)  # noqa: SLF001
    assert out.getpixel((0, 0))[3] == 64


def test_apply_transfer_to_pil_image_unsupported_mode_returns_same() -> None:
    class _Identity:
        def eval(self, x: list[float]) -> list[float]:
            return x

    r = _bare_renderer()
    r._gs.transfer_function = _Identity()  # noqa: SLF001
    img = Image.new("CMYK", (2, 2), (50, 100, 150, 200))
    assert r._apply_transfer_to_pil_image(img) is img  # noqa: SLF001


# ---------- _overprint_suppresses_paint ----------


def test_overprint_suppresses_paint_stroke_non_black_returns_false() -> None:
    gs = _GState(
        overprint_non_stroking=True,
        overprint_stroking=True,
        overprint_mode=1,
        fill_rgb=(0, 0, 0),
        stroke_rgb=(255, 0, 0),
    )
    r = _bare_renderer(gs)
    assert r._overprint_suppresses_paint(stroke=True, fill=True) is False  # noqa: SLF001


# ---------- _apply_ext_gstate clamping ----------


def test_apply_ext_gstate_clamps_line_cap_below_zero() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_line_cap_style(-3)
    r = _attach_renderer(ext)
    assert r._gs.line_cap == 0


def test_apply_ext_gstate_clamps_line_cap_above_two() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_line_cap_style(99)
    r = _attach_renderer(ext)
    assert r._gs.line_cap == 2


def test_apply_ext_gstate_clamps_line_join_below_zero() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_line_join_style(-2)
    r = _attach_renderer(ext)
    assert r._gs.line_join == 0


def test_apply_ext_gstate_clamps_line_join_above_two() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_line_join_style(15)
    r = _attach_renderer(ext)
    assert r._gs.line_join == 2


def test_apply_ext_gstate_miter_limit_non_positive_is_ignored() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_miter_limit(0.0)
    r = _attach_renderer(ext)
    assert r._gs.miter_limit == 10.0


def test_apply_ext_gstate_dash_pattern_empty_means_solid() -> None:
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    ext = PDExtendedGraphicsState()
    ext.set_line_dash_pattern(PDLineDashPattern())
    r = _attach_renderer(ext)
    assert r._gs.dash_pattern is None


def test_apply_ext_gstate_font_setting_with_zero_size() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
    from pypdfbox.pdmodel.graphics.state.pd_font_setting import PDFontSetting

    ext = PDExtendedGraphicsState()
    font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
    setting = PDFontSetting()
    setting.set_font(font)
    setting.set_font_size(0.0)
    ext.set_font_setting(setting)
    r = _attach_renderer(ext)
    assert r._gs.text_font_size == 0.0


# ---------- _flatten_cubic_bezier ----------


def test_flatten_cubic_bezier_depth_cap_emits_chord() -> None:
    out = _flatten_cubic_bezier(
        0.0, 0.0, 1000.0, 1000.0, -1000.0, -1000.0, 5.0, 5.0,
        tolerance=0.0001, _depth=18,
    )
    assert out == [(5.0, 5.0)]


def test_flatten_cubic_bezier_degenerate_chord_with_small_controls() -> None:
    out = _flatten_cubic_bezier(
        0.0, 0.0, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0,
        tolerance=10.0, _depth=0,
    )
    assert out == [(0.0, 0.0)]


def test_flatten_cubic_bezier_normal_curve_produces_polyline() -> None:
    out = _flatten_cubic_bezier(
        0.0, 0.0, 50.0, 50.0, 50.0, -50.0, 100.0, 0.0,
        tolerance=1.0, _depth=0,
    )
    assert len(out) > 1


# ---------- type-3 glyph metrics ----------


def test_type3_d0_with_too_few_operands_is_noop() -> None:
    r = _bare_renderer()
    r._type3_d0_wx = None  # noqa: SLF001
    r._op_type3_d0(None, [COSFloat(100.0)])  # noqa: SLF001
    assert r._type3_d0_wx is None  # noqa: SLF001


def test_type3_d1_with_too_few_operands_is_noop() -> None:
    r = _bare_renderer()
    r._type3_d1_wx = None  # noqa: SLF001
    r._op_type3_d1(None, [COSFloat(100.0), COSFloat(0.0), COSFloat(0.0)])  # noqa: SLF001
    assert r._type3_d1_wx is None  # noqa: SLF001


def test_type3_d1_degenerate_bbox_does_not_set_clip() -> None:
    r = _bare_renderer()
    r._type3_d1_wx = None  # noqa: SLF001
    r._pending_clip = None  # noqa: SLF001
    r._subpaths = []  # noqa: SLF001
    r._current_subpath = None  # noqa: SLF001
    r._current_point = None  # noqa: SLF001
    r._op_type3_d1(  # noqa: SLF001
        None,
        [
            COSFloat(100.0),
            COSFloat(0.0),
            COSFloat(50.0),
            COSFloat(0.0),
            COSFloat(10.0),  # urx < llx — invalid
            COSFloat(50.0),
        ],
    )
    assert r._type3_d1_wx == 100.0  # noqa: SLF001
    assert r._pending_clip is None  # noqa: SLF001


# ---------- _op_set_text_rendering_mode ----------


def test_set_text_rendering_mode_no_operands_is_noop() -> None:
    r = _bare_renderer()
    r._gs.text_rendering_mode = 3  # noqa: SLF001
    r._op_set_text_rendering_mode(None, [])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 3  # noqa: SLF001


def test_set_text_rendering_mode_negative_leaves_previous_unchanged() -> None:
    # Wave 1589 fix: upstream SetTextRenderingMode returns (ignores) on
    # val < 0, leaving the previously-set mode in place rather than
    # clamping to 0.
    r = _bare_renderer()
    r._gs.text_rendering_mode = 2  # noqa: SLF001
    r._op_set_text_rendering_mode(None, [COSInteger(-5)])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 2  # noqa: SLF001


def test_set_text_rendering_mode_above_seven_leaves_previous_unchanged() -> None:
    # Wave 1589 fix: upstream returns (ignores) on val >= 8, leaving the
    # previously-set mode in place rather than clamping to 7.
    r = _bare_renderer()
    r._gs.text_rendering_mode = 1  # noqa: SLF001
    r._op_set_text_rendering_mode(None, [COSInteger(99)])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 1  # noqa: SLF001


# ---------- annotation skip + render ----------


class _AnnotationWithConstruct:
    def __init__(self) -> None:
        self.constructed_with_doc = False

    def get_subtype(self) -> str:
        return "Widget"

    def is_hidden(self) -> bool:
        return False

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return False

    def get_normal_appearance_stream(self) -> Any:
        return None

    def construct_appearances(self, doc: Any = None) -> None:
        self.constructed_with_doc = doc is not None


def test_render_annotation_invokes_construct_appearances_with_document() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._document = doc  # noqa: SLF001
    annot = _AnnotationWithConstruct()
    renderer._render_annotation(annot)  # type: ignore[arg-type]  # noqa: SLF001
    assert annot.constructed_with_doc is True


class _AnnotationConstructRaises:
    def get_subtype(self) -> str:
        return "Widget"

    def is_hidden(self) -> bool:
        return False

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return False

    def get_normal_appearance_stream(self) -> Any:
        return None

    def construct_appearances(self, doc: Any = None) -> None:
        raise RuntimeError("construct failed")


def test_render_annotation_swallows_construct_failure() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._document = doc  # noqa: SLF001
    annot = _AnnotationConstructRaises()
    renderer._render_annotation(annot)  # type: ignore[arg-type]  # noqa: SLF001


class _AnnotationNoRect:
    def get_subtype(self) -> str:
        return "Widget"

    def is_hidden(self) -> bool:
        return False

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return False

    def get_normal_appearance_stream(self) -> Any:
        class _Appearance:
            def get_bbox(self) -> Any:
                return PDRectangle(0, 0, 10, 10)

            def get_matrix(self) -> list[float]:
                return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

            def get_resources(self) -> Any:
                return None

            def get_cos_object(self) -> Any:
                return None

        return _Appearance()

    def get_rectangle(self) -> Any:
        return None


def test_render_annotation_skips_when_rectangle_none() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._document = doc  # noqa: SLF001
    renderer._render_annotation(_AnnotationNoRect())  # type: ignore[arg-type]  # noqa: SLF001


class _AnnotationZeroRect:
    def get_subtype(self) -> str:
        return "Widget"

    def is_hidden(self) -> bool:
        return False

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return False

    def get_normal_appearance_stream(self) -> Any:
        class _Appearance:
            def get_bbox(self) -> Any:
                return PDRectangle(0, 0, 10, 10)

            def get_matrix(self) -> list[float]:
                return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

            def get_resources(self) -> Any:
                return None

            def get_cos_object(self) -> Any:
                return None

        return _Appearance()

    def get_rectangle(self) -> Any:
        return PDRectangle(0, 0, 0, 0)


def test_render_annotation_skips_when_rect_zero_sized() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._document = doc  # noqa: SLF001
    renderer._render_annotation(_AnnotationZeroRect())  # type: ignore[arg-type]  # noqa: SLF001


class _AnnotationHidden:
    def get_subtype(self) -> str:
        return "Widget"

    def is_hidden(self) -> bool:
        return True

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return False


def test_annotation_should_skip_hidden_returns_true() -> None:
    r = _bare_renderer()
    assert r._annotation_should_skip(_AnnotationHidden()) is True  # noqa: SLF001


class _AnnotationFlagsRaise:
    def get_subtype(self) -> str:
        return "Widget"

    def is_hidden(self) -> bool:
        raise RuntimeError("malformed")

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return False


def test_annotation_should_skip_swallows_flag_error() -> None:
    r = _bare_renderer()
    assert r._annotation_should_skip(_AnnotationFlagsRaise()) is False  # noqa: SLF001


class _PDAnnotationUnknown:
    def get_subtype(self) -> str:
        return "Unknown"

    def is_hidden(self) -> bool:
        return False

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        return True


_PDAnnotationUnknown.__name__ = "PDAnnotationUnknown"


def test_annotation_should_skip_unknown_invisible() -> None:
    r = _bare_renderer()
    assert r._annotation_should_skip(_PDAnnotationUnknown()) is True  # noqa: SLF001


class _PDAnnotationUnknownInvisibleRaises:
    def get_subtype(self) -> str:
        return "Unknown"

    def is_hidden(self) -> bool:
        return False

    def is_printed(self) -> bool:
        return True

    def is_no_view(self) -> bool:
        return False

    def is_invisible(self) -> bool:
        raise RuntimeError("malformed")


_PDAnnotationUnknownInvisibleRaises.__name__ = "PDAnnotationUnknown"


def test_annotation_should_skip_unknown_invisible_raises_returns_false() -> None:
    r = _bare_renderer()
    assert r._annotation_should_skip(_PDAnnotationUnknownInvisibleRaises()) is False  # noqa: SLF001


# ---------- behavioural rendering ----------


def test_render_with_invisible_text_mode_3_leaves_canvas_white() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory

    doc, page = _make_doc(80.0, 30.0)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(PDFontFactory.create_default_font("Helvetica"), 12.0)
        cs.set_text_rendering_mode(3)
        cs.new_line_at_offset(10.0, 10.0)
        cs.show_text("X")
        cs.end_text()
    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)
    assert img.getpixel((20, 20)) == (255, 255, 255)


# ---------- _resolve_pattern_operand ----------


def test_resolve_pattern_operand_empty_returns_none() -> None:
    r = _bare_renderer()
    assert r._resolve_pattern_operand([]) is None  # noqa: SLF001


def test_resolve_pattern_operand_non_name_trailing_returns_none() -> None:
    r = _bare_renderer()
    assert r._resolve_pattern_operand([COSFloat(0.5)]) is None  # noqa: SLF001


def test_resolve_pattern_operand_no_resources_returns_none() -> None:
    r = _bare_renderer()
    r._resources = None  # noqa: SLF001
    assert r._resolve_pattern_operand([COSName.get_pdf_name("Pat0")]) is None  # noqa: SLF001


# ---------- _decode_inline_image ----------


def test_decode_inline_image_with_no_params_returns_none() -> None:
    r = _bare_renderer()
    assert r._decode_inline_image(None, b"") is None  # type: ignore[arg-type]  # noqa: SLF001


def test_decode_inline_image_zero_width_returns_none() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 0)
    params.set_int(COSName.get_pdf_name("Height"), 10)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    assert r._decode_inline_image(params, b"\x00" * 10) is None  # noqa: SLF001


def test_decode_inline_image_non_8_bpc_returns_none() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 2)
    params.set_int(COSName.get_pdf_name("Height"), 2)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 1)
    params.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    assert r._decode_inline_image(params, b"\x00" * 4) is None  # noqa: SLF001


def test_decode_inline_image_unknown_filter_returns_none() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 2)
    params.set_int(COSName.get_pdf_name("Height"), 2)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    params.set_item(
        COSName.get_pdf_name("Filter"), COSName.get_pdf_name("FlateDecode")
    )
    assert r._decode_inline_image(params, b"\x00" * 4) is None  # noqa: SLF001


def test_decode_inline_image_filter_array_form() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 2)
    params.set_int(COSName.get_pdf_name("Height"), 2)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    params.set_item(
        COSName.get_pdf_name("Filter"),
        COSArray([COSName.get_pdf_name("Fl")]),
    )
    assert r._decode_inline_image(params, b"\x00" * 4) is None  # noqa: SLF001


def test_decode_inline_image_devicegray_fast_path() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 2)
    params.set_int(COSName.get_pdf_name("Height"), 2)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    params.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("G")
    )
    out = r._decode_inline_image(params, b"\xff\x80\x40\x00")  # noqa: SLF001
    assert out is not None
    assert out.size == (2, 2)


def test_decode_inline_image_devicecmyk_fast_path() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 2)
    params.set_int(COSName.get_pdf_name("Height"), 2)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    params.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CMYK")
    )
    out = r._decode_inline_image(params, b"\x00" * (2 * 2 * 4))  # noqa: SLF001
    assert out is not None


def test_decode_inline_image_default_devicergb_when_cs_absent() -> None:
    r = _bare_renderer()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Width"), 2)
    params.set_int(COSName.get_pdf_name("Height"), 2)
    params.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    out = r._decode_inline_image(  # noqa: SLF001
        params,
        b"\xff\x00\x00\x00\xff\x00\x00\x00\xff\xff\xff\xff",
    )
    assert out is not None


# ---------- _maybe_*_text_knockout ----------


def test_maybe_begin_text_knockout_text_knockout_false_returns_early() -> None:
    r = _bare_renderer()
    r._gs.text_knockout = False  # noqa: SLF001
    r._maybe_begin_text_knockout()  # noqa: SLF001


def test_maybe_end_text_knockout_no_layer_returns_early() -> None:
    r = _bare_renderer()
    r._text_knockout_layer = None  # noqa: SLF001
    r._maybe_end_text_knockout()  # noqa: SLF001


def test_maybe_begin_text_knockout_no_visible_effect_returns_early() -> None:
    r = _bare_renderer()
    r._gs.text_knockout = True  # noqa: SLF001
    r._gs.fill_alpha = 1.0  # noqa: SLF001
    r._gs.blend_mode = None  # noqa: SLF001
    r._image = Image.new("RGB", (10, 10), (255, 255, 255))  # noqa: SLF001
    r._maybe_begin_text_knockout()  # noqa: SLF001
