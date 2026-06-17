"""Fuzz / behavioural-parity tests for clip-path application in
:class:`pypdfbox.rendering.PDFRenderer`.

PDF 32000-1 §8.5.4 and Apache PDFBox ``PageDrawer``: the ``W`` / ``W*``
operators do **not** clip immediately — they merely record a pending
clip-winding-rule flag. The actual clip is committed at the *next*
path-painting operator (``n``, ``S``, ``f``, ``B`` …): the current path
is transformed to device space, rasterised under the chosen winding
rule, and **intersected** (``Area.intersect`` in Java; ``ImageChops.
multiply`` here) with the existing graphics-state clip. The result is
stored on the GS clip and the pending flag is reset. ``q`` saves the
clip; ``Q`` restores it.

This module drives the renderer's internal clip machinery directly
against a real (small) raster so the skia-rasterised mask, the device
CTM transform, and the multiply-intersection all run for real. It
hammers the bug-prone branches:

* ``W`` alone (before any paint op) does NOT clip — the mask stays None.
* The pending-clip flag is reset to ``None`` after application.
* ``W*`` selects even-odd winding; ``W`` selects non-zero.
* The clip rasterises in DEVICE space (CTM applied at commit time).
* Two successive clips intersect to the *smaller* region (never grow).
* ``q ... W n ... Q`` restores the prior clip.
* ``n`` (end-path) commits a pending clip while painting nothing.
* An empty / degenerate clip path yields an all-zero (everything
  clipped out) mask, never a no-op.

Provenance: hand-written for pypdfbox (no direct upstream JUnit
counterpart — PageDrawer's clip path is exercised via rendering parity
in upstream).
"""
from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.rendering.pdf_renderer import (
    _IDENTITY,
    PDFRenderer,
    _GState,
)

W = 60
H = 60


class _StubRenderer:
    """A minimal stand-in that borrows the real :class:`PDFRenderer`
    clip / path methods but skips document construction. We bind the
    unbound methods onto this instance so the genuine skia raster +
    intersection logic runs against a controlled image and CTM.
    """

    def __init__(self, device_ctm: Any = _IDENTITY) -> None:
        self._image: Image.Image | None = Image.new("RGB", (W, H), (255, 255, 255))
        self._device_ctm = device_ctm
        self._gs_stack: list[_GState] = [_GState()]
        self._subpaths: list[list[Any]] = []
        self._current_subpath: list[Any] | None = None
        self._current_point: tuple[float, float] = (0.0, 0.0)
        self._pending_clip: str | None = None

    # --- borrow the real implementations ---
    _full_ctm = PDFRenderer._full_ctm
    _apply_pending_clip = PDFRenderer._apply_pending_clip
    _build_path_mask = PDFRenderer._build_path_mask
    _build_skia_path_alpha_mask = PDFRenderer._build_skia_path_alpha_mask
    _build_skia_path_alpha_mask_rgba = PDFRenderer._build_skia_path_alpha_mask_rgba
    _start_subpath = PDFRenderer._start_subpath
    _reset_path = PDFRenderer._reset_path

    @property
    def _gs(self) -> _GState:
        return self._gs_stack[-1]

    # --- path helpers that mimic the content-stream operators ---
    def rect(self, x: float, y: float, w: float, h: float) -> None:
        """``re`` — append a closed rectangle subpath (user space)."""
        self._current_subpath = [
            ("M", x, y),
            ("L", x + w, y),
            ("L", x + w, y + h),
            ("L", x, y + h),
            ("Z",),
        ]
        self._subpaths.append(self._current_subpath)
        self._current_point = (x, y)

    def push_q(self) -> None:
        self._gs_stack.append(self._gs.clone())

    def pop_q(self) -> None:
        if len(self._gs_stack) > 1:
            self._gs_stack.pop()

    def clip_w(self) -> None:
        self._pending_clip = "W"

    def clip_w_star(self) -> None:
        self._pending_clip = "W*"

    def end_path_n(self) -> None:
        """``n`` — commit the pending clip, painting nothing."""
        self._apply_pending_clip(default_even_odd=False)
        self._reset_path()


def _mask_at(mask: Image.Image | None, x: int, y: int) -> int:
    assert mask is not None
    return mask.getpixel((x, y))


def _full_mask() -> Image.Image:
    return Image.new("L", (W, H), 255)


# ---------------------------------------------------------------------------
# Deferral: W alone does not clip
# ---------------------------------------------------------------------------

def test_w_alone_does_not_clip_until_paint_op() -> None:
    r = _StubRenderer()
    r.rect(10, 10, 20, 20)
    r.clip_w()
    # No paint / n yet — clip must still be unset.
    assert r._gs.clip_mask is None
    assert r._pending_clip == "W"


