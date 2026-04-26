from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
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
    bc = COSArray.of_cos_floats([1.0, 0.0, 0.0])
    mk.set_border_colour(bc)
    rt = mk.get_border_colour()
    assert rt is bc
    assert isinstance(rt, COSArray)
    assert len(rt) == 3


def test_border_colour_clear() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(COSArray.of_cos_floats([1.0, 0.0, 0.0]))
    mk.set_border_colour(None)
    assert mk.get_border_colour() is None


def test_background_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    bg = COSArray.of_cos_floats([0.5])
    mk.set_background(bg)
    assert mk.get_background() is bg


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
