from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)


def test_default_constructor_creates_empty_dict() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert isinstance(mk.get_cos_object(), COSDictionary)
    assert len(mk.get_cos_object()) == 0


def test_constructor_with_dict_preserves_identity() -> None:
    d = COSDictionary()
    mk = PDAppearanceCharacteristicsDictionary(d)
    assert mk.get_cos_object() is d


def test_rotation_default_zero() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_rotation() == 0


def test_rotation_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(90)
    assert mk.get_rotation() == 90
    assert mk.get_cos_object().get_int(COSName.get_pdf_name("R")) == 90


def test_text_position_default_zero() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_text_position() == 0


def test_text_position_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_text_position(2)
    assert mk.get_text_position() == 2


def test_normal_caption_default_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_normal_caption() is None


def test_normal_caption_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_normal_caption("Click")
    assert mk.get_normal_caption() == "Click"


def test_rollover_and_alternate_caption_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rollover_caption("Hover")
    mk.set_alternate_caption("Down")
    assert mk.get_rollover_caption() == "Hover"
    assert mk.get_alternate_caption() == "Down"


def test_border_colour_default_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_border_colour() is None


def test_border_colour_round_trip_rgb() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_components() == [1.0, 0.0, 0.0]
    assert rt.get_color_space() is PDDeviceRGB.INSTANCE


def test_border_colour_round_trip_gray() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(PDColor([0.5], PDDeviceGray.INSTANCE))
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_components() == [0.5]
    assert rt.get_color_space() is PDDeviceGray.INSTANCE


def test_border_colour_round_trip_cmyk() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(
        PDColor([0.1, 0.2, 0.3, 0.4], PDDeviceCMYK.INSTANCE)
    )
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_components() == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert rt.get_color_space() is PDDeviceCMYK.INSTANCE


def test_border_colour_clear() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
    mk.set_border_colour(None)
    assert mk.get_border_colour() is None


def test_background_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_background(PDColor([0.5], PDDeviceGray.INSTANCE))
    rt = mk.get_background()
    assert isinstance(rt, PDColor)
    assert rt.get_components() == [0.5]


def test_icons_default_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_normal_icon() is None
    assert mk.get_rollover_icon() is None
    assert mk.get_alternate_icon() is None


def test_normal_icon_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    stream = COSStream()
    mk.set_normal_icon(stream)
    assert mk.get_normal_icon() is stream


def test_rollover_and_alternate_icon_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    ri = COSStream()
    ix = COSStream()
    mk.set_rollover_icon(ri)
    mk.set_alternate_icon(ix)
    assert mk.get_rollover_icon() is ri
    assert mk.get_alternate_icon() is ix


def test_icon_clear() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_normal_icon(COSStream())
    mk.set_normal_icon(None)
    assert mk.get_normal_icon() is None


def test_set_border_colour_accepts_raw_cos_array() -> None:
    """Low-level callers may still pass a ``COSArray`` directly; the
    raw array round-trips via ``get_border_colour_array()``."""
    mk = PDAppearanceCharacteristicsDictionary()
    raw = COSArray.of_cos_floats([1.0, 0.0, 0.0])
    mk.set_border_colour(raw)
    assert mk.get_border_colour_array() is raw
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_components() == [1.0, 0.0, 0.0]
