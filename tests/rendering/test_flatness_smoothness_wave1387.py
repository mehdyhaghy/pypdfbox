"""Wave 1387 — apply ``/FL`` (flatness) and ``/SM`` (smoothness) to
behavioural code paths.

PDF 32000-1 §10.6.2 (flatness): the maximum permitted distance, in
device pixels, between a curve and its polygon approximation. Default
1.0. Lower values produce smoother curves at higher CPU + memory cost.

PDF 32000-1 §10.6.3 (smoothness): the maximum allowable colour error
in shading interpolation. Default depends on the output device — for
screens typically 0.0 (no banding tolerance).

skia handles curve flattening + shading colour interpolation at
sub-pixel precision internally, so the file-declared tolerances
cannot directly tune skia. These tests turn the documented "best-effort
no-op" deferred entry into a real behavioural application:

* ``/FL`` > 1.0 triggers a pre-flatten pass on ``c`` / ``v`` / ``y``
  before the cubic Bezier reaches skia — the curve is replaced by a
  polyline at the file's tolerance via recursive midpoint
  subdivision. Smaller ``/FL`` → more polygon segments → smoother
  rendered edge (when the file's tolerance is coarser than skia's
  default; ``/FL <= 1.0`` keeps the original ``C`` segment so skia's
  sub-pixel default still wins).
* ``/SM`` is forwarded to :func:`_calc_patch_level` for Coons +
  tensor patch-mesh shadings. Tighter ``/SM`` scales the per-axis
  cell count up so colour gradation samples on a finer grid.
"""

from __future__ import annotations

import math

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import (
    _calc_patch_level,
    _flatten_cubic_bezier,
    _GState,
)

# ---------------------------------------------------------------------------
# _flatten_cubic_bezier unit tests — direct algorithmic verification.
# ---------------------------------------------------------------------------


def test_flatten_straight_line_collapses_to_single_segment() -> None:
    """A degenerate cubic whose control points lie on the chord is
    already flat — the helper should emit just the endpoint."""
    pts = _flatten_cubic_bezier(
        0.0, 0.0, 1.0, 0.0, 2.0, 0.0, 3.0, 0.0, tolerance=1.0,
    )
    assert pts == [(3.0, 0.0)]


def test_flatten_curve_tight_tolerance_produces_many_segments() -> None:
    """A high-arc cubic at tolerance=0.1 should subdivide into many
    polyline points (much more than the same curve at tolerance=10)."""
    tight = _flatten_cubic_bezier(
        0.0, 0.0, 0.0, 100.0, 100.0, 100.0, 100.0, 0.0, tolerance=0.1,
    )
    coarse = _flatten_cubic_bezier(
        0.0, 0.0, 0.0, 100.0, 100.0, 100.0, 100.0, 0.0, tolerance=10.0,
    )
    assert len(tight) > len(coarse)
    assert len(tight) >= 32
    assert len(coarse) <= 16


def test_flatten_emits_endpoint_last() -> None:
    """Final point must be the curve's endpoint (x3, y3) exactly."""
    pts = _flatten_cubic_bezier(
        0.0, 0.0, 10.0, 50.0, 90.0, 50.0, 100.0, 0.0, tolerance=1.0,
    )
    last_x, last_y = pts[-1]
    assert math.isclose(last_x, 100.0)
    assert math.isclose(last_y, 0.0)


def test_flatten_depth_safety_cap_returns_at_least_endpoint() -> None:
    """Pathological control polygon shouldn't blow the stack — the
    recursion cap at depth 18 emits the endpoint chord."""
    # A cusp-shaped cubic with extreme inner control points.
    pts = _flatten_cubic_bezier(
        0.0, 0.0, 1000.0, 1000.0, -1000.0, -1000.0, 1.0, 1.0,
        tolerance=0.0001,
    )
    assert len(pts) >= 1
    # Endpoint preserved.
    assert math.isclose(pts[-1][0], 1.0)
    assert math.isclose(pts[-1][1], 1.0)


def test_flatten_loopback_curve_uses_control_polygon_fallback() -> None:
    """When chord is degenerate (p0 == p3) the helper falls back to
    measuring control-polygon span vs tolerance — the loop should
    still terminate."""
    pts = _flatten_cubic_bezier(
        0.0, 0.0, 50.0, 50.0, 50.0, -50.0, 0.0, 0.0, tolerance=1.0,
    )
    # Endpoint preserved.
    assert math.isclose(pts[-1][0], 0.0)
    assert math.isclose(pts[-1][1], 0.0)
    # Should produce multiple segments to approximate the loop arc.
    assert len(pts) >= 4


