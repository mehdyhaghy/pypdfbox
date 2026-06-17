"""Fuzz / parity tests for transparency-group + soft-mask *rendering*.

Wave 1588 (Agent D). Targets the rendering-side application of:

- :class:`pypdfbox.rendering.soft_mask.SoftMask` / ``SoftPaintContext`` —
  the AWT-paint port that multiplies an inner paint's alpha by a soft
  mask's luminance, with the optional ``/TR`` transfer function and the
  out-of-bounds backdrop ``bc`` value.
- :meth:`PDFRenderer._render_soft_mask_alpha` — builds the ``"L"`` alpha
  plane from a soft-mask ``/G`` group (``/Alpha`` vs ``/Luminosity``,
  ``/BC`` backdrop, ``/TR`` transfer function).
- :meth:`PDFRenderer._soft_mask_backdrop_rgb` — resolves ``/BC`` for the
  three colour-space arities (gray / RGB / CMYK).
- :meth:`PDFRenderer._render_transparency_group` — isolated vs
  non-isolated backdrop, knockout, ``/SMask`` application, group alpha.
- :class:`GroupGraphics` compositing helpers used at end-of-group.

These compare to the upstream PDFBox ``PageDrawer`` / ``SoftMask``
behaviour at the structural / value level (not byte-identical pixels).
"""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.group_graphics import GroupGraphics
from pypdfbox.rendering.soft_mask import SoftMask, SoftPaintContext

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class _SolidContext:
    """A minimal inner paint-context returning a solid RGBA raster."""

    def __init__(self, rgba: tuple[int, int, int, int]) -> None:
        self._rgba = rgba
        self.disposed = False

    def get_raster(self, x1: int, y1: int, w: int, h: int) -> Image.Image:
        return Image.new("RGBA", (w, h), self._rgba)

    def dispose(self) -> None:
        self.disposed = True


class _IdentityFn:
    """Transfer function that maps v -> v (identity)."""

    def is_identity(self) -> bool:
        return True

    def eval(self, inp: list[float]) -> list[float]:
        return [inp[0]]


class _InvertFn:
    """Transfer function that maps v -> 1 - v (non-identity)."""

    def is_identity(self) -> bool:
        return False

    def eval(self, inp: list[float]) -> list[float]:
        return [1.0 - inp[0]]


class _ConstFn:
    """Transfer function that maps every input to a constant."""

    def __init__(self, c: float) -> None:
        self._c = c

    def is_identity(self) -> bool:
        return False

    def eval(self, inp: list[float]) -> list[float]:  # noqa: ARG002
        return [self._c]


def _make_mask(size: tuple[int, int], gray: int) -> Image.Image:
    return Image.new("L", size, gray)


def _make_doc(w: float = 60.0, h: float = 60.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, w, h))
    doc.add_page(page)
    return doc, page


def _group_form(content: bytes, size: float = 60.0) -> PDFormXObject:
    stream = COSStream()
    stream.set_raw_data(content)
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(0.0, 0.0, size, size))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    form.set_group(group)
    return form


def _smask(
    subtype: str,
    group: PDFormXObject,
    *,
    bc: list[float] | None = None,
    tr: Any | None = None,
) -> PDSoftMask:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Mask"))
    d.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name(subtype))
    d.set_item(COSName.get_pdf_name("G"), group.get_cos_object())
    if bc is not None:
        arr = COSArray()
        for v in bc:
            arr.add(COSFloat(v))
        d.set_item(COSName.get_pdf_name("BC"), arr)
    if tr is not None:
        d.set_item(COSName.get_pdf_name("TR"), tr)
    sm = PDSoftMask.create(d)
    assert sm is not None
    return sm


# ===========================================================================
# SoftMask / SoftPaintContext — direct paint-helper fuzz
# ===========================================================================


def test_softmask_full_white_mask_keeps_alpha() -> None:
    """A fully-white (255) mask leaves the inner alpha unchanged."""
    mask = _make_mask((8, 8), 255)
    sm = SoftMask(paint=None, mask=mask, bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((10, 20, 30, 200)))
    out = ctx.get_raster(0, 0, 8, 8)
    assert out.getpixel((4, 4))[3] == 200


