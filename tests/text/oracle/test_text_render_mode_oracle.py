"""Live Apache PDFBox differential parity for text extraction under the
text rendering mode (``Tr``) operator.

PDF 32000-1 §9.3.6 defines eight text rendering modes. The cases that matter
for *extraction* are the ones that paint nothing:

  * ``Tr 3`` — **invisible** text. This is the OCR-layer / searchable-image
    technique: a scanned page image is drawn and an invisible Mode-3 text
    layer is overlaid so the page is selectable/searchable without the text
    ever being visibly painted.
  * ``Tr 7`` — **add-to-clip, no paint**. The glyph outlines are added to the
    clipping path; nothing is painted.

Apache PDFBox's ``PDFTextStripper.getText()`` extracts text from the
show-text operators and the font's code→Unicode map alone; it *never*
consults the rendering mode. So Mode-3 and Mode-7 text must be extracted
exactly as visible (Mode-0) text is — a stripper that dropped invisible text
would lose the entire OCR layer of every scanned PDF.

The headline case builds a page mixing a visible (``Tr 0``) line, an
invisible (``Tr 3``) line, and a clip-only (``Tr 7``) line and asserts the
extracted string contains all three — and equals Java's byte-for-byte. The
:class:`TextRenderModeExtractProbe` Java probe drives PDFBox's
``PDFTextStripper.getText()`` and emits the framed extracted string.

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

_PROBE = "TextRenderModeExtractProbe"


# ---------------------------------------------------------------------------
# Content-stream fixtures. Each show-text run is on its own line (a fresh
# ``Td`` at a lower Y, top-to-bottom) so sort-by-position keeps reading order
# stable and inserts a newline between runs. The rendering mode preceding each
# run is the only thing that varies; the extracted glyphs must be identical
# regardless of whether the run is painted.
# ---------------------------------------------------------------------------

# Visible line, then invisible (Tr 3) line, then a back-to-visible line.
# Extraction must include the invisible middle line.
_MIXED_VISIBLE_INVISIBLE = (
    b"BT /F1 12 Tf "
    b"0 Tr 40 150 Td (VISIBLE) Tj "
    b"3 Tr 0 -20 Td (INVISIBLE) Tj "
    b"0 Tr 0 -20 Td (AGAIN) Tj "
    b"ET"
)

# Visible line then a clip-only (Tr 7) line. Mode-7 paints nothing but the
# glyphs must still be extracted.
_MIXED_VISIBLE_CLIP = (
    b"BT /F1 12 Tf "
    b"0 Tr 40 150 Td (SHOWN) Tj "
    b"7 Tr 0 -20 Td (CLIPPED) Tj "
    b"ET"
)

# A purely invisible page — every run is Tr 3. The whole page is an OCR layer;
# all of it must be extracted.
_ALL_INVISIBLE = (
    b"BT /F1 12 Tf 3 Tr "
    b"40 150 Td (HELLO) Tj "
    b"0 -20 Td (WORLD) Tj "
    b"ET"
)

# Render mode set mid-run (between two Tj in the same line position) does not
# affect which glyphs are extracted; here both fill (0) and fill+stroke (2)
# visible modes plus invisible (3) appear, all on separate lines.
_ALL_MODES = (
    b"BT /F1 12 Tf "
    b"0 Tr 40 150 Td (FILL) Tj "
    b"1 Tr 0 -20 Td (STROKE) Tj "
    b"2 Tr 0 -20 Td (FILLSTROKE) Tj "
    b"3 Tr 0 -20 Td (INVIS) Tj "
    b"7 Tr 0 -20 Td (CLIP) Tj "
    b"ET"
)


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token is rewritten to whatever key the page resources
    allocate for the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 300, 200))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        resources = page.get_resources()
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


def _java(path: str) -> str:
    out = run_probe_text(_PROBE, path)
    return out.split("<<<TEXT\n", 1)[1].split("TEXT>>>\n", 1)[0]


def _py(path: str) -> str:
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        return stripper.get_text(doc)
    finally:
        doc.close()


def _roundtrip(content: bytes) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        return _java(path), _py(path)


# ---------------------------------------------------------------------------
# Headline: extraction is independent of Tr. pypdfbox must match Java's
# getText() byte-for-byte across the visible/invisible/clip combinations.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [
        _MIXED_VISIBLE_INVISIBLE,
        _MIXED_VISIBLE_CLIP,
        _ALL_INVISIBLE,
        _ALL_MODES,
    ],
    ids=[
        "mixed_visible_invisible",
        "mixed_visible_clip",
        "all_invisible",
        "all_modes",
    ],
)
def test_extracted_string_matches_pdfbox(content: bytes) -> None:
    java_text, py_text = _roundtrip(content)
    assert py_text == java_text


# ---------------------------------------------------------------------------
# The OCR-layer guarantee, asserted directly against expected content: the
# invisible Mode-3 line is NOT dropped, and the Mode-7 clip line is NOT
# dropped.
# ---------------------------------------------------------------------------


@requires_oracle
def test_invisible_text_is_extracted() -> None:
    java_text, py_text = _roundtrip(_MIXED_VISIBLE_INVISIBLE)
    assert py_text == java_text
    for token in ("VISIBLE", "INVISIBLE", "AGAIN"):
        assert token in py_text


@requires_oracle
def test_clip_text_is_extracted() -> None:
    java_text, py_text = _roundtrip(_MIXED_VISIBLE_CLIP)
    assert py_text == java_text
    for token in ("SHOWN", "CLIPPED"):
        assert token in py_text


@requires_oracle
def test_all_invisible_page_is_extracted() -> None:
    java_text, py_text = _roundtrip(_ALL_INVISIBLE)
    assert py_text == java_text
    for token in ("HELLO", "WORLD"):
        assert token in py_text
