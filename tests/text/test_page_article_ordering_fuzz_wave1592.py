"""Fuzz / parity coverage for ``PDFTextStripper`` page-level article
(thread-bead) bucketing — the ``processPage`` / ``writePage`` loop, the
``charactersByArticle`` accumulation, and the ``shouldSeparateByBeads``
option.

Hammers the bead-bucketing surface against the upstream Apache PDFBox
contract (``PDFTextStripper.processPage`` sizing —
PDFTextStripper.java:349-377 — and ``processTextPosition`` assignment —
PDFTextStripper.java:954-1020):

* a page with no beads collapses to ONE article holding every glyph;
* a page with beads buckets each glyph into the article whose rectangle
  contains its origin (``rect.contains(x, y)`` ⇒ slot ``i*2 + 1``);
* the article (slot) order follows the bead-chain order;
* ``charactersByArticle`` is the post-filter, post-partition structure
  (the fix this wave restores — ``process_page`` used to leave it a single
  flat group even on a beaded page, so ``get_characters_by_article`` and
  the upstream-signature ``write_page`` both saw the wrong shape);
* ``charactersByArticle`` is reset between pages (no glyph bleed);
* ``set_should_separate_by_beads(False)`` short-circuits to one article;
* a glyph outside every bead falls into a gap / default slot, never lost;
* the per-article ``article_start`` / ``article_end`` markers wrap each
  bucket (default empty → buckets concatenate; promoted under
  ``add_more_formatting`` → buckets split);
* multiple pages accumulate their text in document order.

Hand-written (not ported from upstream JUnit); built with pypdfbox using
Standard-14 Helvetica so glyph metrics resolve identically to PDFBox. The
companion live differential lives in ``test_bead_separation_oracle.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_PAGE_W = 612.0
_PAGE_H = 792.0

# (x, y, text) runs in PDF user space (y-up).
Run = tuple[float, float, str]
# (llx, lly, urx, ury) bead rectangle in PDF user space.
Rect = tuple[float, float, float, float]


def _add_page(
    doc: PDDocument,
    runs: list[Run],
    beads: list[Rect] | None = None,
) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    doc.add_page(page)
    font = PDFontFactory.create_default_font("Helvetica")
    cs = PDPageContentStream(doc, page)
    for x, y, txt in runs:
        cs.begin_text()
        cs.set_font(font, 12.0)
        cs.new_line_at_offset(x, y)
        cs.show_text(txt)
        cs.end_text()
    cs.close()
    if beads is not None:
        bead_objs = []
        for r in beads:
            b = PDThreadBead()
            b.set_rectangle(PDRectangle(*r))
            bead_objs.append(b)
        page.set_thread_beads(bead_objs)
    return page


def _build(
    path: Path,
    pages: list[tuple[list[Run], list[Rect] | None]],
) -> None:
    doc = PDDocument()
    try:
        for runs, beads in pages:
            _add_page(doc, runs, beads)
        doc.save(str(path))
    finally:
        doc.close()


def _strip(
    pdf: Path,
    *,
    separate: bool = True,
    sort: bool = True,
    add_more_formatting: bool = False,
) -> tuple[str, list[list[str]]]:
    """Return (text, [[unicode per glyph] per article]) for the LAST page
    walked (``charactersByArticle`` reflects the most recent page)."""
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.set_sort_by_position(sort)
        s.set_should_separate_by_beads(separate)
        s.set_add_more_formatting(add_more_formatting)
        text = s.get_text(doc)
        cba = [[p.get_unicode() for p in art] for art in s.get_characters_by_article()]
        return text, cba
    finally:
        doc.close()


# Two-column geometry shared by several cases. Bead 0 = LEFT, bead 1 = RIGHT;
# the chain order drives the article reading order.
_LEFT_BEAD: Rect = (60.0, 600.0, 200.0, 760.0)
_RIGHT_BEAD: Rect = (340.0, 600.0, 500.0, 760.0)
_TWO_COL_RUNS: list[Run] = [
    (350.0, 700.0, "RightTop"),
    (350.0, 650.0, "RightBot"),
    (72.0, 700.0, "LeftTop"),
    (72.0, 650.0, "LeftBot"),
]


# ---------------------------------------------------------------- no beads ---


def test_no_beads_single_article(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [([(72.0, 700.0, "Hello"), (72.0, 650.0, "World")], None)])
    text, cba = _strip(pdf)
    assert len(cba) == 1
    assert cba[0] == ["Hello", "World"]
    assert text == "Hello\nWorld\n"


def test_empty_bead_array_single_article(tmp_path: Path) -> None:
    # An empty /B array has no usable rectangles → fall back to one article.
    pdf = tmp_path / "a.pdf"
    _build(pdf, [([(72.0, 700.0, "Solo")], [])])
    _text, cba = _strip(pdf)
    assert len(cba) == 1
    assert cba[0] == ["Solo"]


def test_no_beads_separate_false_single_article(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [([(72.0, 700.0, "Plain")], None)])
    _text, cba = _strip(pdf, separate=False)
    assert len(cba) == 1


# ------------------------------------------------------ bead bucketing -------


def test_two_columns_bucket_into_two_articles(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    text, cba = _strip(pdf)
    assert len(cba) == 2
    assert cba[0] == ["LeftTop", "LeftBot"]
    assert cba[1] == ["RightTop", "RightBot"]
    # Default empty article markers → buckets concatenate.
    assert text == "LeftTop\nLeftBotRightTop\nRightBot\n"


def test_glyph_inside_bead_rectangle_goes_to_that_article(tmp_path: Path) -> None:
    # Each glyph's origin sits inside exactly one bead rectangle; verify it
    # lands in that bead's slot (i*2+1, exposed as its own article).
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    _text, cba = _strip(pdf)
    left_text = set(cba[0])
    right_text = set(cba[1])
    assert left_text == {"LeftTop", "LeftBot"}
    assert right_text == {"RightTop", "RightBot"}
    # No glyph appears in two articles.
    assert left_text.isdisjoint(right_text)


def test_article_order_follows_bead_chain_order(tmp_path: Path) -> None:
    # Reverse the bead chain (RIGHT first, LEFT second) and the article
    # order must reverse with it — the chain order, not the geometry, drives
    # the reading order.
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_RIGHT_BEAD, _LEFT_BEAD])])
    _text, cba = _strip(pdf)
    assert len(cba) == 2
    assert set(cba[0]) == {"RightTop", "RightBot"}
    assert set(cba[1]) == {"LeftTop", "LeftBot"}


def test_three_beads_three_articles(tmp_path: Path) -> None:
    runs: list[Run] = [
        (72.0, 700.0, "A"),
        (280.0, 700.0, "B"),
        (480.0, 700.0, "C"),
    ]
    beads: list[Rect] = [
        (60.0, 680.0, 120.0, 720.0),
        (270.0, 680.0, 330.0, 720.0),
        (470.0, 680.0, 530.0, 720.0),
    ]
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(runs, beads)])
    _text, cba = _strip(pdf)
    assert len(cba) == 3
    assert cba[0] == ["A"]
    assert cba[1] == ["B"]
    assert cba[2] == ["C"]


def test_all_glyphs_inside_one_bead(tmp_path: Path) -> None:
    runs: list[Run] = [
        (72.0, 700.0, "One"),
        (72.0, 650.0, "Two"),
        (72.0, 600.0, "Three"),
    ]
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(runs, [(60.0, 580.0, 300.0, 760.0)])])
    _text, cba = _strip(pdf)
    # One bead → all glyphs in that bead's single slot.
    assert len(cba) == 1
    assert cba[0] == ["One", "Two", "Three"]


# ----------------------------------------- glyph outside every bead ---------


def test_glyph_outside_all_beads_not_lost(tmp_path: Path) -> None:
    # A glyph below + right of the only bead matches neither the contains
    # test nor the left/above gap conditions, so it falls into the trailing
    # default slot — present, not dropped.
    pdf = tmp_path / "a.pdf"
    _build(
        pdf,
        [([(72.0, 700.0, "InBead"), (560.0, 100.0, "Outside")], [_LEFT_BEAD])],
    )
    text, cba = _strip(pdf)
    flat = [g for art in cba for g in art]
    assert "InBead" in flat
    assert "Outside" in flat
    # InBead is bucketed into the bead slot; Outside into a different slot.
    in_art = next(art for art in cba if "InBead" in art)
    out_art = next(art for art in cba if "Outside" in art)
    assert in_art is not out_art
    assert "Outside" in text


def test_glyph_left_of_bead_goes_to_gap_slot(tmp_path: Path) -> None:
    # A glyph to the LEFT of the bead (x < llx) is not contained but the
    # "left/above" gap condition fires → it lands in the gap slot (i*2),
    # which precedes the bead slot.
    pdf = tmp_path / "a.pdf"
    _build(
        pdf,
        [([(20.0, 700.0, "Gap"), (100.0, 700.0, "InBead")], [_LEFT_BEAD])],
    )
    _text, cba = _strip(pdf)
    flat = [g for art in cba for g in art]
    assert flat.count("Gap") == 1
    assert flat.count("InBead") == 1


def test_all_glyphs_outside_beads_still_extracted(tmp_path: Path) -> None:
    # Bead far from all text — every glyph ends up in a gap/default slot but
    # nothing is lost.
    pdf = tmp_path / "a.pdf"
    _build(
        pdf,
        [
            (
                [(72.0, 700.0, "Far1"), (72.0, 650.0, "Far2")],
                [(500.0, 100.0, 550.0, 150.0)],
            )
        ],
    )
    _text, cba = _strip(pdf)
    flat = [g for art in cba for g in art]
    assert sorted(flat) == ["Far1", "Far2"]


# ---------------------------------------- should_separate_by_beads = False --


def test_separate_false_collapses_to_one_article(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    _text, cba = _strip(pdf, separate=False)
    assert len(cba) == 1
    # All four glyphs in the single article.
    assert sorted(cba[0]) == ["LeftBot", "LeftTop", "RightBot", "RightTop"]


def test_separate_true_vs_false_differ(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    on, _ = _strip(pdf, separate=True)
    off, _ = _strip(pdf, separate=False)
    assert on != off


def test_separate_false_interleaves_by_baseline(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    off, _ = _strip(pdf, separate=False)
    # Geometric sort interleaves both columns per shared baseline.
    assert off == "LeftTop RightTop\nLeftBot RightBot\n"


@pytest.mark.parametrize("separate", [True, False])
def test_article_count_flag_consistency(tmp_path: Path, separate: bool) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    _text, cba = _strip(pdf, separate=separate)
    if separate:
        assert len(cba) == 2
    else:
        assert len(cba) == 1


# --------------------------------------- charactersByArticle reset / pages --


def test_characters_by_article_reset_between_pages(tmp_path: Path) -> None:
    # Page 1 has 2 articles (beads); page 2 has none → charactersByArticle
    # after the walk reflects ONLY page 2 (no bleed from page 1).
    pdf = tmp_path / "a.pdf"
    _build(
        pdf,
        [
            (_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD]),
            ([(72.0, 700.0, "Page2")], None),
        ],
    )
    text, cba = _strip(pdf)
    assert len(cba) == 1
    assert cba[0] == ["Page2"]
    # But the joined text spans both pages.
    assert "LeftTop" in text
    assert "Page2" in text


def test_multi_page_accumulates_in_order(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(
        pdf,
        [
            ([(72.0, 700.0, "AAA")], None),
            ([(72.0, 700.0, "BBB")], None),
            ([(72.0, 700.0, "CCC")], None),
        ],
    )
    text, _cba = _strip(pdf)
    assert text == "AAA\nBBB\nCCC\n"


def test_multi_page_each_beaded_independent(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(
        pdf,
        [
            (_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD]),
            (_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD]),
        ],
    )
    text, cba = _strip(pdf)
    # Last page articles only.
    assert len(cba) == 2
    # Text contains both pages' content.
    assert text.count("LeftTop") == 2


def test_reset_engine_clears_articles(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.get_text(doc)
        assert len(s.get_characters_by_article()) == 2
        s.reset_engine()
        assert s.get_characters_by_article() == []
    finally:
        doc.close()


# --------------------------------------------- article start / end markers --


def test_article_markers_wrap_each_bucket(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.set_sort_by_position(True)
        s.set_should_separate_by_beads(True)
        s.set_article_start("<A>")
        s.set_article_end("</A>")
        text = s.get_text(doc)
        # Two articles → two <A>…</A> wraps.
        assert text.count("<A>") == 2
        assert text.count("</A>") == 2
        assert "<A>LeftTop" in text
        assert "<A>RightTop" in text
    finally:
        doc.close()


def test_article_markers_single_article_no_beads(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [([(72.0, 700.0, "Solo")], None)])
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.set_article_start("<A>")
        s.set_article_end("</A>")
        text = s.get_text(doc)
        assert text.count("<A>") == 1
        assert text.count("</A>") == 1
    finally:
        doc.close()


def test_add_more_formatting_splits_buckets(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    plain, _ = _strip(pdf)
    fmt, _ = _strip(pdf, add_more_formatting=True)
    assert "LeftBotRightTop" in plain
    assert "LeftBotRightTop" not in fmt
    assert plain != fmt


def test_default_article_markers_empty(tmp_path: Path) -> None:
    s = PDFTextStripper()
    assert s.get_article_start() == ""
    assert s.get_article_end() == ""


# --------------------------------------------- flag round-trips / defaults --


def test_should_separate_by_beads_default_true() -> None:
    s = PDFTextStripper()
    assert s.get_should_separate_by_beads() is True
    assert s.is_should_separate_by_beads() is True
    assert s.get_separate_by_beads() is True


def test_should_separate_by_beads_round_trip() -> None:
    s = PDFTextStripper()
    s.set_should_separate_by_beads(False)
    assert s.get_should_separate_by_beads() is False
    s.set_should_separate_by_beads(True)
    assert s.get_should_separate_by_beads() is True


def test_characters_by_article_empty_outside_walk() -> None:
    s = PDFTextStripper()
    assert s.get_characters_by_article() == []


def test_empty_page_single_empty_article(tmp_path: Path) -> None:
    # A page with no content stream still produces a single (empty) article
    # slot, mirroring upstream's writePage iterating an empty article.
    pdf = tmp_path / "a.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H)))
        doc.save(str(pdf))
    finally:
        doc.close()
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.get_text(doc)
        cba = s.get_characters_by_article()
        assert len(cba) == 1
        assert cba[0] == []
    finally:
        doc.close()


def test_fill_bead_rectangles_returns_user_space(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    _build(pdf, [(_TWO_COL_RUNS, [_LEFT_BEAD, _RIGHT_BEAD])])
    doc = PDDocument.load(str(pdf))
    try:
        page = next(iter(doc.get_pages()))
        s = PDFTextStripper()
        rects = s.fill_bead_rectangles(page)
        assert len(rects) == 2
        assert rects[0] == _LEFT_BEAD
        assert rects[1] == _RIGHT_BEAD
    finally:
        doc.close()


def test_glyph_on_bead_boundary_inclusive(tmp_path: Path) -> None:
    # The contains test is inclusive (llx <= x <= urx, lly <= y <= ury);
    # a glyph exactly on the lower-left corner is inside.
    bead: Rect = (72.0, 700.0, 300.0, 760.0)
    pdf = tmp_path / "a.pdf"
    _build(pdf, [([(72.0, 700.0, "Corner")], [bead])])
    _text, cba = _strip(pdf)
    assert len(cba) == 1
    assert cba[0] == ["Corner"]
