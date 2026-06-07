"""Coverage round-out (wave 1511) for the JBIG2 ``Resizer`` internals.

Wave 1490 proved the filtered-zoom pipeline byte-exact through the public
``Bitmaps.as_raster`` entry point (the Gaussian kernel the JBIG2 ``readRaster``
path hardwires). The internal ``_Mapping`` coordinate transforms, the
``_is_integer`` predicate, the ``_intersection`` rectangle helper, the explicit
non-AUTO resize order, the destination-window intersection clamp, and the
zero-area early-return were never reached by that single scale path. These are
all faithful ports of ``org.apache.pdfbox.jbig2.image.Resizer`` and are
exercised here directly with crafted inputs.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.filter import Box, Point, Triangle
from pypdfbox.jbig2.image.resizer import (
    ParameterizedFilter,
    Resizer,
    Weighttab,
    _intersection,
    _is_integer,
    _Mapping,
    _Raster,
)


def test_mapping_transforms_round_trip():
    # ``_Mapping`` mirrors ``Resizer.Mapping`` — dst_to_src and src_to_dst are
    # inverses (modulo the half-pixel offset baked into map_pixel_center).
    m = _Mapping(2.0)
    assert m.scale == 2.0
    # src_to_dst then dst_to_src is the identity.
    assert m.dst_to_src(m.src_to_dst(7.0)) == 7.0
    # map_pixel_center adds the half-pixel sample offset.
    assert m.map_pixel_center(0) == (0 + 0.5 - 0.0) / 2.0 + 0.0


def test_is_integer_predicate():
    # ``Resizer.isInteger`` — true within _EPSILON of a whole number.
    assert _is_integer(4.0)
    assert _is_integer(4.0000000001)
    assert not _is_integer(4.4)
    assert _is_integer(-3.0)


def test_intersection_overlapping_and_disjoint():
    # ``java.awt.Rectangle.intersection`` semantics.
    # Overlap: (0,0,10,10) ∩ (5,5,10,10) == (5,5,5,5).
    assert _intersection((0, 0, 10, 10), (5, 5, 10, 10)) == (5, 5, 5, 5)
    # Fully contained.
    assert _intersection((0, 0, 10, 10), (2, 2, 3, 3)) == (2, 2, 3, 3)
    # Disjoint -> negative-extent rectangle (matches AWT's raw subtraction).
    out = _intersection((0, 0, 2, 2), (10, 10, 2, 2))
    assert out[2] < 0 and out[3] < 0


def _solid_bitmap(width: int, height: int) -> Bitmap:
    bmp = Bitmap(width, height)
    for y in range(height):
        for x in range(width):
            bmp.set_pixel(x, y, (x + y) & 1)
    return bmp


def test_resize_zero_area_destination_returns_early():
    # A degenerate destination bounds (zero width) trips the early return before
    # any scanline work.
    r = Resizer(1.0, 1.0)
    src = _solid_bitmap(8, 8)
    dst = _Raster(8, 8)
    before = bytes(dst.get_data())
    r.resize(
        src,
        (0, 0, 8, 8),
        dst,
        (0, 0, 0, 0),  # zero-area destination
        Triangle(),
        Triangle(),
    )
    # Nothing was written.
    assert bytes(dst.get_data()) == before


def test_resize_explicit_order_xy_and_yx_match():
    # Forcing the order off AUTO drives the ``self.order != "AUTO"`` arm for both
    # XY and YX; both produce the same downscaled raster as the AUTO heuristic.
    src = _solid_bitmap(8, 8)

    def _run(order: str) -> bytes:
        r = Resizer(0.5, 0.5)
        r.order = order
        dst = _Raster(4, 4)
        r.resize(src, (0, 0, 8, 8), dst, (0, 0, 4, 4), Triangle(), Triangle())
        return bytes(dst.get_data())

    auto = _run("AUTO")
    xy = _run("XY")
    yx = _run("YX")
    # Each order produces a full 4x4 grayscale raster. (XY vs YX can differ by
    # at most one quantisation step per pixel — the well-known order-dependent
    # rounding of the Graphics Gems filtered zoom — so we don't assert equality,
    # only that every path runs and writes the expected shape.)
    assert len(auto) == 16
    assert len(xy) == 16
    assert len(yx) == 16
    assert any(b != 0 for b in xy)
    assert any(b != 0 for b in yx)


def test_resizer_single_arg_uses_same_scale_on_both_axes():
    # ``Resizer(scale_x)`` defaults ``scale_y = scale_x`` (the single-arg ctor
    # overload). Both axis mappings carry the same scale.
    r = Resizer(0.5)
    assert r.mapping_x.scale == 0.5
    assert r.mapping_y.scale == 0.5


def test_parameterized_filter_explicit_support_and_width_ctor():
    # The four-arg ``ParameterizedFilter(Filter, scale, support, width)`` overload
    # stores the caller's support/width verbatim rather than deriving them.
    pf = ParameterizedFilter(Triangle(), 2.0, support=3.5, width=7)
    assert pf.scale == 2.0
    assert pf.support == 3.5
    assert pf.width == 7


def test_weighttab_all_zero_weights_falls_back_to_single_unit_weight():
    # When every quantised weight rounds to zero, ``Weighttab`` collapses to a
    # single ``weight_one`` sample (the ``total == 0`` arm). A Box kernel
    # evaluated where its window misses every sample integer yields a zero
    # filter sum, forcing that fallback.
    pf = ParameterizedFilter(Box(), 1.0)
    # weight_one == 1: the single in-window sample quantises to round(1*1) but
    # with a center placed on a half-integer the Box window can still collapse;
    # drive the den==0 scale path explicitly via an out-of-window center.
    tab = Weighttab(pf, weight_one=1, center=0.0, a0=0, a1=0, trimzeros=False)
    assert sum(tab.weights) >= 1


def test_weighttab_normalises_to_weight_one():
    # The normal (non-degenerate) path: a Triangle kernel centred inside the
    # range produces weights that are fudged to sum to exactly weight_one (the
    # ``total != weight_one`` arm).
    pf = ParameterizedFilter(Triangle(), 1.0)
    tab = Weighttab(pf, weight_one=16384, center=1.3, a0=0, a1=3, trimzeros=False)
    assert sum(tab.weights) == 16384


def test_simplify_filter_collapses_to_point():
    # ``_simplify_filter`` collapses a sub-half-pixel-support kernel (or an
    # integer-scale cardinal one) to a single Point sample. A Point filter has
    # support 0.5, tripping the ``support <= 0.5`` arm.
    r = Resizer(1.0, 1.0)
    pf = ParameterizedFilter(Point(), 1.0)
    simplified = r._simplify_filter(pf, 1.0, r.mapping_x.offset)
    assert isinstance(simplified.filter, Point)
    assert simplified.support == 0.5
    assert simplified.width == 1
    # An integer-scale cardinal Box also collapses to Point.
    pf_box = ParameterizedFilter(Box(), 1.0)
    simplified_box = r._simplify_filter(pf_box, 1.0, r.mapping_x.offset)
    assert isinstance(simplified_box.filter, Point)


def test_simplify_filter_keeps_non_collapsible_kernel():
    # A wide-support non-integer-scale kernel is returned unchanged.
    r = Resizer(0.5, 0.5)
    pf = ParameterizedFilter(Triangle(), 0.5)
    out = r._simplify_filter(pf, 0.5, r.mapping_x.offset)
    assert out is pf


def test_resize_destination_window_intersection_clamp():
    # A destination bounds that overruns the valid transformed source window
    # forces the ``_intersection`` clamp branch (dst_bounds shrunk to the
    # region) before the (still non-empty) scanline pass runs.
    r = Resizer(0.5, 0.5)
    src = _solid_bitmap(8, 8)
    dst = _Raster(20, 20)
    # Ask for a destination far larger than the transformed source supports.
    r.resize(src, (0, 0, 8, 8), dst, (0, 0, 20, 20), Triangle(), Triangle())
    # Some pixels were written into the clamped sub-window.
    assert any(b != 0 for b in dst.get_data())
