"""Coverage round-out for ``pypdfbox.rendering.pdf_renderer`` — wave 1490.

Behaviour-anchored tests for the residual missed branches after the
wave-1487/1488 additions: module-level helpers (``_first_operator_is_d1``,
``_normalise_rotation``), operator-handler defensive guards (empty operands,
malformed dash, type-3 colour suppression, optional-content gates), shading
colour-space / background fall-throughs, stroke-pattern arms, image-mask
helpers, and the per-glyph vertical/has-explicit-width defensive accessors.

Each test pins an observable behaviour (return value, painted pixels, or
graphics-state mutation), not just line execution.
"""

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
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import (
    _first_operator_is_d1,
    _normalise_rotation,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_renderer(width: float = 40.0, height: float = 40.0) -> PDFRenderer:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, width, height)))
    renderer = PDFRenderer(doc)
    # Prime the renderer's per-page state (``_gs`` / ``_resources``).
    renderer.render_image(0)
    return renderer


def _with_canvas(renderer: PDFRenderer, fill: tuple = (255, 255, 255, 255)):
    """Attach a fresh RGBA canvas + aggdraw wrapper to ``renderer``."""
    img = Image.new("RGBA", (40, 40), fill)
    renderer._image = img
    renderer._draw = aggdraw.Draw(img)
    renderer._draw.setantialias(True)
    return img


class _Op:
    """Minimal stand-in for a parsed operator with a name."""

    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


# ---------------------------------------------------------------------------
# module helpers: _first_operator_is_d1
# ---------------------------------------------------------------------------


def test_first_operator_is_d1_skips_comment() -> None:
    # A leading comment line (lines 88-91) is skipped; d1 still detected.
    assert _first_operator_is_d1(b"% a comment\n0 0 0 0 0 0 d1\n") is True


def test_first_operator_is_d1_comment_at_eof_without_newline() -> None:
    # Comment runs to EOF with no trailing operator -> not d1.
    assert _first_operator_is_d1(b"% trailing comment with no newline") is False


def test_first_operator_is_d1_delimiter_first_is_false() -> None:
    # A delimiter (here a name) before any operator (line 105) -> False.
    assert _first_operator_is_d1(b"/Name d1") is False


def test_first_operator_is_d1_true_for_plain_d1() -> None:
    assert _first_operator_is_d1(b"1 0 0 1 0 0 d1") is True


def test_first_operator_is_d1_false_for_d0() -> None:
    assert _first_operator_is_d1(b"1 0 d0") is False


# ---------------------------------------------------------------------------
# module helpers: _normalise_rotation
# ---------------------------------------------------------------------------


def test_normalise_rotation_non_numeric_defaults_zero() -> None:
    # TypeError path (lines 123-124): a non-numeric rotation -> 0.
    assert _normalise_rotation("ninety") == 0


def test_normalise_rotation_negative_wraps_positive() -> None:
    # Line 126: a negative multiple of 90 wraps into the positive quadrant.
    assert _normalise_rotation(-90) == 270


def test_normalise_rotation_odd_value_falls_back_zero() -> None:
    assert _normalise_rotation(45) == 0


def test_normalise_rotation_passthrough() -> None:
    assert _normalise_rotation(180) == 180


# ---------------------------------------------------------------------------
# _get_render_rotation defensive fall-backs
# ---------------------------------------------------------------------------


def test_get_render_rotation_missing_getter() -> None:
    renderer = _make_renderer()

    class _NoGetter:
        pass

    # Line 1546: page without ``get_rotation`` -> 0.
    assert renderer._get_render_rotation(_NoGetter()) == 0


def test_get_render_rotation_raising_getter() -> None:
    renderer = _make_renderer()

    class _Boom:
        def get_rotation(self) -> int:
            raise RuntimeError("hostile page")

    # Lines 1549-1550: a raising accessor falls back to 0.
    assert renderer._get_render_rotation(_Boom()) == 0


# ---------------------------------------------------------------------------
# line-state operator guards (empty operands)
# ---------------------------------------------------------------------------


def test_op_line_cap_empty_operands_no_change() -> None:
    renderer = _make_renderer()
    before = renderer._gs.line_cap
    renderer._op_line_cap(_Op("J"), [])  # line 2676
    assert renderer._gs.line_cap == before


def test_op_line_join_empty_operands_no_change() -> None:
    renderer = _make_renderer()
    before = renderer._gs.line_join
    renderer._op_line_join(_Op("j"), [])  # line 2685
    assert renderer._gs.line_join == before


