"""Wave 1391 — regression: ``_draw_glyph`` composed the per-glyph CTM in
the wrong order so any text PDF whose producer placed each line via
``cm`` and used ``Tm`` for the font-size matrix (a common pattern from
Word / GIMP / PDFBox itself) rendered as a pure-white page.

The chain was ``ctm * text_local * Tm * device_ctm`` — the page CTM
was prefixed instead of folded in between Tm and device_ctm, so the
DPI-scaled y-flip in ``device_ctm`` got applied to the page-CTM
translation. Resulting glyph paint coordinates landed thousands of
pixels off the canvas (e.g. f=-9962 on a 842-pixel-tall page).

The fix routes through :meth:`_full_ctm` so the composition becomes
``text_local * Tm * (gs.ctm * device_ctm)``, matching PDF 32000-1
§9.4.4. Two real-world fixtures (BidiSample.pdf, poems-beads) now
paint visible glyphs instead of a blank canvas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer

_BIDI_SAMPLE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "text"
    / "BidiSample.pdf"
)
_POEMS_BEADS = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "pdfwriter"
    / "PDFBOX-3110-poems-beads.pdf"
)


def _fraction_non_white(pdf_path: Path, page_index: int = 0) -> float:
    """Render page ``page_index`` of ``pdf_path`` and return the fraction
    of non-white RGB pixels. Closes the document on exit.
    """
    doc = PDDocument.load(pdf_path)
    try:
        renderer = PDFRenderer(doc)
        img = renderer.render_image(page_index, scale=1.0)
        # Walk raw bytes to avoid the deprecated ``Image.getdata`` API.
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
    not _BIDI_SAMPLE.exists(), reason="BidiSample.pdf fixture missing"
)
def test_bidi_sample_renders_non_white() -> None:
    """BidiSample.pdf must produce *some* painted pixels, not a fully
    white canvas (root cause: wave-1391 ``_draw_glyph`` CTM bug).

    The threshold (>=0.5%) is deliberately loose so the test stays
    stable against minor anti-aliasing / font-substitution drift —
    the regression we care about turns the whole page white (0.0%).
    """
    fraction = _fraction_non_white(_BIDI_SAMPLE)
    assert fraction >= 0.005, (
        f"BidiSample.pdf rendered with only {fraction * 100:.3f}% non-white "
        "pixels — the page-CTM y-flip bug has come back."
    )


@pytest.mark.skipif(
    not _POEMS_BEADS.exists(), reason="poems-beads fixture missing"
)
def test_poems_beads_renders_non_white() -> None:
    """PDFBOX-3110-poems-beads.pdf has multi-column text positioned via
    ``cm`` translations and ``Tm`` font-size matrices — the same
    producer pattern that triggered the wave-1391 bug. Page 0 must
    paint visible text.
    """
    fraction = _fraction_non_white(_POEMS_BEADS)
    assert fraction >= 0.05, (
        f"poems-beads page 0 rendered with only {fraction * 100:.3f}% "
        "non-white pixels — text-block positioning is broken again."
    )


def test_draw_glyph_matrix_uses_full_ctm() -> None:
    """White-box: make sure ``_draw_glyph`` routes through
    :meth:`_full_ctm` (the corrected composition) rather than the
    legacy ``gs.ctm`` + ``device_ctm`` two-step that put the page CTM
    on the wrong side of the y-flip.

    Read the source file from disk so the check survives test suites
    that monkeypatch ``PDFRenderer._draw_glyph`` (the patch should be
    undone after the test, but :func:`inspect.getsource` on a method
    that was replaced via ``monkeypatch.setattr`` returned the patched
    closure's source in earlier wave-1391 full-suite runs, breaking
    this check downstream of unrelated tests).
    """
    import pypdfbox.rendering.pdf_renderer as renderer_mod

    src = Path(renderer_mod.__file__).read_text(encoding="utf-8")
    # Slice out the ``_draw_glyph`` body — the matrix composition lives
    # in the first ~30 lines after the marker.
    marker = "    def _draw_glyph("
    idx = src.find(marker)
    assert idx >= 0, "could not locate _draw_glyph in pdf_renderer.py"
    snippet = src[idx : idx + 4000]
    assert "self._full_ctm()" in snippet, (
        "_draw_glyph no longer references _full_ctm — the wave-1391 fix may "
        "have regressed."
    )
    assert "_matmul(self._gs.ctm, glyph_to_device)" not in snippet, (
        "_draw_glyph still prefixes gs.ctm onto a device-space matrix — "
        "the wave-1391 bug is back."
    )
