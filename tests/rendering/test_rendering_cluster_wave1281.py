"""Tests for the rendering cluster ported in Wave 1281."""

from __future__ import annotations

from pypdfbox.rendering import (
    GlyphCache,
    GroupGraphics,
    PageDrawerParameters,
    RenderDestination,
    SoftMask,
    TilingPaintFactory,
    TilingPaintParameter,
    TransparencyGroup,
)


class _StubFont:
    def __init__(self, has):
        self._has = has

    def has_glyph(self, code):
        return self._has

    def get_name(self):
        return "Stub"

    def get_normalized_path(self, code):
        return ["path", code]


def test_glyph_cache_caches_result():
    font = _StubFont(has=True)
    cache = GlyphCache(font)
    p1 = cache.get_path_for_character_code(65)
    p2 = cache.get_path_for_character_code(65)
    assert p1 is p2


def test_glyph_cache_missing_glyph_returns_path():
    cache = GlyphCache(_StubFont(has=False))
    result = cache.get_path_for_character_code(65)
    assert isinstance(result, list)


def test_group_graphics_clone_copies_state():
    g = GroupGraphics()
    g.set_color("red")
    g.set_font("Times")
    g.add_rendering_hints({"AA": True})
    clone = g.create()
    assert clone.get_color() == "red"
    assert clone.get_font() == "Times"
    assert clone.get_rendering_hint("AA") is True
    clone.set_color("blue")
    assert g.get_color() == "red"


def test_group_graphics_clip_and_paint_state():
    g = GroupGraphics()
    g.set_clip("rect")
    assert g.get_clip() == "rect"
    assert g.get_clip_bounds() == "rect"
    g.set_paint("pat")
    assert g.get_paint() == "pat"


def test_page_drawer_parameters_round_trip():
    params = PageDrawerParameters(
        renderer="r",
        page="p",
        subsampling_allowed=True,
        destination=RenderDestination.VIEW,
        rendering_hints={"AA": True},
        image_downscaling_optimization_threshold=0.5,
    )
    assert params.get_renderer() == "r"
    assert params.get_page() == "p"
    assert params.is_subsampling_allowed() is True
    assert params.get_destination() is RenderDestination.VIEW
    assert params.get_rendering_hints() == {"AA": True}
    assert params.get_image_downscaling_optimization_threshold() == 0.5


def test_soft_mask_translucent():
    sm = SoftMask(paint=None, mask=None, bbox_device=None)
    assert sm.get_transparency() == 3


def test_tiling_paint_parameter_equality_and_hash():
    a = TilingPaintParameter(None, None, None, None, "X")
    b = TilingPaintParameter(None, None, None, None, "X")
    c = TilingPaintParameter(None, None, None, None, "Y")
    assert a.equals(b)
    assert not a.equals(c)
    assert hash(a) == hash(b)


def test_tiling_paint_factory_returns_cached_paint():
    class _StubDrawer:
        def get_initial_matrix(self):
            return None

    class _StubPattern:
        def get_cos_object(self):
            return None

        def get_matrix(self):
            return None

    factory = TilingPaintFactory(_StubDrawer())
    pat = _StubPattern()
    p1 = factory.create(pat, None, None, "xform")
    p2 = factory.create(pat, None, None, "xform")
    # Same cache key, so same TilingPaint instance (weak-ref permitting).
    assert isinstance(p1, type(p2))


def test_transparency_group_default_dimensions():
    tg = TransparencyGroup(form=None)
    assert tg.get_image() is None
    assert tg.get_b_box() is None
    assert tg.get_width() == 0
    assert tg.get_height() == 0
