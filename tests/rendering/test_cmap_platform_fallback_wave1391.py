"""Wave 1391 — regression: ``PDTrueTypeFont._code_to_gid`` consulted
only the priority-ordered Unicode subtable returned by
:meth:`TrueTypeFont.get_unicode_cmap_subtable`. Embedded TrueType
subsets that ship only a (1,0) Mac-Roman cmap — for example the
QuarkXPress-era ``QXCTPF+Helvetica`` subset in
``tests/fixtures/pdfwriter/PDFBOX-3110-poems-beads.pdf`` — therefore
returned 0 for every code so every glyph painted as the ``.notdef``
placeholder box. Even after the wave-1391 ``_draw_glyph`` CTM fix
made those boxes visible, the page was an unreadable grid of
identical rectangles.

The fix routes the lookup through the same per-platform table walk
upstream's ``PDTrueTypeFont.codeToGID`` uses: extract the (3,1)
Win-Unicode, (3,0) Win-Symbol, (1,0) Mac-Roman subtables, then map
non-symbolic glyph names through AGL → Unicode → Win-Unicode first,
fall back to the inverted Mac-OS-Roman ``name → mac code`` lookup on
Mac-Roman, then ``post`` table by glyph name. With the fix the
embedded subset resolves real glyph IDs and ``poems-beads`` page 0
paints readable German + French poetry instead of placeholder boxes.

The OrphanPopups fixture has only ``/F``-Hidden popup-text
annotations and no page content stream, so its rendered page is
correctly pure-white (matches upstream PDFBox's
``shouldSkipAnnotation`` path); this test asserts the page renders
without exception rather than checking pixel coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer

_POEMS_BEADS = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "pdfwriter"
    / "PDFBOX-3110-poems-beads.pdf"
)
_ORPHAN_POPUPS = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "multipdf"
    / "PDFBOX-6018-099267-p9-OrphanPopups.pdf"
)


def _fraction_non_white(pdf_path: Path, page_index: int = 0) -> float:
    """Render ``page_index`` of ``pdf_path`` and return the fraction of
    non-white RGB pixels. Closes the document on exit."""
    doc = PDDocument.load(pdf_path)
    try:
        renderer = PDFRenderer(doc)
        img = renderer.render_image(page_index, scale=1.0)
        raw = img.tobytes()
        total = img.size[0] * img.size[1]
        if total == 0:
            return 0.0
        non_white = 0
        for i in range(0, len(raw), 3):
            if raw[i] != 255 or raw[i + 1] != 255 or raw[i + 2] != 255:
                non_white += 1
        return non_white / total
    finally:
        doc.close()


@pytest.mark.skipif(
    not _POEMS_BEADS.exists(), reason="poems-beads fixture missing"
)
def test_poems_beads_resolves_real_glyph_ids() -> None:
    """Cmap-extraction sanity check: the embedded ``QXCTPF+Helvetica``
    subset ships only a (1,0) Mac-Roman cmap. ``_code_to_gid`` must
    walk that subtable (not the missing Unicode subtable) so codes
    like ASCII 'A' / 'G' map to real GIDs."""
    with PDDocument.load(_POEMS_BEADS) as doc:
        page = doc.get_page(0)
        resources = page.get_resources()
        ttf_fonts = []
        for name in resources.get_font_names():
            font = resources.get_font(name)
            if isinstance(font, PDTrueTypeFont):
                ttf_fonts.append(font)
        assert ttf_fonts, "poems-beads has TrueType fonts in /Resources"
        any_resolved = False
        for font in ttf_fonts:
            ttf = font.get_true_type_font()
            assert ttf is not None, f"{font.get_name()} should be embedded"
            for code in (ord("A"), ord("G"), ord("a"), ord("e"), ord("o")):
                gid = font._code_to_gid(code, ttf)  # noqa: SLF001
                if gid != 0:
                    any_resolved = True
                    break
            if any_resolved:
                break
        assert any_resolved, (
            "no ASCII letter resolved to a real glyph in any embedded TTF — "
            "the (1,0) Mac-Roman cmap fallback path regressed"
        )


@pytest.mark.skipif(
    not _POEMS_BEADS.exists(), reason="poems-beads fixture missing"
)
def test_poems_beads_renders_at_least_5_percent_non_white() -> None:
    """End-to-end: page 0 must paint enough non-white pixels to qualify
    as real text (rather than a grid of ``.notdef`` placeholder boxes
    that would also clear ``> 0%`` but show no glyph differentiation)."""
    fraction = _fraction_non_white(_POEMS_BEADS)
    assert fraction >= 0.05, (
        f"poems-beads page 0 rendered with only {fraction * 100:.3f}% "
        "non-white — text decoding regressed."
    )


@pytest.mark.skipif(
    not _ORPHAN_POPUPS.exists(), reason="OrphanPopups fixture missing"
)
def test_orphan_popups_renders_without_error() -> None:
    """OrphanPopups has an empty page content stream and two
    ``/F``-Hidden ``/Subtype /Text`` popup annotations. Upstream
    PDFBox's ``shouldSkipAnnotation`` skips Hidden annotations, so the
    rendered output is correctly pure-white. This regression test
    confirms the page renders without exception (the white-page
    output itself is spec-correct for this PDF's flags).
    """
    with PDDocument.load(_ORPHAN_POPUPS) as doc:
        renderer = PDFRenderer(doc)
        img = renderer.render_image(0, scale=1.0)
        assert img.size[0] > 0 and img.size[1] > 0
        # No exception means success — the page may legitimately be
        # all-white because every annotation has the Hidden flag set
        # and the page Contents stream is empty.
