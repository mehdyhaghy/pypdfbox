"""Wave 1593 — fuzz the dashed-stroke *geometry* generation in the renderer.

Where the dash model + the all-zero / empty guards were covered by earlier
waves, this module hammers the on/off **segment geometry** applied during a
stroke: how a dash array + phase + CTM scale turn a stroked path into a run of
painted (on) and unpainted (off) intervals.

Architecture note — pypdfbox delegates the on/off segment generation to skia's
``DashPathEffect`` (via :mod:`pypdfbox.rendering._aggdraw_compat`), the same as
upstream Apache PDFBox delegates it to ``java.awt.BasicStroke``'s dash array.
There is therefore no pure-Python "segment list" to assert on directly; the
observable segment geometry is the *rasterised* run of on/off pixel intervals
along the stroked line. These tests reconstruct that run from a 72-DPI render
and assert the segment lengths / phase offset / scaling, which is exactly the
behaviour upstream's ``PageDrawer.getStroke`` produces.

Behaviours exercised (cf. PDF 32000-1 §8.4.3.6 + ``BasicStroke`` dash rules):

* a solid line (no dash) → one continuous segment;
* ``[3 3]`` → equal on/off segments along a horizontal line;
* a phase offset shifting where the first dash starts;
* the dash array scaled by the CTM (a 2x CTM doubles the dash lengths);
* a ``[5 2]`` asymmetric dash;
* an odd-length dash array (``[3]`` repeats → 3-on 3-off);
* a phase larger than the pattern period (wraps);
* the dash applied to a multi-segment path (pattern restarts per subpath);
* the ``_make_stroke_paint_from_pen`` odd-length duplication helper directly.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

_PAGE = 120.0  # square page == px at 72 DPI


# ---------------------------------------------------------------------------
# render helpers
# ---------------------------------------------------------------------------


def _render(content: str):
    """Render a one-page PDF whose content stream is ``content`` at 72 DPI."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(content.encode("ascii"))
    page.get_cos_object().set_item(COSName.CONTENTS, stream)

    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        doc.save(path)
        doc.close()
        reopened = PDDocument.load(path)
        try:
            return PDFRenderer(reopened).render_image_with_dpi(0, 72.0)
        finally:
            reopened.close()
    finally:
        os.unlink(path)


def _on_mask(img, y: int) -> list[bool]:
    """Boolean ON/OFF mask of the stroke row at device ``y`` (True == inked)."""
    gray = img.convert("L")
    pixels = gray.load()
    width, _height = gray.size
    return [pixels[x, y] < 128 for x in range(width)]


def _runs(mask: list[bool]) -> list[tuple[bool, int]]:
    """Run-length encode ``mask`` into ``(is_on, length)`` segments."""
    out: list[tuple[bool, int]] = []
    for value in mask:
        if out and out[-1][0] == value:
            out[-1] = (value, out[-1][1] + 1)
        else:
            out.append((value, 1))
    return out


def _on_runs(mask: list[bool]) -> list[tuple[int, int]]:
    """``(start_x, length)`` of every inked (on) run in ``mask``."""
    out: list[tuple[int, int]] = []
    x = 0
    for value, length in _runs(mask):
        if value:
            out.append((x, length))
        x += length
    return out


def _interior_on_runs(mask: list[bool], lo: int, hi: int) -> list[int]:
    """Lengths of on-runs that lie wholly inside ``[lo, hi]`` (avoids the
    butt-cap end runs at the very start/end of the painted line, whose length
    is clipped by the line endpoints rather than the dash rhythm)."""
    return [
        length
        for start, length in _on_runs(mask)
        if start > lo and start + length < hi
    ]


# A 4 user-unit pen at 72 DPI is 4 px wide. The horizontal lines below sit at
# the row y == _Y so that the rendered band is centred on a single device row.
_Y_DEV = int(_PAGE - 60.0)  # PDF y=60 → device row 60 (origin flip)


