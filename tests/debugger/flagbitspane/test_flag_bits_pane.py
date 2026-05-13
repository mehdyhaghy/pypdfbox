"""Tests for the :class:`FlagBitsPane` dispatcher."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.debugger.flagbitspane.flag_bits_pane import FlagBitsPane


def _font_dict():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Flags"), COSInteger.get(34))
    return d


def _annot_dict():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("F"), COSInteger.get(4))
    return d


def _field_dict():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Ff"), COSInteger.get(0))
    return d


def _encrypt_dict():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("P"), COSInteger.get(-4))
    return d


def _sig_dict():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("SigFlags"), COSInteger.get(3))
    return d


def _panose_dict():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Panose"), COSString(bytes(12)))
    return d


def test_dispatch_font_flag(tk_root):
    pane = FlagBitsPane(None, _font_dict(), COSName.get_pdf_name("Flags"), tk_root)
    view = pane.get_pane()
    assert view is not None
    assert view.tree is not None


def test_dispatch_annot_flag(tk_root):
    pane = FlagBitsPane(None, _annot_dict(), COSName.get_pdf_name("F"), tk_root)
    assert pane.get_pane() is not None


def test_dispatch_field_flag(tk_root):
    pane = FlagBitsPane(None, _field_dict(), COSName.get_pdf_name("Ff"), tk_root)
    assert pane.get_pane() is not None


def test_dispatch_encrypt_flag(tk_root):
    pane = FlagBitsPane(None, _encrypt_dict(), COSName.get_pdf_name("P"), tk_root)
    assert pane.get_pane() is not None


def test_dispatch_sig_flag(tk_root):
    pane = FlagBitsPane(
        None, _sig_dict(), COSName.get_pdf_name("SigFlags"), tk_root
    )
    assert pane.get_pane() is not None


def test_dispatch_panose_flag(tk_root):
    pane = FlagBitsPane(
        None, _panose_dict(), COSName.get_pdf_name("Panose"), tk_root
    )
    assert pane.get_pane() is not None


def test_unknown_flag_type_yields_no_pane(tk_root):
    # /Type isn't one of the recognised flag-type names so the dispatcher
    # falls through without creating a view.
    pane = FlagBitsPane(
        None,
        _font_dict(),
        COSName.get_pdf_name("Type"),
        tk_root,
    )
    assert pane.get_pane() is None