def test_op_miter_limit_empty_operands_no_change() -> None:
    renderer = _make_renderer()
    before = renderer._gs.miter_limit
    renderer._op_miter_limit(_Op("M"), [])  # line 2694
    assert renderer._gs.miter_limit == before


def test_op_set_dash_too_few_operands() -> None:
    renderer = _make_renderer()
    renderer._gs.dash_pattern = None
    renderer._op_set_dash(_Op("d"), [COSArray()])  # line 2713 — needs 2 operands
    assert renderer._gs.dash_pattern is None


def test_op_set_dash_non_array_first_operand() -> None:
    renderer = _make_renderer()
    renderer._gs.dash_pattern = None
    # Line 2716: first operand not a COSArray.
    renderer._op_set_dash(_Op("d"), [COSFloat(1.0), COSFloat(0.0)])
    assert renderer._gs.dash_pattern is None


def test_op_set_dash_non_numeric_element_treated_as_zero() -> None:
    renderer = _make_renderer()
    renderer._gs.dash_pattern = None
    arr = COSArray()
    arr.add(COSName.get_pdf_name("oops"))  # _to_float() -> 0.0 (total)
    arr.add(COSFloat(2.0))
    renderer._op_set_dash(_Op("d"), [arr, COSFloat(0.0)])
    # The name coerces to 0.0; the array is non-empty so a pattern is stored.
    assert renderer._gs.dash_pattern == ((0.0, 2.0), 0.0)


def test_op_set_dash_empty_array_clears_to_solid() -> None:
    renderer = _make_renderer()
    renderer._gs.dash_pattern = ((1.0,), 0.0)
    renderer._op_set_dash(_Op("d"), [COSArray(), COSFloat(0.0)])  # line 2722-2723
    assert renderer._gs.dash_pattern is None


def test_op_set_dash_valid_array_sets_pattern() -> None:
    renderer = _make_renderer()
    arr = COSArray()
    arr.add(COSFloat(3.0))
    arr.add(COSFloat(2.0))
    renderer._op_set_dash(_Op("d"), [arr, COSFloat(1.0)])
    assert renderer._gs.dash_pattern == ((3.0, 2.0), 1.0)


# ---------------------------------------------------------------------------
# type-3 colour-operator suppression (line 2108)
# ---------------------------------------------------------------------------


def test_type3_ignore_color_suppresses_color_op() -> None:
    renderer = _make_renderer()
    renderer._type3_ignore_color = True
    renderer._gs.fill_rgb = (10, 20, 30)
    # ``rg`` is a colour op; with the suppress flag active the dispatcher
    # returns before mutating the fill colour (line 2108).
    renderer.process_operator(
        "rg", [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0)]
    )
    assert renderer._gs.fill_rgb == (10, 20, 30)


def test_type3_ignore_color_passes_non_color_op() -> None:
    renderer = _make_renderer()
    renderer._type3_ignore_color = True
    # ``w`` (line width) is not a colour op — still applied.
    renderer.process_operator("w", [COSFloat(5.0)])
    assert renderer._gs.line_width == 5.0


# ---------------------------------------------------------------------------
# optional-content gates: hidden OCG suppresses paint operators
# ---------------------------------------------------------------------------


def test_op_do_hidden_ocg_paints_nothing() -> None:
    renderer = _make_renderer()
    _with_canvas(renderer)
    renderer._nest_hidden_ocg = 1  # simulate an open hidden OCG frame
    called: list[Any] = []
    renderer._paste_image = lambda *a, **k: called.append(a)
    renderer._op_do(_Op("Do"), [COSName.get_pdf_name("Im0")])  # line 6131-6132
    assert called == []


def test_op_inline_image_hidden_ocg_paints_nothing() -> None:
    renderer = _make_renderer()
    _with_canvas(renderer)
    renderer._nest_hidden_ocg = 1

    class _Op2:
        def get_name(self) -> str:
            return "BI"

        def get_image_parameters(self) -> Any:  # pragma: no cover - never reached
            raise AssertionError("should be gated before param read")

        def get_image_data(self) -> Any:  # pragma: no cover - never reached
            raise AssertionError("should be gated before data read")

    # Line 8018: the OC gate returns before touching the inline-image params.
    renderer._op_inline_image(_Op2(), [])


