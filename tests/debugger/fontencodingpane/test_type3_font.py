"""Tests for the :class:`Type3Font` encoding pane."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane.type3_font import Type3Font
from pypdfbox.pdmodel.font import PDType3Font as PDType3FontModel


def _type3_font() -> PDType3FontModel:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type3")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    return PDType3FontModel(font_dict)


def test_type3_pane_builds_view(tk_root):
    pane = Type3Font(_type3_font(), None, tk_root)
    assert pane.view is not None
    assert pane.view.tree is not None
    # WinAnsi encoding alone supplies 224 mapped codes.
    assert pane.total_available_glyphs > 0


def test_type3_pane_get_panel(tk_root):
    pane = Type3Font(_type3_font(), None, tk_root)
    assert pane.get_panel() is pane.view


def test_type3_pane_font_bbox_is_zero_without_char_procs(tk_root):
    """Without /CharProcs the per-glyph BBox union is empty; ``calcBBox``
    falls back to the font's bounding box (also empty for a stub dict),
    so ``font_bbox`` has zero dimensions and the view falls back to the
    ``NO_GLYPH`` text path."""
    pane = Type3Font(_type3_font(), None, tk_root)
    assert pane.font_bbox.get_width() == 0
    assert pane.font_bbox.get_height() == 0


def test_type3_pane_table_has_256_rows(tk_root):
    pane = Type3Font(_type3_font(), None, tk_root)
    assert len(pane.view.tree.get_children()) == 256
