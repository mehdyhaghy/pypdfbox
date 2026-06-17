"""Fuzz / parity tests for the transparency-group composite-back step.

After a Form XObject with a ``/Group`` is rendered into its own RGBA
buffer, the result is composited back onto the parent canvas through:

* the group's overall constant alpha ``ca`` (non-stroking ``/ca`` from
  the ExtGState in force at the ``Do`` operator — §11.6.4.3),
* the active blend mode (§11.3.5 / §11.4.7.4),
* the active soft mask (§11.6.5.2),

with the group buffer as the source and the parent as the backdrop.

These tests hammer :meth:`GroupGraphics.composite_onto` and its
``_scale_alpha`` / ``_blend_or_over`` helpers directly, then exercise
the ``PageDrawer.show_transparency_group`` wiring that reads the
group's overall alpha / blend / soft mask out of the graphics state.

Mirrors upstream ``org.apache.pdfbox.rendering.PageDrawer``'s
``showTransparencyGroup`` composite-back (the group bitmap is treated as
a single object at the group's overall opacity + blend + soft mask).
"""

from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering.group_graphics import GroupGraphics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _solid(size, rgba):
    return Image.new("RGBA", size, rgba)


def _group_with(image):
    g = GroupGraphics(image=image)
    return g


# ---------------------------------------------------------------------------
# constant-alpha scaling (_scale_alpha)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ca",
    [0.0, 0.1, 0.25, 0.5, 0.55, 0.75, 0.9, 1.0],
)
def test_scale_alpha_multiplies_alpha_channel(ca):
    """``_scale_alpha`` scales every pixel's alpha by ``ca`` and leaves
    RGB untouched (straight, not premultiplied)."""
    src = _solid((8, 8), (10, 200, 30, 200))
    scaled = GroupGraphics._scale_alpha(src, ca)
    r, g, b, a = scaled.split()
    # RGB is untouched.
    assert r.getpixel((0, 0)) == 10
    assert g.getpixel((0, 0)) == 200
    assert b.getpixel((0, 0)) == 30
    # Alpha scaled by ca (round).
    assert a.getpixel((0, 0)) == round(200 * ca)


def test_scale_alpha_zero_clears_all_alpha():
    src = _solid((4, 4), (255, 0, 0, 255))
    scaled = GroupGraphics._scale_alpha(src, 0.0)
    assert scaled.split()[3].getpixel((0, 0)) == 0


def test_scale_alpha_one_is_identity_on_alpha():
    src = _solid((4, 4), (255, 0, 0, 137))
    scaled = GroupGraphics._scale_alpha(src, 1.0)
    assert scaled.split()[3].getpixel((0, 0)) == 137


# ---------------------------------------------------------------------------
# composite_onto — constant alpha applied
# ---------------------------------------------------------------------------


def test_full_opacity_paints_group_over_backdrop():
    """ca=1.0, opaque group fully covers the backdrop."""
    target = Image.new("RGB", (4, 4), (255, 128, 0))
    g = _group_with(_solid((4, 4), (0, 200, 255, 255)))
    g.composite_onto(target, constant_alpha=1.0)
    assert target.getpixel((0, 0)) == (0, 200, 255)


def test_alpha_zero_shows_nothing():
    """ca=0.0 → group contributes nothing; backdrop unchanged."""
    target = Image.new("RGB", (4, 4), (255, 128, 0))
    g = _group_with(_solid((4, 4), (0, 200, 255, 255)))
    g.composite_onto(target, constant_alpha=0.0)
    assert target.getpixel((0, 0)) == (255, 128, 0)


@pytest.mark.parametrize("ca", [0.25, 0.5, 0.75])
def test_partial_alpha_blends_toward_group(ca):
    """A partial ca blends the opaque group color toward the backdrop:
    out = ca*group + (1-ca)*backdrop (source-over with scaled alpha)."""
    backdrop = (200, 0, 0)
    group_rgb = (0, 0, 200)
    target = Image.new("RGB", (4, 4), backdrop)
    g = _group_with(_solid((4, 4), (*group_rgb, 255)))
    g.composite_onto(target, constant_alpha=ca)
    out = target.getpixel((0, 0))
    for i in range(3):
        expected = round(group_rgb[i] * ca + backdrop[i] * (1 - ca))
        assert abs(out[i] - expected) <= 1, (out, ca)


def test_constant_alpha_clamped_above_one():
    """A ca > 1 is clamped (defensive) and behaves like full opacity."""
    target = Image.new("RGB", (4, 4), (255, 255, 255))
    g = _group_with(_solid((4, 4), (10, 20, 30, 255)))
    g.composite_onto(target, constant_alpha=2.5)
    assert target.getpixel((0, 0)) == (10, 20, 30)


