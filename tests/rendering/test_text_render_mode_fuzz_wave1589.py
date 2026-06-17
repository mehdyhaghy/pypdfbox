"""Wave 1589 — text rendering mode (``Tr``) fuzz / parity harness.

Hammers the PDF 32000-1 §9.3.6 / Table 106 text-rendering-mode dispatch
across two layers:

* :class:`RenderingMode` predicate parity vs upstream
  ``org.apache.pdfbox.pdmodel.graphics.state.RenderingMode`` — the
  ``is_fill`` / ``is_stroke`` / ``is_clip`` truth table for modes 0-7,
  the ``from_int`` / ``int_value`` round-trip, and the out-of-range
  ``IndexError`` (mirroring upstream's array-index throw).

* The renderer's ``_op_set_text_rendering_mode`` (``Tr`` handler) and
  ``_paint_glyph_path`` fill/stroke/clip decision — exercised with the
  actual rasteriser helpers mocked, so the test asserts the *decision*
  (does this mode fill? stroke? add to the text clip?) rather than pixel
  output. The decision is compared mode-by-mode to upstream PageDrawer /
  RenderingMode semantics.

Wave 1589 fix verified here: the ``Tr`` handler now *ignores* an
out-of-range operand (``< 0`` or ``>= 8``) instead of clamping to 0/7,
matching upstream ``SetTextRenderingMode.process`` which guards
``val < 0 || val >= RenderingMode.values().length`` with a plain return.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.state import RenderingMode

from .test_pdf_renderer_wave1391_coverage import _bare_renderer, _GState

# ----------------------------------------------------------------------
# Upstream truth table — PDF 32000-1 §9.3.6 / Table 106.
# (mode int) -> (fill?, stroke?, clip?)
# ----------------------------------------------------------------------
MODE_TRIPLES: dict[int, tuple[bool, bool, bool]] = {
    0: (True, False, False),   # FILL
    1: (False, True, False),   # STROKE
    2: (True, True, False),    # FILL_STROKE
    3: (False, False, False),  # NEITHER (invisible)
    4: (True, False, True),    # FILL_CLIP
    5: (False, True, True),    # STROKE_CLIP
    6: (True, True, True),     # FILL_STROKE_CLIP
    7: (False, False, True),   # NEITHER_CLIP (clip only)
}


# ======================================================================
# RenderingMode predicate parity (vs upstream RenderingMode.java)
# ======================================================================


@pytest.mark.parametrize("mode_int", list(range(8)))
def test_predicate_triple_matches_upstream(mode_int: int) -> None:
    member = RenderingMode.from_int(mode_int)
    want_fill, want_stroke, want_clip = MODE_TRIPLES[mode_int]
    assert member.is_fill() is want_fill
    assert member.is_stroke() is want_stroke
    assert member.is_clip() is want_clip


@pytest.mark.parametrize("mode_int", list(range(8)))
def test_int_value_round_trips(mode_int: int) -> None:
    member = RenderingMode.from_int(mode_int)
    assert member.int_value() == mode_int
    assert RenderingMode.from_int(member.int_value()) is member


def test_neither_is_fully_invisible() -> None:
    m = RenderingMode.NEITHER
    assert not m.is_fill()
    assert not m.is_stroke()
    assert not m.is_clip()


def test_neither_clip_draws_nothing_but_clips() -> None:
    m = RenderingMode.NEITHER_CLIP
    assert not m.is_fill()
    assert not m.is_stroke()
    assert m.is_clip()


def test_fill_modes_set_matches_upstream() -> None:
    fillers = {m for m in RenderingMode if m.is_fill()}
    assert fillers == {
        RenderingMode.FILL,
        RenderingMode.FILL_STROKE,
        RenderingMode.FILL_CLIP,
        RenderingMode.FILL_STROKE_CLIP,
    }


def test_stroke_modes_set_matches_upstream() -> None:
    strokers = {m for m in RenderingMode if m.is_stroke()}
    assert strokers == {
        RenderingMode.STROKE,
        RenderingMode.FILL_STROKE,
        RenderingMode.STROKE_CLIP,
        RenderingMode.FILL_STROKE_CLIP,
    }


def test_clip_modes_set_matches_upstream() -> None:
    clippers = {m for m in RenderingMode if m.is_clip()}
    assert clippers == {
        RenderingMode.FILL_CLIP,
        RenderingMode.STROKE_CLIP,
        RenderingMode.FILL_STROKE_CLIP,
        RenderingMode.NEITHER_CLIP,
    }


@pytest.mark.parametrize("bad", [8, 9, 99, -1, -5])
def test_from_int_out_of_range_raises_index_error(bad: int) -> None:
    # Upstream RenderingMode.fromInt does VALUES[value] → throws
    # ArrayIndexOutOfBoundsException; pypdfbox raises IndexError.
    with pytest.raises(IndexError):
        RenderingMode.from_int(bad)


# ======================================================================
# Tr operator handler — _op_set_text_rendering_mode
# ======================================================================


@pytest.mark.parametrize("mode_int", list(range(8)))
def test_tr_operator_sets_each_in_range_mode(mode_int: int) -> None:
    r = _bare_renderer()
    r._op_set_text_rendering_mode(None, [COSInteger(mode_int)])  # noqa: SLF001
    assert r._gs.text_rendering_mode == mode_int  # noqa: SLF001


def test_tr_operator_missing_operand_is_noop() -> None:
    r = _bare_renderer()
    r._gs.text_rendering_mode = 5  # noqa: SLF001
    r._op_set_text_rendering_mode(None, [])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 5  # noqa: SLF001


@pytest.mark.parametrize("bad", [8, 9, 99, 1000, -1, -5])
def test_tr_operator_out_of_range_leaves_previous_mode(bad: int) -> None:
    # Wave 1589 fix: upstream SetTextRenderingMode returns (ignores) when
    # val < 0 || val >= 8 — the previously-set mode persists, it is NOT
    # clamped to 0 / 7.
    r = _bare_renderer()
    r._gs.text_rendering_mode = 6  # noqa: SLF001
    r._op_set_text_rendering_mode(None, [COSInteger(bad)])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 6  # noqa: SLF001


def test_tr_operator_non_number_operand_dropped() -> None:
    # Upstream drops a non-COSNumber operand and leaves the mode alone.
    r = _bare_renderer()
    r._gs.text_rendering_mode = 2  # noqa: SLF001
    r._op_set_text_rendering_mode(None, [COSName.get_pdf_name("X")])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 2  # noqa: SLF001


def test_tr_operator_accepts_real_operand_truncates() -> None:
    # COSFloat 2.0 → int_value 2 (FILL_STROKE).
    r = _bare_renderer()
    r._op_set_text_rendering_mode(None, [COSFloat(2.0)])  # noqa: SLF001
    assert r._gs.text_rendering_mode == 2  # noqa: SLF001


# ======================================================================
# _paint_glyph_path fill/stroke/clip decision (rasteriser mocked)
# ======================================================================


class _Recorder:
    """Stand-in for the three glyph paint helpers; records which fired
    and the (do_fill, do_stroke) flags + fill colour passed."""

    def __init__(self) -> None:
        self.clip_calls: list[Any] = []
        self.direct_calls: list[dict[str, Any]] = []
        self.through_clip_calls: list[dict[str, Any]] = []

    def accumulate(self, path: Any, ctm: Any) -> None:
        self.clip_calls.append((path, ctm))

    def direct(self, path: Any, ctm: Any, fill_rgb: Any, *, do_fill: bool,
               do_stroke: bool) -> None:
        self.direct_calls.append(
            {"fill_rgb": fill_rgb, "do_fill": do_fill, "do_stroke": do_stroke}
        )

    def through_clip(self, path: Any, ctm: Any, fill_rgb: Any, *,
                     do_fill: bool, do_stroke: bool, clip_mask: Any) -> None:
        self.through_clip_calls.append(
            {"fill_rgb": fill_rgb, "do_fill": do_fill,
             "do_stroke": do_stroke, "clip_mask": clip_mask}
        )


def _paint_renderer(mode: int, *, clip_mask: Any = None) -> tuple[Any, _Recorder]:
    gs = _GState()
    gs.text_rendering_mode = mode
    gs.clip_mask = clip_mask
    gs.fill_rgb = (10, 20, 30)
    gs.stroke_rgb = (200, 100, 50)
    r = _bare_renderer(gs)
    rec = _Recorder()
    r._accumulate_text_clip_path = rec.accumulate  # noqa: SLF001
    r._paint_glyph_path_direct = rec.direct  # noqa: SLF001
    r._paint_glyph_path_through_clip = rec.through_clip  # noqa: SLF001
    return r, rec


@pytest.mark.parametrize("mode_int", list(range(8)))
def test_paint_decision_triple_matches_upstream(mode_int: int) -> None:
    want_fill, want_stroke, want_clip = MODE_TRIPLES[mode_int]
    r, rec = _paint_renderer(mode_int)
    # fill_rgb is the non-stroking colour passed in by the caller.
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (10, 20, 30))  # noqa: SLF001

    # Clip accumulation must happen for clip modes (4-7) and only those.
    assert (len(rec.clip_calls) == 1) is want_clip

    if not (want_fill or want_stroke):
        # Invisible (3) and clip-only (7) paint nothing.
        assert rec.direct_calls == []
        assert rec.through_clip_calls == []
    else:
        # With no GS clip mask the direct path is taken.
        assert len(rec.direct_calls) == 1
        call = rec.direct_calls[0]
        assert call["do_fill"] is want_fill
        assert call["do_stroke"] is want_stroke


def test_invisible_mode_paints_nothing() -> None:
    r, rec = _paint_renderer(3)
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert rec.direct_calls == []
    assert rec.through_clip_calls == []
    assert rec.clip_calls == []


def test_clip_only_mode_accumulates_but_paints_nothing() -> None:
    r, rec = _paint_renderer(7)
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert len(rec.clip_calls) == 1
    assert rec.direct_calls == []
    assert rec.through_clip_calls == []


def test_fill_uses_non_stroking_colour() -> None:
    # Mode 0 (fill): the colour handed to the direct paint helper is the
    # caller-supplied non-stroking RGB, never the stroking RGB.
    r, rec = _paint_renderer(0)
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (10, 20, 30))  # noqa: SLF001
    assert rec.direct_calls[0]["fill_rgb"] == (10, 20, 30)
    assert rec.direct_calls[0]["fill_rgb"] != (200, 100, 50)


def test_stroke_only_mode_does_not_fill() -> None:
    r, rec = _paint_renderer(1)
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (10, 20, 30))  # noqa: SLF001
    assert rec.direct_calls[0]["do_fill"] is False
    assert rec.direct_calls[0]["do_stroke"] is True


@pytest.mark.parametrize("mode_int", [4, 5, 6])
def test_visible_clip_modes_both_paint_and_clip(mode_int: int) -> None:
    want_fill, want_stroke, _ = MODE_TRIPLES[mode_int]
    r, rec = _paint_renderer(mode_int)
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (10, 20, 30))  # noqa: SLF001
    assert len(rec.clip_calls) == 1  # added to clip path
    assert len(rec.direct_calls) == 1  # and painted
    assert rec.direct_calls[0]["do_fill"] is want_fill
    assert rec.direct_calls[0]["do_stroke"] is want_stroke


@pytest.mark.parametrize("mode_int", [0, 1, 2])
def test_paint_through_clip_when_gs_clip_active(mode_int: int) -> None:
    # A non-None GS clip mask routes painting through the clip-composite
    # helper instead of the direct helper, preserving the decision triple.
    want_fill, want_stroke, _ = MODE_TRIPLES[mode_int]
    sentinel_mask = object()
    r, rec = _paint_renderer(mode_int, clip_mask=sentinel_mask)
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (10, 20, 30))  # noqa: SLF001
    assert rec.direct_calls == []
    assert len(rec.through_clip_calls) == 1
    call = rec.through_clip_calls[0]
    assert call["do_fill"] is want_fill
    assert call["do_stroke"] is want_stroke
    assert call["clip_mask"] is sentinel_mask


# ======================================================================
# Text-clip accumulation across glyphs + ET application
# ======================================================================


def test_clip_path_accumulates_across_glyphs_then_resets_at_et() -> None:
    # In a clip mode, each shown glyph adds to _text_clip_paths; ET
    # commits the union and clears the buffer (PDF 32000-1 §9.3.6 — the
    # clip is established at the end of the text object).
    r, rec = _paint_renderer(7)
    r._text_clip_paths = []  # noqa: SLF001

    # Re-route accumulate to actually append (simulate real behaviour).
    def _append(path: Any, ctm: Any) -> None:
        r._text_clip_paths.append(path)  # noqa: SLF001

    r._accumulate_text_clip_path = _append  # noqa: SLF001

    for _ in range(4):
        r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert len(r._text_clip_paths) == 4  # noqa: SLF001

    # ET clears the buffer. _commit_text_clip needs an image; stub it.
    committed: list[bool] = []
    r._commit_text_clip = lambda: committed.append(True)  # noqa: SLF001
    r._maybe_end_text_knockout = lambda: None  # noqa: SLF001
    r._op_end_text(None, [])  # noqa: SLF001
    assert committed == [True]
    assert r._text_clip_paths == []  # noqa: SLF001


def test_non_clip_mode_does_not_accumulate_clip_path() -> None:
    r, rec = _paint_renderer(0)
    r._text_clip_paths = []  # noqa: SLF001

    def _append(path: Any, ctm: Any) -> None:  # pragma: no cover
        r._text_clip_paths.append(path)  # noqa: SLF001

    r._accumulate_text_clip_path = _append  # noqa: SLF001
    r._paint_glyph_path(object(), (1, 0, 0, 1, 0, 0), (0, 0, 0))  # noqa: SLF001
    assert r._text_clip_paths == []  # noqa: SLF001


def test_et_without_clip_glyphs_does_not_commit() -> None:
    # No clip-mode glyph was shown → no text-clip buffer → ET commits
    # nothing (the clip is unchanged).
    r, rec = _paint_renderer(0)
    r._text_clip_paths = []  # noqa: SLF001
    committed: list[bool] = []
    r._commit_text_clip = lambda: committed.append(True)  # noqa: SLF001
    r._maybe_end_text_knockout = lambda: None  # noqa: SLF001
    r._op_end_text(None, [])  # noqa: SLF001
    assert committed == []
