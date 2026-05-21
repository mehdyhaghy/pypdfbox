"""Wave 1377 — tests for ``_calc_patch_level``, the adaptive subdivision
picker that replaced the fixed N=10 in the Coons (type 6) and tensor
(type 7) patch-mesh renderer.

The picker is a direct port of upstream PDFBox's
``CoonsPatch.calcLevel`` / ``TensorPatch.calcLevel``. The unit tests
exercise the three behaviour modes:

1. **Linear** patch with short edges → minimum subdivision (level 1 →
   2 cells per axis).
2. **Long straight** patch → larger but still capped subdivision
   (levels 2/3/4 depending on chord length).
3. **Curved** patch (cubic control points off the chord, or interior
   bow for tensor) → falls through to the upper-bound cap.
4. CTM scaling matters — the same user-space patch picks a different
   level when the CTM scales coordinates into a larger pixel range.
"""

from __future__ import annotations

from pypdfbox.rendering.pdf_renderer import (
    _PATCH_MAX_LEVEL,
    _calc_patch_level,
    _edge_is_line,
)

_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_MAX_CELLS = 2 ** _PATCH_MAX_LEVEL  # = 16 by default


def _coons_grid_box(
    x0: float, y0: float, x1: float, y1: float
) -> list[tuple[float, float]]:
    """Build a 12-point Coons patch whose 4 boundary curves are
    straight chords forming the rectangle ``(x0, y0) -> (x1, y1)``.
    Inner Bezier control points are placed at the 1/3 / 2/3 marks so
    ``_edge_is_line`` reports True."""
    # Boundary order: bottom (left→right), right (bottom→top),
    # top (right→left), left (top→bottom). We need 12 distinct points;
    # corners are shared (p0 = bottom-left, p3 = bottom-right,
    # p6 = top-right, p9 = top-left).
    return [
        (x0, y0),                            # p0 bottom-left
        (x0 + (x1 - x0) / 3.0, y0),          # p1
        (x0 + 2.0 * (x1 - x0) / 3.0, y0),    # p2
        (x1, y0),                            # p3 bottom-right
        (x1, y0 + (y1 - y0) / 3.0),          # p4
        (x1, y0 + 2.0 * (y1 - y0) / 3.0),    # p5
        (x1, y1),                            # p6 top-right
        (x1 - (x1 - x0) / 3.0, y1),          # p7
        (x1 - 2.0 * (x1 - x0) / 3.0, y1),    # p8
        (x0, y1),                            # p9 top-left
        (x0, y1 - (y1 - y0) / 3.0),          # p10
        (x0, y1 - 2.0 * (y1 - y0) / 3.0),    # p11
    ]


def _tensor_grid_box(
    x0: float, y0: float, x1: float, y1: float,
    *,
    bow: float = 0.0,
) -> list[tuple[float, float]]:
    """Build a 16-point tensor patch as a quadrilateral with optional
    interior bow. ``bow`` displaces the 4 interior control points
    perpendicular to the boundary; 0 produces a flat patch."""
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    # Boundary points first (12), then 4 interior. Ordering matches the
    # ``points`` indexing used by ``_tensor_patch_eval``.
    boundary = _coons_grid_box(x0, y0, x1, y1)
    # Interior 4 points: p12 / p13 (between row 0 and row 3 along col 1
    # and col 2), p14 / p15 (column reversal). We use centre-displaced
    # points to control whether the patch bows.
    p12 = (cx - (x1 - x0) / 6.0, cy - (y1 - y0) / 6.0 + bow)
    p13 = (cx + (x1 - x0) / 6.0, cy - (y1 - y0) / 6.0 - bow)
    p14 = (cx + (x1 - x0) / 6.0, cy + (y1 - y0) / 6.0 + bow)
    p15 = (cx - (x1 - x0) / 6.0, cy + (y1 - y0) / 6.0 - bow)
    return [*boundary, p12, p13, p14, p15]


# ----------------------------------------------------------------------
# _edge_is_line — port of ``Patch.isEdgeALine``
# ----------------------------------------------------------------------


def test_edge_is_line_for_collinear_control_points() -> None:
    edge = [(0.0, 0.0), (33.3, 0.0), (66.6, 0.0), (100.0, 0.0)]
    assert _edge_is_line(edge)


def test_edge_is_line_false_for_bulged_cubic() -> None:
    # Inner control points sit well off the p0->p3 chord.
    edge = [(0.0, 0.0), (33.0, 60.0), (66.0, -60.0), (100.0, 0.0)]
    assert not _edge_is_line(edge)


# ----------------------------------------------------------------------
# Coons-patch level selection
# ----------------------------------------------------------------------


