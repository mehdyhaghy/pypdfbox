"""Live Apache PDFBox parity for ``TextToPDF.createPDFFromText``.

Drives Apache PDFBox 3.0.7's ``org.apache.pdfbox.tools.TextToPDF`` via the
``TextToPdfProbe`` Java probe on a fixed multi-line text, then runs pypdfbox's
:class:`pypdfbox.tools.text_to_pdf.TextToPDF` on the same text and asserts an
identical structural summary:

* page count (multi-page layout — the long body wraps and overflows the
  bottom margin onto extra Letter pages),
* the full text extracted back out via ``PDFTextStripper`` (this is the
  load-bearing parity claim — it proves the layout placed the same words on
  the same pages in the same reading order), and
* the distinct ``/BaseFont`` names across all pages (default font is
  Helvetica).

Both sides build with the *default* TextToPDF configuration: Helvetica at
10pt, 40pt margins on every side, 1.05 line spacing, Letter media box. The
summary string is produced identically on both sides so a divergence in page
count, wrapping, or font selection breaks the equality assertion.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools.text_to_pdf import TextToPDF
from tests.oracle.harness import requires_oracle, run_probe_text

# Fixed multi-line input. A short header, a blank line, then a long
# paragraph whose words wrap at the right margin and overflow onto a second
# Letter page, then a short trailer — so the case exercises page count,
# wrapping, and reading order all at once.
_LONG_PARAGRAPH = (
    "PDFBox is an open source Java library for working with PDF documents. "
    "This tool converts a plain text file into a PDF document by laying the "
    "words out top to bottom in a single column with the Helvetica font at "
    "ten points. Long lines are wrapped at the right margin and a new page "
    "is started whenever the next line would cross below the bottom margin. "
) * 30

_TEXT = "TextToPDF parity sample\n\n" + _LONG_PARAGRAPH + "\n\nEnd of document.\n"


def _escape(value: str) -> str:
    """Mirror the Java probe's ``escape`` so the two summaries are comparable."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _font_name(font: object) -> str | None:
    """Resolve a font resource's ``/BaseFont`` name.

    ``PDResources.get_font`` returns a typed :class:`PDFont` for indirect
    entries and a raw :class:`COSDictionary` for direct ones; handle both so
    the probe parity holds regardless of how the writer stored the font.
    """
    if isinstance(font, PDFont):
        return font.get_name()
    if isinstance(font, COSDictionary):
        base = font.get_name_as_string(COSName.get_pdf_name("BaseFont"))
        return base
    return None


def _pypdfbox_summary(text: str, out_path: Path) -> str:
    """Build a PDF from ``text`` with pypdfbox and emit the probe summary."""
    tool = TextToPDF()
    with PDDocument() as doc:
        tool.create_pdf_from_text(doc, StringIO(text))
        doc.save(str(out_path))

    lines: list[str] = []
    with PDDocument.load(out_path) as doc:
        lines.append(f"pages={doc.get_number_of_pages()}")
        extracted = PDFTextStripper().get_text(doc)
        lines.append(f"text={_escape(extracted)}")

        fonts: list[str] = []
        for page in doc.get_pages():
            resources = page.get_resources()
            if resources is None:
                continue
            for name in resources.get_font_names():
                resolved = _font_name(resources.get_font(name))
                if resolved is not None and resolved not in fonts:
                    fonts.append(resolved)
        fonts.sort()
        lines.append("fonts=" + ",".join(fonts))
    # Trailing newline matches the probe's per-line '\n' terminator.
    return "\n".join(lines) + "\n"


@requires_oracle
def test_create_pdf_from_text_matches_pdfbox(tmp_path: Path) -> None:
    text_path = tmp_path / "input.txt"
    text_path.write_bytes(_TEXT.encode("utf-8"))

    java_out = tmp_path / "java.pdf"
    java_summary = run_probe_text(
        "TextToPdfProbe", str(text_path), str(java_out)
    )

    py_summary = _pypdfbox_summary(_TEXT, tmp_path / "py.pdf")

    assert py_summary == java_summary, (
        "TextToPDF.createPDFFromText divergence:\n"
        f"  java: {java_summary!r}\n"
        f"  py:   {py_summary!r}"
    )


@requires_oracle
def test_create_pdf_from_text_is_multipage() -> None:
    """Guard the fixture: the chosen body must overflow onto >1 page so the
    parity assertion actually exercises multi-page layout."""
    tool = TextToPDF()
    doc = tool.create_pdf_from_text(StringIO(_TEXT))
    try:
        assert doc.get_number_of_pages() > 1
    finally:
        doc.close()
