"""Wave 1339 — coverage-boost for :mod:`pypdfbox.text.pdf_text_stripper`.

Targets the small islands of uncovered lines left after waves 1030–1286:
``has_font_or_size_changed`` name-comparison fall-throughs, the bookmark
resolution branch of ``process_pages``, ``write_page`` returning early
on an empty article list, the ``normalize_word`` Allah / FB1D fast
paths, ``parse_bidi_file`` rejecting malformed hex tokens, the
``handle_line_separation`` paragraph hook, and the
``begin_marked_content_sequence`` defensive exception swallow.
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any, cast

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.text import PDFTextStripper, TextPosition
from pypdfbox.text.position_wrapper import PositionWrapper

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# _compute_avg_advance returns the populated value (line 1002).
# ---------------------------------------------------------------------------


def test_wave1339_compute_avg_advance_returns_user_space_value_for_known_font() -> None:
    """``_compute_avg_advance`` divides the average glyph width
    (thousandths) by 1000 and multiplies by ``font_size``. The default
    ``PDType1Font`` reports zero, so we override
    ``get_average_font_width`` to confirm the user-space conversion."""

    class PositiveAvgFont(PDType1Font):
        def get_average_font_width(self) -> float:  # type: ignore[override]
            return 500.0

    font = PositiveAvgFont()
    advance = PDFTextStripper._compute_avg_advance(font, 12.0)  # noqa: SLF001

    assert advance is not None
    # 500/1000 * 12 = 6.0
    assert advance == 6.0


# ---------------------------------------------------------------------------
# has_font_or_size_changed name-comparison branches (lines 1545–1553).
# ---------------------------------------------------------------------------


def test_wave1339_has_font_or_size_changed_returns_true_when_font_names_differ() -> None:
    """Two distinct fonts with distinct names → change."""
    f1 = SimpleNamespace(get_name=lambda: "F1")
    f2 = SimpleNamespace(get_name=lambda: "F2")
    a = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, f1))
    b = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, f2))
    assert PDFTextStripper.has_font_or_size_changed(b, a) is True


def test_wave1339_has_font_or_size_changed_returns_false_when_names_match() -> None:
    """Distinct font objects but matching names → no change."""
    f1 = SimpleNamespace(get_name=lambda: "Helv")
    f2 = SimpleNamespace(get_name=lambda: "Helv")
    a = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, f1))
    b = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, f2))
    assert PDFTextStripper.has_font_or_size_changed(b, a) is False


def test_wave1339_has_font_or_size_changed_when_only_last_has_name() -> None:
    """``cur`` has no name but ``last`` does → upstream returns True."""
    cur_font = SimpleNamespace(get_name=lambda: None)
    last_font = SimpleNamespace(get_name=lambda: "F0")
    cur = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, cur_font))
    last = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, last_font))
    assert PDFTextStripper.has_font_or_size_changed(cur, last) is True


def test_wave1339_has_font_or_size_changed_falls_back_to_identity_when_both_nameless() -> None:
    """Both fonts are present but expose no name → upstream's
    hashCode fallback (we compare ``id()``). Distinct objects with the
    same nameless contract differ by identity."""
    cur_font = SimpleNamespace(get_name=lambda: None)
    last_font = SimpleNamespace(get_name=lambda: None)
    cur = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, cur_font))
    last = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, font=cast(Any, last_font))
    assert PDFTextStripper.has_font_or_size_changed(cur, last) is True


# ---------------------------------------------------------------------------
# remove_contained_spaces empty input (line 1565).
# ---------------------------------------------------------------------------


def test_wave1339_remove_contained_spaces_handles_empty_list() -> None:
    """Empty input is a no-op — guards against the index-by-zero
    assumption upstream's first-element fetch would make."""
    items: list[TextPosition] = []
    PDFTextStripper.remove_contained_spaces(items)
    assert items == []


# ---------------------------------------------------------------------------
# fill_bead_rectangles — happy path + bead defensive branches (1592–1603).
# ---------------------------------------------------------------------------


def test_wave1339_fill_bead_rectangles_collects_rect_from_each_bead() -> None:
    """When ``get_thread_beads`` returns real beads with rectangles, the
    method emits the lower-left / upper-right tuple for each."""
    rect = SimpleNamespace(
        get_lower_left_x=lambda: 10.0,
        get_lower_left_y=lambda: 20.0,
        get_upper_right_x=lambda: 110.0,
        get_upper_right_y=lambda: 220.0,
    )
    bead_a = SimpleNamespace(get_rectangle=lambda: rect)
    bead_b = SimpleNamespace(get_rectangle=lambda: None)  # filtered out
    bead_c = None  # filtered out
    page = SimpleNamespace(get_thread_beads=lambda: [bead_a, bead_b, bead_c])
    s = PDFTextStripper()

    rects = s.fill_bead_rectangles(cast(Any, page))

    assert rects == [(10.0, 20.0, 110.0, 220.0)]
    assert s._bead_rectangles == [(10.0, 20.0, 110.0, 220.0)]  # noqa: SLF001