# ---------------------------------------------------------------------------
# solid line — one continuous segment
# ---------------------------------------------------------------------------


def test_solid_line_is_one_continuous_segment() -> None:
    """No dash operator → a single uninterrupted on-run across the line."""
    img = _render("4 w 0 0 0 RG 10 60 m 110 60 l S")
    runs = _on_runs(_on_mask(img, _Y_DEV))
    assert len(runs) == 1, f"solid line broke into {len(runs)} runs: {runs}"
    start, length = runs[0]
    assert length >= 95  # ~100 px line, butt caps


def test_empty_dash_array_is_solid() -> None:
    """``[] 0 d`` is the spec default (solid) → one continuous segment."""
    img = _render("4 w 0 0 0 RG [] 0 d 10 60 m 110 60 l S")
    assert len(_on_runs(_on_mask(img, _Y_DEV))) == 1


# ---------------------------------------------------------------------------
# [3 3] symmetric dash — equal on/off segments
# ---------------------------------------------------------------------------


def test_symmetric_dash_alternates_equal_on_off() -> None:
    """``[6 6] 0 d`` → roughly equal on/off segments (6 px on, 6 px off)."""
    img = _render("4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l S")
    mask = _on_mask(img, _Y_DEV)
    on_lengths = _interior_on_runs(mask, 2, 118)
    assert len(on_lengths) >= 3, f"expected multiple dashes, got {on_lengths}"
    # Each interior on-run is ~6 px (allow ±2 for AA threshold rounding).
    for length in on_lengths:
        assert 4 <= length <= 8, f"on-run {length} not ~6 px: {on_lengths}"


def test_symmetric_dash_starts_on() -> None:
    """Phase 0 → the pattern begins with the on-segment at the line origin."""
    img = _render("4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l S")
    mask = _on_mask(img, _Y_DEV)
    # The first inked pixel is at x == 0 (the line starts on an on-segment).
    assert mask[0] is True
    first_run = _runs(mask)[0]
    assert first_run[0] is True


# ---------------------------------------------------------------------------
# phase offset — shifts where the first dash starts
# ---------------------------------------------------------------------------


def test_phase_offset_starts_in_a_gap() -> None:
    """``[6 6] 6 d`` → phase 6 lands exactly on the start of the off-segment,
    so the line origin is *blank* (the first 6 units are a gap)."""
    img = _render("4 w 0 0 0 RG [6 6] 6 d 0 60 m 120 60 l S")
    mask = _on_mask(img, _Y_DEV)
    # First few pixels are in the leading gap → off.
    assert mask[0] is False
    first_run = _runs(mask)[0]
    assert first_run[0] is False
    assert 4 <= first_run[1] <= 8


def test_phase_shifts_dash_positions() -> None:
    """A non-zero phase moves the on-runs vs phase 0 (the operand is applied)."""
    zero = _on_mask(_render("4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l S"), _Y_DEV)
    six = _on_mask(_render("4 w 0 0 0 RG [6 6] 6 d 0 60 m 120 60 l S"), _Y_DEV)
    differing = sum(1 for a, b in zip(zero, six, strict=True) if a != b)
    assert differing >= 20, (
        f"phase=0 and phase=6 renders barely differ ({differing} px) — "
        "the phase operand appears ignored at stroke time"
    )


def test_partial_phase_yields_short_leading_dash() -> None:
    """``[10 5] 3 d`` → phase 3 consumes the first 3 units of the on-segment,
    so the leading on-run is the trailing ~7 units of a dash, then a gap."""
    img = _render("4 w 0 0 0 RG [10 5] 3 d 0 60 m 120 60 l S")
    runs = _runs(_on_mask(img, _Y_DEV))
    assert runs[0][0] is True  # still starts on (3 < 10)
    assert 5 <= runs[0][1] <= 9  # ~7 px leading dash
    assert runs[1][0] is False  # then the gap