def test_w_star_alone_does_not_clip() -> None:
    r = _StubRenderer()
    r.rect(10, 10, 20, 20)
    r.clip_w_star()
    assert r._gs.clip_mask is None
    assert r._pending_clip == "W*"


def test_pending_flag_reset_after_n() -> None:
    r = _StubRenderer()
    r.rect(10, 10, 20, 20)
    r.clip_w()
    r.end_path_n()
    assert r._pending_clip is None
    assert r._gs.clip_mask is not None


def test_n_with_no_pending_clip_is_noop() -> None:
    r = _StubRenderer()
    r.rect(10, 10, 20, 20)
    r.end_path_n()  # no W before — nothing pending
    assert r._gs.clip_mask is None
    assert r._pending_clip is None


# ---------------------------------------------------------------------------
# Mask geometry — inside set, outside cleared (device space)
# ---------------------------------------------------------------------------

def test_clip_mask_inside_rect_is_set_outside_is_cleared() -> None:
    r = _StubRenderer()
    r.rect(15, 15, 20, 20)  # device-identity → pixels (15..35)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    assert _mask_at(mask, 25, 25) > 200  # inside
    assert _mask_at(mask, 2, 2) == 0  # outside
    assert _mask_at(mask, 50, 50) == 0  # outside


def test_clip_uses_device_ctm_at_commit_time() -> None:
    # A device CTM that scales by 2 and translates by (5, 5). A user-space
    # rect (5..15, 5..15) lands at device pixels (15..35, 15..35).
    device = (2.0, 0.0, 0.0, 2.0, 5.0, 5.0)
    r = _StubRenderer(device_ctm=device)
    r.rect(5, 5, 10, 10)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    assert _mask_at(mask, 25, 25) > 200  # device-mapped interior
    assert _mask_at(mask, 8, 8) == 0  # below the device-mapped rect


def test_clip_respects_gs_ctm_too() -> None:
    # gs.ctm translates user space by (20, 20); device identity. A rect at
    # user (0..10) lands at device (20..30).
    r = _StubRenderer()
    r._gs.ctm = (1.0, 0.0, 0.0, 1.0, 20.0, 20.0)
    r.rect(0, 0, 10, 10)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    assert _mask_at(mask, 25, 25) > 200
    assert _mask_at(mask, 5, 5) == 0


# ---------------------------------------------------------------------------
# Intersection shrinks (never grows)
# ---------------------------------------------------------------------------

def test_two_clips_intersect_to_smaller_region() -> None:
    r = _StubRenderer()
    # First clip: big box (5..45).
    r.rect(5, 5, 40, 40)
    r.clip_w()
    r.end_path_n()
    # Second clip: overlapping box (25..55) → intersection (25..45).
    r.rect(25, 25, 30, 30)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    # Inside the intersection.
    assert _mask_at(mask, 35, 35) > 200
    # In the first box but not the second → cleared.
    assert _mask_at(mask, 10, 10) == 0
    # In the second box but not the first → cleared.
    assert _mask_at(mask, 52, 52) == 0


def test_intersection_never_grows_beyond_existing_clip() -> None:
    r = _StubRenderer()
    # Tiny clip (20..30).
    r.rect(20, 20, 10, 10)
    r.clip_w()
    r.end_path_n()
    # Huge second clip covering the whole canvas — intersection stays tiny.
    r.rect(0, 0, W, H)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    assert _mask_at(mask, 25, 25) > 200  # the tiny region survives
    assert _mask_at(mask, 5, 5) == 0  # everything outside it stays clipped
    assert _mask_at(mask, 50, 50) == 0


def test_disjoint_clips_yield_empty_region() -> None:
    r = _StubRenderer()
    r.rect(2, 2, 12, 12)  # (2..14)
    r.clip_w()
    r.end_path_n()
    r.rect(40, 40, 15, 15)  # (40..55) — disjoint
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    # No pixel can be in both boxes — mask is entirely cleared.
    assert mask.getextrema()[1] == 0


# ---------------------------------------------------------------------------
# Winding rule selection: W = non-zero, W* = even-odd
# ---------------------------------------------------------------------------

def _donut(r: _StubRenderer) -> None:
    # Outer rect (10..50) and concentric inner rect (20..40) as ONE path.
    r._current_subpath = [
        ("M", 10, 10), ("L", 50, 10), ("L", 50, 50), ("L", 10, 50), ("Z",),
    ]
    r._subpaths.append(r._current_subpath)
    r._current_subpath = [
        ("M", 20, 20), ("L", 40, 20), ("L", 40, 40), ("L", 20, 40), ("Z",),
    ]
    r._subpaths.append(r._current_subpath)


