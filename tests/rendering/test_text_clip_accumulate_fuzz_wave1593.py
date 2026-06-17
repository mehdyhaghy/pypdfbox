"""Wave 1593 — text-clip accumulation + ET-intersect fuzz / parity.

Exercises the PDF 32000-1 §9.3.6 text-clipping path machinery in
``pypdfbox.rendering.pdf_renderer`` end-to-end, mirroring upstream
``org.apache.pdfbox.rendering.PageDrawer`` (``drawGlyph`` →
``textClippingArea`` accumulation, committed in ``endText``):

* A glyph shown under a clip mode (4-7) adds its device-space outline to
  ``_text_clip_paths`` but the *intersection into the GS clip* is
  deferred until ``ET`` (``_op_end_text`` → ``_commit_text_clip``), never
  applied per-glyph.
* Several clip-mode glyphs accumulate into one combined (unioned) clip
  region; the union — not the last glyph — becomes the clip at ET.
* Mode 7 (clip-only) adds to the clip path but paints nothing; modes
  4/5/6 both paint AND clip.
* The accumulated path is reset at ET so the clip does not leak into the
  next text object.
* An empty text object (no clip glyph) commits nothing — the GS clip is
  left untouched.

The commit path uses the *real* skia rasteriser (skia is a required
runtime dep), so these assertions check the resulting alpha mask pixels,
not a mock. The per-glyph paint helpers are mocked where only the
fill/stroke/clip *decision* is under test.

Upstream parity reference (PageDrawer):
    Area textClippingArea;                       // null until first clip glyph
    void drawGlyph(...) { if (mode.isClip()) textClippingArea.add(outline); }
    void endText() { if (textClippingArea != null) { graphics.clip(area); area = null; } }
"""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.rendering import _aggdraw_compat as aggdraw

from .test_pdf_renderer_wave1391_coverage import _bare_renderer, _GState

skia = pytest.importorskip("skia")


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _rect_path(x0: float, y0: float, x1: float, y1: float) -> Any:
    """A device-space skia rectangle path, as stored in ``_text_clip_paths``
    after accumulation (the buffer holds raw transformed ``skia.Path``)."""
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(x0, y0, x1, y1))
    return p


def _agg_rect(x0: float, y0: float, x1: float, y1: float) -> Any:
    """An aggdraw-compat ``Path`` (glyph-local outline) — what
    ``_accumulate_text_clip_path`` / ``_paint_glyph_path`` receive. Its
    ``_sk`` skia handle is what gets transformed into the buffer."""
    p = aggdraw.Path()
    p.moveto(x0, y0)
    p.lineto(x1, y0)
    p.lineto(x1, y1)
    p.lineto(x0, y1)
    p.close()
    return p


def _commit_renderer(
    size: tuple[int, int] = (60, 40),
    *,
    clip_mask: Image.Image | None = None,
) -> Any:
    """Bare renderer wired with a real RGBA canvas + empty clip buffer so
    ``_commit_text_clip`` / ``_op_end_text`` run their real code paths."""
    gs = _GState()
    gs.clip_mask = clip_mask
    r = _bare_renderer(gs)
    r._image = Image.new("RGBA", size, (0, 0, 0, 0))  # noqa: SLF001
    r._text_clip_paths = []  # noqa: SLF001
    r._text_knockout_layer = None  # noqa: SLF001
    return r


def _solid_mask(size: tuple[int, int], box: tuple[int, int, int, int]) -> Image.Image:
    """An 'L' clip mask that is 255 inside ``box`` (LTRB) and 0 elsewhere."""
    m = Image.new("L", size, 0)
    x0, y0, x1, y1 = box
    for x in range(x0, x1):
        for y in range(y0, y1):
            m.putpixel((x, y), 255)
    return m


# ======================================================================
# A. accumulation: a clip glyph is recorded but NOT applied before ET
# ======================================================================


