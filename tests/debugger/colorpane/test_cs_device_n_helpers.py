"""Tests for promoted :class:`CSDeviceN` helpers.

Covers the public surface promoted from the previously-private
``_get_color_obj`` / ``_get_colorant_data`` / ``_init_ui`` so they can
be exercised directly (and via their back-compat aliases).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.debugger.colorpane.cs_device_n import CSDeviceN


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
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
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(colorants))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(_type2(c0_rgb, c1_rgb))
    return arr


# ---- pure-Python helper (no Tk needed) ----------------------------------


def test_get_color_obj_wraps_three_floats() -> None:
    # ``get_color_obj`` accepts an iterable of three floats and returns
    # an ``(r, g, b)`` tuple — exactly as upstream's private helper did.
    assert CSDeviceN.get_color_obj([0.25, 0.5, 0.75]) == (0.25, 0.5, 0.75)


def test_get_color_obj_handles_none_gracefully() -> None:
    # pypdfbox deviation: upstream NPE'd on ``null`` (toRGB returning
    # null when no alternate is available). We collapse to black so
    # the debugger still renders.
    assert CSDeviceN.get_color_obj(None) == (0.0, 0.0, 0.0)


def test_private_aliases_resolve_to_public() -> None:
    assert CSDeviceN._get_color_obj is CSDeviceN.get_color_obj
    assert CSDeviceN._get_colorant_data is CSDeviceN.get_colorant_data
    assert CSDeviceN._init_ui is CSDeviceN.init_ui


# ---- Tk-dependent smoke test --------------------------------------------


def test_get_colorant_data_and_init_ui_smoke(tk_root) -> None:
    arr = _device_n_array(
        ["Spot1"],
        [1.0, 1.0, 1.0],
        [0.5, 0.0, 0.0],
    )
    pane = CSDeviceN(arr, master=tk_root)
    # ``get_colorant_data`` ran during construction — re-running returns
    # the same set of named colorants.
    colorants = pane.get_colorant_data()
    assert len(colorants) == 1
    assert colorants[0].get_name() == "Spot1"
    # ``init_ui`` populated the treeview during construction.
    assert pane.tree is not None
    assert len(pane.tree.get_children()) == 1
    assert pane.get_panel() is not None