def test_softmask_black_mask_zeroes_alpha() -> None:
    """A fully-black (0) mask zeroes the inner alpha (luminosity sense:
    black = transparent, NOT inverted)."""
    mask = _make_mask((8, 8), 0)
    sm = SoftMask(paint=None, mask=mask, bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((10, 20, 30, 200)))
    out = ctx.get_raster(0, 0, 8, 8)
    assert out.getpixel((4, 4))[3] == 0


@pytest.mark.parametrize("gray", [0, 32, 64, 128, 192, 255])
def test_softmask_gray_scales_alpha_linearly(gray: int) -> None:
    """Mask gray g multiplies inner alpha by g/255 (alpha sense is NOT
    inverted — higher luminance => higher alpha)."""
    mask = _make_mask((4, 4), gray)
    sm = SoftMask(paint=None, mask=mask, bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 4, 4)
    assert out.getpixel((0, 0))[3] == round(255 * (gray / 255.0))


def test_softmask_preserves_rgb_channels() -> None:
    """Only the alpha channel is modulated; RGB is passed through."""
    mask = _make_mask((4, 4), 128)
    sm = SoftMask(paint=None, mask=mask, bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((11, 22, 33, 255)))
    out = ctx.get_raster(0, 0, 4, 4)
    r, g, b, _ = out.getpixel((1, 1))
    assert (r, g, b) == (11, 22, 33)


def test_softmask_outside_bounds_uses_bc_default_black() -> None:
    """Pixels outside the mask bbox use the backdrop luminance ``bc``
    (default 0 => transparent) when no /BC is given."""
    # Mask is 2x2 but we request a 6x6 raster — the right/bottom region
    # falls outside the mask and must use bc (= 0).
    mask = _make_mask((2, 2), 255)
    sm = SoftMask(paint=None, mask=mask, bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 6, 6)
    # inside mask
    assert out.getpixel((0, 0))[3] == 255
    # outside mask -> bc default 0 -> transparent
    assert out.getpixel((5, 5))[3] == 0


def test_softmask_backdrop_color_luminance_outside() -> None:
    """A white /BC backdrop yields full alpha outside the mask bounds."""
    white_bc = PDColor([1.0, 1.0, 1.0], PDDeviceRGB.INSTANCE)
    mask = _make_mask((2, 2), 0)
    sm = SoftMask(
        paint=None, mask=mask, bbox_device=(0, 0), backdrop_color=white_bc
    )
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 6, 6)
    # outside the 2x2 mask -> bc = white luminance (255) -> full alpha
    assert out.getpixel((5, 5))[3] == 255


def test_softmask_bbox_device_offset_translates_mask() -> None:
    """The bbox_device origin translates the mask sampling coordinates."""
    # Mask: left column white (255), right column black (0).
    mask = Image.new("L", (2, 4), 0)
    for y in range(4):
        mask.putpixel((0, y), 255)
    # bbox at (0,0): request at x1=0 -> mask col 0 = white.
    sm0 = SoftMask(paint=None, mask=mask, bbox_device=(0, 0))
    ctx0 = SoftPaintContext(sm0, _SolidContext((0, 0, 0, 255)))
    out0 = ctx0.get_raster(0, 0, 1, 1)
    assert out0.getpixel((0, 0))[3] == 255
    # bbox at (-1,0): mask coord = x1 - (-1) = 1 -> black col.
    sm1 = SoftMask(paint=None, mask=mask, bbox_device=(-1, 0))
    ctx1 = SoftPaintContext(sm1, _SolidContext((0, 0, 0, 255)))
    out1 = ctx1.get_raster(0, 0, 1, 1)
    assert out1.getpixel((0, 0))[3] == 0


def test_softmask_transfer_function_inverts_inside() -> None:
    """A /TR inversion transfer maps mask gray g -> (1-g) inside bounds."""
    mask = _make_mask((4, 4), 255)  # white
    sm = SoftMask(
        paint=None,
        mask=mask,
        bbox_device=(0, 0),
        transfer_function=_InvertFn(),
    )
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 4, 4)
    # white (255) inverted -> 0 -> transparent.
    assert out.getpixel((0, 0))[3] == 0