@pytest.mark.parametrize("mode", [4, 5, 6, 7])
def test_clip_glyph_accumulates_without_touching_gs_clip(mode: int) -> None:
    # PDF §9.3.6: a clip-mode glyph adds to the clipping path, but the
    # actual clip intersection is deferred to ET. Accumulating must not
    # mutate gs.clip_mask.
    r = _commit_renderer()
    before = r._gs.clip_mask  # noqa: SLF001
    r._accumulate_text_clip_path(_agg_rect(5, 5, 20, 20), (1, 0, 0, 1, 0, 0))  # noqa: SLF001
    assert len(r._text_clip_paths) == 1  # noqa: SLF001
    assert r._gs.clip_mask is before  # noqa: SLF001 — untouched until ET


def test_multiple_clip_glyphs_accumulate_in_order() -> None:
    r = _commit_renderer()
    for i in range(5):
        r._accumulate_text_clip_path(  # noqa: SLF001
            _agg_rect(i, i, i + 5, i + 5), (1, 0, 0, 1, 0, 0)
        )
    assert len(r._text_clip_paths) == 5  # noqa: SLF001


def test_accumulate_with_non_skia_path_is_dropped() -> None:
    # A path object lacking the private ``_sk`` skia handle is silently
    # skipped (defensive — never raises mid-text-object).
    r = _commit_renderer()
    r._accumulate_text_clip_path(object(), (1, 0, 0, 1, 0, 0))  # noqa: SLF001
    assert r._text_clip_paths == []  # noqa: SLF001


# ======================================================================
# B. ET commit: the union of accumulated glyphs becomes the clip
# ======================================================================


def test_single_clip_glyph_commits_at_et() -> None:
    r = _commit_renderer((40, 40))
    r._text_clip_paths = [_rect_path(10, 10, 30, 30)]  # noqa: SLF001
    r._commit_text_clip()  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m is not None
    assert m.mode == "L"
    assert m.getpixel((20, 20)) == 255  # inside the glyph box
    assert m.getpixel((2, 2)) == 0  # outside


def test_several_clip_glyphs_union_into_one_region() -> None:
    # Two disjoint glyph boxes: both their interiors survive the clip; the
    # gap between them is clipped out. The union, not the last glyph, wins.
    r = _commit_renderer((60, 30))
    r._text_clip_paths = [  # noqa: SLF001
        _rect_path(5, 5, 15, 25),
        _rect_path(40, 5, 55, 25),
    ]
    r._commit_text_clip()  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m.getpixel((10, 15)) == 255  # glyph 1
    assert m.getpixel((47, 15)) == 255  # glyph 2
    assert m.getpixel((28, 15)) == 0  # gap between glyphs


def test_overlapping_clip_glyphs_union_not_xor() -> None:
    # Two overlapping boxes use the non-zero winding rule (upstream
    # PageDrawer adds outlines into one Area) → the overlap stays filled,
    # it is not XOR'd out.
    r = _commit_renderer((40, 40))
    r._text_clip_paths = [  # noqa: SLF001
        _rect_path(5, 5, 25, 25),
        _rect_path(15, 15, 35, 35),
    ]
    r._commit_text_clip()  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m.getpixel((20, 20)) == 255  # overlap region stays inside


def test_commit_intersects_with_existing_gs_clip_at_et() -> None:
    # An existing GS clip (left half) intersected with a text clip
    # spanning the full width yields only the left-half overlap. The
    # intersection happens here, at ET — not before.
    existing = _solid_mask((60, 30), (0, 0, 30, 30))
    r = _commit_renderer((60, 30), clip_mask=existing)
    r._text_clip_paths = [_rect_path(5, 5, 55, 25)]  # noqa: SLF001
    r._commit_text_clip()  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m.getpixel((10, 15)) == 255  # left half: in both → survives
    assert m.getpixel((45, 15)) == 0  # right half: outside existing clip