def test_w_star_donut_leaves_hole_even_odd() -> None:
    r = _StubRenderer()
    _donut(r)
    r.clip_w_star()
    r.end_path_n()
    mask = r._gs.clip_mask
    # Ring (between inner and outer) — set.
    assert _mask_at(mask, 15, 15) > 200
    # Hole centre — cleared (even-odd punches it out).
    assert _mask_at(mask, 30, 30) == 0


def test_w_donut_fills_through_hole_non_zero() -> None:
    r = _StubRenderer()
    _donut(r)  # both subpaths wind the same direction (CCW as emitted)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    # With the non-zero rule and same-direction windings the hole is filled.
    assert _mask_at(mask, 15, 15) > 200
    assert _mask_at(mask, 30, 30) > 200


@pytest.mark.parametrize("winding", ["W", "W*"])
def test_simple_rect_same_under_both_rules(winding: str) -> None:
    # A simple non-self-intersecting rect clips identically under both rules.
    r = _StubRenderer()
    r.rect(12, 12, 18, 18)
    r._pending_clip = winding
    r.end_path_n()
    mask = r._gs.clip_mask
    assert _mask_at(mask, 20, 20) > 200
    assert _mask_at(mask, 2, 2) == 0


# ---------------------------------------------------------------------------
# q / Q save & restore of the clip
# ---------------------------------------------------------------------------

def test_q_q_restores_prior_clip() -> None:
    r = _StubRenderer()
    # Outer clip established before q.
    r.rect(5, 5, 50, 50)
    r.clip_w()
    r.end_path_n()
    outer_mask = r._gs.clip_mask
    # q, then a tighter inner clip.
    r.push_q()
    r.rect(20, 20, 10, 10)
    r.clip_w()
    r.end_path_n()
    inner_mask = r._gs.clip_mask
    assert inner_mask is not outer_mask
    assert _mask_at(inner_mask, 8, 8) == 0  # tightened
    # Q restores the outer clip exactly.
    r.pop_q()
    assert r._gs.clip_mask is outer_mask
    assert _mask_at(r._gs.clip_mask, 8, 8) > 200  # the outer region returns


def test_q_without_clip_then_clip_inside_does_not_leak_out() -> None:
    r = _StubRenderer()
    r.push_q()
    r.rect(20, 20, 10, 10)
    r.clip_w()
    r.end_path_n()
    assert r._gs.clip_mask is not None
    r.pop_q()
    # After restore the (unclipped) outer state must be clip-free.
    assert r._gs.clip_mask is None


def test_nested_q_w_q_three_levels() -> None:
    r = _StubRenderer()
    r.rect(2, 2, 56, 56)
    r.clip_w()
    r.end_path_n()
    lvl0 = r._gs.clip_mask
    r.push_q()
    r.rect(10, 10, 40, 40)
    r.clip_w()
    r.end_path_n()
    r.push_q()
    r.rect(24, 24, 12, 12)
    r.clip_w()
    r.end_path_n()
    assert _mask_at(r._gs.clip_mask, 30, 30) > 200
    assert _mask_at(r._gs.clip_mask, 12, 12) == 0  # tight innermost
    r.pop_q()
    assert _mask_at(r._gs.clip_mask, 12, 12) > 200  # middle level back
    assert _mask_at(r._gs.clip_mask, 4, 4) == 0
    r.pop_q()
    assert r._gs.clip_mask is lvl0
    assert _mask_at(r._gs.clip_mask, 4, 4) > 200  # outermost back


def test_clip_inside_q_does_not_mutate_parent_mask() -> None:
    r = _StubRenderer()
    r.rect(5, 5, 50, 50)
    r.clip_w()
    r.end_path_n()
    parent = r._gs.clip_mask
    parent_pixels = parent.tobytes()
    r.push_q()
    r.rect(20, 20, 10, 10)
    r.clip_w()
    r.end_path_n()
    r.pop_q()
    # The parent mask object must be byte-for-byte unchanged.
    assert r._gs.clip_mask.tobytes() == parent_pixels


# ---------------------------------------------------------------------------
# Empty / degenerate clip paths
# ---------------------------------------------------------------------------

def test_empty_path_with_pending_clip_resets_flag_no_mask() -> None:
    r = _StubRenderer()
    # No subpaths at all, but a pending W.
    r._pending_clip = "W"
    r._apply_pending_clip(default_even_odd=False)
    # Upstream: with no path the clip is a no-op but the flag is consumed.
    assert r._pending_clip is None
    assert r._gs.clip_mask is None