def test_constant_alpha_clamped_below_zero():
    target = Image.new("RGB", (4, 4), (255, 255, 255))
    g = _group_with(_solid((4, 4), (10, 20, 30, 255)))
    g.composite_onto(target, constant_alpha=-3.0)
    assert target.getpixel((0, 0)) == (255, 255, 255)


def test_default_constant_alpha_is_full_opacity():
    target = Image.new("RGB", (4, 4), (255, 255, 255))
    g = _group_with(_solid((4, 4), (5, 6, 7, 255)))
    g.composite_onto(target)
    assert target.getpixel((0, 0)) == (5, 6, 7)


# ---------------------------------------------------------------------------
# composite_onto — group alpha channel respected (transparent group pixels)
# ---------------------------------------------------------------------------


def test_transparent_group_pixel_leaves_backdrop():
    """A clear group pixel (alpha 0) must not overwrite the backdrop even
    at ca=1.0 (the group's own alpha bounds the composite)."""
    target = Image.new("RGB", (4, 4), (40, 50, 60))
    buf = _solid((4, 4), (255, 255, 255, 0))
    g = _group_with(buf)
    g.composite_onto(target, constant_alpha=1.0)
    assert target.getpixel((0, 0)) == (40, 50, 60)


def test_group_own_alpha_and_constant_alpha_multiply():
    """Group pixel alpha 128 + ca 0.5 → effective ~0.25 coverage."""
    backdrop = (0, 0, 0)
    target = Image.new("RGB", (4, 4), backdrop)
    g = _group_with(_solid((4, 4), (255, 255, 255, 128)))
    g.composite_onto(target, constant_alpha=0.5)
    out = target.getpixel((0, 0))
    eff = (128 / 255.0) * 0.5
    expected = round(255 * eff)
    for c in out:
        assert abs(c - expected) <= 3, out


# ---------------------------------------------------------------------------
# composite_onto — isolated group from a clear backdrop
# ---------------------------------------------------------------------------


def test_isolated_group_onto_clear_rgba_backdrop():
    """An isolated group composites onto a fully-transparent RGBA backdrop
    and records straight (un-premultiplied) color + correct alpha."""
    target = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    g = _group_with(_solid((4, 4), (100, 150, 200, 128)))
    g.composite_onto(target, constant_alpha=1.0)
    r, gg, b, a = target.split()
    assert a.getpixel((0, 0)) == 128
    assert (r.getpixel((0, 0)), gg.getpixel((0, 0)), b.getpixel((0, 0))) == (
        100,
        150,
        200,
    )


def test_isolated_group_constant_alpha_scales_clear_backdrop_alpha():
    target = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    g = _group_with(_solid((4, 4), (10, 20, 30, 200)))
    g.composite_onto(target, constant_alpha=0.5)
    assert target.split()[3].getpixel((0, 0)) == round(200 * 0.5)


# ---------------------------------------------------------------------------
# composite_onto — blend mode applied at composite
# ---------------------------------------------------------------------------


def test_normal_blend_is_plain_over():
    target = Image.new("RGB", (4, 4), (200, 200, 200))
    g = _group_with(_solid((4, 4), (50, 50, 50, 255)))
    g.composite_onto(target, blend_mode=BlendMode.NORMAL)
    assert target.getpixel((0, 0)) == (50, 50, 50)


def test_none_blend_is_plain_over():
    target = Image.new("RGB", (4, 4), (200, 200, 200))
    g = _group_with(_solid((4, 4), (50, 50, 50, 255)))
    g.composite_onto(target, blend_mode=None)
    assert target.getpixel((0, 0)) == (50, 50, 50)


def test_multiply_blend_darkens():
    """Multiply: out = backdrop*source/255. Opaque mid-gray group over
    mid-gray backdrop → darker than either."""
    target = Image.new("RGB", (4, 4), (200, 200, 200))
    g = _group_with(_solid((4, 4), (100, 100, 100, 255)))
    g.composite_onto(target, blend_mode=BlendMode.MULTIPLY)
    out = target.getpixel((0, 0))
    expected = round(200 * 100 / 255)
    for c in out:
        assert abs(c - expected) <= 2, out


def test_screen_blend_lightens():
    """Screen: out = 255 - (255-b)(255-s)/255 → lighter than either."""
    target = Image.new("RGB", (4, 4), (100, 100, 100))
    g = _group_with(_solid((4, 4), (100, 100, 100, 255)))
    g.composite_onto(target, blend_mode=BlendMode.SCREEN)
    out = target.getpixel((0, 0))
    expected = 255 - round((155 * 155) / 255)
    for c in out:
        assert abs(c - expected) <= 2, out


