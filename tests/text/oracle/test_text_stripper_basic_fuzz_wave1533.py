"""Live Apache PDFBox differential parity for ``PDFTextStripper`` *basic*
horizontal text extraction — word/line segmentation and output ordering over
tiny, fully controlled single-page content streams (wave 1533).

The companion ``test_vertical_text_strip_oracle.py`` pins the vertical
writing-mode reading order and ``test_text_sort_inline_oracle.py`` /
``test_sort_by_position_oracle.py`` pin the position-sort re-ordering on
multi-line / multi-column pages. This file's distinct angle is the *baseline
horizontal-extraction* surface: a matrix of minimal synthetic pages
(empty page, whitespace-only positioning with no glyphs, a wide-gap word
break, a tight abutting pair, two lines via ``Td`` and via ``T*``,
overlapping glyphs, multiple ``Tj`` runs, ``TJ`` kerning vs space-sized
negative adjustments) each extracted in *both* ``sortByPosition`` modes and
compared byte-for-byte against the live PDFBox 3.0.7 jar.

The :class:`TextStripperBasicProbe` Java probe emits two escaped projections
of the extracted text — one per sort mode — so newlines / word breaks are
recovered exactly (newlines escaped as ``\\n`` so each marker is one physical
line). Each mode loads the document FRESH: a ``PDFTextStripper`` run mutates
per-page parser state that a second stripper on the same ``PDDocument``
inherits, which would otherwise make the sorted-mode reading order depend on
whether the unsorted mode ran first (an observed, probe-only artifact — not a
segmentation difference). Loading a clean document per mode is the
deterministic comparison.

Every case is built with a Standard-14 Helvetica font so PDFBox and pypdfbox
resolve identical glyph metrics; the content streams are tiny and fully
controlled so the oracle is deterministic. All cases are at full parity in
both modes — there are no pinned divergences in this surface. (The known
word-break gap-threshold calibration carve-out — DEFERRED.md — is *not*
exercised here: this file's only positional word break uses a page-spanning
gap that clears even the lite stripper's coarse ``font_size * 1.5``
threshold, so both engines insert exactly one space.)

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "TextStripperBasicProbe"

# ---------------------------------------------------------------------------
# Synthetic single-page content streams. The ``/F1`` token is rewritten to
# whatever key the page resources actually allocate for the embedded
# Helvetica font. Page is 612x792 (US Letter), so a y of 660..740 is well
# inside the page and a 250pt x jump is a genuine wide gap.
# ---------------------------------------------------------------------------

# Empty page — no content operators at all.
_EMPTY = b""
# Two words split by a page-wide x jump (Td of +300): a positional word break
# with no space glyph. Clears even the coarse lite gap threshold -> one space.
_WIDE_GAP = b"BT /F1 24 Tf 72 700 Td (Hello) Tj 300 0 Td (World) Tj ET"
# Two runs abutting (Td of +60 ~ "Hello" width at 24pt): no word break.
_TIGHT = b"BT /F1 24 Tf 72 700 Td (Hello) Tj 60 0 Td (World) Tj ET"
# Two lines via an explicit Td vertical move.
_TWO_LINES_TD = b"BT /F1 24 Tf 72 700 Td (Line1) Tj 0 -40 Td (Line2) Tj ET"
# Two lines via TL + T* (next-line operator).
_TWO_LINES_TSTAR = b"BT /F1 24 Tf 40 TL 72 700 Td (Line1) Tj T* (Line2) Tj ET"
# Two glyphs drawn at the SAME origin (Td 0 0): overlapping glyphs.
_OVERLAP = b"BT /F1 24 Tf 72 700 Td (A) Tj 0 0 Td (B) Tj ET"
# Only positioning operators, no show-text: whitespace-positioned, no glyphs.
_WS_ONLY = b"BT /F1 24 Tf 72 700 Td 200 0 Td 0 -40 Td ET"
# Three consecutive Tj runs with no intervening positioning: abut into one
# word, stream order preserved.
_MULTI_TJ = b"BT /F1 24 Tf 72 700 Td (One) Tj (Two) Tj (Three) Tj ET"
# Two lines drawn bottom-then-top (out of visual reading order): sort mode
# must reorder top-to-bottom; unsorted preserves stream order.
_OOO_LINE = b"BT /F1 24 Tf 72 660 Td (Bottom) Tj 0 80 Td (Top) Tj ET"
# Two words on one baseline drawn right-then-left (out of reading order).
_OOO_INLINE = b"BT /F1 24 Tf 300 700 Td (Right) Tj -250 0 Td (Left) Tj ET"
# TJ with a small negative adjustment (kerning-sized, -80): no word break.
_TJ_KERN = b"BT /F1 24 Tf 72 700 Td [(Wo) -80 (rld)] TJ ET"
# TJ with a large negative adjustment (-2000 = 48pt, space-sized): word break.
_TJ_SPACE = b"BT /F1 24 Tf 72 700 Td [(Wo) -2000 (rld)] TJ ET"

_CASES = {
    "empty": _EMPTY,
    "wide_gap": _WIDE_GAP,
    "tight": _TIGHT,
    "two_lines_td": _TWO_LINES_TD,
    "two_lines_tstar": _TWO_LINES_TSTAR,
    "overlap": _OVERLAP,
    "ws_only": _WS_ONLY,
    "multi_tj": _MULTI_TJ,
    "ooo_line": _OOO_LINE,
    "ooo_inline": _OOO_INLINE,
    "tj_kern": _TJ_KERN,
    "tj_space": _TJ_SPACE,
}


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page US-Letter PDF whose content is exactly ``content``.

    The ``/F1`` token is rewritten to the key the page resources allocate for
    the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 612, 792))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        resources = page.get_or_create_resources()
        font_key = resources.add(font)
        page.set_resources(resources)
        rewritten = content.replace(
            b"/F1", b"/" + font_key.get_name().encode("ascii")
        )
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(rewritten)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()


def _java(path: str) -> tuple[str, str]:
    """Run the probe; return ``(unsorted_text, sorted_text)`` unescaped.

    The probe emits exactly two physical lines, ``UNSORTED:<escaped>`` and
    ``SORTED:<escaped>`` (the payload's own newlines are escaped, so each
    marker is one physical line). We match on the line *prefix* rather than
    a bare ``split("SORTED:")`` — the latter would also match the ``SORTED:``
    substring inside ``UNSORTED:``.
    """
    out = run_probe_text(_PROBE, path)
    unsorted = ""
    sorted_ = ""
    for line in out.split("\n"):
        if line.startswith("UNSORTED:"):
            unsorted = line[len("UNSORTED:") :]
        elif line.startswith("SORTED:"):
            sorted_ = line[len("SORTED:") :]
    return _unesc(unsorted), _unesc(sorted_)


def _unesc(s: str) -> str:
    """Reverse the probe's escape (``\\n`` / ``\\r`` / ``\\\\``)."""
    result: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                result.append("\n")
                i += 2
                continue
            if nxt == "r":
                result.append("\r")
                i += 2
                continue
            if nxt == "\\":
                result.append("\\")
                i += 2
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _py(path: str, sort: bool) -> str:
    """Extract with pypdfbox in the requested sort mode.

    The document is closed in a ``finally`` so a Windows file lock is always
    released before the temp dir is removed.
    """
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(sort)
        return stripper.get_text(doc)
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_basic_extraction_matches_pdfbox_both_modes(name: str) -> None:
    content = _CASES[name]
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        java_unsorted, java_sorted = _java(path)
        py_unsorted = _py(path, False)
        py_sorted = _py(path, True)
    assert py_unsorted == java_unsorted
    assert py_sorted == java_sorted


