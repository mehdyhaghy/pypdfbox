"""Tests for promoted :class:`CSIndexed` helpers.

Covers the public surface promoted from the previously-private
``_get_colorant_data`` / ``_get_hival`` / ``_init_ui`` so they can be
exercised directly (and via their back-compat aliases).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.debugger.colorpane.cs_indexed import CSIndexed
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def _indexed_array(hival: int, palette: bytes) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(palette))
    return arr


# ---- pure-Python helpers (no Tk needed) ---------------------------------


def test_get_hival_returns_raw_when_below_clamp() -> None:
    arr = _indexed_array(2, b"\x00\x00\x00\xff\x00\x00\x00\xff\x00")
    assert CSIndexed.get_hival(arr) == 2


def test_get_hival_clamps_to_255() -> None:
    # Upstream clamps via ``Math.min(hival, 255)`` — verify we match.
    palette = bytes(range(256)) * 3
    arr = _indexed_array(300, palette)
    assert CSIndexed.get_hival(arr) == 255


def test_get_hival_rejects_non_number() -> None:
    # pypdfbox deviation: upstream casts blindly and throws
    # ClassCastException; we raise the more-Pythonic ``TypeError``.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSName.get_pdf_name("notanumber"))
    arr.add(COSString(b""))
    with pytest.raises(TypeError):
        CSIndexed.get_hival(arr)


def test_private_aliases_resolve_to_public() -> None:
    assert CSIndexed._get_hival is CSIndexed.get_hival
    assert CSIndexed._get_colorant_data is CSIndexed.get_colorant_data
    assert CSIndexed._init_ui is CSIndexed.init_ui


# ---- Tk-dependent smoke test --------------------------------------------


def test_get_colorant_data_and_init_ui_smoke(tk_root) -> None:
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00"
    pane = CSIndexed(_indexed_array(2, palette), master=tk_root)
    # ``get_colorant_data`` ran during construction; calling it again
    # gives the same palette-walk result.
    colorants = pane.get_colorant_data()
    assert len(colorants) == 3
    assert [c.get_index() for c in colorants] == [0, 1, 2]
    # ``init_ui`` populated the treeview with three rows.
    assert pane.tree is not None
    assert len(pane.tree.get_children()) == 3
    assert pane.get_panel() is not None