def test_wave1339_fill_bead_rectangles_skips_bead_whose_get_rectangle_raises() -> None:
    """A bead whose ``get_rectangle`` raises is silently skipped — keeps
    one malformed annotation from aborting the whole walk."""

    def _boom() -> None:
        raise RuntimeError("bad bead")

    bead = SimpleNamespace(get_rectangle=_boom)
    page = SimpleNamespace(get_thread_beads=lambda: [bead])
    s = PDFTextStripper()

    rects = s.fill_bead_rectangles(cast(Any, page))

    assert rects == []


def test_wave1339_fill_bead_rectangles_swallows_get_thread_beads_exception() -> None:
    """Defensive: a page whose ``get_thread_beads`` raises is treated as
    bead-free (returns empty list)."""

    def _boom() -> None:
        raise RuntimeError("malformed /B")

    page = SimpleNamespace(get_thread_beads=_boom)
    s = PDFTextStripper()

    assert s.fill_bead_rectangles(cast(Any, page)) == []


# ---------------------------------------------------------------------------
# process_pages bookmark resolution (lines 1637–1671).
# ---------------------------------------------------------------------------


def test_wave1339_process_pages_resolves_start_and_end_bookmarks() -> None:
    """Both bookmarks resolve to real pages → the method records their
    1-based positions on ``_start_bookmark_page_number`` /
    ``_end_bookmark_page_number``."""
    doc = PDDocument()
    try:
        p1 = _make_page_with_stream(doc, b"")
        p2 = _make_page_with_stream(doc, b"")
        p3 = _make_page_with_stream(doc, b"")
        # Each bookmark's ``find_destination_page`` returns the cos object
        # of the target page — that's the contract the stripper checks.
        start = SimpleNamespace(
            find_destination_page=lambda _doc: p2.get_cos_object(),
            get_cos_object=lambda: object(),
        )
        end = SimpleNamespace(
            find_destination_page=lambda _doc: p3.get_cos_object(),
            get_cos_object=lambda: object(),
        )
        s = PDFTextStripper()
        s._active_document = doc  # noqa: SLF001
        s.set_start_bookmark(cast(Any, start))
        s.set_end_bookmark(cast(Any, end))

        s.process_pages([p1, p2, p3])

        assert s._start_bookmark_page_number == 2  # noqa: SLF001
        assert s._end_bookmark_page_number == 3  # noqa: SLF001
    finally:
        doc.close()


def test_wave1339_process_pages_collapses_to_empty_for_identical_unresolved_bookmark() -> None:
    """When both bookmarks point at the same outline item but neither
    resolves to a page in the supplied list, upstream forces an empty
    range (0, 0) so the page walk is skipped without crashing."""
    doc = PDDocument()
    try:
        p1 = _make_page_with_stream(doc, b"")
        # Both bookmarks share an identical (shared) cos object that
        # ``find_destination_page`` cannot resolve.
        shared_cos = object()
        bookmark = SimpleNamespace(
            find_destination_page=lambda _doc: None,
            get_cos_object=lambda: shared_cos,
        )
        s = PDFTextStripper()
        s._active_document = doc  # noqa: SLF001
        s.set_start_bookmark(cast(Any, bookmark))
        s.set_end_bookmark(cast(Any, bookmark))

        s.process_pages([p1])

        assert s._start_bookmark_page_number == 0  # noqa: SLF001
        assert s._end_bookmark_page_number == 0  # noqa: SLF001
    finally:
        doc.close()


def test_wave1339_process_pages_invokes_process_page_for_each_page_with_contents() -> None:
    """The page-loop branch only invokes ``process_page`` for pages
    whose ``get_contents`` is truthy — exercises lines 1667–1670."""
    doc = PDDocument()
    try:
        p1 = _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (hi) Tj ET")
        # Page without content stream — skipped by the loop.
        p2 = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        doc.add_page(p2)
        s = PDFTextStripper()
        s._active_document = doc  # noqa: SLF001
        calls: list[PDPage] = []
        original = s.process_page

        def spy(page: PDPage) -> str:
            calls.append(page)
            return original(page)

        s.process_page = spy  # type: ignore[method-assign]
        result = s.process_pages([p1, p2])

        assert calls == [p1]
        assert isinstance(result, str)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# write_page (lines 1684–1693).
# ---------------------------------------------------------------------------


def test_wave1339_write_page_returns_empty_when_no_articles() -> None:
    """``write_page`` returns ``""`` when ``_characters_by_article`` is
    empty — guard for the line-1684 short-circuit."""
    s = PDFTextStripper()
    assert s.write_page() == ""