# ---------------------------------------------------------------------------
# CTM scaling — a 2x CTM doubles the dash lengths
# ---------------------------------------------------------------------------


def test_ctm_scale_doubles_dash_lengths() -> None:
    """Under a 2x CTM the same ``[6 6]`` pattern paints ~12 px on/off runs."""
    plain = _interior_on_runs(
        _on_mask(_render("4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l S"), _Y_DEV),
        2,
        118,
    )
    scaled = _interior_on_runs(
        _on_mask(
            _render(
                "2 0 0 2 0 0 cm 2 w 0 0 0 RG [6 6] 0 d 0 30 m 60 30 l S"
            ),
            _Y_DEV,
        ),
        2,
        118,
    )
    plain_avg = sum(plain) / len(plain)
    scaled_avg = sum(scaled) / len(scaled)
    assert plain_avg == pytest.approx(6, abs=2)
    assert scaled_avg == pytest.approx(12, abs=3)
    assert scaled_avg > plain_avg + 3, (
        f"2x CTM did not lengthen the dashes: plain={plain_avg:.1f} "
        f"scaled={scaled_avg:.1f}"
    )


def test_ctm_scale_phase_scaled_too() -> None:
    """The phase is scaled by the same factor as the array: a phase of 6 at 2x
    behaves like a phase of 12 in device space (still starts in a gap for the
    ``[6 6]`` pattern whose scaled period is 12 on / 12 off)."""
    img = _render("2 0 0 2 0 0 cm 2 w 0 0 0 RG [6 6] 6 d 0 30 m 60 30 l S")
    mask = _on_mask(img, _Y_DEV)
    # phase 6 → device phase 12 == one full scaled on-segment → line origin is
    # the start of the scaled off-segment → blank at x == 0.
    assert mask[0] is False


# ---------------------------------------------------------------------------
# [5 2] asymmetric dash
# ---------------------------------------------------------------------------