def test_multiply_differs_from_normal():
    """The blend mode must actually be applied at composite, not ignored."""
    g_rgb = (120, 60, 30)
    bd = (90, 180, 240)
    t_norm = Image.new("RGB", (4, 4), bd)
    t_mul = Image.new("RGB", (4, 4), bd)
    GroupGraphics(image=_solid((4, 4), (*g_rgb, 255))).composite_onto(
        t_norm, blend_mode=BlendMode.NORMAL
    )
    GroupGraphics(image=_solid((4, 4), (*g_rgb, 255))).composite_onto(
        t_mul, blend_mode=BlendMode.MULTIPLY
    )
    assert t_norm.getpixel((0, 0)) != t_mul.getpixel((0, 0))


def test_transparent_group_with_blend_leaves_backdrop():
    """Even under a blend mode, a fully transparent group pixel must not
    change the backdrop (alpha bounds the blend)."""
    target = Image.new("RGB", (4, 4), (70, 80, 90))
    g = _group_with(_solid((4, 4), (255, 255, 255, 0)))
    g.composite_onto(target, blend_mode=BlendMode.MULTIPLY)
    assert target.getpixel((0, 0)) == (70, 80, 90)


def test_blend_or_over_normal_returns_alpha_composite():
    src = _solid((4, 4), (10, 20, 30, 255))
    target = Image.new("RGBA", (4, 4), (200, 200, 200, 255))
    out = GroupGraphics._blend_or_over(src, target, None)
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[:3] == (10, 20, 30)


def test_blend_or_over_multiply_uses_blend():
    src = _solid((4, 4), (100, 100, 100, 255))
    target = Image.new("RGBA", (4, 4), (200, 200, 200, 255))
    out = GroupGraphics._blend_or_over(src, target, BlendMode.MULTIPLY)
    expected = round(200 * 100 / 255)
    px = out.getpixel((0, 0))
    for c in px[:3]:
        assert abs(c - expected) <= 2, px


# ---------------------------------------------------------------------------
# composite_onto — soft mask applied at composite
# ---------------------------------------------------------------------------


def test_soft_mask_zero_hides_group():
    """A soft mask of all-zero alpha hides the group entirely."""
    target = Image.new("RGB", (4, 4), (10, 20, 30))
    g = _group_with(_solid((4, 4), (255, 0, 0, 255)))
    mask = Image.new("L", (4, 4), 0)
    g.composite_onto(target, soft_mask_alpha=mask)
    assert target.getpixel((0, 0)) == (10, 20, 30)


def test_soft_mask_full_shows_group():
    target = Image.new("RGB", (4, 4), (10, 20, 30))
    g = _group_with(_solid((4, 4), (255, 0, 0, 255)))
    mask = Image.new("L", (4, 4), 255)
    g.composite_onto(target, soft_mask_alpha=mask)
    assert target.getpixel((0, 0)) == (255, 0, 0)


def test_soft_mask_half_blends_group():
    target = Image.new("RGB", (4, 4), (0, 0, 0))
    g = _group_with(_solid((4, 4), (255, 255, 255, 255)))
    mask = Image.new("L", (4, 4), 128)
    g.composite_onto(target, soft_mask_alpha=mask)
    out = target.getpixel((0, 0))
    expected = round(255 * 128 / 255)
    for c in out:
        assert abs(c - expected) <= 2, out


def test_soft_mask_combines_with_constant_alpha():
    """Soft mask alpha and constant alpha both modulate the group alpha."""
    target = Image.new("RGB", (4, 4), (0, 0, 0))
    g = _group_with(_solid((4, 4), (255, 255, 255, 255)))
    mask = Image.new("L", (4, 4), 128)  # ~0.5
    g.composite_onto(target, constant_alpha=0.5, soft_mask_alpha=mask)
    out = target.getpixel((0, 0))
    eff = 0.5 * (128 / 255.0)
    expected = round(255 * eff)
    for c in out:
        assert abs(c - expected) <= 3, out


def test_soft_mask_resized_to_group():
    """A mask of a different size is resized to the group buffer."""
    target = Image.new("RGB", (8, 8), (0, 0, 0))
    g = _group_with(_solid((8, 8), (255, 255, 255, 255)))
    mask = Image.new("L", (2, 2), 255)
    g.composite_onto(target, soft_mask_alpha=mask)
    assert target.getpixel((4, 4)) == (255, 255, 255)