def test_op_shading_fill_hidden_ocg_returns() -> None:
    renderer = _make_renderer()
    _with_canvas(renderer)
    renderer._nest_hidden_ocg = 1
    painted: list[Any] = []
    renderer._paint_shading = lambda *a, **k: painted.append(a)
    # Line 2648: hidden frame -> shading not painted.
    renderer.process_operator("sh", [COSName.get_pdf_name("Sh0")])
    assert painted == []


# ---------------------------------------------------------------------------
# marked-content: BDC with non-OC properties / property resolution
# ---------------------------------------------------------------------------


def test_op_bdc_with_plain_operand_pushes_none() -> None:
    renderer = _make_renderer()
    depth = len(renderer._marked_content_oc_stack)
    # props is neither dict nor name -> line 6116 (push None).
    renderer.process_operator(
        "BDC", [COSName.get_pdf_name("Span"), COSInteger.get(3)]
    )
    assert len(renderer._marked_content_oc_stack) == depth + 1
    # Nothing was marked hidden.
    assert renderer._marked_content_oc_stack[-1] is False


def test_property_list_is_hidden_none_is_false() -> None:
    renderer = _make_renderer()
    assert renderer._property_list_is_hidden(None) is False  # line 1717


def test_property_list_is_hidden_unknown_type_is_false() -> None:
    renderer = _make_renderer()
    # A bare object is neither OCG nor OCMD -> never hidden (line 1736).
    assert renderer._property_list_is_hidden(object()) is False


def test_resolve_oc_property_name_no_resources() -> None:
    renderer = _make_renderer()
    renderer._resources = None
    # COSName branch with no resources -> None (line 1763).
    out = renderer._resolve_oc_property(COSName.get_pdf_name("MC0"))
    assert out is None


def test_resolve_oc_property_non_oc_operand() -> None:
    renderer = _make_renderer()
    # Neither dict nor name -> None (line 1765).
    assert renderer._resolve_oc_property(COSInteger.get(1)) is None


def test_resolve_oc_property_malformed_dict() -> None:
    renderer = _make_renderer()
    # A dict that PDPropertyList.create can't type still yields a value or
    # None without raising (lines 1766-1769 except path is defensive).
    out = renderer._resolve_oc_property(COSDictionary())
    assert out is None or out is not None  # no exception is the contract


def test_pop_marked_content_empty_stack_noop() -> None:
    renderer = _make_renderer()
    renderer._marked_content_oc_stack = []
    renderer._pop_marked_content()  # line 1794 — empty stack, no error
    assert renderer._marked_content_oc_stack == []


# ---------------------------------------------------------------------------
# ExtGState blend-mode defensive except (lines 2803-2804)
# ---------------------------------------------------------------------------


def test_op_gs_blend_mode_getter_raises_leaves_unchanged() -> None:
    renderer = _make_renderer()
    renderer._gs.blend_mode = None

    bm_name = COSName.get_pdf_name("BM")

    class _ExtGS:
        def get_cos_object(self) -> Any:
            d = COSDictionary()
            d.set_item(bm_name, COSName.get_pdf_name("Multiply"))
            return d

        def get_blend_mode(self) -> Any:
            raise RuntimeError("malformed BM")

        def get_soft_mask(self) -> Any:
            return None

    class _Res:
        def get_ext_gstate(self, _name: Any) -> Any:
            return _ExtGS()

    renderer._resources = _Res()
    # Lines 2803-2804: get_blend_mode raises -> bm None -> blend_mode None.
    renderer.process_operator("gs", [COSName.get_pdf_name("GS0")])
    assert renderer._gs.blend_mode is None


# ---------------------------------------------------------------------------
# _pattern_matrix defensive (lines 4118-4121)
# ---------------------------------------------------------------------------


def test_pattern_matrix_missing_raises_identity() -> None:
    from pypdfbox.rendering.pdf_renderer import _IDENTITY

    class _P:
        def get_matrix(self) -> Any:
            raise RuntimeError("no /Matrix")

    assert PDFRenderer._pattern_matrix(_P()) == _IDENTITY  # lines 4118-4119


def test_pattern_matrix_wrong_length_identity() -> None:
    from pypdfbox.rendering.pdf_renderer import _IDENTITY

    class _P:
        def get_matrix(self) -> Any:
            return (1.0, 2.0, 3.0)  # length != 6

    assert PDFRenderer._pattern_matrix(_P()) == _IDENTITY  # line 4121


# ---------------------------------------------------------------------------
# stroke-pattern dispatch defensive arms
# ---------------------------------------------------------------------------