def test_softmask_transfer_function_applied_outside_bounds() -> None:
    """REGRESSION (wave 1588): the out-of-bounds region samples the
    backdrop ``bc`` and must ALSO pass through the /TR transfer function,
    matching upstream's single 256-entry ``map`` table indexed by ``bc``.

    Setup: default bc = 0 (black). With an inversion transfer, the
    outside region should become 1-0 = full alpha, NOT raw bc/255 = 0.
    """
    mask = _make_mask((2, 2), 255)
    sm = SoftMask(
        paint=None,
        mask=mask,
        bbox_device=(0, 0),
        transfer_function=_InvertFn(),
    )
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 6, 6)
    # outside the 2x2 mask: bc=0, inverted -> 255 (full alpha).
    assert out.getpixel((5, 5))[3] == 255, out.getpixel((5, 5))


def test_softmask_const_transfer_outside_matches_inside() -> None:
    """With a constant transfer function the outside-bounds and
    inside-bounds alpha agree (the bug would leave outside at raw bc)."""
    mask = _make_mask((2, 2), 200)
    sm = SoftMask(
        paint=None,
        mask=mask,
        bbox_device=(0, 0),
        transfer_function=_ConstFn(0.5),
    )
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 6, 6)
    inside = out.getpixel((0, 0))[3]
    outside = out.getpixel((5, 5))[3]
    assert inside == outside == round(255 * 0.5)


def test_softmask_identity_transfer_treated_as_none() -> None:
    """An identity transfer function is short-circuited to None (parity
    with upstream where Identity functions skip the per-pixel map)."""
    sm = SoftMask(
        paint=None,
        mask=_make_mask((2, 2), 100),
        bbox_device=(0, 0),
        transfer_function=_IdentityFn(),
    )
    assert sm._transfer_function is None  # noqa: SLF001


def test_softmask_zero_size_raster_returns_min_image() -> None:
    """A degenerate (w<=0 or h<=0) raster returns a 1x1 transparent
    image rather than crashing."""
    sm = SoftMask(paint=None, mask=_make_mask((2, 2), 255), bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 0, 5)
    assert out.size == (1, 5)


def test_softmask_none_mask_uses_bc_everywhere() -> None:
    """When mask is None every pixel falls to the bc branch."""
    sm = SoftMask(paint=None, mask=None, bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, _SolidContext((0, 0, 0, 255)))
    out = ctx.get_raster(0, 0, 4, 4)
    # bc default 0 -> all transparent.
    assert out.getpixel((2, 2))[3] == 0


def test_softmask_no_inner_context_yields_transparent() -> None:
    """A null inner paint context yields an all-transparent raster
    (matches AWT's behaviour when ``paint`` is null)."""
    sm = SoftMask(paint=None, mask=_make_mask((4, 4), 255), bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, None)
    out = ctx.get_raster(0, 0, 4, 4)
    assert out.getpixel((0, 0))[3] == 0


def test_softmask_dispose_forwards_to_inner() -> None:
    inner = _SolidContext((0, 0, 0, 255))
    sm = SoftMask(paint=None, mask=_make_mask((2, 2), 255), bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, inner)
    ctx.dispose()
    assert inner.disposed is True


def test_softmask_get_transparency_translucent() -> None:
    sm = SoftMask(paint=None, mask=_make_mask((2, 2), 255), bbox_device=(0, 0))
    assert sm.get_transparency() == 3  # TRANSLUCENT


def test_softmask_color_model_is_argb() -> None:
    sm = SoftMask(paint=None, mask=_make_mask((2, 2), 255), bbox_device=(0, 0))
    ctx = SoftPaintContext(sm, None)
    assert ctx.get_color_model() == "ARGB"


# ===========================================================================
# _soft_mask_backdrop_rgb — /BC colour-space arity dispatch
# ===========================================================================


def _renderer() -> PDFRenderer:
    doc, _ = _make_doc()
    return PDFRenderer(doc)