def test_commit_does_not_widen_existing_clip() -> None:
    # The text clip can only ever *narrow* (multiply) the existing clip —
    # a glyph outside the existing clip cannot re-open clipped pixels.
    existing = _solid_mask((40, 40), (0, 0, 15, 40))
    r = _commit_renderer((40, 40), clip_mask=existing)
    r._text_clip_paths = [_rect_path(20, 5, 35, 35)]  # noqa: SLF001 — disjoint
    r._commit_text_clip()  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m.getpixel((25, 20)) == 0  # glyph region, but outside old clip
    assert m.getpixel((5, 20)) == 0  # old clip, but outside glyph


# ======================================================================
# C. mode dispatch through _paint_glyph_path with a real accumulate
# ======================================================================


class _PaintRec:
    def __init__(self) -> None:
        self.direct: list[dict[str, Any]] = []
        self.through: list[dict[str, Any]] = []

    def direct_paint(self, path: Any, ctm: Any, fill_rgb: Any, *, do_fill: bool,
                     do_stroke: bool) -> None:
        self.direct.append({"do_fill": do_fill, "do_stroke": do_stroke})

    def through_paint(self, path: Any, ctm: Any, fill_rgb: Any, *, do_fill: bool,
                      do_stroke: bool, clip_mask: Any) -> None:
        self.through.append({"do_fill": do_fill, "do_stroke": do_stroke})


def _paint_wired(mode: int, *, clip_mask: Any = None) -> tuple[Any, _PaintRec]:
    gs = _GState()
    gs.text_rendering_mode = mode
    gs.clip_mask = clip_mask
    r = _bare_renderer(gs)
    r._image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))  # noqa: SLF001
    r._text_clip_paths = []  # noqa: SLF001
    rec = _PaintRec()
    r._paint_glyph_path_direct = rec.direct_paint  # noqa: SLF001
    r._paint_glyph_path_through_clip = rec.through_paint  # noqa: SLF001
    return r, rec


@pytest.mark.parametrize("mode", [4, 5, 6])
def test_visible_clip_mode_both_paints_and_accumulates(mode: int) -> None:
    # Mode 4 (fill+clip), 5 (stroke+clip), 6 (fill+stroke+clip): the glyph
    # is painted AND its outline lands in _text_clip_paths.
    r, rec = _paint_wired(mode)
    r._paint_glyph_path(_agg_rect(0, 0, 10, 10), (1, 0, 0, 1, 0, 0), (1, 2, 3))  # noqa: SLF001
    assert len(r._text_clip_paths) == 1  # noqa: SLF001 — accumulated
    assert len(rec.direct) == 1  # noqa: SLF001 — and painted
    assert rec.direct[0]["do_fill"] is (mode in (4, 6))
    assert rec.direct[0]["do_stroke"] is (mode in (5, 6))