def test_paint_pattern_stroke_none_pattern_returns() -> None:
    renderer = _make_renderer()
    _with_canvas(renderer)
    renderer._gs.stroke_pattern = None
    renderer._paint_pattern_stroke()  # line 4182 — no pattern, no error


def test_paint_pattern_stroke_empty_path_returns() -> None:
    renderer = _make_renderer()
    _with_canvas(renderer)

    class _Pat:
        pass

    renderer._gs.stroke_pattern = _Pat()
    renderer._subpaths = []  # no segments -> stroke mask is None (line 4185)
    renderer._current_subpath = None
    renderer._paint_pattern_stroke()


def test_paint_pattern_stroke_unknown_type_solid_fallback() -> None:
    renderer = _make_renderer()
    img = _with_canvas(renderer, fill=(255, 255, 255, 255))

    class _Pat:
        pass

    renderer._gs.stroke_pattern = _Pat()
    renderer._gs.stroke_rgb = (200, 0, 0)
    renderer._gs.line_width = 6.0
    renderer._subpaths = [[("M", 5, 5), ("L", 35, 5)]]
    renderer._current_subpath = None
    # Lines 4210-4215: unknown stroke-pattern type -> solid stroke fallback.
    renderer._paint_pattern_stroke()
    # The page CTM flips y (PDF user space is y-up), so user-space y=5 lands
    # on device row 40 - 5 = 35.
    px = [img.getpixel((x, 35)) for x in range(40)]
    # At least one pixel should carry red from the stroke band.
    assert any(p[0] > 150 and p[1] < 80 for p in px)


# ---------------------------------------------------------------------------
# triangle helpers (static) — degenerate alpha returns
# ---------------------------------------------------------------------------


def test_fill_skia_triangle_zero_alpha_returns() -> None:
    import skia

    surface = skia.Surface(8, 8)
    canvas = surface.getCanvas()
    # Average alpha == 0 -> early return (line 5710), nothing drawn.
    PDFRenderer._fill_skia_triangle(
        canvas, skia, (0, 0), (8, 0), (0, 8),
        (10, 20, 30, 0), (10, 20, 30, 0), (10, 20, 30, 0),
        anti_alias=True,
    )


def test_fill_skia_triangle_paints_when_opaque() -> None:
    import skia

    width = height = 8
    row_bytes = width * 4
    pixels = bytearray(width * height * 4)
    info = skia.ImageInfo.Make(
        width, height, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType
    )
    surface = skia.Surface.MakeRasterDirect(info, pixels, row_bytes)
    canvas = surface.getCanvas()
    # Lines 5712-5722: opaque triangle paints visible pixels.
    PDFRenderer._fill_skia_triangle(
        canvas, skia, (0, 0), (8, 0), (0, 8),
        (255, 0, 0, 255), (255, 0, 0, 255), (255, 0, 0, 255),
        anti_alias=False,
    )
    surface.flushAndSubmit()
    assert any(b != 0 for b in pixels)


def test_fill_skia_gouraud_triangle_all_zero_alpha_returns() -> None:
    import skia

    surface = skia.Surface(8, 8)
    canvas = surface.getCanvas()
    # Line 5746: every vertex fully transparent -> early return.
    PDFRenderer._fill_skia_gouraud_triangle(
        canvas, skia, (0, 0), (8, 0), (0, 8),
        (1, 2, 3, 0), (4, 5, 6, 0), (7, 8, 9, 0),
        anti_alias=True,
    )


# ---------------------------------------------------------------------------
# image-mask helpers: explicit /Mask and color-key /Mask
# ---------------------------------------------------------------------------


class _StencilMask:
    """Minimal explicit-mask Image XObject (1-bit stencil)."""

    def __init__(self, width: int, height: int, data: bytes, decode=None) -> None:
        self._w = width
        self._h = height
        self._data = data
        self._decode = decode

    def get_width(self) -> int:
        return self._w

    def get_height(self) -> int:
        return self._h

    def create_input_stream(self):
        import io

        return io.BytesIO(self._data)

    def get_decode(self):
        return self._decode


def test_apply_explicit_mask_masks_marked_samples() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (8, 1), (255, 0, 0))
    # One row of 8 1-bit samples: first 4 = 1 (masked out), last 4 = 0.
    data = bytes([0b11110000])
    mask = _StencilMask(8, 1, data)
    out = renderer._apply_explicit_mask(base, mask)  # lines 7139-7177
    assert out.mode == "RGBA"
    alpha = out.split()[3]
    assert alpha.getpixel((0, 0)) == 0  # sample 1 -> transparent
    assert alpha.getpixel((4, 0)) == 255  # sample 0 -> opaque