def test_asymmetric_dash_on_longer_than_off() -> None:
    """``[10 4] 0 d`` → on-runs (~10 px) longer than off-runs (~4 px)."""
    img = _render("4 w 0 0 0 RG [10 4] 0 d 0 60 m 120 60 l S")
    runs = _runs(_on_mask(img, _Y_DEV))
    on_lengths = [length for value, length in runs if value]
    off_lengths = [length for value, length in runs if not value]
    # Drop the trailing partial run; compare interior medians.
    interior_on = sorted(on_lengths)[len(on_lengths) // 2]
    interior_off = sorted(off_lengths)[len(off_lengths) // 2]
    assert interior_on > interior_off, (
        f"asymmetric [10 4] did not produce longer on than off: "
        f"on={on_lengths} off={off_lengths}"
    )


# ---------------------------------------------------------------------------
# odd-length dash array — repeats so [3] means 3-on 3-off
# ---------------------------------------------------------------------------


def test_odd_length_array_repeats_as_on_off() -> None:
    """``[6] 0 d`` (single element) → the array repeats so it means 6-on /
    6-off, identical to ``[6 6] 0 d``."""
    single = _on_mask(_render("4 w 0 0 0 RG [6] 0 d 0 60 m 120 60 l S"), _Y_DEV)
    pair = _on_mask(_render("4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l S"), _Y_DEV)
    assert single == pair, "[6] did not behave like [6 6] (odd-length repeat)"


def test_odd_length_array_produces_dashes() -> None:
    """Sanity: ``[8] 0 d`` actually breaks the line into multiple on-runs."""
    img = _render("4 w 0 0 0 RG [8] 0 d 0 60 m 120 60 l S")
    on_runs = _on_runs(_on_mask(img, _Y_DEV))
    assert len(on_runs) >= 3, f"odd-length dash stayed mostly solid: {on_runs}"


# ---------------------------------------------------------------------------
# phase larger than the pattern period — wraps
# ---------------------------------------------------------------------------


def test_phase_larger_than_period_wraps() -> None:
    """A phase larger than the pattern period wraps modulo the period: for
    ``[6 6]`` (period 12) phase 18 ≡ phase 6, so it renders like phase 6."""
    big = _on_mask(_render("4 w 0 0 0 RG [6 6] 18 d 0 60 m 120 60 l S"), _Y_DEV)
    six = _on_mask(_render("4 w 0 0 0 RG [6 6] 6 d 0 60 m 120 60 l S"), _Y_DEV)
    assert big == six, "phase 18 did not wrap to phase 6 (period 12)"


def test_phase_full_period_equals_zero() -> None:
    """Phase == one full period (12 for ``[6 6]``) ≡ phase 0."""
    full = _on_mask(_render("4 w 0 0 0 RG [6 6] 12 d 0 60 m 120 60 l S"), _Y_DEV)
    zero = _on_mask(_render("4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l S"), _Y_DEV)
    assert full == zero, "phase 12 (full period) did not equal phase 0"


# ---------------------------------------------------------------------------
# multi-segment path — pattern restarts per subpath
# ---------------------------------------------------------------------------


def test_dash_restarts_each_subpath() -> None:
    """The dash pattern restarts at the start of each subpath (PDF spec): two
    identical horizontal subpaths at different y get the same dash phase, so
    their on/off masks match."""
    content = (
        "4 w 0 0 0 RG [6 6] 0 d "
        "0 60 m 120 60 l S "
        "0 30 m 120 30 l S"
    )
    img = _render(content)
    top = _on_mask(img, _Y_DEV)            # y == 60 → device row 60
    bottom = _on_mask(img, int(_PAGE - 30.0))  # y == 30 → device row 90
    assert top == bottom, (
        "dash pattern did not restart per subpath — the two parallel lines "
        "have different on/off geometry"
    )


def test_dash_applied_to_each_segment_of_polyline() -> None:
    """A polyline (multiple connected ``l`` segments in one subpath) gets the
    dash applied continuously, not reset at each vertex — the horizontal leg
    is broken into multiple dashes."""
    content = "4 w 0 0 0 RG [6 6] 0 d 0 60 m 120 60 l 120 90 l S"
    img = _render(content)
    on_runs = _on_runs(_on_mask(img, _Y_DEV))
    assert len(on_runs) >= 3, f"polyline leg was not dashed: {on_runs}"


# ---------------------------------------------------------------------------
# line cap interaction with each dash segment
# ---------------------------------------------------------------------------


def test_round_cap_extends_each_dash() -> None:
    """A round cap (``1 J``) extends each dash by half the pen width at both
    ends, so the on-runs are longer than under the default butt cap."""
    butt = _interior_on_runs(
        _on_mask(_render("8 w 0 0 0 RG [10 10] 0 d 0 60 m 120 60 l S"), _Y_DEV),
        2,
        118,
    )
    round_cap = _interior_on_runs(
        _on_mask(
            _render("8 w 1 J 0 0 0 RG [10 10] 0 d 0 60 m 120 60 l S"), _Y_DEV
        ),
        2,
        118,
    )
    assert butt and round_cap
    butt_avg = sum(butt) / len(butt)
    round_avg = sum(round_cap) / len(round_cap)
    assert round_avg > butt_avg, (
        f"round cap did not extend dashes: butt={butt_avg:.1f} "
        f"round={round_avg:.1f}"
    )


# ---------------------------------------------------------------------------
# low-level: _make_stroke_paint_from_pen odd-length duplication
# ---------------------------------------------------------------------------


def _draw_module():
    from pypdfbox.rendering import _aggdraw_compat

    return _aggdraw_compat


def _make_draw():
    from PIL import Image

    mod = _draw_module()
    return mod, mod.Draw(Image.new("RGB", (10, 10), (255, 255, 255)))


def test_make_stroke_paint_odd_length_duplicated() -> None:
    """``_make_stroke_paint_from_pen`` duplicates an odd-length interval array
    (``[3] -> [3, 3]``) so skia (which requires an even count) realises the PDF
    single-element "same length for gaps" rule. The paint is built without
    error and carries a path effect."""
    mod, draw = _make_draw()
    pen = mod.Pen((0, 0, 0), width=2.0, dash=((3.0,), 0.0))
    paint = draw._make_stroke_paint_from_pen(pen)  # noqa: SLF001
    assert paint.getPathEffect() is not None


def test_make_stroke_paint_even_length_kept() -> None:
    """An even-length array keeps its dash effect too (no duplication needed)."""
    mod, draw = _make_draw()
    pen = mod.Pen((0, 0, 0), width=2.0, dash=((5.0, 2.0), 1.0))
    paint = draw._make_stroke_paint_from_pen(pen)  # noqa: SLF001
    assert paint.getPathEffect() is not None


def test_make_stroke_paint_all_zero_skips_effect() -> None:
    """An all-zero / sum<=0 interval array produces no path effect (the line
    stays solid rather than vanishing into a degenerate dash)."""
    mod, draw = _make_draw()
    pen = mod.Pen((0, 0, 0), width=2.0, dash=((0.0, 0.0), 0.0))
    paint = draw._make_stroke_paint_from_pen(pen)  # noqa: SLF001
    assert paint.getPathEffect() is None


def test_make_stroke_paint_no_dash_no_effect() -> None:
    """A pen with ``dash=None`` produces a solid stroke (no path effect)."""
    mod, draw = _make_draw()
    pen = mod.Pen((0, 0, 0), width=2.0)
    paint = draw._make_stroke_paint_from_pen(pen)  # noqa: SLF001
    assert paint.getPathEffect() is None


# ---------------------------------------------------------------------------
# parametrised period sweep — every period produces alternating geometry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dash", "ident"),
    [
        ("4 4", "4_4"),
        ("8 8", "8_8"),
        ("10 5", "10_5"),
        ("5 10", "5_10"),
        ("12 3", "12_3"),
        ("3 12", "3_12"),
        ("2 2", "2_2"),
        ("15 5", "15_5"),
    ],
    ids=[
        "4_4",
        "8_8",
        "10_5",
        "5_10",
        "12_3",
        "3_12",
        "2_2",
        "15_5",
    ],
)
def test_dash_period_sweep_alternates(dash: str, ident: str) -> None:
    """Every reasonable dash period breaks a long line into alternating on/off
    runs (more than one on-run), i.e. the geometry is actually segmented."""
    img = _render(f"4 w 0 0 0 RG [{dash}] 0 d 0 60 m 120 60 l S")
    on_runs = _on_runs(_on_mask(img, _Y_DEV))
    assert len(on_runs) >= 2, f"[{dash}] did not segment the line: {on_runs}"


@pytest.mark.parametrize(
    ("phase", "ident"),
    [
        (0.0, "p0"),
        (3.0, "p3"),
        (6.0, "p6"),
        (9.0, "p9"),
        (12.0, "p12"),
        (15.0, "p15"),
    ],
    ids=["p0", "p3", "p6", "p9", "p12", "p15"],
)
def test_phase_sweep_consistent(phase: float, ident: str) -> None:
    """A phase sweep over the ``[6 6]`` pattern (period 12): phase p and p+12
    render identically (the pattern is periodic), and every render still
    produces a dashed (multi-run) line."""
    base = _on_mask(
        _render(f"4 w 0 0 0 RG [6 6] {phase} d 0 60 m 120 60 l S"), _Y_DEV
    )
    wrapped = _on_mask(
        _render(f"4 w 0 0 0 RG [6 6] {phase + 12.0} d 0 60 m 120 60 l S"),
        _Y_DEV,
    )
    assert base == wrapped, f"phase {phase} != phase {phase + 12} (period 12)"
    assert len(_on_runs(base)) >= 2