# ---------------------------------------------------------------------------
# A handful of targeted assertions on the *shape* of the segmentation, so a
# future regression that silently changes both engines identically (e.g. a
# probe that stopped emitting newlines) is still caught against a literal
# expectation.
# ---------------------------------------------------------------------------


@requires_oracle
def test_empty_page_yields_only_page_separator() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(_EMPTY, path)
        java_unsorted, java_sorted = _java(path)
        assert java_unsorted == java_sorted == "\n"
        assert _py(path, False) == "\n"
        assert _py(path, True) == "\n"


@requires_oracle
def test_whitespace_only_positioning_yields_no_glyphs() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(_WS_ONLY, path)
        java_unsorted, _ = _java(path)
        assert java_unsorted == "\n"
        assert _py(path, False) == "\n"


@requires_oracle
def test_wide_gap_inserts_single_space() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(_WIDE_GAP, path)
        _, java_sorted = _java(path)
        assert java_sorted == "Hello World\n"
        assert _py(path, True) == "Hello World\n"


@requires_oracle
def test_two_lines_insert_line_break() -> None:
    for content in (_TWO_LINES_TD, _TWO_LINES_TSTAR):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "case.pdf")
            _build_pdf(content, path)
            _, java_sorted = _java(path)
            assert java_sorted == "Line1\nLine2\n"
            assert _py(path, True) == "Line1\nLine2\n"
