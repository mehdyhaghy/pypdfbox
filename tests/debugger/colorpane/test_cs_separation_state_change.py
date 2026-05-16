"""Tests for promoted :class:`CSSeparation` methods.

Covers :py:meth:`CSSeparation.state_changed` and
:py:meth:`CSSeparation.update_color_bar`, formerly private. Both mirror
upstream slot-listener entry points.
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


def test_state_changed_is_underscore_alias(tk_root) -> None:
    """The original ``_on_slider`` name should resolve to the promoted method."""
    assert CSSeparation._on_slider is CSSeparation.state_changed  # noqa: SLF001


def test_state_changed_updates_tint(tk_root) -> None:
    pane = CSSeparation(_separation_array(), master=tk_root)
    pane.state_changed("75")
    assert pane.tint_value == 0.75


def test_update_color_bar_alias_and_invocation(tk_root) -> None:
    """``_update_color_bar`` should be the underscore alias of the new public method."""
    assert CSSeparation._update_color_bar is CSSeparation.update_color_bar  # noqa: SLF001
    pane = CSSeparation(_separation_array(), master=tk_root)
    # Bumping the slider through state_changed routes through
    # update_color_bar; the canvas background should change as a side-effect.
    pane.state_changed("0")
    assert pane._color_bar is not None  # noqa: SLF001
    # The bar's background string is non-empty after the recolor.
    assert pane._color_bar.cget("background")  # noqa: SLF001