def _ready_renderer(size: tuple[int, int] = (60, 60)) -> PDFRenderer:
    """A renderer with the minimal in-render state that
    :meth:`_render_soft_mask_alpha` requires (an active canvas, a draw
    handle, a one-entry GS stack and resources). Mirrors the state the
    page-render loop establishes before any soft-mask is rasterised."""
    from pypdfbox.rendering import _aggdraw_compat as aggdraw  # noqa: PLC0415
    from pypdfbox.rendering.pdf_renderer import _GState  # noqa: PLC0415

    rdr = _renderer()
    img = Image.new("RGB", size, (255, 255, 255))
    rdr._image = img  # noqa: SLF001
    rdr._draw = aggdraw.Draw(img)  # noqa: SLF001
    rdr._gs_stack = [_GState()]  # noqa: SLF001
    rdr._resources = PDResources()  # noqa: SLF001
    return rdr


def test_backdrop_rgb_default_black_when_absent() -> None:
    rdr = _renderer()
    sm = _smask("Luminosity", _group_form(b""))
    assert rdr._soft_mask_backdrop_rgb(sm) == (0, 0, 0)  # noqa: SLF001


def test_backdrop_rgb_gray_single_component() -> None:
    rdr = _renderer()
    sm = _smask("Luminosity", _group_form(b""), bc=[1.0])
    r, g, b = rdr._soft_mask_backdrop_rgb(sm)  # noqa: SLF001
    assert r == g == b == 255


def test_backdrop_rgb_three_component_white() -> None:
    rdr = _renderer()
    sm = _smask("Luminosity", _group_form(b""), bc=[1.0, 1.0, 1.0])
    assert rdr._soft_mask_backdrop_rgb(sm) == (255, 255, 255)  # noqa: SLF001


def test_backdrop_rgb_cmyk_four_component() -> None:
    rdr = _renderer()
    # CMYK (0,0,0,0) -> white-ish.
    sm = _smask("Luminosity", _group_form(b""), bc=[0.0, 0.0, 0.0, 0.0])
    r, g, b = rdr._soft_mask_backdrop_rgb(sm)  # noqa: SLF001
    assert r > 200 and g > 200 and b > 200


def test_backdrop_rgb_cmyk_full_black() -> None:
    rdr = _renderer()
    sm = _smask("Luminosity", _group_form(b""), bc=[0.0, 0.0, 0.0, 1.0])
    r, g, b = rdr._soft_mask_backdrop_rgb(sm)  # noqa: SLF001
    assert r < 40 and g < 40 and b < 40


# ===========================================================================
# _render_soft_mask_alpha — group-built mask planes
# ===========================================================================


def test_render_soft_mask_alpha_none_for_non_softmask() -> None:
    rdr = _ready_renderer((60, 60))
    assert rdr._render_soft_mask_alpha(object(), (10, 10)) is None  # noqa: SLF001


def test_render_soft_mask_alpha_none_for_missing_group() -> None:
    rdr = _ready_renderer((60, 60))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha"))
    sm = PDSoftMask.create(d)
    assert sm is not None
    assert rdr._render_soft_mask_alpha(sm, (10, 10)) is None  # noqa: SLF001


def test_render_soft_mask_alpha_alpha_subtype_returns_plane() -> None:
    """An /Alpha soft mask whose group paints a filled rect yields a
    non-trivial alpha plane (covered region opaque, rest zero)."""
    rdr = _ready_renderer((60, 60))
    group = _group_form(
        b"1 1 1 rg\n10 10 20 20 re\nf\n", size=60.0
    )
    sm = _smask("Alpha", group)
    plane = rdr._render_soft_mask_alpha(sm, (60, 60))  # noqa: SLF001
    assert plane is not None
    assert plane.mode == "L"
    assert plane.size == (60, 60)
    # Covered area should be opaque; a far corner should be zero.
    extrema = plane.getextrema()
    assert extrema[1] > 200  # some fully-opaque pixels
    assert extrema[0] == 0  # untouched region zero


def test_render_soft_mask_alpha_luminosity_white_fill_opaque() -> None:
    """A /Luminosity mask whose group paints white => opaque mask in the
    covered region (luminance high * coverage high)."""
    rdr = _ready_renderer((60, 60))
    group = _group_form(b"1 1 1 rg\n0 0 60 60 re\nf\n", size=60.0)
    sm = _smask("Luminosity", group)
    plane = rdr._render_soft_mask_alpha(sm, (60, 60))  # noqa: SLF001
    assert plane is not None
    assert plane.getextrema()[1] > 200