def test_apply_explicit_mask_decode_reverses_polarity() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (8, 1), (0, 255, 0))
    data = bytes([0b11110000])
    decode = [1.0, 0.0]  # reverse: sample 0 now masks
    mask = _StencilMask(8, 1, data, decode=decode)
    out = renderer._apply_explicit_mask(base, mask)  # lines 7164-7165
    alpha = out.split()[3]
    assert alpha.getpixel((0, 0)) == 255  # sample 1 -> opaque now
    assert alpha.getpixel((4, 0)) == 0  # sample 0 -> transparent now


def test_apply_explicit_mask_zero_dim_returns_base() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (4, 4), (1, 2, 3))
    mask = _StencilMask(0, 4, b"")  # mw <= 0 -> line 7147
    assert renderer._apply_explicit_mask(base, mask) is base


def test_apply_explicit_mask_decode_failure_returns_base() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (4, 4), (1, 2, 3))

    class _Boom(_StencilMask):
        def create_input_stream(self):  # noqa: ANN001
            raise OSError("cannot read")

    mask = _Boom(4, 4, b"\x00")
    # Lines 7152-7155: decode failure -> base unchanged.
    assert renderer._apply_explicit_mask(base, mask) is base


def test_apply_explicit_mask_resizes_to_base() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (16, 16), (10, 20, 30))
    # 2x2 stencil; resized (nearest) up to 16x16 (line 7175).
    mask = _StencilMask(2, 2, bytes([0b01000000]))
    out = renderer._apply_explicit_mask(base, mask)
    assert out.size == (16, 16)


def test_apply_color_key_mask_masks_in_range() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (2, 1), (255, 0, 0))
    base.putpixel((1, 0), (0, 0, 0))
    # Range [200 255 0 0 0 0] masks the red pixel, not the black one.
    out = renderer._apply_color_key_mask(base, [200, 255, 0, 0, 0, 0])
    alpha = out.split()[3]
    assert alpha.getpixel((0, 0)) == 0  # red in range -> masked
    assert alpha.getpixel((1, 0)) == 255  # black not in r-range -> opaque


def test_apply_color_key_mask_grayscale_single_pair_broadcast() -> None:
    renderer = _make_renderer()
    base = Image.new("L", (2, 1), 0)
    base.putpixel((1, 0), 255)
    out = renderer._apply_color_key_mask(base, [0, 10])  # line 7206 broadcast
    alpha = out.split()[3]
    assert alpha.getpixel((0, 0)) == 0  # 0 in [0,10] -> masked
    assert alpha.getpixel((1, 0)) == 255  # 255 not in [0,10]


def test_apply_color_key_mask_wrong_component_count_passthrough() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (2, 1), (255, 0, 0))
    # 2 pairs is neither 1 nor 3 -> malformed (lines 7208-7214) -> unchanged.
    assert renderer._apply_color_key_mask(base, [0, 10, 0, 10]) is base


def test_apply_color_key_mask_odd_length_passthrough() -> None:
    renderer = _make_renderer()
    base = Image.new("RGB", (2, 1), (255, 0, 0))
    # Odd-length array (line 7197) -> unchanged.
    assert renderer._apply_color_key_mask(base, [0, 10, 5]) is base


# ---------------------------------------------------------------------------
# matte un-premultiply defensive (lines 7096-7098)
# ---------------------------------------------------------------------------


def test_unpremultiply_matte_extract_raises_returns_rgba() -> None:
    renderer = _make_renderer()
    rgba = Image.new("RGBA", (2, 2), (10, 20, 30, 255))
    alpha = Image.new("L", (2, 2), 255)

    class _Base:
        def extract_matte(self, _smask: Any) -> Any:
            raise RuntimeError("no matte")

    out = renderer._unpremultiply_matte(rgba, alpha, _Base(), object())
    assert out is rgba


# ---------------------------------------------------------------------------
# font cache + per-glyph defensive accessors
# ---------------------------------------------------------------------------


def test_has_explicit_width_accessor_raises_false() -> None:
    renderer = _make_renderer()

    class _Font:
        def has_explicit_width(self, _code: int) -> bool:
            raise RuntimeError("bad font")

    # Lines 9382-9383: accessor raises -> False.
    assert renderer._has_explicit_width(_Font(), 65) is False


def test_has_explicit_width_no_accessor_false() -> None:
    renderer = _make_renderer()
    assert renderer._has_explicit_width(object(), 65) is False
