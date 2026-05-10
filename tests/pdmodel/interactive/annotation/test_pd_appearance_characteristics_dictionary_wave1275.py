"""Wave 1275 parity test for PDAppearanceCharacteristicsDictionary.get_color."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (  # noqa: E501
    PDAppearanceCharacteristicsDictionary,
)


def test_get_color_returns_pd_color_for_rgb_entry() -> None:
    mk = COSDictionary()
    arr = COSArray()
    for c in (1.0, 0.5, 0.0):
        arr.add(COSFloat(c))
    mk.set_item(COSName.get_pdf_name("BC"), arr)
    chars = PDAppearanceCharacteristicsDictionary(mk)
    color = chars.get_color(COSName.get_pdf_name("BC"))
    assert color is not None
    assert color.get_color_space() is PDDeviceRGB.INSTANCE


def test_get_color_returns_none_for_missing_entry() -> None:
    chars = PDAppearanceCharacteristicsDictionary()
    assert chars.get_color(COSName.get_pdf_name("BG")) is None


def test_get_color_matches_dedicated_getters() -> None:
    mk = COSDictionary()
    arr = COSArray()
    arr.add(COSFloat(0.3))
    mk.set_item(COSName.get_pdf_name("BG"), arr)
    chars = PDAppearanceCharacteristicsDictionary(mk)
    via_get_color = chars.get_color(COSName.get_pdf_name("BG"))
    via_typed = chars.get_background()
    assert via_get_color is not None
    assert via_typed is not None
    # Both routes return the same underlying COSArray reference.
    assert (
        via_get_color.get_color_space() is via_typed.get_color_space()
    )