def test_render_soft_mask_alpha_luminosity_black_fill_transparent() -> None:
    """A /Luminosity mask whose group paints black => mask ~0 (black
    luminance) even though coverage is full."""
    rdr = _ready_renderer((60, 60))
    group = _group_form(b"0 0 0 rg\n0 0 60 60 re\nf\n", size=60.0)
    sm = _smask("Luminosity", group)
    plane = rdr._render_soft_mask_alpha(sm, (60, 60))  # noqa: SLF001
    assert plane is not None
    assert plane.getextrema()[1] < 40


def test_render_soft_mask_alpha_empty_group_luminosity_zero() -> None:
    """An empty /Luminosity group masks to ~0 everywhere (oracle-verified
    wave 1434: uncovered region contributes mask alpha 0 regardless of
    /BC luminance)."""
    rdr = _ready_renderer((40, 40))
    group = _group_form(b"", size=40.0)
    sm = _smask("Luminosity", group, bc=[1.0, 1.0, 1.0])
    plane = rdr._render_soft_mask_alpha(sm, (40, 40))  # noqa: SLF001
    assert plane is not None
    assert plane.getextrema()[1] == 0


def test_render_soft_mask_alpha_tr_inversion_remaps() -> None:
    """A /TR inversion transfer remaps the mask plane (white group fill
    -> inverted -> ~0)."""
    rdr = _ready_renderer((40, 40))
    group = _group_form(b"1 1 1 rg\n0 0 40 40 re\nf\n", size=40.0)
    # Type-2 exponential function acting as inversion: C0=[1], C1=[0], N=1.
    from pypdfbox.cos import COSInteger  # noqa: PLC0415

    tr = COSDictionary()
    tr.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(2))
    dom = COSArray()
    dom.add(COSFloat(0.0))
    dom.add(COSFloat(1.0))
    tr.set_item(COSName.get_pdf_name("Domain"), dom)
    c0 = COSArray()
    c0.add(COSFloat(1.0))
    tr.set_item(COSName.get_pdf_name("C0"), c0)
    c1 = COSArray()
    c1.add(COSFloat(0.0))
    tr.set_item(COSName.get_pdf_name("C1"), c1)
    tr.set_item(COSName.get_pdf_name("N"), COSFloat(1.0))
    sm = _smask("Luminosity", group, tr=tr)
    plane = rdr._render_soft_mask_alpha(sm, (40, 40))  # noqa: SLF001
    assert plane is not None
    # white-fill luminance ~255 inverted -> ~0.
    assert plane.getextrema()[1] < 40


def test_render_soft_mask_alpha_identity_tr_no_remap() -> None:
    """An /Identity /TR is a no-op (white fill stays opaque)."""
    rdr = _ready_renderer((40, 40))
    group = _group_form(b"1 1 1 rg\n0 0 40 40 re\nf\n", size=40.0)
    sm = _smask("Luminosity", group, tr=COSName.get_pdf_name("Identity"))
    plane = rdr._render_soft_mask_alpha(sm, (40, 40))  # noqa: SLF001
    assert plane is not None
    assert plane.getextrema()[1] > 200


# ===========================================================================
# _render_transparency_group — isolated / non-isolated / knockout
# ===========================================================================


