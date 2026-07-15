"""Correctness + parity tests for the spatial-grid duplicate-overlap
suppressor (wave 1601 perf fix).

The suppression *decision* must be byte-for-byte identical to the former
O(n^2) linear scan for every input, so these tests pin the grid output
against a verbatim reconstruction of the pre-fix algorithm across randomized
and tolerance-boundary layouts, and confirm the ``has_contents()`` page gate
extracts identically to the old ``get_contents()`` truthiness check.
"""

from __future__ import annotations

import io
import math
import random

from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.text_position import TextPosition


def _reference_drop(positions):
    """Verbatim pre-fix O(n^2) linear-scan suppressor (the oracle)."""
    result = []
    seen: dict = {}
    for pos in positions:
        if pos.from_actual_text:
            result.append(pos)
            continue
        text = pos.text
        char_count = len(text)
        if pos.width > 0.0:
            tol = math.inf if char_count == 0 else pos.width / char_count / 3.0
        elif char_count == 0:
            tol = math.nan
        else:
            tol = max(pos.font_size, 0.1) * 0.25
        same_text = seen.setdefault(text, {})
        suppress = False
        x_lo = pos.x - tol
        x_hi = pos.x + tol
        y_lo = pos.y - tol
        y_hi = pos.y + tol
        for x_key, y_values in same_text.items():
            if x_lo <= x_key < x_hi and any(
                y_lo <= y_val < y_hi for y_val in y_values
            ):
                suppress = True
                break
        if not suppress:
            same_text.setdefault(pos.x, []).append(pos.y)
            result.append(pos)
    return result


def _pos(x, y, text=".", width=6.0, font_size=12.0, from_actual_text=False):
    p = TextPosition(
        text=text,
        x=float(x),
        y=float(y),
        font_size=font_size,
        font_size_in_pt=font_size,
        font_name="F",
        font=None,
        resolved_font_name="F",
        width=width,
        width_of_space=3.0,
        char_spacing=0.0,
        word_spacing=0.0,
        dir=0.0,
        height=font_size,
        text_matrix=[1, 0, 0, 1, float(x), float(y)],
    )
    p.from_actual_text = from_actual_text
    return p


def _assert_same_decision(positions):
    ref = _reference_drop(list(positions))
    got = PDFTextStripper._drop_overlapping_duplicates(list(positions))
    # Identity list must match exactly (same runs kept, same order).
    assert [id(p) for p in got] == [id(p) for p in ref]


def test_grid_matches_linear_scan_randomized():
    rng = random.Random(20260714)
    for _ in range(60):
        n = rng.randint(1, 400)
        positions = []
        for _ in range(n):
            # Small coordinate space so overlaps + near-boundary hits are common.
            x = rng.randint(0, 40) * 1.0
            y = rng.randint(0, 40) * 1.0
            text = rng.choice([".", "o", "ab", "x"])
            width = rng.choice([6.0, 3.0, 12.0])
            positions.append(_pos(x, y, text=text, width=width))
        _assert_same_decision(positions)


def test_grid_near_tolerance_boundary():
    # tol = width/len/3 = 6/1/3 = 2.0 exactly. Probe origins at exactly
    # +/- tol (half-open: -tol matches, +tol does not) and just inside/outside.
    base = _pos(100.0, 100.0)
    tol = 2.0
    eps = 1e-9
    cases = [
        _pos(100.0 - tol, 100.0),       # exactly x_lo -> inclusive -> match
        _pos(100.0 + tol, 100.0),       # exactly x_hi -> exclusive -> no match
        _pos(100.0 + tol - eps, 100.0),  # just inside high edge -> match
        _pos(100.0, 100.0 - tol),       # exactly y_lo -> inclusive
        _pos(100.0, 100.0 + tol),       # exactly y_hi -> exclusive
        _pos(100.0 - tol, 100.0 - tol),  # corner, both inclusive
        _pos(100.0 + tol, 100.0 + tol),  # corner, both exclusive
    ]
    for probe in cases:
        _assert_same_decision([base, probe])
        # Also the reverse order (probe recorded first).
        _assert_same_decision([probe, base])


