"""Tests for :class:`CSSeparation`."""

from __future__ import annotations

from tkinter import ttk

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.debugger.colorpane.cs_separation import CSSeparation


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _separation_array(
    colorant: str = "PANTONE 185 C",
    alternate: str = "DeviceRGB",
    c0: list[float] | None = None,
    c1: list[float] | None = None,
) -> COSArray:
    if c0 is None:
        c0 = [1.0, 1.0, 1.0]
    if c1 is None:
        c1 = [0.8, 0.0, 0.0]
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(_type2(c0, c1))
    return arr


def test_cs_separation_builds_panel(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    panel = pane.get_panel()
    assert isinstance(panel, ttk.Frame)
    # Initial tint defaults to 1.0 (matches upstream).
    assert pane.tint_value == 1.0


def test_cs_separation_int_float_helpers_round_trip(tk_root) -> None:
    # Sanity check on the static representation helpers — exposed
    # indirectly through tint_value, but unit-tested here for clarity.
    from pypdfbox.debugger.colorpane.cs_separation import CSSeparation as Cls

    assert Cls._get_int_representation(0.5) == 50
    assert Cls._get_float_representation(50) == 0.5
    assert Cls._get_int_representation(1.0) == 100
    assert Cls._get_float_representation(0) == 0.0


def test_cs_separation_tint_field_invalid_input_keeps_old_value(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    assert pane._tint_var is not None
    assert pane._tint_field is not None
    # Set an invalid value into the entry, fire the listener.
    pane._tint_var.set("not-a-number")
    pane._on_tint_entry(None)
    # Tint must remain the prior value (1.0) and the entry must reset.
    assert pane.tint_value == 1.0
    assert pane._tint_var.get() == "1.0"


def test_cs_separation_tint_field_valid_input_updates(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    assert pane._tint_var is not None
    pane._tint_var.set("0.5")
    pane._on_tint_entry(None)
    assert pane.tint_value == 0.5
