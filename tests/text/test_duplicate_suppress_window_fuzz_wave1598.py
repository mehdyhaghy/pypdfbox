"""Wave 1598 — duplicate-overlapping-text suppression window fuzz.

Hammers the ``suppressDuplicateOverlappingText`` filter of
``PDFTextStripper.processTextPosition`` (PDFBox 3.0.7), which pypdfbox's
lite stripper applies in ``_drop_overlapping_duplicates``:

  * the dedup map is PAGE-global (upstream ``characterListMapping``,
    cleared per page) — a re-paint anywhere later in the page's content
    stream is suppressed, not just one painted immediately after its
    original (wave 1598 fixed a trailing-4-runs window here);
  * ``tolerance = width / len(text) / 3`` on BOTH axes (upstream reuses
    the same ``tolerance`` for the x ``subMap`` and the y ``subSet``;
    the old lite code used ``0.05 × font_size`` on y — also fixed);
  * the window is half-open ``[v - tol, v + tol)`` (Java's two-argument
    ``TreeMap.subMap`` / ``TreeSet.subSet`` are from-inclusive,
    to-exclusive);
  * only a SHOWN run records its origin — a suppressed run never extends
    the map, so near-duplicates cannot chain-suppress a drifting run;
  * glyphs emitted inside an ``/ActualText`` span bypass the filter
    entirely (upstream guards the block with ``this.actualText == null``)
    and are never recorded;
  * empty decoded text mirrors Java float arithmetic — ``width / 0`` is
    ``+Infinity`` (any earlier empty-text run suppresses) and ``0 / 0``
    is ``NaN`` (nothing ever matches).

The live-oracle section diffs full ``getText`` output against Apache
PDFBox 3.0.7 over probe-built fixtures (DuplicateSuppressWindowProbe).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _tp(
    text: str,
    x: float,
    y: float,
    *,
    width: float = 0.0,
    font_size: float = 12.0,
    from_actual_text: bool = False,
) -> TextPosition:
    return TextPosition(
        text=text,
        x=x,
        y=y,
        font_size=font_size,
        width=width,
        from_actual_text=from_actual_text,
    )


def _dedup(positions: list[TextPosition]) -> list[str]:
    """Run the filter and project the survivors to ``"text@x,y"`` labels."""
    kept = PDFTextStripper._drop_overlapping_duplicates(positions)
    return [f"{p.text}@{p.x:g},{p.y:g}" for p in kept]


def _page(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _text(content: bytes, *, suppress: bool = True, sort: bool = False) -> str:
    doc = PDDocument()
    _page(doc, content)
    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(suppress)
    if sort:
        s.set_sort_by_position(True)
    try:
        return s.get_text(doc)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# tolerance formula: width / len(text) / 3, same on both axes
# ---------------------------------------------------------------------------


def test_single_char_inside_x_tolerance_suppressed() -> None:
    # width 30, one char -> tol 10; dx 9.9 is inside the window.
    out = _dedup([_tp("X", 0.0, 0.0, width=30.0), _tp("X", 9.9, 0.0, width=30.0)])
    assert out == ["X@0,0"]


def test_single_char_outside_x_tolerance_kept() -> None:
    out = _dedup([_tp("X", 0.0, 0.0, width=30.0), _tp("X", 10.5, 0.0, width=30.0)])
    assert out == ["X@0,0", "X@10.5,0"]


def test_half_open_window_lower_bound_inclusive() -> None:
    # Prior origin exactly at new_x - tol matches (subMap fromInclusive).
    out = _dedup([_tp("X", 0.0, 0.0, width=30.0), _tp("X", 10.0, 0.0, width=30.0)])
    assert out == ["X@0,0"]


def test_half_open_window_upper_bound_exclusive() -> None:
    # Prior origin exactly at new_x + tol does NOT match (subMap toExclusive).
    out = _dedup([_tp("X", 20.0, 0.0, width=30.0), _tp("X", 10.0, 0.0, width=30.0)])
    assert out == ["X@20,0", "X@10,0"]


def test_multi_char_run_divides_tolerance_by_length() -> None:
    # "abc" width 30 -> tol 30/3/3 = 10/3 ~ 3.33: dy 3 in, dy 4 out.
    out = _dedup(
        [
            _tp("abc", 0.0, 0.0, width=30.0),
            _tp("abc", 0.0, 3.0, width=30.0),
            _tp("abc", 0.0, 4.0, width=30.0),
        ]
    )
    assert out == ["abc@0,0", "abc@0,4"]


def test_y_axis_uses_same_tolerance_as_x() -> None:
    # Regression pin for the old lite 0.05*font_size y window: width 30,
    # one char -> tol 10 on y too, so dy 9 is a duplicate even though it is
    # far beyond 0.05 * 12 = 0.6.
    out = _dedup([_tp("X", 0.0, 0.0, width=30.0), _tp("X", 0.0, 9.0, width=30.0)])
    assert out == ["X@0,0"]


def test_diagonal_offset_within_both_axes_suppressed() -> None:
    out = _dedup([_tp("X", 0.0, 0.0, width=30.0), _tp("X", 6.0, -6.0, width=30.0)])
    assert out == ["X@0,0"]


def test_offset_inside_x_but_outside_y_kept() -> None:
    out = _dedup([_tp("X", 0.0, 0.0, width=30.0), _tp("X", 6.0, 11.0, width=30.0)])
    assert out == ["X@0,0", "X@6,11"]


# ---------------------------------------------------------------------------
# page-global map (no trailing window)
# ---------------------------------------------------------------------------


def test_duplicate_far_behind_in_stream_order_is_suppressed() -> None:
    # 20 unrelated runs between the original and its re-paint: a trailing
    # window misses this; upstream's page-global characterListMapping does not.
    positions = [_tp("dup", 100.0, 500.0, width=30.0)]
    positions += [
        _tp(f"w{i}", 100.0 + 40.0 * i, 400.0, width=30.0) for i in range(20)
    ]
    positions.append(_tp("dup", 100.4, 500.3, width=30.0))
    out = _dedup(positions)
    assert out[0] == "dup@100,500"
    assert len(out) == 21  # 1 original + 20 fillers; the re-paint is gone
    assert "dup@100.4,500.3" not in out


def test_every_word_of_double_painted_block_suppressed() -> None:
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
    first = [_tp(w, 72.0 + 80.0 * i, 700.0, width=45.0) for i, w in enumerate(words)]
    second = [_tp(w, 72.3 + 80.0 * i, 700.2, width=45.0) for i, w in enumerate(words)]
    out = _dedup(first + second)
    assert out == [f"{w}@{72 + 80 * i:g},700" for i, w in enumerate(words)]


def test_dedup_map_keyed_by_exact_text() -> None:
    # Different text at the same origin is never a duplicate; the key is the
    # decoded string, case-sensitively.
    out = _dedup(
        [
            _tp("X", 0.0, 0.0, width=30.0),
            _tp("Y", 0.0, 0.0, width=30.0),
            _tp("x", 0.0, 0.0, width=30.0),
        ]
    )
    assert out == ["X@0,0", "Y@0,0", "x@0,0"]


def test_suppressed_run_does_not_extend_the_map() -> None:
    # R2 duplicates R1 and is dropped; R3 sits within tolerance of R2 but
    # NOT of R1 — upstream records origins only for shown characters, so R3
    # survives (no chain suppression through a dropped run).
    out = _dedup(
        [
            _tp("X", 0.0, 0.0, width=30.0),
            _tp("X", 9.0, 0.0, width=30.0),
            _tp("X", 18.0, 0.0, width=30.0),
        ]
    )
    assert out == ["X@0,0", "X@18,0"]


def test_kept_runs_all_recorded_as_anchors() -> None:
    # Two distinct kept origins; a third run near EITHER anchor is dropped.
    out = _dedup(
        [
            _tp("X", 0.0, 0.0, width=30.0),
            _tp("X", 50.0, 0.0, width=30.0),
            _tp("X", 50.5, 0.2, width=30.0),
            _tp("X", 0.5, 0.2, width=30.0),
        ]
    )
    assert out == ["X@0,0", "X@50,0"]


def test_order_of_survivors_is_input_order() -> None:
    positions = [
        _tp("b", 100.0, 0.0, width=30.0),
        _tp("a", 0.0, 0.0, width=30.0),
        _tp("b", 100.1, 0.1, width=30.0),
        _tp("c", 200.0, 0.0, width=30.0),
        _tp("a", 0.1, 0.1, width=30.0),
    ]
    out = _dedup(positions)
    assert out == ["b@100,0", "a@0,0", "c@200,0"]


def test_empty_input_and_single_run_identity() -> None:
    assert PDFTextStripper._drop_overlapping_duplicates([]) == []
    single = [_tp("X", 1.0, 2.0, width=30.0)]
    assert PDFTextStripper._drop_overlapping_duplicates(single) == single


# ---------------------------------------------------------------------------
# /ActualText bypass (upstream: dedup only runs while actualText == null)
# ---------------------------------------------------------------------------


def test_actual_text_runs_bypass_suppression() -> None:
    out = _dedup(
        [
            _tp("AT", 0.0, 0.0, width=30.0, from_actual_text=True),
            _tp("AT", 0.1, 0.1, width=30.0, from_actual_text=True),
        ]
    )
    assert out == ["AT@0,0", "AT@0.1,0.1"]


def test_actual_text_runs_are_not_recorded_in_the_map() -> None:
    # A tagged run never enters characterListMapping, so the FIRST untagged
    # run at the same origin is shown (it becomes the anchor) and only a
    # SECOND untagged run is suppressed.
    out = _dedup(
        [
            _tp("AT", 0.0, 0.0, width=30.0, from_actual_text=True),
            _tp("AT", 0.0, 0.0, width=30.0),
            _tp("AT", 0.1, 0.1, width=30.0),
        ]
    )
    assert out == ["AT@0,0", "AT@0,0"]


# ---------------------------------------------------------------------------
# degenerate text / width corners
# ---------------------------------------------------------------------------


def test_empty_text_with_positive_width_has_infinite_tolerance() -> None:
    # Java: width / 0 (float) = +Infinity -> the whole page is one window;
    # any earlier empty-text run suppresses, no matter how far away.
    out = _dedup([_tp("", 0.0, 0.0, width=5.0), _tp("", 400.0, 700.0, width=5.0)])
    assert out == ["@0,0"]


def test_empty_text_with_zero_width_never_suppressed() -> None:
    # Java: 0f / 0 = NaN -> subMap(NaN, NaN) is empty; every occurrence is
    # shown, even exact re-paints.
    out = _dedup([_tp("", 10.0, 10.0), _tp("", 10.0, 10.0), _tp("", 10.0, 10.0)])
    assert out == ["@10,10", "@10,10", "@10,10"]


def test_widthless_run_uses_font_size_fallback_window() -> None:
    # Lite-only fallback (documented in _drop_overlapping_duplicates): the
    # vertical emitter and synthetic positions carry no run width, so a
    # quarter-font-size window applies instead of upstream's literal 0
    # tolerance (upstream positions always carry the real glyph advance).
    out = _dedup(
        [
            _tp("X", 0.0, 0.0, font_size=8.0),
            _tp("X", 1.0, 1.0, font_size=8.0),
            _tp("X", 3.0, 0.0, font_size=8.0),
        ]
    )
    assert out == ["X@0,0", "X@3,0"]


def test_negative_width_run_uses_fallback_window() -> None:
    out = _dedup(
        [
            _tp("X", 0.0, 0.0, width=-5.0, font_size=8.0),
            _tp("X", 0.5, 0.5, width=-5.0, font_size=8.0),
        ]
    )
    assert out == ["X@0,0"]


# ---------------------------------------------------------------------------
# end-to-end: content-stream double paints through get_text
# ---------------------------------------------------------------------------


def test_double_painted_word_block_extracts_once() -> None:
    # Six words in separate Tm runs, then the whole block re-painted at a
    # +0.3/+0.2 offset. The re-paints trail the originals by six runs — only
    # the page-global map collapses them (the old trailing-4 window failed).
    first = b" ".join(
        b"1 0 0 1 %d 700 Tm (w%d) Tj" % (72 + 80 * i, i) for i in range(6)
    )
    second = b" ".join(
        b"1 0 0 1 %d.3 700.2 Tm (w%d) Tj" % (72 + 80 * i, i) for i in range(6)
    )
    content = b"BT /F0 18 Tf " + first + b" " + second + b" ET"
    assert _text(content) == "w0 w1 w2 w3 w4 w5\n"


def test_double_painted_word_block_kept_when_suppression_off() -> None:
    first = b" ".join(
        b"1 0 0 1 %d 700 Tm (w%d) Tj" % (72 + 80 * i, i) for i in range(6)
    )
    second = b" ".join(
        b"1 0 0 1 %d.3 700.2 Tm (w%d) Tj" % (72 + 80 * i, i) for i in range(6)
    )
    content = b"BT /F0 18 Tf " + first + b" " + second + b" ET"
    out = _text(content, suppress=False, sort=True)
    for i in range(6):
        assert out.count(f"w{i}") == 2


def test_fake_bold_y_offset_within_width_tolerance_suppressed() -> None:
    # 12pt metric-less font -> per-char advance 6, run width 5*6 = 30,
    # tol = 30/5/3 = 2. A 0.9pt vertical stroke offset is a duplicate
    # (the old 0.05*font_size = 0.6 y window kept it).
    content = (
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (Hello) Tj "
        b"1 0 0 1 100 700.9 Tm (Hello) Tj "
        b"ET"
    )
    assert _text(content) == "Hello\n"


def test_same_word_repainted_far_later_on_page_suppressed() -> None:
    # target ... ten filler words ... target re-painted at +0.2/+0.1.
    fillers = b" ".join(
        b"1 0 0 1 %d %d Tm (f%d) Tj" % (72 + (i % 5) * 90, 660 - (i // 5) * 40, i)
        for i in range(10)
    )
    content = (
        b"BT /F0 18 Tf 1 0 0 1 72 700 Tm (target) Tj "
        + fillers
        + b" 1 0 0 1 72.2 700.1 Tm (target) Tj ET"
    )
    out = _text(content, sort=True)
    assert out.count("target") == 1


def test_distinct_same_text_words_far_apart_both_kept() -> None:
    content = (
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (Hello) Tj "
        b"1 0 0 1 300 700 Tm (Hello) Tj "
        b"ET"
    )
    assert _text(content) == "Hello Hello\n"


def test_actual_text_spans_survive_suppression_end_to_end() -> None:
    # Two /ActualText spans painted at (nearly) the same origin: upstream
    # bypasses the dedup while actualText is set, so BOTH replacements are
    # extracted even with suppression on.
    span = (
        b"/Span <</ActualText (AT)>> BDC "
        b"BT /F0 18 Tf 1 0 0 1 %s 700 Tm (xy) Tj ET "
        b"EMC "
    )
    content = (span % b"72") + (span % b"72.3")
    assert _text(content) == "ATAT\n"


# ---------------------------------------------------------------------------
# live oracle — Apache PDFBox 3.0.7 differential
# ---------------------------------------------------------------------------

_PROBE = "DuplicateSuppressWindowProbe"


def _oracle_frames(case: str, tmp_path: Path) -> tuple[str, str]:
    pdf = tmp_path / f"{case}.pdf"
    run_probe_text(_PROBE, "build", case, str(pdf))
    out = run_probe_text(_PROBE, "extract", str(pdf))
    on = out.split("<<<ON\n", 1)[1].split("ON>>>", 1)[0]
    off = out.split("<<<OFF\n", 1)[1].split("OFF>>>", 1)[0]
    return on, off


def _py_text(pdf: Path, *, suppress: bool) -> str:
    doc = PDDocument.load(pdf)
    s = PDFTextStripper()
    s.set_sort_by_position(True)
    s.set_suppress_duplicate_overlapping_text(suppress)
    try:
        return s.get_text(doc)
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize(
    "case",
    ["farpair", "latedup", "yoffset", "ontop", "apart", "actualtext"],
)
def test_oracle_suppression_on_output_matches_pdfbox(
    case: str, tmp_path: Path
) -> None:
    java_on, _ = _oracle_frames(case, tmp_path)
    py_on = _py_text(tmp_path / f"{case}.pdf", suppress=True)
    assert py_on == java_on


@requires_oracle
@pytest.mark.parametrize(
    "case",
    ["farpair", "latedup", "yoffset", "ontop", "apart", "actualtext"],
)
def test_oracle_suppression_off_word_multiset_matches_pdfbox(
    case: str, tmp_path: Path
) -> None:
    # With suppression off, upstream's per-glyph positions interleave the
    # double-painted glyphs under sortByPosition ("aallpphhaa"); the lite
    # run-level positions keep each run contiguous ("alphaalpha"). The
    # CHARACTER multiset per line is identical, so compare that projection.
    _, java_off = _oracle_frames(case, tmp_path)
    py_off = _py_text(tmp_path / f"{case}.pdf", suppress=False)

    def lines_as_char_multisets(text: str) -> list[str]:
        return [
            "".join(sorted(line.replace(" ", "")))
            for line in text.splitlines()
            if line.strip()
        ]

    assert lines_as_char_multisets(py_off) == lines_as_char_multisets(java_off)