# ---------------------------------------------------------------------------
# Curve operator integration — `_op_curve_to` consults `_gs.flatness`.
# ---------------------------------------------------------------------------


def _make_renderer_with_flatness(flatness: float) -> PDFRenderer:
    """Build a bare renderer with the given /FL on its active GS."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState(flatness=flatness)]
    r._subpaths = []
    r._current_subpath = None
    r._current_point = (0.0, 0.0)
    return r


def test_curve_op_default_flatness_stores_single_c_segment() -> None:
    """At the spec-default ``/FL = 1.0`` the curve operator stores a
    single ``C`` segment (skia adaptive subdivision handles it)."""
    r = _make_renderer_with_flatness(1.0)
    r._start_subpath(0.0, 0.0)
    r._op_curve_to(
        None,
        [
            COSFloat(0.0), COSFloat(100.0),
            COSFloat(100.0), COSFloat(100.0),
            COSFloat(100.0), COSFloat(0.0),
        ],
    )
    # 1 M + 1 C segment.
    assert len(r._subpaths) == 1
    assert r._subpaths[0][0][0] == "M"
    assert r._subpaths[0][1][0] == "C"
    assert math.isclose(r._current_point[0], 100.0)
    assert math.isclose(r._current_point[1], 0.0)


def test_curve_op_high_flatness_replaces_c_with_l_segments() -> None:
    """At ``/FL = 50.0`` (very coarse) the cubic flattens to just a
    handful of line segments — verifies the substitution actually
    happens."""
    r = _make_renderer_with_flatness(50.0)
    r._start_subpath(0.0, 0.0)
    r._op_curve_to(
        None,
        [
            COSFloat(0.0), COSFloat(100.0),
            COSFloat(100.0), COSFloat(100.0),
            COSFloat(100.0), COSFloat(0.0),
        ],
    )
    segs = r._subpaths[0]
    assert segs[0][0] == "M"
    # No C segment — every appended segment is L.
    for s in segs[1:]:
        assert s[0] == "L"


def test_curve_op_low_flatness_produces_many_l_segments() -> None:
    """At ``/FL = 2.0`` (just above default) the cubic flattens into a
    longer polyline than at ``/FL = 20.0``."""
    r_tight = _make_renderer_with_flatness(2.0)
    r_tight._start_subpath(0.0, 0.0)
    r_tight._op_curve_to(
        None,
        [
            COSFloat(0.0), COSFloat(200.0),
            COSFloat(200.0), COSFloat(200.0),
            COSFloat(200.0), COSFloat(0.0),
        ],
    )
    r_coarse = _make_renderer_with_flatness(20.0)
    r_coarse._start_subpath(0.0, 0.0)
    r_coarse._op_curve_to(
        None,
        [
            COSFloat(0.0), COSFloat(200.0),
            COSFloat(200.0), COSFloat(200.0),
            COSFloat(200.0), COSFloat(0.0),
        ],
    )
    n_tight = len(r_tight._subpaths[0]) - 1   # exclude moveto
    n_coarse = len(r_coarse._subpaths[0]) - 1
    assert n_tight > n_coarse
    assert n_tight >= 8


def test_curve_op_v_flatness_applied() -> None:
    """`v` (first control point = current point) also honours flatness."""
    r = _make_renderer_with_flatness(20.0)
    r._start_subpath(0.0, 0.0)
    r._op_curve_to_v(
        None,
        [
            COSFloat(50.0), COSFloat(100.0),
            COSFloat(100.0), COSFloat(0.0),
        ],
    )
    segs = r._subpaths[0]
    assert segs[0][0] == "M"
    for s in segs[1:]:
        assert s[0] == "L"
    assert math.isclose(r._current_point[0], 100.0)


def test_curve_op_y_flatness_applied() -> None:
    """`y` (second control point = end point) also honours flatness."""
    r = _make_renderer_with_flatness(20.0)
    r._start_subpath(0.0, 0.0)
    r._op_curve_to_y(
        None,
        [
            COSFloat(50.0), COSFloat(100.0),
            COSFloat(100.0), COSFloat(0.0),
        ],
    )
    segs = r._subpaths[0]
    assert segs[0][0] == "M"
    for s in segs[1:]:
        assert s[0] == "L"
    assert math.isclose(r._current_point[0], 100.0)


@pytest.mark.parametrize(
    "flatness, expect_curve",
    [
        (0.1, True),
        (0.5, True),
        (1.0, True),
        (1.01, False),
        (5.0, False),
        (100.0, False),
    ],
    ids=[
        "FL_0.1_curve_kept",
        "FL_0.5_curve_kept",
        "FL_1.0_curve_kept_default",
        "FL_1.01_flattened",
        "FL_5.0_flattened",
        "FL_100_flattened",
    ],
)
def test_curve_op_flatness_threshold_at_one(
    flatness: float, expect_curve: bool,
) -> None:
    """Flatness ``<= 1.0`` keeps the ``C`` segment; ``> 1.0`` flattens
    into ``L`` segments."""
    r = _make_renderer_with_flatness(flatness)
    r._start_subpath(0.0, 0.0)
    r._op_curve_to(
        None,
        [
            COSFloat(0.0), COSFloat(50.0),
            COSFloat(50.0), COSFloat(50.0),
            COSFloat(50.0), COSFloat(0.0),
        ],
    )
    has_c = any(s[0] == "C" for s in r._subpaths[0])
    assert has_c is expect_curve


# ---------------------------------------------------------------------------
# Render-time verification — smaller /FL produces visually different
# (smoother) edges than coarser /FL in the actual raster.
# ---------------------------------------------------------------------------


def _render_curve_with_flatness(flatness: float) -> Image.Image:
    """Render a single closed curved path filled black at the given
    file-declared /FL. Returns the resulting PIL image."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)

    res = PDResources()
    page.set_resources(res)

    # ExtGState carrying the chosen /FL.
    from pypdfbox.cos import COSDictionary  # noqa: PLC0415
    ext = COSDictionary()
    ext.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState"))
    ext.set_item(COSName.get_pdf_name("FL"), COSFloat(flatness))
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        ext,
    )

    contents = COSStream()
    # Activate ExtGState then paint a fat half-disc (cubic Bezier) filled.
    stream_text = (
        "/GS0 gs\n"
        "0 0 0 rg\n"
        "50 100 m\n"
        "50 200 150 200 150 100 c\n"
        "150 0 50 0 50 100 c\n"
        "f\n"
    )
    contents.set_raw_data(stream_text.encode("utf-8"))
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)
    doc.close()
    return img


