"""Tests for the promoted :py:meth:`SimpleFont.get_glyphs` method.

Mirrors upstream ``SimpleFont.getGlyphs(PDSimpleFont)`` (package-private)
which builds the ``Object[256][4]`` row table that backs the encoding view.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane.simple_font import SimpleFont
from pypdfbox.pdmodel.font import PDType1Font


def _helvetica() -> PDType1Font:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    return PDType1Font(font_dict)


def test_get_glyphs_returns_256_row_table(tk_root) -> None:
    pane = SimpleFont(_helvetica(), tk_root)
    rows = pane.get_glyphs(_helvetica())
    # Direct invocation should produce a fresh 256-row table independent
    # of the table the constructor already built.
    assert len(rows) == 256
    assert all(len(row) == 4 for row in rows)


def test_get_glyphs_underscore_alias_matches_public(tk_root) -> None:
    """The legacy ``_get_glyphs`` name should resolve to the promoted method."""
    assert SimpleFont._get_glyphs is SimpleFont.get_glyphs  # noqa: SLF001


def test_get_glyphs_first_row_is_code_zero(tk_root) -> None:
    pane = SimpleFont(_helvetica(), tk_root)
    rows = pane.get_glyphs(_helvetica())
    # Column 0 of each row is the integer codepoint, mirroring upstream.
    assert rows[0][0] == 0
    assert rows[255][0] == 255