# ---------------------------------------------------------------------------
# composite_onto — guards / edge cases
# ---------------------------------------------------------------------------


def test_composite_onto_no_image_is_noop():
    target = Image.new("RGB", (4, 4), (1, 2, 3))
    GroupGraphics(image=None).composite_onto(target)
    assert target.getpixel((0, 0)) == (1, 2, 3)


def test_composite_onto_no_target_is_noop():
    g = _group_with(_solid((4, 4), (1, 2, 3, 255)))
    g.composite_onto(None)  # type: ignore[arg-type]


def test_composite_onto_rgb_group_buffer_converted():
    """A non-RGBA group buffer is promoted to RGBA before compositing."""
    target = Image.new("RGB", (4, 4), (0, 0, 0))
    g = GroupGraphics(image=Image.new("RGB", (4, 4), (40, 80, 120)))
    g.composite_onto(target, constant_alpha=1.0)
    assert target.getpixel((0, 0)) == (40, 80, 120)


# ---------------------------------------------------------------------------
# PageDrawer.show_transparency_group wiring — reads alpha/blend/smask
# from the graphics state and applies them at composite-back.
# ---------------------------------------------------------------------------


def _make_drawer():
    from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
    from pypdfbox.rendering import _aggdraw_compat as aggdraw
    from pypdfbox.rendering.page_drawer import PageDrawer
    from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
    from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState
    from pypdfbox.rendering.render_destination import RenderDestination

    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (16, 16), (255, 128, 0))
    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._scale = 1.0
    renderer._gs_stack = [_GState()]
    renderer._subpaths = []
    renderer._current_subpath = None
    renderer._current_point = (0.0, 0.0)
    renderer._pending_clip = None
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints={"AA": True},
        image_downscaling_optimization_threshold=0.5,
    )
    return doc, renderer, PageDrawer(params)


def test_show_group_applies_constant_alpha_from_state():
    """``show_transparency_group`` must read ``/ca`` off the graphics
    state and apply it at composite-back. We stub ``_render_form_xobject``
    to paint the group buffer a solid color, then assert the backdrop is
    blended by ca (not fully overwritten)."""
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.fill_alpha = 0.0  # group fully transparent

        def _paint(_form):
            # Fill the active (group) canvas opaque blue.
            img = renderer._image
            img.paste((0, 0, 255, 255), (0, 0, img.size[0], img.size[1]))

        renderer._render_form_xobject = _paint  # type: ignore[assignment]
        drawer.show_transparency_group(form="grp")
        # ca=0 → group contributes nothing → backdrop orange survives.
        assert renderer._image.getpixel((1, 1)) == (255, 128, 0)
        assert drawer._transparency_group_stack == []
        # interior alpha was reset to 1.0 then restored.
        assert renderer._gs.fill_alpha == 0.0
    finally:
        doc.close()


def test_show_group_resets_interior_alpha_then_restores():
    """The group's interior paints render at alpha 1.0; the saved alpha is
    restored for the caller after composite-back."""
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.fill_alpha = 0.4
        renderer._gs.stroke_alpha = 0.3
        seen = {}

        def _paint(_form):
            seen["fill"] = renderer._gs.fill_alpha
            seen["stroke"] = renderer._gs.stroke_alpha

        renderer._render_form_xobject = _paint  # type: ignore[assignment]
        drawer.show_transparency_group(form="grp")
        assert seen["fill"] == 1.0
        assert seen["stroke"] == 1.0
        # Restored for the caller.
        assert renderer._gs.fill_alpha == 0.4
        assert renderer._gs.stroke_alpha == 0.3
    finally:
        doc.close()


def test_show_group_full_opacity_paints_group():
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.fill_alpha = 1.0

        def _paint(_form):
            img = renderer._image
            img.paste((0, 200, 0, 255), (0, 0, img.size[0], img.size[1]))

        renderer._render_form_xobject = _paint  # type: ignore[assignment]
        drawer.show_transparency_group(form="grp")
        assert renderer._image.getpixel((1, 1)) == (0, 200, 0)
    finally:
        doc.close()


def test_show_group_restores_alpha_even_on_paint_error():
    doc, renderer, drawer = _make_drawer()
    try:
        renderer._gs.fill_alpha = 0.6

        def _paint(_form):
            raise RuntimeError("boom")

        renderer._render_form_xobject = _paint  # type: ignore[assignment]
        with pytest.raises(RuntimeError):
            drawer.show_transparency_group(form="grp")
        # finally-block restored the inherited alpha and popped the stack.
        assert renderer._gs.fill_alpha == 0.6
        assert drawer._transparency_group_stack == []
    finally:
        doc.close()