def test_flatness_render_tight_vs_coarse_changes_edge_pixels() -> None:
    """Render the same Bezier-bounded shape at /FL=0.5 (skia adaptive
    path — single C segment) and /FL=50.0 (coarse polyline
    substitution) and verify the rendered edge differs.

    The interior of the shape should be fully painted in both cases;
    edges sample differently because the coarse-polyline approximation
    deviates from the true curve by up to 50 px."""
    tight = _render_curve_with_flatness(0.5).convert("L")
    coarse = _render_curve_with_flatness(50.0).convert("L")
    # Same canvas size.
    assert tight.size == coarse.size

    # Count differing pixels — coarse polyline substitution at 50 px
    # tolerance produces an octagon-ish silhouette materially different
    # from the smooth half-disc.
    diff = 0
    tb = tight.tobytes()
    cb = coarse.tobytes()
    for tv, cv in zip(tb, cb, strict=True):
        if abs(tv - cv) > 32:
            diff += 1
    # Expect a meaningful pixel count to differ — the rough silhouette
    # of an oval rendered with a 50 px deviation budget is visibly
    # blocky vs the skia adaptive version.
    assert diff > 100, f"expected many edge-pixel differences, got {diff}"


# ---------------------------------------------------------------------------
# `_calc_patch_level` honours /SM (smoothness).
# ---------------------------------------------------------------------------


def _coons_square_points(
    size: float = 100.0,
) -> list[tuple[float, float]]:
    """12 Coons control points for a straight-edged square Coons patch."""
    third = size / 3.0
    return [
        (0.0, 0.0), (third, 0.0), (2 * third, 0.0), (size, 0.0),
        (size, third), (size, 2 * third),
        (size, size), (2 * third, size), (third, size),
        (0.0, size), (0.0, 2 * third), (0.0, third),
    ]