def test_grid_all_distinct_same_text_none_suppressed():
    # Origins spaced beyond tol -> every run kept; grid must keep all.
    positions = [_pos(i * 5.0, 100.0) for i in range(500)]
    got = PDFTextStripper._drop_overlapping_duplicates(list(positions))
    assert len(got) == 500
    _assert_same_decision(positions)


def test_grid_heavy_overlap_collapses():
    # Many stamps within tol of 3 origins -> collapses to 3 kept runs.
    positions = []
    for i in range(600):
        base = (i % 3) * 50.0
        positions.append(_pos(base + (i % 2) * 0.0005, 100.0))
    got = PDFTextStripper._drop_overlapping_duplicates(list(positions))
    assert len(got) == 3
    _assert_same_decision(positions)


def test_grid_empty_text_and_zero_width_edges():
    # Empty text: width>0 -> tol=inf (any earlier empty-text run suppresses);
    # width==0 -> tol=NaN (never suppresses, always recorded).
    positions = [
        _pos(10.0, 10.0, text="", width=5.0),
        _pos(999.0, 999.0, text="", width=5.0),   # inf tol -> suppressed by first
        _pos(20.0, 20.0, text="", width=0.0),      # NaN tol -> kept
        _pos(20.0, 20.0, text="", width=0.0),      # NaN tol -> kept again
    ]
    _assert_same_decision(positions)


def test_grid_zero_width_nonempty_fallback_tol():
    # width<=0, non-empty text -> lite fallback tol = max(font_size,0.1)*0.25.
    positions = [
        _pos(50.0, 50.0, text="o", width=0.0, font_size=12.0),
        _pos(51.0, 50.0, text="o", width=0.0, font_size=12.0),   # within 3.0
        _pos(70.0, 50.0, text="o", width=0.0, font_size=12.0),   # outside
    ]
    _assert_same_decision(positions)


def test_grid_actual_text_bypass():
    # from_actual_text runs bypass the filter entirely and are never recorded.
    positions = [
        _pos(10.0, 10.0, text="A", from_actual_text=True),
        _pos(10.0, 10.0, text="A", from_actual_text=True),   # both kept
        _pos(10.0, 10.0, text="A"),                          # kept (no prior record)
        _pos(10.0, 10.0, text="A"),                          # suppressed by the 3rd
    ]
    got = PDFTextStripper._drop_overlapping_duplicates(list(positions))
    assert [id(p) for p in got] == [id(positions[i]) for i in (0, 1, 2)]
    _assert_same_decision(positions)


def test_grid_varying_tol_same_text():
    # Same text but widely varying width -> varying tol; exercises the
    # grow-neighbourhood / degenerate-fallback branches. Must still match.
    rng = random.Random(1234)
    positions = []
    for _ in range(300):
        x = rng.randint(0, 100) * 1.0
        y = rng.randint(0, 5) * 1.0
        width = rng.choice([0.5, 6.0, 60.0, 600.0])
        positions.append(_pos(x, y, text="z", width=width))
    _assert_same_decision(positions)


# ---- Fix 1: has_contents() page gate extracts identically ----


def _extract(doc):
    return PDFTextStripper().get_text(doc)


def test_multi_stream_contents_array_extracts():
    # A page whose /Contents is an array of two streams must extract the
    # concatenation, exactly as the old get_contents()-truthiness gate did.
    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    font = PDType1Font()
    cs1 = PDPageContentStream(doc, page)
    cs1.begin_text()
    cs1.set_font(font, 12)
    cs1.new_line_at_offset(50, 700)
    cs1.show_text("Hello")
    cs1.end_text()
    cs1.close()
    # Append a second content stream (array form).
    cs2 = PDPageContentStream(doc, page, "APPEND", True, True)
    cs2.begin_text()
    cs2.set_font(font, 12)
    cs2.new_line_at_offset(50, 680)
    cs2.show_text("World")
    cs2.end_text()
    cs2.close()

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    reloaded = PDDocument.load(buf.getvalue())
    try:
        text = _extract(reloaded)
    finally:
        reloaded.close()
    assert "Hello" in text
    assert "World" in text


def test_blank_page_no_contents_extracts_empty():
    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        text = _extract(doc)
    finally:
        doc.close()
    # A page with no /Contents contributes no visible text (empty-article wrap
    # is invisible under default markers).
    assert text.strip() == ""