def _render_group_page(
    content: bytes,
    *,
    isolated: bool,
    knockout: bool = False,
    size: float = 60.0,
) -> Image.Image:
    doc, page = _make_doc(size, size)
    form = _group_form(content, size=size)
    grp = form.get_group()
    if isolated:
        grp.set_item(COSName.get_pdf_name("I"), COSName.get_pdf_name("true"))
        from pypdfbox.cos import COSBoolean  # noqa: PLC0415

        grp.set_item(COSName.get_pdf_name("I"), COSBoolean.TRUE)
    if knockout:
        from pypdfbox.cos import COSBoolean  # noqa: PLC0415

        grp.set_item(COSName.get_pdf_name("K"), COSBoolean.TRUE)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(b"q\n/F0 Do\nQ\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    return PDFRenderer(doc).render_image(0)


def test_transparency_group_isolated_paints_content() -> None:
    img = _render_group_page(
        b"1 0 0 rg\n10 10 30 30 re\nf\n", isolated=True
    )
    # PIL y flipped: PDF (20,20) -> PIL (20,39).
    px = img.getpixel((20, 39))
    assert abs(px[0] - 255) < 40 and px[1] < 60 and px[2] < 60, px


def test_transparency_group_non_isolated_paints_content() -> None:
    img = _render_group_page(
        b"0 0 1 rg\n10 10 30 30 re\nf\n", isolated=False
    )
    px = img.getpixel((20, 39))
    assert px[2] > 200 and px[0] < 60, px


def test_transparency_group_empty_isolated_keeps_background() -> None:
    """An empty isolated group leaves the page background untouched."""
    img = _render_group_page(b"", isolated=True)
    px = img.getpixel((30, 30))
    assert px[0] > 240 and px[1] > 240 and px[2] > 240, px


def test_transparency_group_knockout_renders() -> None:
    """A knockout group still composites its final content (last child
    replaces prior at group level)."""
    img = _render_group_page(
        b"0 1 0 rg\n10 10 30 30 re\nf\n", isolated=True, knockout=True
    )
    px = img.getpixel((20, 39))
    assert px[1] > 180, px


# ===========================================================================
# GroupGraphics — end-of-group compositing helpers
# ===========================================================================


def test_group_graphics_composite_onto_rgb_target() -> None:
    target = Image.new("RGB", (10, 10), (0, 0, 0))
    group = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
    gg = GroupGraphics(image=group)
    gg.composite_onto(target)
    px = target.getpixel((5, 5))
    # half-alpha red over black -> ~ (128, 0, 0).
    assert 100 < px[0] < 160 and px[1] < 20 and px[2] < 20, px


def test_group_graphics_composite_onto_rgba_target() -> None:
    target = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    group = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
    gg = GroupGraphics(image=group)
    gg.composite_onto(target)
    assert target.getpixel((5, 5)) == (0, 255, 0, 255)


def test_group_graphics_composite_onto_none_target_noop() -> None:
    gg = GroupGraphics(image=Image.new("RGBA", (4, 4), (255, 0, 0, 255)))
    # Should not raise.
    gg.composite_onto(None)  # type: ignore[arg-type]


def test_group_graphics_backdrop_removal_subtracts() -> None:
    """backdrop_removal subtracts the stored backdrop RGB from the buffer."""
    img = Image.new("RGB", (4, 4), (200, 100, 50))
    gg = GroupGraphics(image=img)
    gg.set_background((50, 30, 10))
    gg.backdrop_removal()
    px = gg._image.getpixel((0, 0))  # noqa: SLF001
    assert px == (150, 70, 40)


def test_group_graphics_backdrop_removal_no_background_noop() -> None:
    img = Image.new("RGB", (4, 4), (200, 100, 50))
    gg = GroupGraphics(image=img)
    gg.backdrop_removal()  # no background set -> no-op
    assert gg._image.getpixel((0, 0)) == (200, 100, 50)  # noqa: SLF001


def test_group_graphics_clip_rect_intersection() -> None:
    gg = GroupGraphics()
    gg.clip_rect(0, 0, 10, 10)
    gg.clip_rect(5, 5, 10, 10)
    assert gg.get_clip() == (5, 5, 10, 10)


# ===========================================================================
# End-to-end: SMask /None clears the mask
# ===========================================================================


def test_extgstate_smask_none_clears_active_mask() -> None:
    """A /SMask /None ExtGState clears a previously-active soft mask so a
    subsequent fill paints unmodulated."""
    doc, page = _make_doc(50.0, 50.0)
    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState"))
    egs.set_item(COSName.get_pdf_name("SMask"), COSName.get_pdf_name("None"))
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), egs
    )
    contents = COSStream()
    contents.set_raw_data(b"/GS0 gs\n1 0 0 rg\n10 10 30 30 re\nf\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((20, 30))
    assert abs(px[0] - 255) < 30 and px[1] < 60 and px[2] < 60, px