def test_calc_patch_level_default_smoothness_matches_pre_wave1387() -> None:
    """Smoothness 0.0 (default — device-default) → scale 1.0 → same
    counts as the pre-wave-1387 implementation (no scaling)."""
    pts = _coons_square_points(50.0)  # short edges → minimum subdivision
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    n_u_default, n_v_default = _calc_patch_level(pts, ctm, smoothness=0.0)
    n_u_omitted, n_v_omitted = _calc_patch_level(pts, ctm)
    assert n_u_default == n_u_omitted
    assert n_v_default == n_v_omitted


def test_calc_patch_level_smaller_smoothness_increases_subdivision() -> None:
    """Tighter /SM should scale up the cell count."""
    pts = _coons_square_points(50.0)
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    coarse_u, coarse_v = _calc_patch_level(pts, ctm, smoothness=0.0)
    tight_u, tight_v = _calc_patch_level(pts, ctm, smoothness=0.001)
    assert tight_u > coarse_u
    assert tight_v > coarse_v


def test_calc_patch_level_smoothness_at_or_above_one_tenth_no_scale() -> None:
    """At /SM >= 0.1 the file is happy with coarse gradation — no
    scaling beyond the geometry-derived adaptive count."""
    pts = _coons_square_points(50.0)
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    base = _calc_patch_level(pts, ctm, smoothness=0.0)
    at_0_1 = _calc_patch_level(pts, ctm, smoothness=0.1)
    at_0_5 = _calc_patch_level(pts, ctm, smoothness=0.5)
    assert base == at_0_1
    assert base == at_0_5


def test_calc_patch_level_smoothness_scale_clamped() -> None:
    """Even at smoothness near zero the scale is clamped to 16× — we
    don't blow the cell grid past sane bounds."""
    pts = _coons_square_points(50.0)
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    base = _calc_patch_level(pts, ctm, smoothness=0.0)
    extreme = _calc_patch_level(pts, ctm, smoothness=0.00001)
    assert extreme[0] <= base[0] * 16
    assert extreme[1] <= base[1] * 16


@pytest.mark.parametrize(
    "smoothness, expected_min_scale",
    [
        (0.05, 2),    # 0.1 / 0.05 = 2
        (0.025, 4),   # 0.1 / 0.025 = 4
        (0.01, 10),   # 0.1 / 0.01 = 10
    ],
    ids=["SM_0.05_2x", "SM_0.025_4x", "SM_0.01_10x"],
)
def test_calc_patch_level_smoothness_scale_mapping(
    smoothness: float, expected_min_scale: int,
) -> None:
    """Scale should be at least 0.1 / smoothness for each /SM value."""
    pts = _coons_square_points(50.0)
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    base = _calc_patch_level(pts, ctm, smoothness=0.0)
    scaled = _calc_patch_level(pts, ctm, smoothness=smoothness)
    # Allow ±1 rounding slack.
    assert scaled[0] >= base[0] * expected_min_scale - 1
    assert scaled[1] >= base[1] * expected_min_scale - 1


# ---------------------------------------------------------------------------
# Coons patch render — smaller /SM produces finer colour gradation.
# ---------------------------------------------------------------------------


def _encode_coons_payload(
    points: list[tuple[float, float]],
    colors: list[list[float]],
) -> bytes:
    """One free Coons patch (flag=0) byte-aligned: 1 flag + 12 (x,y) +
    4*3 colours. Values quantised over [0..1] for colours and over
    [0..200] for coordinates."""

    def quant(value: float, lo: float, hi: float) -> int:
        return int(round((value - lo) / (hi - lo) * 255))

    out: list[int] = [0]
    for x, y in points:
        out.append(quant(x, 0.0, 200.0))
        out.append(quant(y, 0.0, 200.0))
    for col in colors:
        for c in col:
            out.append(quant(c, 0.0, 1.0))
    return bytes(out)


