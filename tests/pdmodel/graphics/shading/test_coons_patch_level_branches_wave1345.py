"""Wave 1345 coverage-boost — exercise the cold ``calc_level`` branches
of :class:`CoonsPatch`.

Pre-wave 1345 the only existing fixture (a 3x3 unit square in
``test_shading_rendering_wave1280.py``) collapses both edge-pair lengths
to <= 200, hitting only the smallest-bucket branch. The branches at
``coons_patch.py`` lines 47, 49, 51 (level[0]) and 60, 62, 65 (level[1])
needed a wider patch + an aligned-edge layout so :meth:`is_edge_a_line`
returns ``True``.

Patch points layout (order matches upstream PDF Type-6 mesh):
``[p0..p11]`` per the Coons spec — control points stored in 4 rows by
:meth:`CoonsPatch.reshape_control_points`:

* row 0 = [p0, p11, p10, p9]   (used by level[0] — the "c" edges)
* row 1 = [p3, p4, p5, p6]     (used by level[0] — the "c" edges)
* row 2 = [p0, p1, p2, p3]     (used by level[1] — the "d" edges)
* row 3 = [p9, p8, p7, p6]     (used by level[1] — the "d" edges)
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.shading.coons_patch import CoonsPatch


def _coons_with_corners(
    p0: tuple[float, float],
    p3: tuple[float, float],
    p9: tuple[float, float],
    p6: tuple[float, float],
) -> CoonsPatch:
    """Build a Coons patch where every interior control point lies on the
    straight segment between its row's two corners (so
    :meth:`is_edge_a_line` reports ``True`` on every edge).

    Layout — bottom edge ``p0 -> p3`` divided into thirds at ``p1, p2``;
    right edge ``p3 -> p6`` at ``p4, p5``; top edge ``p9 -> p6`` reversed
    at ``p7, p8``; left edge ``p0 -> p9`` at ``p11, p10``.
    """
    def lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    p1 = lerp(p0, p3, 1 / 3)
    p2 = lerp(p0, p3, 2 / 3)
    p4 = lerp(p3, p6, 1 / 3)
    p5 = lerp(p3, p6, 2 / 3)
    p7 = lerp(p9, p6, 2 / 3)
    p8 = lerp(p9, p6, 1 / 3)
    p10 = lerp(p0, p9, 2 / 3)
    p11 = lerp(p0, p9, 1 / 3)
    pts = [p0, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11]
    colors = [[0.0], [1.0], [1.0], [0.0]]
    return CoonsPatch(pts, colors)


# ----------------------------------------------------------------------
# level[0]: rows 0 (left edge p0 -> p9) and 1 (right edge p3 -> p6)
# ----------------------------------------------------------------------


def test_coons_patch_level0_size_2_branch() -> None:
    """200 < edge <= 400  ->  ``level[0] = 2`` (line 51)."""
    # Square 250 x 250 — left edge p0(0,0)->p9(0,250) has length 250,
    # right edge p3(250,0)->p6(250,250) also 250.
    patch = _coons_with_corners((0, 0), (250, 0), (0, 250), (250, 250))
    assert patch.level[0] == 2


def test_coons_patch_level0_size_3_branch() -> None:
    """400 < edge <= 800  ->  ``level[0] = 3`` (line 49)."""
    patch = _coons_with_corners((0, 0), (500, 0), (0, 500), (500, 500))
    assert patch.level[0] == 3


def test_coons_patch_level0_oversize_keeps_default_4_branch() -> None:
    """> 800  ->  ``pass`` (line 47), level[0] keeps the default 4."""
    patch = _coons_with_corners((0, 0), (900, 0), (0, 900), (900, 900))
    assert patch.level[0] == 4


# ----------------------------------------------------------------------
# level[1]: rows 2 (bottom edge p0 -> p3) and 3 (top edge p9 -> p6)
# ----------------------------------------------------------------------


def test_coons_patch_level1_size_2_branch() -> None:
    """Bottom and top edges 200 < L <= 400, left/right > 800 so level[0]
    keeps the default 4 (cheaper construction than scaling both axes)."""
    # Bottom/top length 250; left/right length 900 -> level[0]=4.
    patch = _coons_with_corners((0, 0), (250, 0), (0, 900), (250, 900))
    assert patch.level[1] == 2


def test_coons_patch_level1_size_3_branch() -> None:
    """400 < edge <= 800  ->  ``level[1] = 3`` (line 63)."""
    patch = _coons_with_corners((0, 0), (500, 0), (0, 900), (500, 900))
    assert patch.level[1] == 3


def test_coons_patch_level1_oversize_keeps_default_4_branch() -> None:
    """> 800  ->  ``pass`` (line 61), level[1] keeps the default 4."""
    patch = _coons_with_corners((0, 0), (900, 0), (0, 900), (900, 900))
    assert patch.level[1] == 4
