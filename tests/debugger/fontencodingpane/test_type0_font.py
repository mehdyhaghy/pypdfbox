"""Tests for the :class:`Type0Font` encoding pane."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane.type0_font import Type0Font
from pypdfbox.pdmodel.font import PDType0Font


def _type0_with_descendant() -> PDType0Font:
    descendant = COSDictionary()
    descendant.set_name(COSName.get_pdf_name("Type"), "Font")
    descendant.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    sysinfo = COSDictionary()
    sysinfo.set_string(COSName.get_pdf_name("Registry"), "Adobe")
    sysinfo.set_string(COSName.get_pdf_name("Ordering"), "Identity")
    sysinfo.set_int(COSName.get_pdf_name("Supplement"), 0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), sysinfo)

    parent = COSDictionary()
    parent.set_name(COSName.get_pdf_name("Type"), "Font")
    parent.set_name(COSName.get_pdf_name("Subtype"), "Type0")
    parent.set_name(COSName.get_pdf_name("BaseFont"), "MyTTF")
    parent.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    return PDType0Font(parent)


def test_type0_pane_builds_view(tk_root):
    parent = _type0_with_descendant()
    descendant = parent.get_descendant_font()
    assert descendant is not None
    pane = Type0Font(descendant, parent, tk_root)
    # No /CIDToGIDMap and no embedded program => readMap yields zero rows.
    assert pane.view is not None
    assert pane.view.tree is not None


def test_type0_pane_get_panel(tk_root):
    parent = _type0_with_descendant()
    descendant = parent.get_descendant_font()
    pane = Type0Font(descendant, parent, tk_root)
    assert pane.get_panel() is pane.view


def test_type0_pane_total_glyphs_starts_at_zero(tk_root):
    parent = _type0_with_descendant()
    descendant = parent.get_descendant_font()
    pane = Type0Font(descendant, parent, tk_root)
    # No embedded TTF program => has_glyph(code) is False for every code.
    assert pane.total_available_glyphs == 0
