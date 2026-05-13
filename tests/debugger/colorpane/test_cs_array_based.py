"""Tests for :class:`CSArrayBased`.

Widget tests need a Tk root — these use the ``tk_root`` fixture which
skips on headless. Tests cover three branches of the upstream
``initUI`` switch:

* successful build with a non-ICCBased color space (CalGray) — sets
  number of components but no ICC labels.
* unrecognised array — falls into the ``colorSpace == null`` branch and
  renders the error message.
"""

from __future__ import annotations

from tkinter import ttk

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.debugger.colorpane.cs_array_based import (
    CS_GRAY,
    CS_LINEAR_RGB,
    CS_SRGB,
    CS_XYZ,
    CSArrayBased,
    _format_color_space_type,
)
from pypdfbox.pdmodel.graphics.color.pd_icc_based import (
    TYPE_CMYK,
    TYPE_GRAY,
    TYPE_RGB,
)


def _cal_gray_array() -> COSArray:
    """Build a minimal valid CalGray array — ``[/CalGray <dict>]``."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    d = COSDictionary()
    d.set_item("WhitePoint", COSArray.of_cos_floats([1.0, 1.0, 1.0]))
    arr.add(d)
    return arr


def _bogus_array() -> COSArray:
    """Array whose first element is an unknown color-space name."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("NotAColorSpace"))
    return arr


def test_format_color_space_type_known_constants() -> None:
    assert _format_color_space_type(CS_LINEAR_RGB) == "linear RGB"
    assert _format_color_space_type(CS_XYZ) == "CIEXYZ"
    assert _format_color_space_type(CS_GRAY) == "linear gray"
    assert _format_color_space_type(CS_SRGB) == "sRGB"
    assert _format_color_space_type(TYPE_RGB) == "RGB"
    assert _format_color_space_type(TYPE_GRAY) == "gray"
    assert _format_color_space_type(TYPE_CMYK) == "CMYK"


def test_format_color_space_type_unknown_falls_through_to_type_label() -> None:
    assert _format_color_space_type(9999) == "type 9999"


def test_cs_array_based_with_cal_gray_builds_panel(tk_root) -> None:
    pane = CSArrayBased(_cal_gray_array(), master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    # Panel must have at least the colorspace-name label and the
    # component-count label packed inside.
    children = panel.winfo_children()
    assert len(children) >= 2


def test_cs_array_based_with_unknown_space_renders_error_panel(tk_root) -> None:
    pane = CSArrayBased(_bogus_array(), master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    # The error-branch packs at most one label (the error message).
    children = panel.winfo_children()
    assert len(children) <= 1