def test_coons_short_flat_patch_minimum_subdivision() -> None:
    """A short patch (<200 px in both axes) with straight edges should
    fall to level 1 → 2 cells per axis."""
    pts = _coons_grid_box(0.0, 0.0, 100.0, 100.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == 2
    assert n_v == 2


def test_coons_medium_flat_patch_level_2() -> None:
    """201..400 px chord → level 2 → 4 cells per axis."""
    pts = _coons_grid_box(0.0, 0.0, 300.0, 300.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == 4
    assert n_v == 4


def test_coons_long_flat_patch_level_3() -> None:
    """401..800 px chord → level 3 → 8 cells per axis."""
    pts = _coons_grid_box(0.0, 0.0, 500.0, 500.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == 8
    assert n_v == 8


def test_coons_very_long_flat_patch_caps_at_max_level() -> None:
    """>800 px chord → level 4 → ``2 ** _PATCH_MAX_LEVEL`` cells, the cap."""
    pts = _coons_grid_box(0.0, 0.0, 1000.0, 1000.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == _MAX_CELLS
    assert n_v == _MAX_CELLS


def test_coons_curved_patch_falls_back_to_max_level() -> None:
    """When the boundary cubics are NOT straight lines, the picker
    defaults to the max level regardless of edge length."""
    pts = _coons_grid_box(0.0, 0.0, 100.0, 100.0)
    # Bow the bottom edge so it's no longer a line.
    pts[1] = (33.0, 60.0)
    pts[2] = (66.0, -60.0)
    # And the top edge too.
    pts[7] = (66.0, 160.0)
    pts[8] = (33.0, 40.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    # u-axis can't reduce (top + bottom are curved); should be max cells.
    assert n_u == _MAX_CELLS


# ----------------------------------------------------------------------
# CTM-aware length measurement
# ----------------------------------------------------------------------


def test_ctm_scaling_pushes_level_up() -> None:
    """A 100x100 user-space patch with identity CTM is small (level 1);
    the SAME patch with a 5x scale CTM is 500 px wide → level 3."""
    pts = _coons_grid_box(0.0, 0.0, 100.0, 100.0)
    n_u_identity, _ = _calc_patch_level(pts, _IDENTITY)
    scale_5x = (5.0, 0.0, 0.0, 5.0, 0.0, 0.0)
    n_u_scaled, _ = _calc_patch_level(pts, scale_5x)
    assert n_u_identity == 2
    assert n_u_scaled == 8


def test_ctm_translation_does_not_affect_level() -> None:
    """Only the linear part of the CTM enters chord length; translation
    is identity in length."""
    pts = _coons_grid_box(0.0, 0.0, 100.0, 100.0)
    translation = (1.0, 0.0, 0.0, 1.0, 1000.0, 2000.0)
    n_u, n_v = _calc_patch_level(pts, translation)
    n_u_no_t, n_v_no_t = _calc_patch_level(pts, _IDENTITY)
    assert (n_u, n_v) == (n_u_no_t, n_v_no_t)


# ----------------------------------------------------------------------
# Tensor-patch level selection
# ----------------------------------------------------------------------


def test_tensor_flat_short_patch_minimum_subdivision() -> None:
    pts = _tensor_grid_box(0.0, 0.0, 100.0, 100.0, bow=0.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == 2
    assert n_v == 2


def test_tensor_bowed_interior_keeps_max_level() -> None:
    """Even with straight boundaries, a tensor patch whose interior
    control points have bowed OUT keeps the high subdivision."""
    # Boundary stays straight, but bow the interior by 200 px so the
    # interior points sit outside the patch's strip.
    pts = _tensor_grid_box(0.0, 0.0, 100.0, 100.0, bow=200.0)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == _MAX_CELLS
    assert n_v == _MAX_CELLS


# ----------------------------------------------------------------------
# Cap behaviour
# ----------------------------------------------------------------------


def test_cap_clamps_to_max_level() -> None:
    """The picker never returns more than ``2 ** _PATCH_MAX_LEVEL``
    cells per axis even for pathological inputs."""
    pts = _coons_grid_box(0.0, 0.0, 1e6, 1e6)
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u <= _MAX_CELLS
    assert n_v <= _MAX_CELLS


def test_invalid_point_count_returns_safe_default() -> None:
    """An unexpected number of control points triggers the
    ``2 ** _PATCH_MAX_LEVEL`` fall-back (this branch is defensive — the
    caller in ``_paint_patch_mesh_shading`` always passes 12 or 16
    points)."""
    pts = [(0.0, 0.0)] * 5
    n_u, n_v = _calc_patch_level(pts, _IDENTITY)
    assert n_u == _MAX_CELLS
    assert n_v == _MAX_CELLS