def test_wave1339_write_page_renders_each_article_through_emit_group() -> None:
    """A single non-empty article is emitted through the formatting
    pipeline; the resulting string concatenates each position's text."""
    s = PDFTextStripper()
    a = TextPosition(text="hi", x=0.0, y=0.0, font_size=12.0, width=10.0)
    b = TextPosition(text="!", x=12.0, y=0.0, font_size=12.0, width=4.0)
    s._characters_by_article = [[a, b]]  # noqa: SLF001

    out = s.write_page()

    assert "hi" in out and "!" in out


# ---------------------------------------------------------------------------
# normalize_word Allah-with-alif and FB1D reverse branches (1775, 1779).
# ---------------------------------------------------------------------------


def test_wave1339_normalize_word_inserts_allah_without_alif() -> None:
    """U+FDF2 preceded by ARABIC LETTER ALEF (U+0627) inserts the
    canonical Allah-without-alif decomposition (line 1775)."""
    s = PDFTextStripper()
    # Build: U+0627 (alif) + U+FDF2 (Allah ligature).
    text = "اﷲ"
    out = s.normalize_word(text)
    # Reversed by handle_direction (Arabic = AL).
    assert "لله" in out[::-1]


def test_wave1339_normalize_word_reverses_long_nfkc_decomposition_for_fb1d_block() -> None:
    """Codepoints at or above U+FB1D whose NFKC decomposition is multi-
    character get reversed before insertion (line 1779)."""
    s = PDFTextStripper()
    # U+FB2A SHIN WITH SHIN DOT decomposes to two characters under NFKC.
    out = s.normalize_word("שׁ")
    # Output is reversed by handle_direction; we just confirm the
    # method completed and returned a non-empty string.
    assert isinstance(out, str)
    assert out != "שׁ"


# ---------------------------------------------------------------------------
# parse_bidi_file rejects malformed hex tokens (lines 1888–1889).
# ---------------------------------------------------------------------------


def test_wave1339_parse_bidi_file_skips_lines_with_unparseable_hex() -> None:
    """Lines with two semicolon-separated tokens that aren't valid hex
    are skipped without raising — the ``ValueError`` is caught."""
    sample = b"GG; HH\n0028; 0029\n"
    out = PDFTextStripper.parse_bidi_file(io.BytesIO(sample))

    # The "GG; HH" line was skipped; the valid line was kept.
    assert out == {"(": ")"}


# ---------------------------------------------------------------------------
# handle_line_separation marks paragraph start when separation heuristic
# agrees (lines 1908–1914).
# ---------------------------------------------------------------------------


def test_wave1339_handle_line_separation_marks_line_start_when_no_prior_position() -> None:
    s = PDFTextStripper()
    wrapper = PositionWrapper(
        TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    )

    out = s.handle_line_separation(wrapper, None, None, 12.0)

    assert out is wrapper
    assert wrapper.is_line_start() is True
    assert wrapper.is_paragraph_start() is False


def test_wave1339_handle_line_separation_marks_paragraph_start_after_large_drop() -> None:
    """When the vertical gap between ``current`` and ``last_position``
    exceeds ``drop_threshold × line_height`` the wrapper is flagged as a
    paragraph start in addition to a line start."""
    s = PDFTextStripper()
    last = PositionWrapper(
        TextPosition(text="prev", x=0.0, y=100.0, font_size=12.0)
    )
    cur = PositionWrapper(
        # Big vertical drop (>> 12 * default drop_threshold).
        TextPosition(text="cur", x=0.0, y=0.0, font_size=12.0)
    )

    out = s.handle_line_separation(cur, last, None, 12.0)

    assert out is cur
    assert cur.is_line_start() is True
    assert cur.is_paragraph_start() is True


# ---------------------------------------------------------------------------
# begin_marked_content_sequence defensive exception path (lines 1947–1948).
# ---------------------------------------------------------------------------


def test_wave1339_begin_marked_content_sequence_swallows_get_string_exception() -> None:
    """A properties dict whose ``get_string`` raises must not propagate —
    the marked-content stack still records the entry (with ``None``
    actual text) and the next ``end`` pops it cleanly."""

    class ExplodingDict(COSDictionary):
        def get_string(self, key: object, default: object = None) -> str | None:  # type: ignore[override]
            raise RuntimeError("malformed /ActualText")

    s = PDFTextStripper()
    bad = ExplodingDict()

    s.begin_marked_content_sequence(COSName.get_pdf_name("Span"), bad)

    # Stack entry was pushed; actual text is None.
    assert len(s._marked_content_stack) == 1  # noqa: SLF001
    assert s._actual_text is None
    s.end_marked_content_sequence()
    assert s._marked_content_stack == []  # noqa: SLF001