def test_clip_only_mode7_accumulates_but_paints_nothing() -> None:
    r, rec = _paint_wired(7)
    r._paint_glyph_path(_agg_rect(0, 0, 10, 10), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert len(r._text_clip_paths) == 1  # noqa: SLF001 — added to clip
    assert rec.direct == []  # but never painted
    assert rec.through == []


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_non_clip_modes_never_accumulate(mode: int) -> None:
    r, rec = _paint_wired(mode)
    r._paint_glyph_path(_agg_rect(0, 0, 10, 10), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert r._text_clip_paths == []  # noqa: SLF001 — no clip contribution


@pytest.mark.parametrize("mode", [4, 5, 6])
def test_visible_clip_mode_routes_through_clip_when_gs_clip_active(mode: int) -> None:
    sentinel = _solid_mask((40, 40), (0, 0, 40, 40))
    r, rec = _paint_wired(mode, clip_mask=sentinel)
    r._paint_glyph_path(_agg_rect(0, 0, 10, 10), (1, 0, 0, 1, 0, 0), (1, 2, 3))  # noqa: SLF001
    assert rec.direct == []
    assert len(rec.through) == 1
    assert len(r._text_clip_paths) == 1  # noqa: SLF001 — still accumulates


# ======================================================================
# D. switching render mode mid-text-object
# ======================================================================


def test_mode_switch_mid_text_object_only_clip_glyphs_accumulate() -> None:
    # Glyph 1 in mode 0 (no clip), then Tr 7, then glyphs 2-3 (clip-only).
    # Only the two clip-mode glyphs land in the buffer.
    r, rec = _paint_wired(0)
    r._paint_glyph_path(_agg_rect(0, 0, 5, 5), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert r._text_clip_paths == []  # noqa: SLF001
    r._gs.text_rendering_mode = 7  # noqa: SLF001 — switch mid-object
    r._paint_glyph_path(_agg_rect(5, 0, 10, 5), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    r._paint_glyph_path(_agg_rect(10, 0, 15, 5), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert len(r._text_clip_paths) == 2  # noqa: SLF001 — only clip glyphs


def test_mode_switch_clip_then_fill_keeps_only_clip_glyphs() -> None:
    r, rec = _paint_wired(4)
    r._paint_glyph_path(_agg_rect(0, 0, 5, 5), (1, 0, 0, 1, 0, 0), (1, 1, 1))  # noqa: SLF001
    assert len(r._text_clip_paths) == 1  # noqa: SLF001
    r._gs.text_rendering_mode = 0  # noqa: SLF001 — back to plain fill
    r._paint_glyph_path(_agg_rect(5, 0, 10, 5), (1, 0, 0, 1, 0, 0), (1, 1, 1))  # noqa: SLF001
    assert len(r._text_clip_paths) == 1  # noqa: SLF001 — fill glyph not added


# ======================================================================
# E. ET semantics: commit once, reset, no leak, empty case
# ======================================================================


def _stub_knockout(r: Any) -> None:
    r._maybe_end_text_knockout = lambda: None  # noqa: SLF001


def test_et_commits_exactly_once_and_resets_buffer() -> None:
    r = _commit_renderer((40, 40))
    r._text_clip_paths = [_rect_path(5, 5, 25, 25)]  # noqa: SLF001
    calls: list[bool] = []
    real_commit = r._commit_text_clip  # noqa: SLF001

    def _counting() -> None:
        calls.append(True)
        real_commit()

    r._commit_text_clip = _counting  # noqa: SLF001
    _stub_knockout(r)
    r._op_end_text(None, [])  # noqa: SLF001
    assert calls == [True]  # committed exactly once
    assert r._text_clip_paths == []  # noqa: SLF001 — buffer reset


def test_empty_text_object_commits_nothing() -> None:
    # No clip-mode glyph shown → no buffer → ET leaves the GS clip alone.
    r = _commit_renderer((40, 40))
    before = r._gs.clip_mask  # noqa: SLF001 — None
    calls: list[bool] = []
    r._commit_text_clip = lambda: calls.append(True)  # noqa: SLF001
    _stub_knockout(r)
    r._op_end_text(None, [])  # noqa: SLF001
    assert calls == []  # commit skipped
    assert r._gs.clip_mask is before  # noqa: SLF001


def test_clip_does_not_leak_into_next_text_object() -> None:
    # First BT/ET establishes a left-box clip; BT resets the buffer; the
    # second (non-clip) text object must not re-apply or extend the clip.
    r = _commit_renderer((60, 30))
    r._text_clip_paths = [_rect_path(5, 5, 25, 25)]  # noqa: SLF001
    _stub_knockout(r)
    r._op_end_text(None, [])  # noqa: SLF001
    first_clip = r._gs.clip_mask  # noqa: SLF001
    assert first_clip is not None
    # New text object.
    r._maybe_begin_text_knockout = lambda: None  # noqa: SLF001
    r._op_begin_text(None, [])  # noqa: SLF001
    assert r._text_clip_paths == []  # noqa: SLF001 — fresh buffer
    # No clip glyph this round; ET must not change the clip.
    r._op_end_text(None, [])  # noqa: SLF001
    assert r._gs.clip_mask is first_clip  # noqa: SLF001 — unchanged


def test_second_text_object_clip_narrows_first() -> None:
    # Two sequential clip text objects: the second clip is intersected
    # with the (already-narrowed) clip from the first — clips compound.
    r = _commit_renderer((60, 30))
    r._maybe_begin_text_knockout = lambda: None  # noqa: SLF001
    _stub_knockout(r)
    # Object 1: clip to the left 0..40.
    r._op_begin_text(None, [])  # noqa: SLF001
    r._text_clip_paths = [_rect_path(0, 0, 40, 30)]  # noqa: SLF001
    r._op_end_text(None, [])  # noqa: SLF001
    # Object 2: clip to the right 20..60 → intersection is 20..40.
    r._op_begin_text(None, [])  # noqa: SLF001
    r._text_clip_paths = [_rect_path(20, 0, 60, 30)]  # noqa: SLF001
    r._op_end_text(None, [])  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m.getpixel((30, 15)) == 255  # in both clips
    assert m.getpixel((10, 15)) == 0  # only in object 1's clip
    assert m.getpixel((50, 15)) == 0  # only in object 2's clip


def test_begin_text_resets_inflight_clip_buffer() -> None:
    # If a BT arrives with stale clip paths (e.g. a malformed stream that
    # re-emits BT without an intervening ET), the buffer is wiped so the
    # previous object's glyphs do not bleed into the new one.
    r = _commit_renderer((40, 40))
    r._maybe_begin_text_knockout = lambda: None  # noqa: SLF001
    r._text_clip_paths = [_rect_path(0, 0, 10, 10)]  # noqa: SLF001 — stale
    r._op_begin_text(None, [])  # noqa: SLF001
    assert r._text_clip_paths == []  # noqa: SLF001


# ======================================================================
# F. commit edge cases
# ======================================================================


def test_commit_with_empty_buffer_is_noop() -> None:
    r = _commit_renderer((40, 40))
    r._text_clip_paths = []  # noqa: SLF001
    r._commit_text_clip()  # noqa: SLF001 — must not raise
    assert r._gs.clip_mask is None  # noqa: SLF001


def test_commit_without_image_is_noop() -> None:
    gs = _GState()
    r = _bare_renderer(gs)
    r._image = None  # noqa: SLF001
    r._text_clip_paths = [_rect_path(0, 0, 10, 10)]  # noqa: SLF001
    r._commit_text_clip()  # noqa: SLF001 — guarded on _image is None
    assert r._gs.clip_mask is None  # noqa: SLF001


def test_degenerate_zero_area_glyph_does_not_crash() -> None:
    # A collapsed (zero-width) glyph outline: union bounds are degenerate;
    # the commit returns without raising and leaves the clip untouched.
    # (Divergence from upstream graphics.clip(emptyArea) is a documented
    # deferred follow-up; here we only assert no crash.)
    r = _commit_renderer((40, 40))
    r._text_clip_paths = [_rect_path(10, 10, 10, 30)]  # noqa: SLF001 — zero width
    r._commit_text_clip()  # noqa: SLF001
    # No exception. clip_mask may stay None (degenerate early-return).
    assert r._gs.clip_mask is None  # noqa: SLF001


def test_full_glyph_clip_leaves_inside_opaque_outside_clipped() -> None:
    # End-to-end through _op_end_text with a real glyph box: inside the
    # box is fully kept (255), outside is fully clipped (0).
    r = _commit_renderer((50, 50))
    r._maybe_begin_text_knockout = lambda: None  # noqa: SLF001
    _stub_knockout(r)
    r._op_begin_text(None, [])  # noqa: SLF001
    r._accumulate_text_clip_path(  # noqa: SLF001
        _agg_rect(12, 12, 38, 38), (1, 0, 0, 1, 0, 0)
    )
    r._op_end_text(None, [])  # noqa: SLF001
    m = r._gs.clip_mask  # noqa: SLF001
    assert m.getpixel((25, 25)) == 255
    assert m.getpixel((3, 3)) == 0
    assert r._text_clip_paths == []  # noqa: SLF001 — reset after ET
