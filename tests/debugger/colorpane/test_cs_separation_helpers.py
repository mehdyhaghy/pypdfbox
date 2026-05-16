"""Tests for :class:`CSSeparation` int/float helpers + init methods.

Covers the public surface promoted from the previously-private
``_get_float_representation`` / ``_get_int_representation`` /
``_init_ui`` / ``_init_values`` / ``_set_color_bar_border`` so they can
be exercised directly (and via their back-compat aliases).
"""

from __future__ import annotations

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


def _separation_array() -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("PANTONE 185 C"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(_type2([1.0, 1.0, 1.0], [0.8, 0.0, 0.0]))
    return arr


# ---- pure-Python conversion helpers (no Tk needed) ----------------------


def test_get_float_representation_lower_bound() -> None:
    assert CSSeparation.get_float_representation(0) == 0.0


def test_get_float_representation_upper_bound() -> None:
    # Slider domain is 0..100 (matches upstream); 100 → 1.0 tint.
    assert CSSeparation.get_float_representation(100) == 1.0


def test_get_float_representation_midpoint() -> None:
    assert CSSeparation.get_float_representation(50) == 0.5


def test_get_int_representation_midpoint() -> None:
    # Upstream uses ``(int) (value*100)`` — truncation toward zero.
    # 0.5 * 100 = 50.0 → 50.
    assert CSSeparation.get_int_representation(0.5) == 50


def test_get_int_representation_bounds() -> None:
    assert CSSeparation.get_int_representation(0.0) == 0
    assert CSSeparation.get_int_representation(1.0) == 100


def test_round_trip_half() -> None:
    half = CSSeparation.get_float_representation(
        CSSeparation.get_int_representation(0.5)
    )
    assert abs(half - 0.5) < 1e-9


def test_private_aliases_resolve_to_public() -> None:
    # The back-compat ``_`` aliases must keep working for legacy callers
    # (the existing test_cs_separation.py still uses them).
    assert CSSeparation._get_float_representation is (
        CSSeparation.get_float_representation
    )
    assert CSSeparation._get_int_representation is (
        CSSeparation.get_int_representation
    )


# ---- Tk-dependent smoke tests -------------------------------------------


def test_init_ui_builds_widgets(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    # ``init_ui`` ran during construction — assert the widgets exist.
    assert pane.get_panel() is not None
    assert pane._slider is not None
    assert pane._tint_field is not None
    assert pane._color_bar is not None


def test_init_values_resyncs_after_mutation(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    # Mutate the underlying tint and rerun init_values; widgets must catch up.
    pane._tint_value = 0.25
    pane.init_values()
    assert pane._tint_var is not None
    assert pane._tint_var.get() == "0.25"
    # Slider stores as float internally; compare numerically.
    assert pane._slider is not None
    assert int(float(pane._slider.get())) == 25


def test_set_color_bar_border_smoke(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    # Should not raise; idempotent re-application is fine.
    pane.set_color_bar_border()
    # Optional ``border`` argument is accepted and forwarded as relief.
    pane.set_color_bar_border("ridge")
    assert pane._color_bar is not None
    assert str(pane._color_bar.cget("relief")) == "ridge"


def test_private_init_aliases_callable(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    # Aliases must be live references to the public methods.
    assert pane._init_values.__func__ is pane.init_values.__func__
    assert pane._set_color_bar_border.__func__ is (
        pane.set_color_bar_border.__func__
    )