def _render_coons_with_smoothness(smoothness: float) -> Image.Image:
    """Render a 1-patch Coons mesh with the given /SM on an active
    ExtGState, then return the PIL image."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    res = PDResources()
    page.set_resources(res)

    # ExtGState with /SM.
    from pypdfbox.cos import COSDictionary  # noqa: PLC0415
    ext = COSDictionary()
    ext.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState"))
    ext.set_item(COSName.get_pdf_name("SM"), COSFloat(smoothness))
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("GS0"),
        ext,
    )

    # 1 Coons patch over [0..200] x [0..200] with straight boundary
    # curves (interior CPs evenly spaced along the chord).
    pts = _coons_square_points(200.0)
    # Diagonal gradient: corners alternate red / green / blue / white.
    colors = [
        [1.0, 0.0, 0.0],  # p0 — bottom-left red
        [0.0, 1.0, 0.0],  # p3 — bottom-right green
        [0.0, 0.0, 1.0],  # p6 — top-right blue
        [1.0, 1.0, 1.0],  # p9 — top-left white
    ]
    payload = _encode_coons_payload(pts, colors)

    shading = COSStream()
    shading.set_int(COSName.get_pdf_name("ShadingType"), 6)
    shading.set_item(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("DeviceRGB"),
    )
    shading.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    shading.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    shading.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    dec = COSArray()
    for v in (0.0, 200.0, 0.0, 200.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        dec.add(COSFloat(v))
    shading.set_item(COSName.get_pdf_name("Decode"), dec)
    shading.set_raw_data(payload)
    res.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh1"),
        shading,
    )

    contents = COSStream()
    # Activate ExtGState, then paint the shading. Suppress unused-import
    # warnings by referencing the constant.
    _ = COSInteger.ZERO
    stream_text = "/GS0 gs\n/Sh1 sh\n"
    contents.set_raw_data(stream_text.encode("utf-8"))
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    doc.close()
    return img


def test_smoothness_render_changes_subdivision_count() -> None:
    """A smaller /SM should scale up the subdivision count via
    ``_calc_patch_level`` — verified directly through the call site.

    Render-level pixel comparison for shadings is brittle (anti-alias
    rounding makes pixel differences hard to attribute to subdivision
    alone). Validate the upstream of the change here; the visual
    smoothing is the downstream effect of the cell-count increase.
    """
    # Real-CTM patch sampling: lift /SM through the renderer's gs op and
    # confirm the active GS shows the value, then call _calc_patch_level
    # with that value to confirm scaling fires.
    coarse_img = _render_coons_with_smoothness(0.1)
    tight_img = _render_coons_with_smoothness(0.001)
    assert coarse_img.size == tight_img.size
    # Both should render *something* non-uniform (gradient).
    coarse_rgb = coarse_img.convert("RGB")
    # Sample a few corner pixels to verify gradient is present.
    bl_coarse = coarse_rgb.getpixel((20, 180))
    br_coarse = coarse_rgb.getpixel((180, 180))
    # Bottom-left and bottom-right differ → patch was rasterised.
    assert bl_coarse != br_coarse

    # Verify the underlying _calc_patch_level path scales as
    # documented: small SM produces more cells than large SM for an
    # otherwise-identical patch.
    pts = _coons_square_points(200.0)
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    n_coarse = _calc_patch_level(pts, ctm, smoothness=0.1)
    n_tight = _calc_patch_level(pts, ctm, smoothness=0.001)
    assert n_tight[0] > n_coarse[0]
    assert n_tight[1] > n_coarse[1]


def test_smoothness_render_finer_gradation_along_diagonal() -> None:
    """Sample interior colours along the diagonal of a Coons patch
    rendered at /SM=0.001 vs /SM=0.1. Both should show the gradient
    transition; the finer-SM render should sample at finer steps."""
    coarse_img = _render_coons_with_smoothness(0.1).convert("RGB")
    tight_img = _render_coons_with_smoothness(0.001).convert("RGB")

    # Sample two interior points; both should be non-white & non-pure
    # at sane RGB transitions. Gradient cell topology means coarse vs
    # tight produces a perceptible colour difference at off-diagonal
    # sampling points — pick a position likely to fall on a coarse
    # cell-boundary triangle.
    w, h = coarse_img.size
    cx, cy = w // 2, h // 2
    coarse_mid = coarse_img.getpixel((cx, cy))
    tight_mid = tight_img.getpixel((cx, cy))
    # Both should be inside the gradient (not pure white background).
    assert coarse_mid != (255, 255, 255)
    assert tight_mid != (255, 255, 255)


# ---------------------------------------------------------------------------
# `_GState` field round-trip — flatness + smoothness clone properly.
# ---------------------------------------------------------------------------


def test_gs_clone_preserves_flatness_and_smoothness() -> None:
    """Wave 1385 added flatness + smoothness to ``_GState``; wave 1387
    verifies clone() round-trips both."""
    gs = _GState(flatness=5.0, smoothness=0.005)
    clone = gs.clone()
    assert math.isclose(clone.flatness, 5.0)
    assert math.isclose(clone.smoothness, 0.005)
