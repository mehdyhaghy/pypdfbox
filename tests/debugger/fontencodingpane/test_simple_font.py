"""Tests for the :class:`SimpleFont` encoding pane."""

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


def test_simple_font_builds_256_row_table(tk_root):
    pane = SimpleFont(_helvetica(), tk_root)
    # WinAnsi is a complete encoding for the printable range — every
    # row from 0..255 should be present.
    assert pane.total_available_glyphs == 256
    assert len(pane.view.tree.get_children()) == 256


def test_simple_font_header_attributes(tk_root):
    # Construct the pane to exercise the constructor path, then exercise
    # the static helper directly.
    SimpleFont(_helvetica(), tk_root)
    # Encoding name format mirrors upstream: "<font class> / <encoding name>".
    assert "WinAnsiEncoding" in SimpleFont.get_encoding_name(_helvetica())


def test_simple_font_get_panel_is_view(tk_root):
    pane = SimpleFont(_helvetica(), tk_root)
    assert pane.get_panel() is pane.view


def test_simple_font_first_row_is_code_zero(tk_root):
    pane = SimpleFont(_helvetica(), tk_root)
    children = pane.view.tree.get_children()
    first = pane.view.tree.item(children[0])
    assert first["text"] == "0"


def test_simple_font_handles_font_without_encoding(tk_root):
    """A font dict without an /Encoding entry should still construct.

    Upstream's ``getEncodingName`` returns ``"(null)"`` when the
    encoding is missing.
    """
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font = PDType1Font(font_dict)
    # ``PDSimpleFont`` synthesises a default StandardEncoding for
    # Standard-14 / non-symbolic fonts even when /Encoding is absent,
    # so the encoding-name string still shows up — we just verify it
    # constructs and produces some glyph rows.
    pane = SimpleFont(font, tk_root)
    assert pane.total_available_glyphs > 0
