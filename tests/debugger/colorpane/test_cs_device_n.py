"""Tests for :class:`CSDeviceN`."""

from __future__ import annotations

from tkinter import ttk

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.debugger.colorpane.cs_device_n import CSDeviceN


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    """Build a /FunctionType 2 (exponential) tint-transform dictionary."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _device_n_array(
    colorants: list[str],
    c0_rgb: list[float],
    c1_rgb: list[float],
) -> COSArray:
    """``[/DeviceN <names> <alternate=DeviceRGB> <tint>]``.

    Single-component DeviceN. For our 2-colorant tests we'd need a
    multi-output tint transform — we keep things simple by limiting
    to a single colorant.
    """
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(colorants))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(_type2(c0_rgb, c1_rgb))
    return arr


def test_cs_device_n_single_colorant_builds_panel(tk_root) -> None:
    arr = _device_n_array(
        ["Spot1"],
        [1.0, 1.0, 1.0],
        [0.5, 0.0, 0.0],
    )
    pane = CSDeviceN(arr, master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    # Treeview should hold one row per colorant.
    tree = pane.tree
    assert tree is not None
    assert len(tree.get_children()) == 1


def test_cs_device_n_table_model_columns_match_upstream(tk_root) -> None:
    arr = _device_n_array(
        ["Spot1"],
        [1.0, 1.0, 1.0],
        [0.5, 0.0, 0.0],
    )
    pane = CSDeviceN(arr, master=tk_root)
    assert pane.table_model.get_columns() == ["Colorant", "Maximum", "Minimum"]
    # Colorant name is in column 0 of the model.
    assert pane.table_model.get_value_at(0, 0) == "Spot1"
