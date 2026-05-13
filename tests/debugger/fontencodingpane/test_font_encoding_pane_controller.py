"""Tests for the :class:`FontEncodingPaneController` dispatcher."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane import FontEncodingPaneController
from pypdfbox.debugger.fontencodingpane.simple_font import SimpleFont
from pypdfbox.debugger.fontencodingpane.type0_font import Type0Font
from pypdfbox.debugger.fontencodingpane.type3_font import Type3Font


def _resources_with(font_name: str, font_dict: COSDictionary) -> COSDictionary:
    fonts = COSDictionary()
    fonts.set_item(COSName.get_pdf_name(font_name), font_dict)
    resources = COSDictionary()
    resources.set_item(COSName.get_pdf_name("Font"), fonts)
    return resources


def _type1_dict() -> COSDictionary:
    fd = COSDictionary()
    fd.set_name(COSName.get_pdf_name("Type"), "Font")
    fd.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    fd.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    fd.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    return fd


def _type3_dict() -> COSDictionary:
    fd = COSDictionary()
    fd.set_name(COSName.get_pdf_name("Type"), "Font")
    fd.set_name(COSName.get_pdf_name("Subtype"), "Type3")
    fd.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    return fd


def _type0_dict() -> COSDictionary:
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
    return parent


def test_dispatch_simple_font(tk_root):
    resources = _resources_with("F1", _type1_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F1"), resources, tk_root
    )
    assert isinstance(ctrl.font_pane, SimpleFont)
    assert ctrl.get_pane() is not None


def test_dispatch_type3_font(tk_root):
    resources = _resources_with("F3", _type3_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F3"), resources, tk_root
    )
    assert isinstance(ctrl.font_pane, Type3Font)
    assert ctrl.get_pane() is not None


def test_dispatch_type0_font(tk_root):
    resources = _resources_with("F2", _type0_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F2"), resources, tk_root
    )
    assert isinstance(ctrl.font_pane, Type0Font)
    assert ctrl.get_pane() is not None


def test_unknown_font_returns_none(tk_root):
    resources = _resources_with("F1", _type1_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("DoesNotExist"), resources, tk_root
    )
    assert ctrl.font_pane is None
    assert ctrl.get_pane() is None


def test_empty_resources_returns_none(tk_root):
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F1"), COSDictionary(), tk_root
    )
    assert ctrl.font_pane is None
    assert ctrl.get_pane() is None


def test_font_load_oserror_returns_no_pane(tk_root, monkeypatch):
    """When ``PDResources.get_font`` raises ``OSError`` the controller
    swallows the error and surfaces ``None`` for the pane (mirrors
    upstream's IOException handler)."""
    from pypdfbox.pdmodel.pd_resources import PDResources

    def _boom(self, _name):
        raise OSError("forced")

    monkeypatch.setattr(PDResources, "get_font", _boom)
    resources = _resources_with("F1", _type1_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F1"), resources, tk_root
    )
    assert ctrl.font_pane is None
    assert ctrl.get_pane() is None


def test_direct_cos_dict_wrap_failure_returns_no_pane(tk_root, monkeypatch):
    """``PDFontFactory.create_font`` raising ``OSError`` on a direct font
    entry falls through to the early-return branch."""
    from pypdfbox.pdmodel.font import PDFontFactory
    from pypdfbox.pdmodel.pd_resources import PDResources

    direct_dict = _type1_dict()

    def _direct_font(self, _name):
        return direct_dict

    def _boom(_d):
        raise OSError("forced create_font failure")

    monkeypatch.setattr(PDResources, "get_font", _direct_font)
    monkeypatch.setattr(PDFontFactory, "create_font", staticmethod(_boom))
    resources = _resources_with("F1", _type1_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F1"), resources, tk_root
    )
    assert ctrl.font_pane is None


def test_pane_construction_oserror_swallowed(tk_root, monkeypatch):
    """An OSError raised by the pane constructor itself (rare, but
    upstream catches it) leaves the controller's pane as ``None``."""
    from pypdfbox.debugger.fontencodingpane import (
        font_encoding_pane_controller as mod,
    )

    class _BoomPane:
        def __init__(self, *args, **kwargs):
            raise OSError("pane build failed")

    monkeypatch.setattr(mod, "SimpleFont", _BoomPane)
    resources = _resources_with("F1", _type1_dict())
    ctrl = FontEncodingPaneController(
        COSName.get_pdf_name("F1"), resources, tk_root
    )
    assert ctrl.font_pane is None