def test_degenerate_zero_area_clip_clears_everything() -> None:
    # A single point / zero-area subpath produces no fillable interior.
    # The pending clip still commits → intersect with an all-zero mask →
    # everything is clipped out (mask all zero), never a no-op.
    r = _StubRenderer()
    r._current_subpath = [("M", 30, 30), ("L", 30, 30), ("Z",)]
    r._subpaths.append(r._current_subpath)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    assert mask is not None
    assert mask.getextrema()[1] == 0


def test_degenerate_clip_with_existing_clip_shrinks_to_empty() -> None:
    r = _StubRenderer()
    r.rect(10, 10, 30, 30)
    r.clip_w()
    r.end_path_n()
    assert _mask_at(r._gs.clip_mask, 20, 20) > 200
    # Now a degenerate (collinear) clip — intersection collapses to empty.
    r._current_subpath = [("M", 5, 5), ("L", 50, 50), ("Z",)]
    r._subpaths.append(r._current_subpath)
    r.clip_w()
    r.end_path_n()
    assert r._gs.clip_mask.getextrema()[1] == 0


def test_collinear_clip_yields_no_mask_alone() -> None:
    # With no existing clip a degenerate path → all-zero mask (per
    # _apply_pending_clip's None → blank fallback).
    r = _StubRenderer()
    r._current_subpath = [("M", 5, 5), ("L", 50, 5), ("L", 25, 5), ("Z",)]
    r._subpaths.append(r._current_subpath)
    r.clip_w()
    r.end_path_n()
    assert r._gs.clip_mask.getextrema()[1] == 0


# ---------------------------------------------------------------------------
# Path is consumed by the commit (no carry-over to a later op)
# ---------------------------------------------------------------------------

def test_path_reset_after_n_commit() -> None:
    r = _StubRenderer()
    r.rect(10, 10, 20, 20)
    r.clip_w()
    r.end_path_n()
    assert r._subpaths == []
    assert r._current_subpath is None


def test_second_clip_uses_only_its_own_path() -> None:
    r = _StubRenderer()
    r.rect(5, 5, 50, 50)
    r.clip_w()
    r.end_path_n()
    # The next clip's path must be a fresh rect, not the union with the old.
    r.rect(40, 40, 15, 15)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    # (5..14) was in the first clip but is outside the second → cleared.
    assert _mask_at(mask, 8, 8) == 0
    assert _mask_at(mask, 45, 45) > 200


# ---------------------------------------------------------------------------
# Many randomised intersections shrink monotonically
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "boxes",
    [
        [(0, 0, 60, 60), (10, 10, 40, 40), (20, 20, 20, 20)],
        [(5, 5, 50, 50), (5, 30, 50, 25), (30, 5, 25, 50)],
        [(0, 0, 60, 60), (15, 15, 30, 30)],
        [(10, 0, 40, 60), (0, 10, 60, 40)],
    ],
    ids=["concentric3", "cross", "concentric2", "plus"],
)
def test_successive_intersections_are_monotone(
    boxes: list[tuple[int, int, int, int]],
) -> None:
    r = _StubRenderer()
    prev_count: int | None = None
    for (x, y, w, h) in boxes:
        r.rect(x, y, w, h)
        r.clip_w()
        r.end_path_n()
        count = sum(1 for v in r._gs.clip_mask.tobytes() if v > 127)
        if prev_count is not None:
            # Intersection can only keep or shrink the lit-pixel count.
            assert count <= prev_count
        prev_count = count


@pytest.mark.parametrize("device_scale", [1.0, 0.5, 2.0])
def test_clip_under_various_device_scales(device_scale: float) -> None:
    device = (device_scale, 0.0, 0.0, device_scale, 0.0, 0.0)
    r = _StubRenderer(device_ctm=device)
    # User rect (10..30). Device pixels = scale * (10..30).
    r.rect(10, 10, 20, 20)
    r.clip_w()
    r.end_path_n()
    mask = r._gs.clip_mask
    cx = int(20 * device_scale)
    cy = int(20 * device_scale)
    assert _mask_at(mask, cx, cy) > 200


def test_w_then_w_star_pending_flag_overwritten() -> None:
    # If W is issued then W* before any paint, the later flag wins (upstream
    # stores a single clipWindingRule field; the last W/W* sets it).
    r = _StubRenderer()
    r.rect(15, 15, 20, 20)
    r.clip_w()
    r.clip_w_star()
    assert r._pending_clip == "W*"
    r.end_path_n()
    assert r._pending_clip is None
    assert r._gs.clip_mask is not None
