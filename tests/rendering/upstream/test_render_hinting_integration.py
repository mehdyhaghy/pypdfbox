"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``pdfbox/src/test/java/org/apache/pdfbox/rendering/RenderHintingIntegrationTest.java``.

Proves that hinting is wired into the render path: with hinting enabled,
a page of embedded TrueType text rasterizes to a different image than
with it disabled.
"""

import io
from pathlib import Path

import pytest

# The GlyphHinter port (wave 1611) is required to produce hinted paths.
pytest.importorskip("pypdfbox.fontbox.ttf.glyph_hinter")

from PIL import Image, ImageChops

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDTrueTypeFont
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer

_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _build_pdf() -> bytes:
    with PDDocument() as doc:
        page = PDPage(PDRectangle(0.0, 0.0, 160.0, 60.0))
        doc.add_page(page)
        font = PDTrueTypeFont.load(doc, _TTF.read_bytes(), WinAnsiEncoding.INSTANCE)
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(font, 11)
            cs.new_line_at_offset(8, 24)
            cs.show_text("Hamburgefons 123")
            cs.end_text()
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()


def _render(pdf: bytes, hinting: bool) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        renderer = PDFRenderer(doc)
        renderer.set_hinting_enabled(hinting)
        return renderer.render_image_with_dpi(0, 96)


def _count_differences(a: Image.Image, b: Image.Image) -> int:
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L")
    return sum(diff.histogram()[1:])


def test_hinting_changes_rendered_pixels() -> None:
    pdf = _build_pdf()
    off = _render(pdf, False)
    on = _render(pdf, True)

    assert on.size == off.size
    assert _count_differences(off, on) > 0, (
        "enabling hinting should change the rendered glyph pixels"
    )


def test_disabled_hinting_is_deterministic() -> None:
    """A page must rasterize identically across two renders with hinting off."""
    pdf = _build_pdf()
    assert _count_differences(_render(pdf, False), _render(pdf, False)) == 0
